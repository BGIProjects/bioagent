#!/usr/bin/env python3
"""
W1 上游 QC 报告（可移植版）。

用法（目录模式，推荐跨平台）:
  python run_w1_qc_report.py --batch-dir /path/to/batch --host rat

batch-dir 需包含:
  cohorts/sampleinfo.tsv  或  sampleinfo.tsv
  harmonized/workflow1/qc_upstream_run.tsv + qc_upstream_sample.tsv
    或根目录下同名 TSV
  可选: workflow_results/workflow1_upstream/filter/<run>/01_fastp.json

兼容 XvirBench:
  python run_w1_qc_report.py --batch-id vazyme_fragment_test --host rat
  （需在 XvirBench 仓库根目录运行，或同时给 --batch-dir）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from w1_qc.compute import run_w1_qc_pipeline


def main() -> None:
    ap = argparse.ArgumentParser(description="W1 上游 QC 报告（portable）")
    ap.add_argument("--batch-id", default="batch", help="批次名（写入报告元数据）")
    ap.add_argument("--batch-dir", type=Path, default=None, help="批次根目录（跨平台必填）")
    ap.add_argument("--wf1-dir", type=Path, default=None, help="workflow1_upstream 结果目录（可选）")
    ap.add_argument("--out-dir", type=Path, default=None, help="输出目录（默认 batch-dir/analysis/w1_qc_<host>）")
    ap.add_argument("--host", default="rat", help="rat / tick / mosquito / all")
    args = ap.parse_args()
    host = None if args.host == "all" else args.host
    if args.batch_dir is None and not (Path.cwd() / "batches" / args.batch_id).is_dir():
        ap.error("请提供 --batch-dir，或在 XvirBench 仓库根目录使用 --batch-id")
    result = run_w1_qc_pipeline(
        args.batch_id,
        host=host,
        batch_dir=args.batch_dir,
        wf1_dir=args.wf1_dir,
        out_dir=args.out_dir,
    )
    print(f"W1 QC 完成: {result.out_dir}")
    print(f"  样本数: {result.batch_summary['n_samples']}")
    print(f"  批次通过: {result.batch_summary['batch_pass']}")
    print(f"  等级分布: {result.batch_summary['rating_counts']}")
    for k in ("report_internal.html", "report_delivery.html", "report_delivery.md"):
        p = result.out_dir / k
        if p.exists():
            print(f"  {k}: {p}")


if __name__ == "__main__":
    main()
