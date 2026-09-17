"""Overall descriptive stats and grouped nonparametric tests."""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .config import METRIC_LABELS, METHOD_LABEL, METHOD_ORDER


def _bh(pvals: list[float]) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    out = np.full(n, np.nan)
    mask = np.isfinite(p)
    if mask.sum() == 0:
        return out
    pv = p[mask]
    m = len(pv)
    order = np.argsort(pv)
    ranked = pv[order]
    adj = ranked * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    tmp = np.empty(m)
    tmp[order] = adj
    out[mask] = tmp
    return out


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def describe_overall(df: pd.DataFrame, metrics: Iterable[str], dataset: str = "all") -> pd.DataFrame:
    rows = []
    for m in metrics:
        if m not in df.columns:
            continue
        x = _num(df[m]).dropna()
        if x.empty:
            continue
        rows.append(
            {
                "dataset": dataset,
                "metric": m,
                "label": METRIC_LABELS.get(m, m),
                "n": int(len(x)),
                "n_missing": int(_num(df[m]).isna().sum()),
                "mean": float(x.mean()),
                "sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
                "median": float(x.median()),
                "q25": float(x.quantile(0.25)),
                "q75": float(x.quantile(0.75)),
                "min": float(x.min()),
                "max": float(x.max()),
            }
        )
    return pd.DataFrame(rows)


def describe_by_group(df: pd.DataFrame, metrics: Iterable[str], group_col: str, dataset: str) -> pd.DataFrame:
    rows = []
    if group_col not in df.columns:
        return pd.DataFrame()
    for g, sub in df.groupby(group_col, dropna=True):
        part = describe_overall(sub, metrics, dataset=f"{dataset}|{group_col}={g}")
        if not part.empty:
            part["group_col"] = group_col
            part["group"] = str(g)
            part["group_label"] = METHOD_LABEL.get(str(g), str(g))
            part["n_group"] = len(sub)
            rows.append(part)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _epsilon_sq(h: float, k: int, n: int) -> float:
    if n <= k:
        return np.nan
    return max(0.0, (h - k + 1) / (n - k))


def _rank_biserial(x: np.ndarray, y: np.ndarray, u: float) -> float:
    nx, ny = len(x), len(y)
    if nx * ny == 0:
        return np.nan
    return 1.0 - (2.0 * u) / (nx * ny)


def group_tests(df: pd.DataFrame, metrics: Iterable[str], group_col: str, dataset: str) -> pd.DataFrame:
    if group_col not in df.columns:
        return pd.DataFrame()
    rows = []
    levels = [str(x) for x in df[group_col].dropna().unique()]
    if group_col == "method":
        levels = [m for m in METHOD_ORDER if m in levels] or levels
    if len(levels) < 2:
        return pd.DataFrame()

    for metric in metrics:
        if metric not in df.columns:
            continue
        groups = {
            g: _num(df.loc[df[group_col].astype(str) == g, metric]).dropna().to_numpy()
            for g in levels
        }
        present = [g for g, arr in groups.items() if len(arr) >= 2]
        if len(present) < 2:
            continue
        arrays = [groups[g] for g in present]
        n = int(sum(len(a) for a in arrays))
        try:
            h, p = stats.kruskal(*arrays)
        except ValueError:
            h, p = np.nan, np.nan
        rows.append(
            {
                "dataset": dataset,
                "group_col": group_col,
                "metric": metric,
                "label": METRIC_LABELS.get(metric, metric),
                "test": "kruskal_wallis",
                "comparison": "all_levels",
                "n": n,
                "k": len(present),
                "statistic": h,
                "p_value": p,
                "p_adj_bh": p,
                "effect": _epsilon_sq(h, len(present), n) if np.isfinite(h) else np.nan,
                "effect_name": "epsilon_squared",
            }
        )
        pair_ps = []
        pair_buf = []
        for a, b in itertools.combinations(present, 2):
            x, y = groups[a], groups[b]
            try:
                u, p_u = stats.mannwhitneyu(x, y, alternative="two-sided")
            except ValueError:
                u, p_u = np.nan, np.nan
            pair_buf.append((a, b, u, p_u, len(x), len(y)))
            pair_ps.append(p_u)
        adj = _bh(pair_ps) if pair_ps else []
        for i, (a, b, u, p_u, nx, ny) in enumerate(pair_buf):
            rows.append(
                {
                    "dataset": dataset,
                    "group_col": group_col,
                    "metric": metric,
                    "label": METRIC_LABELS.get(metric, metric),
                    "test": "mannwhitney_bh",
                    "comparison": f"{METHOD_LABEL.get(b, b)} vs {METHOD_LABEL.get(a, a)}",
                    "n": nx + ny,
                    "k": 2,
                    "statistic": u,
                    "p_value": p_u,
                    "p_adj_bh": adj[i] if len(adj) else np.nan,
                    "effect": _rank_biserial(groups[a], groups[b], u) if np.isfinite(u) else np.nan,
                    "effect_name": "rank_biserial",
                }
            )
    return pd.DataFrame(rows)


CORE_METRICS = [
    "merge_r1_reads",
    "read_retention_fastp_median",
    "q30_after_fastp_median",
    "duplication_rate_median",
    "rrna_retention_r1_median",
    "contigs_ge1kb_n",
    "contigs_avg_len",
    "n_putative_viral_contigs",
    "n_high_quality",
    "n_clusters",
    "n_species_inferred",
    "kraken_unclassified_frac",
    "bracken_species_taxa",
    "n_viral_contigs_with_reads",
    "max_rpm",
    "median_rpm",
    "mapping_rate_pct",
]


def run_stats(master: pd.DataFrame, group_cols: list[str], out_dir: Path) -> dict[str, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = [m for m in CORE_METRICS if m in master.columns]
    # also include any extra numeric sample metrics
    extra = [
        c
        for c in master.columns
        if c not in metrics
        and c not in {"sample_id", "sn", "host", "method", "group", "raw_id", "low_depth", "in_core_cohort"}
        and pd.api.types.is_numeric_dtype(master[c])
    ]
    metrics = list(dict.fromkeys(metrics + extra))

    frames = {}
    # all rows with at least a sample id
    overall = describe_overall(master, metrics, "all_samples")
    frames["overall_all"] = overall

    core = master[master["in_core_cohort"] == True].copy() if "in_core_cohort" in master.columns else master
    frames["overall_core"] = describe_overall(core, metrics, "core_cohort")

    excl = core[~core["low_depth"].fillna(False)] if "low_depth" in core.columns else core
    frames["overall_core_excl_lowdepth"] = describe_overall(excl, metrics, "core_excl_lowdepth")

    grouped = []
    tests = []
    for gcol in group_cols:
        grouped.append(describe_by_group(core, metrics, gcol, "core_cohort"))
        tests.append(group_tests(core, metrics, gcol, "core_cohort"))
        tests.append(group_tests(excl, metrics, gcol, "core_excl_lowdepth"))
        grouped.append(describe_by_group(excl, metrics, gcol, "core_excl_lowdepth"))

    frames["by_group"] = pd.concat([x for x in grouped if not x.empty], ignore_index=True) if grouped else pd.DataFrame()
    frames["tests"] = pd.concat([x for x in tests if not x.empty], ignore_index=True) if tests else pd.DataFrame()

    for name, df in frames.items():
        df.to_csv(out_dir / f"{name}.tsv", sep="\t", index=False)
    return frames
