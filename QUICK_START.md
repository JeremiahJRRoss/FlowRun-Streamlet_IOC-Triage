# FlowRun Streamlet: IoC Triage — Quick Start Guide

## 1. Extract and enter the project

```bash
tar xzf flowrun-streamlet-ioc-triage.tar.gz
cd flowrun-streamlet-ioc-triage
```

## 2. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv            # Python 3.11 or newer (tested on 3.14)
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate          # Windows

pip install -r requirements.txt
```

## 3. Set up your API keys

Copy the template and fill in your keys:

```bash
cp .env.template .env
```

Open `.env` in any text editor and paste each key directly after the `=` sign — no quotes, no spaces:

```
OPENAI_API_KEY=sk-your-openai-key-here
VIRUSTOTAL_API_KEY=your-vt-key-here
ABUSEIPDB_API_KEY=your-abuseipdb-key-here
OTX_API_KEY=your-otx-key-here
URLSCAN_API_KEY=your-urlscan-key-here
```

If you skip the `.env` file, the agent will prompt you for each key interactively at startup.

### Where to get your API keys

| Key | Where to find it |
|-----|-----------------|
| OPENAI_API_KEY | [platform.openai.com → API Keys](https://platform.openai.com/api-keys) |
| VIRUSTOTAL_API_KEY | [virustotal.com → Profile → API Key](https://www.virustotal.com) |
| ABUSEIPDB_API_KEY | [abuseipdb.com → Account → API](https://www.abuseipdb.com) |
| OTX_API_KEY | [otx.alienvault.com → Settings → API Key](https://otx.alienvault.com) |
| URLSCAN_API_KEY | [urlscan.io → Settings → API Keys](https://urlscan.io) |

### Tracing (optional)

By default the agent ships OpenTelemetry spans via OTLP/HTTP to `http://localhost:4318` — the standard port for a local OpenTelemetry collector agent. If you don't have a collector running locally, that's fine; tracing fails silently and triage continues normally.

To send traces somewhere else, set `OTEL_EXPORTER_OTLP_ENDPOINT` (and optionally `OTEL_EXPORTER_OTLP_HEADERS` for authenticated backends) in your `.env`:

```
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
# OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer your_token
# OTEL_SERVICE_NAME=flowrun-streamlet-ioc-triage
```

## 4. Run the CLI

```bash
source .venv/bin/activate
python flowrun_agent.py
```

Type or paste any IOC (IP, domain, URL, file hash, CVE, or package) at the `IOC ▶` prompt and press Enter.

Example package IOC:
```
npm:postmark-mcp
```

## 5. Run the Jupyter Notebook

### First-time setup: register the virtual environment as a Jupyter kernel

Jupyter does not automatically use your virtual environment's packages. You must register it as a kernel once:

```bash
source .venv/bin/activate
pip install ipykernel
python -m ipykernel install --user --name=flowrun --display-name="FlowRun (venv)"
```

### Launch the notebook

```bash
jupyter notebook flowrun_agent.ipynb
```

**Before running any cells**, go to **Kernel → Change kernel** and select **"FlowRun (venv)"**.

Then run cells 1 through 5 in order to initialise the environment, and use Cell 6 to submit IOCs for triage.

## 6. Run the test suite

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'langgraph'` in Jupyter | You need to register the venv kernel — see Step 5 above |
| API key errors at startup | Check your `.env` file has no quotes around values and no trailing spaces |
| `EnvironmentError: Required API keys not provided` | One or more keys are missing — check the list above |
| Cell hangs or behaves unexpectedly | Use Kernel → Restart & Clear Output, verify the "FlowRun (venv)" kernel is selected, then re-run from Cell 1 |
