# agent/tracing.py
# ─────────────────────────────────────────────────────────────────────────────
# OpenTelemetry + Traceloop (OpenLLMetry) tracing setup.
#
# Auto-instruments all LangChain, LangGraph, and OpenAI operations and ships
# spans via OTLP/HTTP to the configured collector. The default destination is
# a local OpenTelemetry collector agent listening on http://localhost:4318
# (the standard OTLP/HTTP port). Override via OTEL_EXPORTER_OTLP_ENDPOINT or
# TRACELOOP_BASE_URL.
#
# Called once at agent startup — before graph.compile() is invoked.
# ─────────────────────────────────────────────────────────────────────────────

import os
import sys

DEFAULT_OTLP_ENDPOINT = "http://localhost:4318"
DEFAULT_SERVICE_NAME = "flowrun-streamlet-ioc-triage"


def _resolve_endpoint() -> str:
    """
    Resolve the OTLP endpoint with the following precedence:
      1. OTEL_EXPORTER_OTLP_ENDPOINT (standard OTEL env var)
      2. TRACELOOP_BASE_URL          (Traceloop env var)
      3. DEFAULT_OTLP_ENDPOINT       (local collector agent)
    """
    return (
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.getenv("TRACELOOP_BASE_URL")
        or DEFAULT_OTLP_ENDPOINT
    )


def _parse_headers(raw: str | None) -> dict[str, str] | None:
    """Parse an OTEL_EXPORTER_OTLP_HEADERS-style string into a dict."""
    if not raw:
        return None
    headers: dict[str, str] = {}
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        k, _, v = pair.partition("=")
        k = k.strip()
        v = v.strip()
        if k:
            headers[k] = v
    return headers or None


def init_tracing(service_name: str | None = None):
    """
    Initialise OpenTelemetry tracing via Traceloop (OpenLLMetry).

    Returns the active endpoint string on success, or None if setup fails
    (non-blocking — tracing failure must never prevent triage completion,
    per NFR-07).
    """
    endpoint = _resolve_endpoint()
    headers = _parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))
    app_name = service_name or os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)

    try:
        from traceloop.sdk import Traceloop

        Traceloop.init(
            app_name=app_name,
            api_endpoint=endpoint,
            disable_batch=True,
            headers=headers,
            resource_attributes={
                "service.name": app_name,
                "service.version": "0.0.33",
            },
        )
        return endpoint
    except Exception as exc:
        # NFR-07: tracing failure must NOT block triage completion.
        print(
            f"⚠️  OpenTelemetry tracing initialisation failed: {exc}\n"
            f"   (endpoint: {endpoint}) — triage will continue without tracing.",
            file=sys.stderr,
        )
        return None
