from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xvirmind.config import load
from xvirmind.mcp.protocol import mcp_app

_CFG = load()
ROOT = Path(_CFG["paths"]["annotation_root"])
SPLIT = ROOT / "data" / "benchmarks" / "vertebrate_rna" / "intrafamily_split.json"
SCRIPTS = ROOT / "scripts" / "core"
RUN_ROOT = Path(_CFG["paths"]["run_root"])
ALLOW = bool(_CFG["policy"]["allow_compute"])
MAX_FASTA = int(_CFG["policy"].get("max_fasta_bytes", 5_000_000))


def _families() -> list[str]:
    if not SPLIT.exists():
        return []
    data = json.loads(SPLIT.read_text(encoding="utf-8"))
    return sorted(data.keys()) if isinstance(data, dict) else []


def capability(_: dict[str, Any]) -> dict[str, Any]:
    families = _families()
    return {
        "capability_id": "rna_virus_annotation.annotate",
        "version": "rva-hybrid-rule",
        "source": str(ROOT),
        "readme": str(ROOT / "README.md"),
        "core_scripts": str(SCRIPTS),
        "family_count": len(families),
        "families": families,
        "outputs": ["JSON", "GTF", "evidence", "confidence"],
        "query_tools": ["annotation_list_families"],
        "compute_tools": ["annotation_annotate"],
        "increment_over_workflow6": "de novo gene structure (frameshift/cleavage/nested ORF) + structure-aware domains for weak-homology RNA viruses",
        "compute_default": "dry-run unless confirm=true and XVIRMIND_ALLOW_COMPUTE=1",
    }


def list_families(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip().lower()
    families = _families()
    if query:
        families = [f for f in families if query in f.lower()]
    return {
        "knowledge_release": "rna_virus_annotation/data/benchmarks/vertebrate_rna/intrafamily_split.json",
        "count": len(families),
        "families": families,
        "status": "ok" if families else "KNOWLEDGE_INSUFFICIENT",
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
    return {"path": str(fasta.resolve()), "bytes": size, "n_records": text.count(">"), "first_header": text.splitlines()[0][:120]}


def annotate(args: dict[str, Any]) -> dict[str, Any]:
    genome = str(args.get("genome") or "").strip()
    family = args.get("family")
    confirm = bool(args.get("confirm"))
    inspect = _inspect_fasta(genome)
    families = _families()
    family_ok = (not family) or (family in families)
    cmd = ["conda", "run", "-n", "rnavirus", "python", "scripts/core/annot_v16_cons.py", "--fasta", inspect["path"]]
    if family:
        cmd.extend(["--family", str(family)])
    task = {
        "capability_id": "rna_virus_annotation.annotate",
        "mode": "dry-run",
        "confirm": confirm,
        "allow_compute": ALLOW,
        "command": cmd,
        "input": inspect,
        "family": family,
        "family_registered": family_ok,
        "note": "RVA is a specialist plugin. Dry-run validates FASTA and family. Full decode/hybrid annotate needs confirm + allow_compute.",
    }
    if family and not family_ok:
        task["status"] = "UNKNOWN_FAMILY"
        return task
    if not confirm:
        task["status"] = "AWAITING_CONFIRM"
        return task
    if not ALLOW:
        task["status"] = "BLOCKED_LOCAL_POLICY"
        return task
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    out_dir = RUN_ROOT / "annotation" / "last"
    out_dir.mkdir(parents=True, exist_ok=True)
    import subprocess

    # Prefer documenting the real entry; do not invent a missing CLI. Record the attempt.
    script = SCRIPTS / "annot_v16_cons.py"
    if not script.exists():
        task.update({"status": "SCRIPT_MISSING", "mode": "compute", "script": str(script)})
        return task
    real = ["python3", str(script), "--help"]
    proc = subprocess.run(real, cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    task.update(
        {
            "mode": "compute-help-probe",
            "status": "PROBED",
            "returncode": proc.returncode,
            "help_tail": ((proc.stdout or proc.stderr) or "")[:1500],
            "output_dir": str(out_dir),
            "note": "Full RVA jobs are long-running GPU/CPU pipelines. This host only probes the entry script unless a dedicated runner is registered.",
        }
    )
    return task


TOOLS = {
    "annotation_capability": {
        "description": "Describe the RNA virus annotation plugin (RVA): families, outputs, increment over Workflow 6.",
        "schema": {"type": "object", "properties": {}},
        "handler": capability,
    },
    "annotation_list_families": {
        "description": "List or filter families covered by the local RVA intrafamily split.",
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        "handler": list_families,
    },
    "annotation_annotate": {
        "description": "Specialist annotation tool. Default dry-run validates FASTA. Real RVA compute requires confirm and allow_compute.",
        "schema": {
            "type": "object",
            "properties": {
                "genome": {"type": "string"},
                "family": {"type": "string"},
                "confirm": {"type": "boolean"},
            },
            "required": ["genome"],
        },
        "handler": annotate,
    },
}

app = mcp_app("xvirmind-annotation-mcp", "1.1.0", TOOLS)
