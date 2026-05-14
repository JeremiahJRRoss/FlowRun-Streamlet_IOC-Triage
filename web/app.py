# web/app.py
# ─────────────────────────────────────────────────────────────────────────────
# FastAPI web interface for FlowRun Streamlet: IoC Triage.
#
# Default deployment surface. Listens on port 7777, serves a minimal htmx UI
# at GET /, accepts IOC submissions at POST /triage, and exposes GET /health
# for container liveness probes.
#
# The agent graph is compiled once at startup; per-request work is just
# graph.ainvoke().
# ─────────────────────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from agent import credentials as _credentials
from agent import graph as _graph
from agent import tracing as _tracing


_WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))

_runtime: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resolve via module attribute access so test fixtures can monkeypatch the
    # underlying agent.credentials / agent.tracing / agent.graph names.
    _credentials.resolve_credentials()
    _runtime["trace_endpoint"] = _tracing.init_tracing()
    _runtime["graph"] = _graph.build_graph()
    yield


app = FastAPI(title="FlowRun Streamlet: IoC Triage", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "trace_endpoint": _runtime.get("trace_endpoint"),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"trace_endpoint": _runtime.get("trace_endpoint") or "(tracing disabled)"},
    )


@app.post("/triage", response_class=HTMLResponse)
async def triage(ioc: str = Form(...)):
    ioc = (ioc or "").strip()
    if not ioc:
        return PlainTextResponse(
            '<p style="color:#dc2626;">Please enter an IOC.</p>',
            status_code=400,
        )

    graph = _runtime.get("graph")
    if graph is None:
        return PlainTextResponse(
            '<p style="color:#dc2626;">Agent not initialised.</p>',
            status_code=503,
        )

    try:
        result = await graph.ainvoke({"ioc_raw": ioc})
    except SystemExit as exc:
        return HTMLResponse(
            f'<p style="color:#f59e0b;">⚠️ {exc}</p>',
            status_code=200,
        )
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(
            f'<p style="color:#dc2626;">❌ Triage failed: '
            f'{type(exc).__name__}: {exc}</p>',
            status_code=500,
        )

    return result.get(
        "report_html",
        '<p style="color:#dc2626;">No report generated.</p>',
    )
