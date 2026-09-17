"""组间比较统计工具。"""
from __future__ import annotations

import itertools
from typing import Iterable, List

import numpy as np
import pandas as pd
from scipy import stats

from cohort import METHOD_ORDER


def method_summary(
    df: pd.DataFrame,
    metrics: Iterable[str],
    group_col: str = "method",
) -> pd.DataFrame:
    rows = []
    for meth in METHOD_ORDER:
        sub = df[df[group_col] == meth]
        if sub.empty:
            continue
        row = {"method": meth, "n": len(sub)}
        for m in metrics:
            s = pd.to_numeric(sub[m], errors="coerce").dropna()
            row[f"{m}_mean"] = s.mean()
            row[f"{m}_sd"] = s.std(ddof=1) if len(s) > 1 else np.nan
            row[f"{m}_median"] = s.median()
        rows.append(row)
    return pd.DataFrame(rows)


def pairwise_tests(df: pd.DataFrame, metric: str, group_col: str = "method") -> List[dict]:
    out = []
    groups = {
        m: pd.to_numeric(df.loc[df[group_col] == m, metric], errors="coerce").dropna().values
        for m in METHOD_ORDER
    }
    present = [m for m in METHOD_ORDER if len(groups[m]) > 0]
    if len(present) < 2:
        return out

    arrays = [groups[m] for m in present]
    try:
        kw_stat, kw_p = stats.kruskal(*arrays)
    except ValueError:
        kw_stat, kw_p = np.nan, np.nan
    out.append(
        {
            "metric": metric,
            "test": "kruskal_wallis",
            "comparison": "all_methods",
            "statistic": kw_stat,
            "p_value": kw_p,
        }
    )

    pairs = list(itertools.combinations(present, 2))
    raw_ps = []
    pair_rows = []
    for a, b in pairs:
        x, y = groups[a], groups[b]
        if len(x) < 1 or len(y) < 1:
            continue
        try:
            stat, p = stats.mannwhitneyu(x, y, alternative="two-sided")
        except ValueError:
            stat, p = np.nan, np.nan
        pair_rows.append((a, b, stat, p))
        raw_ps.append(p)

    for i, (a, b, stat, _) in enumerate(pair_rows):
        adj_p = min(raw_ps[i] * len(raw_ps), 1.0) if raw_ps else np.nan
        out.append(
            {
                "metric": metric,
                "test": "mannwhitney_pairwise_BH",
                "comparison": f"{b}_vs_{a}",
                "statistic": stat,
                "p_value": adj_p,
            }
        )
    return out


def run_all_tests(
    df: pd.DataFrame,
    metrics: Iterable[str],
    dataset: str,
    group_col: str = "method",
) -> pd.DataFrame:
    tests = []
    for m in metrics:
        if m not in df.columns or pd.to_numeric(df[m], errors="coerce").notna().sum() < 3:
            continue
        tests.extend(pairwise_tests(df, m, group_col))
    tdf = pd.DataFrame(tests)
    if not tdf.empty:
        tdf["dataset"] = dataset
    return tdf
