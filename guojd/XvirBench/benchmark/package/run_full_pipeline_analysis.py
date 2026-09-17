#!/usr/bin/env python3
"""Post-workflow analysis: extract → stats → R figures → HTML report.

Example:
  python run_full_pipeline_analysis.py \\
    --run-dir /data/user/guojindan/Projects/Workflows/benchmark/test/runs/pxy_V350399508 \\
    --out-dir /data/user/guojindan/Projects/XvirMind/XvirBench/benchmark/runs/pxy_V350399508
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from xvir_full.config import DEFAULT_WORKFLOWS_ROOT, default_rscript
from xvir_full.discover import discover
from xvir_full.extract import extract_all_present
from xvir_full.narrative import build_sections
from xvir_full.plots_r import run_r_figures, stage_tables
from xvir_full.report import build_html, build_pdf
from xvir_full.stats import run_stats
from xvir_full.tables import coverage_matrix, master_sample_table


def main() -> None:
    ap = argparse.ArgumentParser(description="W1–W7 工作流完成后分析")
    ap.add_argument("--run-dir", required=True, help="含 workflow1_upstream/ 等子目录的运行根")
    ap.add_argument("--out-dir", required=True, help="分析输出目录")
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--workflows-root", default=str(DEFAULT_WORKFLOWS_ROOT))
    ap.add_argument("--rscript", default=None)
    ap.add_argument("--skip-extract", action="store_true", help="复用 out-dir/extracted")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    extract_dir = out_dir / "extracted"
    table_dir = out_dir / "tables"
    fig_dir = out_dir / "figures"
    r_dir = out_dir / "r"

    disc = discover(run_dir, args.batch_id)
    (out_dir / "discovery.json").write_text(
        json.dumps(
            {
                "batch_id": disc.batch_id,
                "run_dir": str(disc.run_dir),
                "group_cols": disc.cohort.group_cols,
                "grouping_notes": disc.cohort.grouping_notes,
                "n_samples": int(len(disc.cohort.samples)),
                "workflows": [
                    {
                        "key": w.spec.key,
                        "short": w.spec.short,
                        "present": w.present,
                        "path": str(w.path) if w.path else None,
                        "reason": w.reason,
                    }
                    for w in disc.workflows
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    disc.cohort.samples.to_csv(out_dir / "cohort_samples.tsv", sep="\t", index=False)

    if args.skip_extract and extract_dir.is_dir():
        import pandas as pd

        log_path = extract_dir / "extract_log.tsv"
        extract_log = pd.read_csv(log_path, sep="\t") if log_path.is_file() else pd.DataFrame()
    else:
        extract_log = extract_all_present(disc, extract_dir, Path(args.workflows_root))

    coverage = coverage_matrix(extract_dir, disc)
    master = master_sample_table(extract_dir, disc.cohort)
    coverage.to_csv(table_dir / "coverage.tsv", sep="\t", index=False) if False else None
    table_dir.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(table_dir / "coverage.tsv", sep="\t", index=False)
    master.to_csv(table_dir / "master_sample_metrics.tsv", sep="\t", index=False)

    stats_frames = run_stats(master, disc.cohort.group_cols, table_dir / "stats")
    stage_tables(extract_dir, table_dir, master, coverage)
    rlog = run_r_figures(table_dir, fig_dir, r_dir, Path(args.rscript) if args.rscript else default_rscript())
    (out_dir / "r_run_log.json").write_text(json.dumps(rlog, ensure_ascii=False, indent=2))

    sections = build_sections(disc, master, coverage, stats_frames, table_dir=table_dir)
    r_src = ""
    r_file = r_dir / "make_figures.R"
    if r_file.is_file():
        r_src = r_file.read_text(errors="replace")
    theme = r_dir / "00_sci_theme.R"
    if theme.is_file():
        r_src = theme.read_text(errors="replace") + "\n\n# ---- make_figures.R ----\n" + r_src

    report = build_html(
        batch_id=disc.batch_id,
        out_dir=out_dir,
        fig_dir=fig_dir,
        sections=sections,
        master=master,
        coverage=coverage,
        overall=stats_frames.get("overall_core"),
        tests=stats_frames.get("tests"),
        extract_log=extract_log,
        r_source=r_src,
        grouping_notes=disc.cohort.grouping_notes,
    )
    print(f"batch {disc.batch_id}")
    print(f"  present: {', '.join(w.spec.short for w in disc.workflows if w.present) or 'none'}")
    print(f"  groups: {', '.join(disc.cohort.group_cols) or 'overall only'}")
    print(f"  samples: {len(master)}")
    try:
        pdf = build_pdf(report, out_dir / "report.pdf")
        print(f"  pdf: {pdf}")
    except Exception as exc:
        print(f"  pdf FAILED: {type(exc).__name__}: {exc}")
    print(f"  report: {report}")
    print(f"  figures: {len(list(fig_dir.glob('*.png')))} png")


if __name__ == "__main__":
    main()
