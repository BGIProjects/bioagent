from __future__ import annotations

import traceback
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


def mcp_app(name: str, version: str, tools: dict[str, dict[str, Any]]) -> FastAPI:
    """Minimal MCP JSON-RPC over HTTP POST /mcp plus REST /health and /tools."""
    app = FastAPI(title=name, version=version)

    def _tool_list() -> list[dict[str, Any]]:
        return [
            {
                "name": key,
                "description": spec["description"],
                "inputSchema": spec.get("schema") or {"type": "object", "properties": {}},
            }
            for key, spec in tools.items()
        ]

    def _call(name_: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        if name_ not in tools:
            return {"isError": True, "content": [{"type": "text", "text": f"unknown tool: {name_}"}]}
        try:
            result = tools[name_]["handler"](arguments or {})
        except Exception as exc:  # noqa: BLE001 — surface tool errors to the host
            result = {"error": str(exc), "trace": traceback.format_exc()[-800:]}
            return {"isError": True, "content": [{"type": "text", "text": _as_text(result)}], "structuredContent": result}
        return {"isError": False, "content": [{"type": "text", "text": _as_text(result)}], "structuredContent": result}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "server": name, "version": version, "tools": list(tools)}

    @app.get("/tools")
    def rest_tools() -> dict[str, Any]:
        return {"tools": _tool_list()}

    @app.post("/tools/{tool_name}")
    def rest_call(tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return _call(tool_name, payload or {})

    @app.post("/mcp")
    async def mcp_rpc(request: Request) -> JSONResponse:
        body = await request.json()
        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params") or {}
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": name, "version": version},
            }
        elif method == "tools/list":
            result = {"tools": _tool_list()}
        elif method == "tools/call":
            result = _call(params.get("name", ""), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": method}}, status_code=200)
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})

    return app


def _as_text(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
