from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from xvirmind.config import load
from xvirmind.mcp.protocol import mcp_app

_CFG = load()
ROOT = Path(_CFG["paths"]["taxonomy_root"])
KB = ROOT / "data" / "kb" / "kb.jsonl"
FAMILIES = ROOT / "config" / "families.yaml"
CLASSIFY = ROOT / "scripts" / "classify" / "classify_sequence.py"
RUN_ROOT = Path(_CFG["paths"]["run_root"])
ALLOW = bool(_CFG["policy"]["allow_compute"])
MAX_FASTA = int(_CFG["policy"].get("max_fasta_bytes", 5_000_000))

_INDEX: list[dict[str, Any]] | None = None


def _load_kb() -> list[dict[str, Any]]:
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    rows: list[dict[str, Any]] = []
    if KB.exists():
        with KB.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                taxon = rec.get("taxon") or {}
                rows.append(
                    {
                        "level": taxon.get("level"),
                        "name": taxon.get("name"),
                        "family": taxon.get("family"),
                        "ictv_id": taxon.get("ictv_id"),
                        "report_status": taxon.get("report_status"),
                        "demarcation_rules": rec.get("demarcation_rules") or [],
                        "markers": rec.get("markers") or [],
                        "genome": rec.get("genome") or {},
                        "biology": rec.get("biology") or {},
                        "provenance": rec.get("provenance"),
                    }
                )
    _INDEX = rows
    return rows


def _families() -> list[str]:
    if not FAMILIES.exists():
        return sorted({r["family"] for r in _load_kb() if r.get("family")})
    names = re.findall(r"family:\s*(\S+)", FAMILIES.read_text(encoding="utf-8"))
    return names


def capability(_: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability_id": "virus_taxonomy.classify",
        "version": "kb+classify_sequence",
        "source": str(ROOT),
        "kb": str(KB),
        "kb_exists": KB.exists(),
        "kb_records": len(_load_kb()) if KB.exists() else 0,
        "families": _families(),
        "msl": "MSL40",
        "classify_script": str(CLASSIFY),
        "classify_script_exists": CLASSIFY.exists(),
        "query_tools": ["taxonomy_search_kb", "taxonomy_family_info"],
        "compute_tools": ["taxonomy_classify"],
        "compute_default": "dry-run unless confirm=true and XVIRMIND_ALLOW_COMPUTE=1",
    }


