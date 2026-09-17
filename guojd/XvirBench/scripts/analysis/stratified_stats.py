"""多层级组间比较统计：全队列 / 排除低深度 / 分宿主。"""
from __future__ import annotations

from typing import Iterable, List

import pandas as pd

from cohort import LOW_DEPTH_READS
from stats_lib import method_summary, run_all_tests


def datasets_for_comparison(df: pd.DataFrame, low_depth_col: str = "low_depth") -> List[tuple[str, pd.DataFrame]]:
    out: List[tuple[str, pd.DataFrame]] = [("all_samples", df)]
    if low_depth_col in df.columns:
        excl = df[~df[low_depth_col].fillna(False)]
        if len(excl) >= 6:
            out.append(("exclude_low_depth", excl))
    for host in ("rat", "tick", "mosquito"):
        sub = df[df["host"] == host]
        if len(sub) >= 4 and sub["method"].nunique() >= 2:
            out.append((f"host_{host}", sub))
    return out


def run_multi_level_tests(
    df: pd.DataFrame,
    metrics: Iterable[str],
    low_depth_col: str = "low_depth",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回 (tests_long, summary_by_dataset)。"""
    tests_parts = []
    summ_parts = []
    for label, sub in datasets_for_comparison(df, low_depth_col):
        tests_parts.append(run_all_tests(sub, metrics, label))
        sm = method_summary(sub, metrics)
        if not sm.empty:
            sm["dataset"] = label
            summ_parts.append(sm)
    tests = pd.concat(tests_parts, ignore_index=True) if tests_parts else pd.DataFrame()
    summary = pd.concat(summ_parts, ignore_index=True) if summ_parts else pd.DataFrame()
    return tests, summary
