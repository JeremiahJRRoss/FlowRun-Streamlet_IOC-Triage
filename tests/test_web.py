# tests/test_web.py
# ─────────────────────────────────────────────────────────────────────────────
# Smoke tests for the FastAPI web interface. Uses FastAPI's TestClient with a
# stubbed graph so the agent's real intel calls are never made.
# ─────────────────────────────────────────────────────────────────────────────

import pytest
from fastapi.testclient import TestClient


class _StubGraph:
    """Minimal stand-in for the compiled LangGraph."""

    def __init__(self, response: dict | None = None, exc: Exception | None = None):
        self._response = response or {"report_html": "<p>stub-report</p>"}
        self._exc = exc

    async def ainvoke(self, _state):  # noqa: D401 — mimics LangGraph API
        if self._exc is not None:
            raise self._exc
        return self._response


@pytest.fixture
def client(monkeypatch):
    """A TestClient with credential resolution, tracing init, and graph compile stubbed."""
    monkeypatch.setattr("agent.credentials.resolve_credentials", lambda: None)
    monkeypatch.setattr("agent.tracing.init_tracing", lambda: "http://localhost:4318")
    monkeypatch.setattr("agent.graph.build_graph", lambda: _StubGraph())

    # Import here so the patches above apply to web.app's lifespan
    from web.app import app

    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["trace_endpoint"] == "http://localhost:4318"


def test_index_renders_form(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "FlowRun Streamlet" in html
    assert "<textarea" in html
    assert 'name="ioc"' in html
    assert "/static/style.css" in html


def test_triage_returns_report_html(client):
    resp = client.post("/triage", data={"ioc": "8.8.8.8"})
    assert resp.status_code == 200
    assert resp.text == "<p>stub-report</p>"


def test_triage_rejects_empty_input(client):
    resp = client.post("/triage", data={"ioc": "   "})
    assert resp.status_code == 400
    assert "Please enter an IOC" in resp.text


def test_triage_handles_graph_exception(monkeypatch):
    monkeypatch.setattr("agent.credentials.resolve_credentials", lambda: None)
    monkeypatch.setattr("agent.tracing.init_tracing", lambda: None)
    monkeypatch.setattr(
        "agent.graph.build_graph",
        lambda: _StubGraph(exc=RuntimeError("boom")),
    )
    from web.app import app

    with TestClient(app) as c:
        resp = c.post("/triage", data={"ioc": "8.8.8.8"})
    assert resp.status_code == 500
    assert "Triage failed" in resp.text
    assert "RuntimeError" in resp.text


def test_static_css_served(client):
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
