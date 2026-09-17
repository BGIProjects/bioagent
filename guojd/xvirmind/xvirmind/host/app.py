from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from xvirmind import __version__
from xvirmind.config import load
from xvirmind.host import agent, mcp_client
from xvirmind.ops.api import router as ops_router

CFG = load()
WEB = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(title="XvirMind Host", version=__version__)
app.include_router(ops_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "role": "host-orchestrator",
        "harness": "deepseek-harness-compatible-web",
        "local_only": CFG["policy"]["local_only"],
        "allow_compute": CFG["policy"]["allow_compute"],
        "plugins": mcp_client.health(),
    }


@app.get("/api/plugins")
def plugins() -> dict:
    return {"tools": mcp_client.list_remote_tools(), "health": mcp_client.health()}


@app.get("/api/sessions")
def sessions() -> dict:
    return {"sessions": [{"id": s["id"], "created": s["created"], "n_events": len(s["events"])} for s in agent.SESSIONS.values()]}


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str) -> dict:
    return agent.get_session(session_id)


@app.post("/api/chat")
def chat(payload: dict) -> dict:
    return agent.chat(
        message=str(payload.get("message") or ""),
        session_id=payload.get("session_id"),
        confirm_compute=bool(payload.get("confirm_compute")),
    )


@app.post("/api/tools/{name}")
def tool(name: str, payload: dict | None = None) -> dict:
    return mcp_client.call_tool(name, payload or {})


if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB / "index.html")

    @app.get("/knowledge")
    def knowledge_demo() -> FileResponse:
        return FileResponse(WEB / "knowledge.html")

    @app.get("/ops")
    def ops_demo() -> FileResponse:
        page = WEB / "knowledge.html"
        return FileResponse(page)