def search_kb(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    limit = max(1, min(int(args.get("limit") or 8), 30))
    if not query:
        raise ValueError("query is required")
    q = query.lower()
    hits = []
    for rec in _load_kb():
        name = (rec.get("name") or "") + " " + (rec.get("family") or "")
        if q not in name.lower():
            continue
        hits.append(
            {
                "level": rec.get("level"),
                "name": rec.get("name"),
                "family": rec.get("family"),
                "report_status": rec.get("report_status"),
                "rule_count": len(rec.get("demarcation_rules") or []),
                "marker_count": len(rec.get("markers") or []),
                "hosts": (rec.get("biology") or {}).get("host_range"),
            }
        )
        if len(hits) >= limit:
            break
    return {
        "query": query,
        "knowledge_release": "virus_taxonomy/data/kb/kb.jsonl",
        "hit_count": len(hits),
        "hits": hits,
        "status": "ok" if hits else "KNOWLEDGE_INSUFFICIENT",
    }


def family_info(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("family_name") or args.get("name") or "").strip()
    if not name:
        raise ValueError("family_name is required")
    target = name.lower().replace("idae", "idae")
    matches = [r for r in _load_kb() if (r.get("name") or "").lower() == target or (r.get("family") or "").lower() == target]
    family_row = next((r for r in matches if r.get("level") == "family"), None)
    genera = [r for r in matches if r.get("level") == "genus"]
    if not family_row and not genera:
        return {"family_name": name, "status": "KNOWLEDGE_INSUFFICIENT", "citation": None}
    rules = (family_row or {}).get("demarcation_rules") or []
    compact_rules = []
    for rule in rules[:6]:
        compact_rules.append(
            {
                "level": rule.get("level"),
                "rule_type": rule.get("rule_type"),
                "confidence": rule.get("confidence"),
                "requires_expert_review": rule.get("requires_expert_review"),
                "quantitative": [
                    {k: q.get(k) for k in ("metric", "operator", "value", "gene_target", "method")}
                    for q in (rule.get("quantitative_rules") or [])[:4]
                ],
                "ictv_quote": ((rule.get("quantitative_rules") or [{}])[0].get("ictv_quote") if rule.get("quantitative_rules") else None),
            }
        )
    return {
        "family_name": (family_row or {}).get("name") or name,
        "status": "ok",
        "knowledge_release": "virus_taxonomy/data/kb/kb.jsonl",
        "genome": (family_row or {}).get("genome"),
        "biology": (family_row or {}).get("biology"),
        "rules": compact_rules,
        "genus_count": len(genera),
        "genera": [g.get("name") for g in genera[:40]],
        "source_locator": f"kb.jsonl taxon.name={name}",
    }


def _inspect_fasta(path: str) -> dict[str, Any]:
    fasta = Path(path).expanduser()
    if not fasta.is_file():
        raise FileNotFoundError(f"genome not found: {fasta}")
    size = fasta.stat().st_size
    if size > MAX_FASTA:
        raise ValueError(f"fasta too large: {size} > {MAX_FASTA}")
    text = fasta.read_text(encoding="utf-8", errors="replace")[:200_000]
    if not text.lstrip().startswith(">"):
        raise ValueError("file does not look like FASTA")
    n = text.count(">")
    first = text.splitlines()[0][:120]
    return {"path": str(fasta.resolve()), "bytes": size, "n_records": n, "first_header": first}


def classify(args: dict[str, Any]) -> dict[str, Any]:
    genome = str(args.get("genome") or "").strip()
    family = (args.get("family") or None)
    confirm = bool(args.get("confirm"))
    inspect = _inspect_fasta(genome)
    cmd = ["python3", str(CLASSIFY), "--genome", inspect["path"], "--out", "<run>/classify.json"]
    if family:
        cmd.extend(["--family", str(family)])
    task = {
        "capability_id": "virus_taxonomy.classify",
        "mode": "dry-run",
        "confirm": confirm,
        "allow_compute": ALLOW,
        "command": cmd,
        "input": inspect,
        "family": family,
        "note": "Host must confirm. Full HMM/tree classify is not started unless confirm and allow_compute are both true.",
    }
    if not confirm:
        task["status"] = "AWAITING_CONFIRM"
        return task
    if not ALLOW:
        task["status"] = "BLOCKED_LOCAL_POLICY"
        task["note"] = "confirm=true received, but XVIRMIND_ALLOW_COMPUTE=0. Task recorded as dry-run only."
        return task
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    out = RUN_ROOT / "taxonomy" / "last_classify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    import subprocess

    real_cmd = ["python3", str(CLASSIFY), "--genome", inspect["path"], "--out", str(out)]
    if family:
        real_cmd.extend(["--family", str(family)])
    try:
        proc = subprocess.run(real_cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=int(_CFG["policy"]["compute_timeout_sec"]))
    except subprocess.TimeoutExpired:
        return {**task, "status": "TIMEOUT", "mode": "compute", "command": real_cmd}
    task.update({"mode": "compute", "status": "ok" if proc.returncode == 0 else "FAILED", "returncode": proc.returncode, "stdout_tail": (proc.stdout or "")[-1500:], "stderr_tail": (proc.stderr or "")[-1500:], "output": str(out)})
    return task


TOOLS = {
    "taxonomy_capability": {
        "description": "Describe the local ICTV taxonomy plugin: kb path, families, classify script, compute policy.",
        "schema": {"type": "object", "properties": {}},
        "handler": capability,
    },
    "taxonomy_search_kb": {
        "description": "Offline search of virus_taxonomy kb.jsonl by taxon or family name. Returns citations to local KB.",
        "schema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
        "handler": search_kb,
    },
    "taxonomy_family_info": {
        "description": "Return ICTV demarcation rules, markers and genera for one family from the local knowledge release.",
        "schema": {"type": "object", "properties": {"family_name": {"type": "string"}}, "required": ["family_name"]},
        "handler": family_info,
    },
    "taxonomy_classify": {
        "description": "Specialist classify tool. Default is dry-run (validate FASTA + show command). Real classify_sequence.py runs only when confirm=true and allow_compute is on.",
        "schema": {
            "type": "object",
            "properties": {
                "genome": {"type": "string", "description": "Absolute FASTA path"},
                "family": {"type": "string"},
                "confirm": {"type": "boolean"},
            },
            "required": ["genome"],
        },
        "handler": classify,
    },
}

app = mcp_app("xvirmind-taxonomy-mcp", "1.1.0", TOOLS)
