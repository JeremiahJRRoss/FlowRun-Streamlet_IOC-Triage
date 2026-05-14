# tests/test_tracing.py
# ─────────────────────────────────────────────────────────────────────────────
# Smoke tests for agent.tracing: endpoint resolution precedence, header
# parsing, and graceful failure of init_tracing when no collector is reachable.
# ─────────────────────────────────────────────────────────────────────────────

from agent import tracing


def test_resolve_endpoint_default(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("TRACELOOP_BASE_URL", raising=False)
    assert tracing._resolve_endpoint() == "http://localhost:4318"


def test_resolve_endpoint_otel_env(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.example:4318")
    assert tracing._resolve_endpoint() == "http://collector.example:4318"


def test_resolve_endpoint_traceloop_env(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("TRACELOOP_BASE_URL", "http://traceloop.example:4318")
    assert tracing._resolve_endpoint() == "http://traceloop.example:4318"


def test_parse_headers_none():
    assert tracing._parse_headers(None) is None
    assert tracing._parse_headers("") is None


def test_parse_headers_single():
    assert tracing._parse_headers("Authorization=Bearer abc") == {"Authorization": "Bearer abc"}


def test_parse_headers_multi():
    parsed = tracing._parse_headers("a=1,b=2,c=3")
    assert parsed == {"a": "1", "b": "2", "c": "3"}


def test_init_tracing_returns_endpoint_or_none():
    # Must not raise even if the collector is unreachable.
    result = tracing.init_tracing()
    assert result is None or isinstance(result, str)
