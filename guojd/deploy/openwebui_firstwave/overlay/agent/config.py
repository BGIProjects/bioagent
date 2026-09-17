"""Static configuration for the BioAgent runtime."""

import ast
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL = "MiniMax-M3"
ANTHROPIC_BASE_URL = "https://api.minimaxi.com/anthropic"

def _minimax_key() -> str:
    env = os.getenv("MINIMAX_API_KEY", "").strip()
    if env:
        return env
    live = Path("/data/bioagent/agent/config.py")
    if not live.is_file():
        return ""
    try:
        for line in live.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("MINIMAX_API_KEY"):
                _, _, rhs = line.partition("=")
                value = ast.literal_eval(rhs.strip())
                return value if isinstance(value, str) else ""
    except Exception:
        return ""
    return ""


MINIMAX_API_KEY = _minimax_key()
USE_LOCAL_CONVERSATION = os.getenv("BIOAGENT_LOCAL_CONVERSATION", "0") in {"1", "true", "TRUE"} or not MINIMAX_API_KEY
CLAUDE_STATE_DIR = PROJECT_ROOT / ".claude" / "sessions"
CLAUDE_RUNTIME_CONFIG_DIR = Path(
    os.getenv(
        "CLAUDE_RUNTIME_CONFIG_DIR", f"/tmp/bioagent-claude-runtime-{os.getuid()}"
    )
)
SESSION_IDLE_TIMEOUT_SECONDS = 30 * 60
CONVERSATION_TIMEOUT_SECONDS = float(
    os.getenv("BIOAGENT_CONVERSATION_TIMEOUT_SECONDS", "180")
)
ANALYSIS_RUN_ROOT = Path(os.getenv("BIOAGENT_RUN_ROOT", "/data/runs")).resolve()

ANALYSIS_TESTDATA_ROOT = Path(
    os.getenv(
        "BIOAGENT_TESTDATA_ROOT",
        "/data/user/guojindan/Projects/XvirMind/testdata",
    )
).resolve()


def allowed_input_roots() -> tuple[Path, ...]:
    roots = [ANALYSIS_RUN_ROOT]
    if ANALYSIS_TESTDATA_ROOT not in roots:
        roots.append(ANALYSIS_TESTDATA_ROOT)
    return tuple(roots)

SYSTEM_PROMPT = """You are BioAgent, a bioinformatics assistant specialized in virus metagenomics.

The dataset, analysis goals, viral type, routing mode, executable stages, resource estimate,
and run admission are owned by structured UI controls and a deterministic planner.

- Explain the current dataset or plan in clear language and answer scientific questions.
- If the user asks to change goals or viral type, propose only that controlled patch.
- The only supported goals are: contig_filter (quality control plus assembly), virus_summary
  (virus identification), host_summary (host identification), microbe_summary (microbial
  profile), virus_rpm (virus abundance), and annotation_delivery (virus annotation).
- Do not map a narrower request to a broader goal. In particular, "quality control only" is not
  contig_filter because contig_filter also performs assembly; explain that only the six fixed goals
  are currently supported and do not propose a patch for unsupported granularity.
- Routing mode can only be changed with the top Smart/Standard/Emergency control.
- Never output an analysis_plan control block, paths, commands, or runner instructions.
- Never claim that you changed a plan, started a run, or confirmed execution.
- Do not create files, run workflows, or mutate analysis state.

Return exactly one action using the runtime JSON Schema. Use respond for an answer, clarify for
one necessary question, or propose_patch for a requested goals/viral_type change. respond and
clarify must omit proposed_patch. propose_patch must include proposed_patch, containing only goals
and viral_type. Put the complete user-visible answer in message and use an empty citations list
until a retrieval result is supplied. If structured output is unavailable, use the exact
conversation_action fenced JSON fallback requested in the user prompt.

- 定种走 wangdaxi virus_taxonomy（kb.jsonl / classify_sequence）；RNA 病毒注释增量走 wangdaxi RVA。
- 用户问 testdata、定种、RVA/注释时，引导其使用 testdata/scenarios 与右侧「知识/专项」。

- W1=contig_filter, W2=virus_summary, W3=host_summary, W4=microbe_summary, W5=virus_rpm, W6=annotation_delivery。用户说「只要 W1 和 W4」时必须 propose_patch 这两个 goals。
- 用户要流程图时，在 message 里给 mermaid flowchart LR，节点用上述中文目标名。
When the user asks about ICTV virus taxonomy, demarcation criteria, classification rules, marker genes,
genome type, or a specific virus family, use ictv_family_info from the taxonagent MCP server.
"""

TAXONAGENT_MCP_URL = os.getenv("TAXONAGENT_MCP_URL", "http://172.24.202.246:8765/mcp")
