#!/usr/bin/env python3
"""
批次分组比较分析：读 cohorts/ + harmonized/，输出 tables/ figures/ report.html。

用法:
  python run_analysis.py --batch-id vazyme_fragment_test --all
  python run_analysis.py --batch-id vazyme_fragment_test -w workflow7
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
XVIRBENCH_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from analyze_workflows import CLI_ALIASES, run_analyses
from build_html_report import build_html_report
from cohort import cohort_overview, load_sampleinfo


def main() -> None:
    ap = argparse.ArgumentParser(description="批次分组比较分析")
    ap.add_argument("--batch-id", default="vazyme_fragment_test")
    ap.add_argument("-w", "--workflow", action="append", help="workflow1–7 / w1–w7")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-html", action="store_true", help="仅输出 TSV/图，不生成 HTML")
    args = ap.parse_args()

    batch_dir = XVIRBENCH_ROOT / "batches" / args.batch_id
    if not batch_dir.is_dir():
        ap.error(f"批次不存在: {batch_dir}")

    if args.all:
        workflows = None
    elif args.workflow:
        workflows = []
        for w in args.workflow:
            key = w.strip().lower()
            if key not in CLI_ALIASES:
                ap.error(f"未知 workflow: {w}")
            workflows.append(CLI_ALIASES[key])
    else:
        workflows = None

    out_dir = batch_dir / "analysis"
    tab_dir = out_dir / "tables"
    tab_dir.mkdir(parents=True, exist_ok=True)

    cohort = load_sampleinfo(batch_dir / "cohorts")
    cohort_overview(cohort).to_csv(tab_dir / "cohort_overview.tsv", sep="\t", index=False)

    merged, results = run_analyses(batch_dir, workflows)
    print(f"分析输出 → {out_dir}")
    print(f"  样本宽表: {len(merged)} rows × {len(merged.columns)} cols")
    for wf, res in results.items():
        print(f"  {wf}: {len(res.metrics)} metrics, {len(res.figures)} figures")

    if not args.no_html:
        html_path = build_html_report(batch_dir, args.batch_id, results)
        print(f"  HTML: {html_path}")

    if not results:
        sys.exit(1)


if __name__ == "__main__":
    main()
