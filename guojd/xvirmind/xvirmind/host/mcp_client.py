from __future__ import annotations

from typing import Any

import httpx

from xvirmind.config import load

_CFG = load()
BIND = _CFG["host"]["bind"]
TAX = f"http://{BIND}:{_CFG['mcp']['taxonomy_port']}"
ANN = f"http://{BIND}:{_CFG['mcp']['annotation_port']}"

ROUTES = {
    "taxonomy_capability": TAX,
    "taxonomy_search_kb": TAX,
    "taxonomy_family_info": TAX,
    "taxonomy_classify": TAX,
    "annotation_capability": ANN,
    "annotation_list_families": ANN,
    "annotation_annotate": ANN,
}


def list_remote_tools() -> list[dict[str, Any]]:
    tools = []
    for base in (TAX, ANN):
        try:
            data = httpx.get(f"{base}/tools", timeout=5.0).json()
            for item in data.get("tools") or []:
                item = dict(item)
                item["server"] = base
                tools.append(item)
        except Exception as exc:  # noqa: BLE001
            tools.append({"name": f"UNAVAILABLE:{base}", "description": str(exc), "server": base})
    return tools


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    base = ROUTES.get(name)
    if not base:
        return {"isError": True, "structuredContent": {"error": f"unregistered tool {name}"}}
    resp = httpx.post(f"{base}/tools/{name}", json=arguments or {}, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def health() -> dict[str, Any]:
    out = {}
    for key, base in (("taxonomy", TAX), ("annotation", ANN)):
        try:
            out[key] = httpx.get(f"{base}/health", timeout=3.0).json()
        except Exception as exc:  # noqa: BLE001
            out[key] = {"status": "down", "error": str(exc), "url": base}
    return out
