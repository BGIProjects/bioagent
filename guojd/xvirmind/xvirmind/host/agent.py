from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from xvirmind.host import mcp_client

SESSIONS: dict[str, dict[str, Any]] = {}

COMPUTE_TOOLS = {"taxonomy_classify", "annotation_annotate"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_session(session_id: str | None) -> dict[str, Any]:
    sid = session_id or str(uuid.uuid4())
    if sid not in SESSIONS:
        SESSIONS[sid] = {"id": sid, "created": _now(), "events": [], "messages": []}
    return SESSIONS[sid]


def _event(session: dict[str, Any], kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    ev = {"ts": _now(), "kind": kind, **payload}
    session["events"].append(ev)
    return ev


def _route(text: str) -> list[dict[str, Any]]:
    t = text.lower()
    calls: list[dict[str, Any]] = []
    family = _guess_family(text)

    if any(k in t for k in ("注释", "annotate", "annotation", "rdrp", "orf", "基因结构", "rva")):
        if family and "科" in text or family:
            calls.append({"name": "annotation_list_families", "arguments": {"query": family or ""}})
        else:
            calls.append({"name": "annotation_capability", "arguments": {}})
        genome = _guess_path(text)
        if genome:
            calls.append({"name": "annotation_annotate", "arguments": {"genome": genome, "family": family, "confirm": "确认执行" in text or "confirm=true" in t}})
        return calls

    if any(k in t for k in ("分类", "ictv", "taxonomy", "科", "属", "种", "新种", "kb")):
        if family:
            calls.append({"name": "taxonomy_family_info", "arguments": {"family_name": family}})
        else:
            q = text.strip()
            for prefix in ("查询", "搜索", "search", "分类", "ictv"):
                q = q.replace(prefix, "")
            q = q.strip() or "Coronaviridae"
            calls.append({"name": "taxonomy_search_kb", "arguments": {"query": q, "limit": 8}})
        genome = _guess_path(text)
        if genome:
            calls.append({"name": "taxonomy_classify", "arguments": {"genome": genome, "family": family, "confirm": "确认执行" in text or "confirm=true" in t}})
        return calls

    calls.append({"name": "taxonomy_capability", "arguments": {}})
    calls.append({"name": "annotation_capability", "arguments": {}})
    return calls


_FAM_RE = re.compile(r"\b([A-Z][a-z]+viridae)\b")
_PATH_RE = re.compile(r"(/[^\s]+\.(?:fa|fna|fasta|fa\.gz))")


def _guess_family(text: str) -> str | None:
    m = _FAM_RE.search(text)
    return m.group(1) if m else None


def _guess_path(text: str) -> str | None:
    m = _PATH_RE.search(text)
    return m.group(1) if m else None


def chat(message: str, session_id: str | None = None, confirm_compute: bool = False) -> dict[str, Any]:
    session = get_session(session_id)
    session["messages"].append({"role": "user", "content": message})
    _event(session, "user", {"text": message})
    planned = _route(message)
    if confirm_compute:
        for call in planned:
            if call["name"] in COMPUTE_TOOLS:
                call.setdefault("arguments", {})["confirm"] = True

    tool_events = []
    for call in planned:
        _event(session, "tool_call", call)
        try:
            result = mcp_client.call_tool(call["name"], call.get("arguments") or {})
        except Exception as exc:  # noqa: BLE001
            result = {"isError": True, "structuredContent": {"error": str(exc)}}
        _event(session, "tool_result", {"name": call["name"], "result": result})
        tool_events.append({"name": call["name"], "arguments": call.get("arguments"), "result": result})

    reply = _compose(message, tool_events)
    session["messages"].append({"role": "assistant", "content": reply})
    _event(session, "assistant", {"text": reply})
    return {
        "session_id": session["id"],
        "reply": reply,
        "tools": tool_events,
        "events": session["events"][-20:],
        "local_only": True,
    }


def _compose(message: str, tool_events: list[dict[str, Any]]) -> str:
    if not tool_events:
        return "没有可调用的本地插件。"
    parts = ["主 Agent 只编排本地 MCP 插件，不把领域规则写进 DeepSeek Harness。本次调用："]
    for ev in tool_events:
        payload = (ev.get("result") or {}).get("structuredContent") or ev.get("result")
        name = ev["name"]
        if name.endswith("capability"):
            parts.append(f"- {name}: capability `{payload.get('capability_id')}`，源 `{payload.get('source')}`")
        elif name == "taxonomy_family_info":
            parts.append(f"- 科级知识 {payload.get('family_name')} 状态 {payload.get('status')}，属 {payload.get('genus_count')} 个。引用 {payload.get('knowledge_release')}")
        elif name == "taxonomy_search_kb":
            hits = payload.get("hits") or []
            names = ", ".join(f"{h.get('name')}({h.get('level')})" for h in hits[:6]) or "无命中"
            parts.append(f"- 知识检索 {payload.get('status')}：{names}")
        elif name in COMPUTE_TOOLS:
            parts.append(f"- {name} 状态 {payload.get('status')}，模式 {payload.get('mode')}。未确认或未开计算开关时不会跑完整流程。")
        else:
            parts.append(f"- {name}: {json.dumps(payload, ensure_ascii=False)[:280]}")
    parts.append("若要真正启动分类/注释计算，请勾选界面中的「确认计算」并设置 XVIRMIND_ALLOW_COMPUTE=1。")
    return "\n".join(parts)
