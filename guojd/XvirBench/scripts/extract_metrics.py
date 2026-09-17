#!/usr/bin/env python3
"""
从批次 workflow 结果抽取 harmonized 表。

用法:
  # 单流程
  python extract_metrics.py --batch-id vazyme_fragment_test --workflow workflow1
  python extract_metrics.py --batch-id vazyme_fragment_test -w w4

  # 全量
  python extract_metrics.py --batch-id vazyme_fragment_test --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from extract_lib import XVIRBENCH_ROOT, extract_batch, resolve_cli_workflow


def main() -> None:
    ap = argparse.ArgumentParser(description="抽取批次 harmonized 指标")
    ap.add_argument("--batch-id", default="vazyme_fragment_test")
    ap.add_argument("-w", "--workflow", action="append", help="workflow1–7 / w1–w7，可重复")
    ap.add_argument("--all", action="store_true", help="抽取全部 workflow")
    args = ap.parse_args()

    if args.all:
        workflows = None
    elif args.workflow:
        workflows = [resolve_cli_workflow(w) for w in args.workflow]
    else:
        ap.error("请指定 --workflow 或 --all")

    counts = extract_batch(args.batch_id, workflows)
    harm = XVIRBENCH_ROOT / "batches" / args.batch_id / "harmonized"
    print(f"批次 {args.batch_id} → {harm}")
    for name, n in sorted(counts.items()):
        print(f"  {name}: {n} rows")
    if not counts:
        print("  (无输出)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
