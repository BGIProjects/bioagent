#!/usr/bin/env python3
"""
W1 上游数据质量评估报告（按宿主/批次）。

用法:
  python3 scripts/analysis/run_w1_qc_report.py --batch-id vazyme_fragment_test --host rat
  python3 scripts/analysis/run_w1_qc_report.py --batch-id vazyme_fragment_test --host all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from w1_qc.compute import run_w1_qc_pipeline


def main() -> None:
    ap = argparse.ArgumentParser(description="W1 上游 QC 报告")
    ap.add_argument("--batch-id", default="vazyme_fragment_test")
    ap.add_argument("--host", default="rat", help="rat / tick / mosquito / all")
    args = ap.parse_args()
    host = None if args.host == "all" else args.host
    result = run_w1_qc_pipeline(args.batch_id, host=host)
    print(f"W1 QC 完成: {result.out_dir}")
    print(f"  样本数: {result.batch_summary['n_samples']}")
    print(f"  批次通过: {result.batch_summary['batch_pass']}")
    print(f"  等级分布: {result.batch_summary['rating_counts']}")
    print("  表格:", len(result.tables))
    for k in ("report_internal.html", "report_delivery.html", "report_delivery.md"):
        p = result.out_dir / k
        if p.exists():
            print(f"  {k}: {p}")


if __name__ == "__main__":
    main()
