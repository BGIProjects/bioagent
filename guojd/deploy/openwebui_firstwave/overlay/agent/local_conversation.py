"""Conversation fallback plus MiniMax-compatible propose_patch / flowchart."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, AsyncIterator

from conversation_contract import ConversationAction, ProposedPatch, proposal_output
from conversation_events import OutputItemAdded, TextDelta

TAXONOMY = os.getenv("XVIRMIND_TAXONOMY_MCP", "http://127.0.0.1:8766")
ANNOTATION = os.getenv("XVIRMIND_ANNOTATION_MCP", "http://127.0.0.1:8767")
TESTDATA = os.getenv(
    "BIOAGENT_TESTDATA_ROOT",
    "/data/user/guojindan/Projects/XvirMind/testdata",
)
DEFAULT_GENOME = f"{TESTDATA}/scenarios/S3_hepacivirus_contigs/KP641127.fna"

GOAL_LABELS = {
    "contig_filter": "W1 质控与组装",
    "virus_summary": "W2 病毒识别",
    "host_summary": "W3 宿主识别",
    "microbe_summary": "W4 微生物谱",
    "virus_rpm": "W5 病毒定量",
    "annotation_delivery": "W6 病毒注释",
}
GOAL_PATTERNS = (
    (r"(?<![A-Za-z0-9])w1(?![A-Za-z0-9])|质控|组装|contig_filter", "contig_filter"),
    (r"(?<![A-Za-z0-9])w2(?![A-Za-z0-9])|病毒识别|virus_summary", "virus_summary"),
    (r"(?<![A-Za-z0-9])w3(?![A-Za-z0-9])|宿主", "host_summary"),
    (r"(?<![A-Za-z0-9])w4(?![A-Za-z0-9])|微生物|kraken|bracken|microbe_summary", "microbe_summary"),
    (r"(?<![A-Za-z0-9])w5(?![A-Za-z0-9])|定量|rpm|virus_rpm", "virus_rpm"),
    (r"(?<![A-Za-z0-9])w6(?![A-Za-z0-9])|流程注释|annotation_delivery", "annotation_delivery"),
)


def _latest_user(messages: list[dict]) -> str:
    for message in reversed(messages or []):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [str(item.get("text") or "") for item in content if isinstance(item, dict)]
            return " ".join(parts).strip()
    return ""


def _mcp(base: str, tool: str, payload: dict[str, Any], timeout: float = 25) -> dict[str, Any]:
    url = f"{base.rstrip('/')}/tools/{tool}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        return {"error": f"{tool} HTTP {error.code}: {detail}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{tool} 不可用: {exc}"}
    structured = body.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    content = body.get("content")
    if isinstance(content, list) and content:
        text = content[0].get("text") if isinstance(content[0], dict) else None
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
    return body if isinstance(body, dict) else {"result": body}


def _dataset_files(dataset: dict[str, Any] | None) -> list[str]:
    if not dataset:
        return []
    files: list[str] = []
    raw_files = dataset.get("files")
    if isinstance(raw_files, list):
        files.extend(str(item) for item in raw_files if item)
    elif isinstance(raw_files, dict):
        for value in raw_files.values():
            if isinstance(value, dict) and value.get("path"):
                files.append(str(value["path"]))
            elif isinstance(value, str) and value:
                files.append(value)
    for artifact in dataset.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        for record in artifact.get("records") or []:
            if not isinstance(record, dict):
                continue
            rec_files = record.get("files") or {}
            if isinstance(rec_files, dict):
                for spec in rec_files.values():
                    if isinstance(spec, dict) and spec.get("path"):
                        files.append(str(spec["path"]))
                    elif isinstance(spec, str) and spec:
                        files.append(spec)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in files:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _summarize_ctx(dataset: dict[str, Any] | None, plan: dict[str, Any] | None) -> str:
    lines = []
    files = _dataset_files(dataset)
    if dataset:
        ident = dataset.get("dataset_id") or dataset.get("id") or "未创建"
        status = dataset.get("status") or "未知"
        lines.append(f"当前数据集：{ident}（revision {dataset.get('revision', '?')}，状态 {status}）。")
        if files:
            lines.append(f"文件 {len(files)} 个：")
            lines.extend(f"- {path}" for path in files)
        else:
            lines.append("数据集还没有文件列表。")
        if status == "needs_review":
            lines.append("多样本需要确认 sample 分组后才能出正式方案；页面会尝试自动确认已配对的 demoA/demoB。")
    else:
        lines.append("还没有数据集。请先在右侧确认选用文件。")
    if plan and (plan.get("goals") or plan.get("title")):
        goals = plan.get("goals") or []
        labels = [GOAL_LABELS.get(goal, goal) for goal in goals]
        lines.append(f"当前方案：{plan.get('title') or plan.get('summary') or '已生成'}。")
        if labels:
            lines.append("目标：" + "、".join(labels) + "。")
        if plan.get("ready_to_execute") is True:
            lines.append("方案可执行。请在中间点「确认启动分析」。")
        elif plan.get("blocking_reason"):
            lines.append(f"方案未就绪：{plan.get('blocking_reason')}")
    else:
        lines.append("当前还没有已编译的确定性方案。")
    return "\n".join(lines)


def _parse_goals(text: str) -> list[str]:
    found: list[str] = []
    for pattern, goal in GOAL_PATTERNS:
        if re.search(pattern, text, re.I) and goal not in found:
            found.append(goal)
    return found


def _mermaid(goals: list[str]) -> str:
    if not goals:
        return ""
    nodes = ["reads[已选用 reads/contigs]"]
    edges = []
    prev = "reads"
    for index, goal in enumerate(goals):
        node = f"g{index}[{GOAL_LABELS.get(goal, goal)}]"
        nodes.append(node)
        edges.append(f"    {prev} --> {node.split('[')[0]}")
        prev = node.split("[")[0]
    return "```mermaid\nflowchart LR\n    " + "\n    ".join(nodes) + "\n" + "\n".join(edges) + "\n```"


def _pick_genome(text: str) -> str:
    match = re.search(r"(/data/\S+\.(?:fna|fa|fasta))", text)
    if match:
        return match.group(1)
    if "KP325401" in text:
        return f"{TESTDATA}/scenarios/S3_hepacivirus_contigs/KP325401.fna"
    return DEFAULT_GENOME


def _pick_family(text: str) -> str:
    match = re.search(r"(Flaviviridae|Coronaviridae|Adenoviridae|Hepacivirus)", text, re.I)
    return match.group(1) if match else "Flaviviridae"


def build_reply(
    messages: list[dict],
    dataset: dict[str, Any] | None,
    plan: dict[str, Any] | None,
) -> tuple[str, ConversationAction | None]:
    text = _latest_user(messages)
    lowered = text.lower()
    ctx = _summarize_ctx(dataset, plan)
    goals = _parse_goals(text)
    exclusive = bool(re.search(r"只想|只要|仅|only", text))

    if re.search(r"定种|classify|taxonomy|分类|科级|kb\.jsonl", lowered):
        genome = _pick_genome(text)
        family = _pick_family(text)
        confirm = bool(re.search(r"确认定种", text))
        result = _mcp(TAXONOMY, "taxonomy_classify", {"genome": genome, "family": family, "confirm": confirm})
        return (
            f"已走 wangdaxi virus_taxonomy。\n输入：{genome}　科：{family}\n"
            f"{json.dumps(result, ensure_ascii=False, indent=2)[:1600]}\n\n{ctx}",
            None,
        )

    if re.search(r"\brva\b|rna 注释|注释专项|annotation_annotate", lowered):
        genome = _pick_genome(text)
        family = _pick_family(text)
        confirm = bool(re.search(r"确认\s*rva|确认注释", text))
        result = _mcp(ANNOTATION, "annotation_annotate", {"genome": genome, "family": family, "confirm": confirm})
        return (
            f"已走 wangdaxi RVA。流程注释仍是 W6。\n{json.dumps(result, ensure_ascii=False, indent=2)[:1600]}\n\n{ctx}",
            None,
        )

    if goals and re.search(r"方案|制定|只要|只想|改成|改成只|调整目标|w[1-6]", lowered):
        labels = "、".join(GOAL_LABELS[goal] for goal in goals)
        chart = _mermaid(goals)
        message = (
            f"按你的要求，方案目标改为：{labels}。\n"
            f"{chart}\n"
            "这是确定性规划器支持的受控补丁（goals）。"
            "工具级参数、技能库、文献库按建设方案 1C 仍走白名单 preset，当前最新 lfz 契约还不能从对话改任意参数。\n"
            f"{ctx}\n"
            "请在对话里确认这条方案修改；确认后中间会重绘流程并给出「确认启动分析」。"
        )
        action = ConversationAction(
            action="propose_patch",
            message=message,
            proposed_patch=ProposedPatch(goals=goals),
        )
        return message, action

    if re.search(r"流程图|流程预测|画一下流程|mermaid", text):
        current = (plan or {}).get("goals") or goals
        chart = _mermaid(current) if current else "还没有可绘制的目标。先说只要 W1/W4，或先确认选用文件。"
        return f"当前流程如下。\n{chart}\n{ctx}", None

    if re.search(r"现在.*方案|当前方案|方案是什么|计算方案是什么", text):
        current = (plan or {}).get("goals") or []
        chart = _mermaid(current)
        extra = (
            f"已编译目标：{'、'.join(GOAL_LABELS.get(g, g) for g in current)}。"
            if current
            else "还没有已编译方案。你可以直接说「我只想计算 W1 和 W4，给我制定方案」。"
        )
        return f"{extra}\n{chart}\n{ctx}", None

    if re.search(r"参数|fastp|preset|工具库|技能库|文献库", text):
        return (
            "对话改方案目前与 liufangzhou 最新契约一致：只能改 goals / viral_type，"
            "不能直接改 workflow 内部参数。建设方案 1C 要求参数走工具目录白名单 preset，"
            "由确定性编译器校验后再展开。工具库 / 技能库 / 文献库已在方案里，尚未接到这条对话补丁上。\n"
            f"{ctx}",
            None,
        )

    if exclusive and goals:
        message = "按你的范围只保留：" + "、".join(GOAL_LABELS[g] for g in goals) + f"。\n{_mermaid(goals)}\n{ctx}"
        return message, ConversationAction(
            action="propose_patch",
            message=message,
            proposed_patch=ProposedPatch(goals=goals),
        )

    return (
        "可以说「只要 W1 和 W4」「当前方案是什么」「画流程图」「定种 / RVA」。\n"
        "目标变更会生成一条可确认的方案补丁，不是只回固定说明。\n"
        f"{ctx}",
        None,
    )


class LocalSessionManager:
    async def ensure_session(self, chat_id: str | None) -> None:
        return None

    async def close_all(self) -> None:
        return None

    async def stream_ephemeral_turn(self, messages: list[dict]) -> AsyncIterator[TextDelta | OutputItemAdded]:
        async for event in self.stream_turn(messages, None):
            yield event

    async def stream_turn(
        self,
        messages: list[dict],
        chat_id: str | None,
        routing_request: dict[str, Any] | None = None,
        dataset_context: dict[str, Any] | None = None,
        plan_context: dict[str, Any] | None = None,
        **_: Any,
    ) -> AsyncIterator[TextDelta | OutputItemAdded]:
        text, action = build_reply(messages, dataset_context, plan_context)
        step = 160
        for start in range(0, max(len(text), 1), step):
            yield TextDelta(text[start : start + step])
        if action is not None:
            item = proposal_output(action)
            if item:
                yield OutputItemAdded(item)
