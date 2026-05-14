# BUILD PROMPT — FlowRun Streamlet: IoC Triage v0.0.33
## Complete Engineering Instructions

---

## CONTEXT & YOUR MISSION

You are maintaining a working application called **FlowRun Streamlet: IoC Triage**. This document is the single source of truth for the codebase as of v0.0.33. Reference documents: User Manual v3, PRD v3, Architecture v3.

---

## WHAT THIS APPLICATION DOES

A security operations tool that:
- Accepts a single IOC (IP address, domain, URL, file hash, CVE identifier, prefixed package, or bare package name) from an analyst
- Classifies the IOC type via regex pre-classification (9 types) with GPT-4o-mini fallback
- Queries up to 9 threat intelligence APIs **concurrently** using `asyncio.gather()`
- Correlates results using weighted scoring across 4 weight sets into a composite threat score (0.0–1.0)
- Maps the score to one of **five** severity verdicts: CLEAN, LOW, MEDIUM, HIGH, CRITICAL
- Outputs a structured threat report with TL;DR summary, detection names, conflict callouts, and per-ecosystem breakdown
- Sends a full execution trace via OpenTelemetry (OTLP/HTTP) to the configured collector for observability
- Pauses for human confirmation before releasing a CRITICAL verdict (CLI mode; auto-proceeds in Jupyter)
- Runs as both a **CLI application** and a **Jupyter Notebook**

---

## TECHNICAL STACK

| Component | Library / Version |
|---|---|
| Agent orchestration | `langgraph >= 0.2` — StateGraph |
| LLM framework | `langchain >= 0.3`, `langchain-openai >= 0.1` |
| Language model (classifier) | OpenAI `gpt-4o-mini`, `temperature=0.0` |
| Language model (report) | OpenAI `gpt-4o`, `temperature=0.3` |
| HTTP client | `httpx >= 0.27` (async) |
| Observability | `traceloop-sdk` (OpenLLMetry on OpenTelemetry) |
| Tracing protocol | OTLP/HTTP → local OpenTelemetry collector (default) or any OTLP endpoint |
| Key loading | `python-dotenv` |
| Notebook widgets | `ipywidgets >= 8.0` |
| Runtime | Python 3.11+ (tested on 3.14), `asyncio` |

**requirements.txt:**
```
langgraph>=0.2
langchain>=0.3
langchain-openai>=0.1
openai>=1.0
httpx>=0.27
traceloop-sdk>=0.30
opentelemetry-sdk>=1.27
opentelemetry-exporter-otlp-proto-http>=1.27
python-dotenv>=1.0
ipywidgets>=8.0
```

---

## PROJECT FILE STRUCTURE

```
flowrun-streamlet-ioc-triage-v0.0.33/
│
├── flowrun_agent.py              # CLI entry point
├── flowrun_agent.ipynb           # Jupyter Notebook (8 cells)
├── requirements.txt
├── .env.template
├── .gitignore
│
├── agent/
│   ├── __init__.py
│   ├── graph.py                  # LangGraph StateGraph — all nodes and edges
│   ├── state.py                  # AgentState TypedDict
│   ├── llm.py                    # MODEL_CONFIG dict + get_llm(task) factory
│   ├── tracing.py                # OpenTelemetry / Traceloop (OpenLLMetry) tracer setup
│   ├── credentials.py            # Key resolution: .env → os.environ → getpass()
│   ├── scoring.py                # 4 weight sets, 8 normalisers, conflict detection, TL;DR
│   ├── report.py                 # Report formatter — CLI text + HTML (Jupyter)
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py               # ThreatIntelTool abstract base class with retry
│   │   ├── virustotal.py
│   │   ├── abuseipdb.py
│   │   ├── otx.py
│   │   ├── urlscan.py            # Two-phase: submit scan then poll result
│   │   ├── nvd.py
│   │   ├── osv.py                # OSVTool (single) + OSVMultiTool (×10 ecosystems)
│   │   └── registry.py           # npm/PyPI registry metadata
│   │
│   └── integrations/
│       ├── __init__.py
│       ├── virustotal.py
│       ├── abuseipdb.py
│       ├── otx.py
│       ├── urlscan.py
│       ├── nvd.py
│       ├── osv.py                # 27-ecosystem map + query builders
│       └── registry.py           # npm/PyPI metadata parsers
│
└── tests/
    ├── test_classifier.py        # 26 tests — all 9 IOC types + edge cases
    ├── test_scoring.py           # 72 tests — weights, normalisers, conflicts, TL;DR, packages
    ├── test_tools.py             # 25 tests — URL routing, response parsing, OSV, registry
    └── test_graph.py             # 34 tests — integration with stubbed tools
```

