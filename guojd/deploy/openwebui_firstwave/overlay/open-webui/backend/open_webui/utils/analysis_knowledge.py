"""Proxy Open WebUI analysis-page knowledge calls to local XvirMind MCP servers."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

TAXONOMY_BASE = os.getenv("XVIRMIND_TAXONOMY_MCP", "http://127.0.0.1:8766")
ANNOTATION_BASE = os.getenv("XVIRMIND_ANNOTATION_MCP", "http://127.0.0.1:8767")

QUERY_TOOLS = {
    "taxonomy_capability": TAXONOMY_BASE,
    "taxonomy_search_kb": TAXONOMY_BASE,
    "taxonomy_family_info": TAXONOMY_BASE,
    "annotation_capability": ANNOTATION_BASE,
    "annotation_list_families": ANNOTATION_BASE,
}

COMPUTE_TOOLS = {
    "taxonomy_classify": TAXONOMY_BASE,
    "annotation_annotate": ANNOTATION_BASE,
}


class KnowledgeProxyError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _call(base: str, tool: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    url = f"{base.rstrip('/')}/tools/{tool}"
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:800]
        raise KnowledgeProxyError(f"{tool} HTTP {error.code}: {detail}", 502) from error
    except urllib.error.URLError as error:
        raise KnowledgeProxyError(f"{tool} unreachable at {base}: {error.reason}", 503) from error
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise KnowledgeProxyError(f"{tool} returned non-JSON", 502) from error


def mcp_health() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, base in (("taxonomy", TAXONOMY_BASE), ("annotation", ANNOTATION_BASE)):
        url = f"{base.rstrip('/')}/health"
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                out[key] = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            out[key] = {"status": "down", "error": str(exc), "url": base}
    return out


def call_query(tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    base = QUERY_TOOLS.get(tool)
    if not base:
        raise KnowledgeProxyError(f"unknown query tool: {tool}", 400)
    return _call(base, tool, arguments, timeout=20)


def call_classify(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(arguments or {})
    timeout = 180 if payload.get("confirm") else 20
    return _call(TAXONOMY_BASE, "taxonomy_classify", payload, timeout=timeout)


def call_annotate(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(arguments or {})
    timeout = 180 if payload.get("confirm") else 20
    return _call(ANNOTATION_BASE, "annotation_annotate", payload, timeout=timeout)
