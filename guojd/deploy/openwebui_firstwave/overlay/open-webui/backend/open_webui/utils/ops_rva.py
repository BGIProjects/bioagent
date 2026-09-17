from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

RNA_PY = os.getenv(
    "RVA_PYTHON",
    "/home/wangdaxi/miniconda3/envs/rnavirus/bin/python3",
)
RVA_ROOT = Path(os.getenv("RVA_ROOT", "/data/user/wangdaxi/rna_virus_annotation"))
RVA_SCRIPT = RVA_ROOT / "scripts/core/rva_annotate.py"


def gpu_status() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        return {"available": proc.returncode == 0 and bool(lines), "devices": lines}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc), "devices": []}


def job_status(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    pid_path = run_dir / "rva.pid"
    log_path = run_dir / "rva.log"
    out_path = run_dir / "event_graph.json"
    gtf_path = run_dir / "event_graph.gtf"
    status = "missing"
    running = False
    pid = None
    if pid_path.exists():
        pid = int(pid_path.read_text().strip() or "0")
        try:
            os.kill(pid, 0)
            running = True
            status = "running"
        except OSError:
            running = False
            status = "completed" if out_path.exists() else "exited"
    log_tail = ""
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        log_tail = "\n".join(text.splitlines()[-40:])
    summary = None
    if out_path.exists():
        try:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            summary = _summarize(payload)
            status = "completed"
        except json.JSONDecodeError:
            summary = {"status": "INVALID_JSON"}
    return {
        "run_dir": str(run_dir),
        "pid": pid,
        "running": running,
        "status": status,
        "python": RNA_PY,
        "script": str(RVA_SCRIPT),
        "script_exists": RVA_SCRIPT.exists(),
        "output": str(out_path) if out_path.exists() else None,
        "gtf": str(gtf_path) if gtf_path.exists() else None,
        "gpu": gpu_status(),
        "summary": summary,
        "log_tail": log_tail,
    }


def _summarize(payload: Any) -> dict[str, Any]:
    records = payload if isinstance(payload, list) else [payload]
    n_cds = n_nsp = n_fs = 0
    families = set()
    mix_modes = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        families.add(str(rec.get("family") or rec.get("fam") or ""))
        cds = rec.get("cds") if isinstance(rec.get("cds"), list) else []
        nsp = rec.get("nsp_annotation") if isinstance(rec.get("nsp_annotation"), list) else []
        frameshifts = rec.get("frameshifts") if isinstance(rec.get("frameshifts"), list) else []
        n_cds += len(cds)
        n_nsp += len(nsp)
        n_fs += len(frameshifts)
        if rec.get("mix_mode"):
            mix_modes.append(str(rec.get("mix_mode")))
    families.discard("")
    return {
        "n_records": len([r for r in records if isinstance(r, dict)]),
        "n_cds": n_cds,
        "n_nsp": n_nsp,
        "n_frameshifts": n_fs,
        "n_features": n_nsp or n_cds,
        "families": sorted(families),
        "mix_mode": mix_modes[0] if mix_modes else None,
        "status": "ok",
    }