---

## CRITICAL IMPLEMENTATION RULES

### 1. IOC Types
The classifier must detect and handle exactly **nine** IOC types + unknown:
- `ip` — IPv4 or IPv6
- `domain` — hostname/FQDN without scheme (must contain a dot)
- `url` — full URL with http/https/ftp scheme
- `hash_md5` — exactly 32 hex characters
- `hash_sha1` — exactly 40 hex characters
- `hash_sha256` — exactly 64 hex characters
- `cve` — CVE-YYYY-NNNNN format
- `package` — prefixed as `ecosystem:name` (e.g., `npm:postmark-mcp`, `rhel:openssl`)
- `package_multi` — bare package name with no prefix (e.g., `traceroute`, `express`)
- `unknown` — routes to error_node

Regex classification order matters: package first (uses `:`), then CVE (also uses `:`), then URL (scheme), IP, hashes, domain, bare package last.

### 2. Severity Tiers — Five Distinct Bands
```
0.00 – 0.10  →  CLEAN
0.11 – 0.30  →  LOW
0.31 – 0.55  →  MEDIUM
0.56 – 0.75  →  HIGH
0.76 – 1.00  →  CRITICAL
```
CRITICAL triggers escalation gate. HIGH does not.

### 3. Scoring Weights — Four Separate Dicts, Each Sums to 1.00

**BASE_WEIGHTS** (IP, domain, URL, hash types):
```python
BASE_WEIGHTS = {
    'virustotal': 0.40,
    'abuseipdb':  0.30,  # IP only — redistributed for others
    'otx':        0.20,
    'urlscan':    0.10,  # URL + domain — redistributed for others
}
```

**CVE_WEIGHTS** (CVE type only — VirusTotal excluded, has no CVE endpoint):
```python
CVE_WEIGHTS = {
    'otx':  0.40,
    'nvd':  0.60,
}
```

**PACKAGE_WEIGHTS** (prefixed package type):
```python
PACKAGE_WEIGHTS = {
    'osv':      0.60,
    'registry': 0.40,
}
```

**PACKAGE_MULTI_WEIGHTS** (bare package name):
```python
PACKAGE_MULTI_WEIGHTS = {
    'osv_multi': 1.00,
}
```

### 4. VirusTotal Normaliser — Non-Linear Tiered Curve
Do NOT use linear `(malicious + suspicious*0.5) / total`. Use tiered detection count:
```
0 detections       → 0.00
1–2 detections     → 0.20
3–5 detections     → 0.40
6–15 detections    → 0.60
16–30 detections   → 0.80
31+ detections     → 1.00
```

### 5. API Routing by IOC Type

| API | IP | Domain | URL | Hash | CVE | Package | Package Multi |
|-----|:--:|:------:|:---:|:----:|:---:|:-------:|:-------------:|
| VirusTotal | ✅ | ✅ | ✅* | ✅ | ❌ | ❌ | ❌ |
| AbuseIPDB | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| OTX | ✅ | ✅ | ✅* | ✅ | ✅ | ❌ | ❌ |
| urlscan.io | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| NIST NVD | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| OSV.dev | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| OSV.dev ×10 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| npm/PyPI registry | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |

*For URL types: VT and OTX also query the extracted domain separately. The merge step keeps the stronger signal.

### 6. Parallelism — asyncio.gather(), Not LangGraph Fan-Out
The enrichment node is a **single async node** that calls all applicable tools via `asyncio.gather(return_exceptions=True)`.

### 7. urlscan.io — Two-Phase Async Poll
POST to `/api/v1/scan/` → get UUID → poll GET `/api/v1/result/{uuid}/` every 3s, up to 10 attempts (30s max).

### 8. Credentials — Three-Step Resolution, No Hardcoding
1. `.env` file via `load_dotenv(override=False)`
2. `os.environ` check
3. `getpass()` for any still-missing keys

