"""Run per-workflow extract_results.py; tolerate missing stages and failed parsers."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .config import DEFAULT_WORKFLOWS_ROOT, DEFAULT_XVIRBENCH_ROOT, WORKFLOWS, WorkflowSpec
from .discover import Discovery


def _load_module(script: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {script}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_tables(tables: dict[str, list], out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for key, rows in tables.items():
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        path = out_dir / f"{key}.tsv"
        df.to_csv(path, sep="\t", index=False)
        counts[key] = int(len(df))
    return counts


def extract_one(
    spec: WorkflowSpec,
    result_dir: Path,
    out_dir: Path,
    workflows_root: Path,
    sample_list: Optional[Path] = None,
) -> dict[str, Any]:
    script = workflows_root / spec.extractor_rel
    rec: dict[str, Any] = {
        "workflow": spec.key,
        "short": spec.short,
        "result_dir": str(result_dir),
        "extractor": str(script),
        "ok": False,
        "error": None,
        "n_tables": 0,
        "table_rows": {},
    }
    if not script.is_file():
        rec["error"] = f"extractor missing: {script}"
        return rec
    try:
        os.environ.setdefault("XVIRBENCH_ROOT", str(DEFAULT_XVIRBENCH_ROOT))
        os.environ.setdefault("WORKFLOWS_ROOT", str(workflows_root))
        xvir_scripts = DEFAULT_XVIRBENCH_ROOT / "scripts"
        if str(xvir_scripts) not in sys.path:
            sys.path.insert(0, str(xvir_scripts))
        mod = _load_module(script, f"extract_{spec.short}")
        if spec.key == "workflow1_upstream":
            payload = mod.extract_all(Path(result_dir), Path(sample_list) if sample_list else None)
        else:
            payload = mod.extract_all(Path(result_dir))
        tables = payload.get("tables") or {}
        wf_out = out_dir / spec.short
        rows = _write_tables(tables, wf_out)
        (wf_out / f"{spec.key}_extracted.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        )
        rec.update(
            ok=True,
            n_tables=len(rows),
            table_rows=rows,
            batch_summary=payload.get("batch_summary") or payload.get("counts") or {},
            out_dir=str(wf_out),
        )
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc()[-4000:]
    return rec


def _fallback_from_xlsx(run_dir: Path, out_dir: Path) -> list[dict[str, Any]]:
    """Best-effort: reuse an existing benchmark xlsx if live extract failed."""
    hits = list((run_dir / "reports").glob("*benchmark_metrics.xlsx")) if (run_dir / "reports").is_dir() else []
    if not hits:
        return []
    xlsx = hits[0]
    recs = []
    sheet_map = {
        "W1": {
            "W1_run质控": "run_qc",
            "W1_sample组装": "samples",
        },
        "W2": {
            "W2_病毒contigs": "contigs",
            "W2_cluster_members": "cluster_members",
            "W2_cluster汇总": "cluster_summary",
            "W2_sample聚类": "sample_cluster",
            "W2_HMM迭代": "hmm_iterations",
        },
        "W3": {
            "W3_宿主_sample": "host_sample",
            "W3_宿主_top物种": "host_top_species",
        },
        "W4": {
            "W4_kraken_bracken": "sample_qc",
            "W4_bracken_top15": "bracken_top15_species",
            "W4_物种汇总表": "combined_species",
        },
        "W5": {
            "W5_sample定量": "sample_summary",
            "W5_top20_RPM": "top20_rpm",
        },
    }
    xl = pd.ExcelFile(xlsx)
    for short, mapping in sheet_map.items():
        tables = {}
        for sheet, key in mapping.items():
            if sheet in xl.sheet_names:
                df = pd.read_excel(xl, sheet)
                tables[key] = df.to_dict(orient="records")
        if not tables:
            continue
        wf_out = out_dir / short
        counts = _write_tables(tables, wf_out)
        recs.append(
            {
                "workflow": next(w.key for w in WORKFLOWS if w.short == short),
                "short": short,
                "ok": True,
                "error": None,
                "n_tables": len(counts),
                "table_rows": counts,
                "fallback": str(xlsx),
                "out_dir": str(wf_out),
            }
        )
    return recs


def extract_all_present(
    disc: Discovery,
    out_dir: Path,
    workflows_root: Path = DEFAULT_WORKFLOWS_ROOT,
) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_list = None
    for cand in (
        disc.run_dir / "lists" / "w1_samples.txt",
        disc.run_dir / "cohorts" / "sampleinfo.txt",
    ):
        if cand.is_file():
            sample_list = cand
            break

    records = []
    for wp in disc.workflows:
        if not wp.present:
            records.append(
                {
                    "workflow": wp.spec.key,
                    "short": wp.spec.short,
                    "ok": False,
                    "skipped": True,
                    "error": wp.reason,
                    "n_tables": 0,
                    "table_rows": {},
                }
            )
            continue
        rec = extract_one(wp.spec, wp.path, out_dir, workflows_root, sample_list=sample_list)
        records.append(rec)

    failed_present = [r for r in records if not r.get("ok") and not r.get("skipped")]
    if failed_present:
        fb = _fallback_from_xlsx(disc.run_dir, out_dir)
        by_short = {r["short"]: r for r in fb}
        merged = []
        for r in records:
            if (not r.get("ok")) and r["short"] in by_short:
                alt = dict(by_short[r["short"]])
                alt["error_original"] = r.get("error")
                merged.append(alt)
            else:
                merged.append(r)
        records = merged

    log = pd.DataFrame(
        [
            {
                "workflow": r.get("workflow"),
                "short": r.get("short"),
                "ok": bool(r.get("ok")),
                "skipped": bool(r.get("skipped")),
                "n_tables": r.get("n_tables", 0),
                "table_rows_json": json.dumps(r.get("table_rows") or {}, ensure_ascii=False),
                "error": r.get("error") or r.get("error_original"),
                "fallback": r.get("fallback"),
                "out_dir": r.get("out_dir"),
            }
            for r in records
        ]
    )
    log.to_csv(out_dir / "extract_log.tsv", sep="\t", index=False)
    (out_dir / "extract_log.json").write_text(json.dumps(records, ensure_ascii=False, indent=2, default=str))
    return log