Required keys (5): OPENAI_API_KEY, VIRUSTOTAL_API_KEY, ABUSEIPDB_API_KEY, OTX_API_KEY, URLSCAN_API_KEY. Note: OSV.dev, npm, PyPI require no keys. OpenTelemetry configuration is fully optional; the agent defaults to a local OTLP/HTTP collector on `http://localhost:4318`. Override via `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, or `OTEL_SERVICE_NAME`.

### 9. AgentState Schema
```python
class AgentState(TypedDict):
    ioc_raw: str
    ioc_clean: str
    ioc_type: str                       # 9 types + 'unknown'
    raw_intel: dict[str, Any]
    intel_errors: list[str]
    score_breakdown: dict[str, float]
    composite_score: float
    active_weights: dict[str, float]
    severity_band: str
    verdict_justification: str
    escalation_required: bool
    report_text: str
    report_html: str
    trace_endpoint: str
```

### 10. OpenTelemetry Tracing
```python
from traceloop.sdk import Traceloop

def init_tracing(app_name='flowrun-streamlet-ioc-triage'):
    endpoint = (
        os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
        or os.getenv('TRACELOOP_BASE_URL')
        or 'http://localhost:4318'
    )
    Traceloop.init(
        app_name=app_name,
        api_endpoint=endpoint,
        disable_batch=True,
        resource_attributes={'service.name': app_name},
    )
    return endpoint
```

Traceloop installs a global OpenTelemetry `TracerProvider` and auto-instruments LangChain, LangGraph, and OpenAI. Custom manual spans in `correlation_node` (`flowrun.correlate`) and `severity_node` (`flowrun.severity`) use the standard `opentelemetry.trace.get_tracer()` API and are picked up automatically.

### 11. MODEL_CONFIG — Single Source of Truth
```python
MODEL_CONFIG = {
    "classifier": {
        "model":       "gpt-4o-mini",
        "temperature": 0.0,
    },
    "report": {
        "model":       "gpt-4o",
        "temperature": 0.3,
    },
}
```
No other file contains a hardcoded model string. `get_llm("classifier")` → GPT-4o-mini. `get_llm("report")` → GPT-4o.

### 12. Escalation Gate — Environment-Aware
- CLI mode: `input("Proceed? (yes / abort): ")`
- Jupyter mode: Detects ZMQInteractiveShell → auto-proceeds with stderr warning
- Non-interactive (piped/CI): Catches EOFError → auto-proceeds

### 13. Report Features
Every report includes: TL;DR summary, timestamp, IOC details, per-source findings with extracted details (AV detection names for hashes, OTX adversary/campaign tags, CVSS severity string for CVEs), conflict callouts, per-ecosystem breakdown (package_multi), score breakdown, correlation summary, recommended actions, error list, data confidence indicator.

### 14. Package Multi-Ecosystem Scan
Bare package names (no prefix) are scanned across 10 ecosystems simultaneously: npm, PyPI, crates.io, Go, Maven, NuGet, RubyGems, Packagist, Pub, Hex. 27 total ecosystems supported for prefixed queries, including Linux distros (Red Hat, Debian, Ubuntu, Alpine, Rocky, AlmaLinux, SUSE).

---

## COMMON MISTAKES TO AVOID

- ❌ Do NOT use `gpt-5.2` — use `gpt-4o-mini` (classifier) and `gpt-4o` (report)
- ❌ Do NOT use `requests` — use `httpx` (async)
- ❌ Do NOT pin `arize-otel` or `openinference-instrumentation-langchain` — use `traceloop-sdk` instead
- ❌ Do NOT require `ARIZE_API_KEY` / `ARIZE_SPACE_ID` — they were removed; OpenTelemetry config is optional via standard env vars
- ❌ Do NOT include VirusTotal in CVE_WEIGHTS — VT has no CVE endpoint
- ❌ Do NOT use linear VT normalisation — use the non-linear tiered curve
- ❌ Do NOT hardcode model strings outside `agent/llm.py`
- ❌ Do NOT use `input()` in Jupyter — use `ipywidgets`; escalation gate must detect environment
- ❌ Do NOT implement only 7 IOC types — there are 9 (+ unknown)
- ❌ Do NOT query VT/OTX for package types — they're skipped; only OSV.dev + registry are queried
- ❌ Do NOT allow a single API failure to abort the whole triage
- ❌ Do NOT allow OTLP export failure to block the triage report

---

*FlowRun Streamlet: IoC Triage — Build Prompt v3 — Reconciled with codebase v0.0.33*
