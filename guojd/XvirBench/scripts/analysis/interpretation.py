"""从统计结果自动生成简要解读。"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from cohort import METHOD_LABEL, METHOD_ORDER


def _fmt_p(p: float) -> str:
    if pd.isna(p):
        return "NA"
    if p < 0.001:
        return f"{p:.2e}"
    return f"{p:.4g}"


def interpret_metric_kw(
    tests_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    metric: str,
    label: str,
    dataset: str = "all_samples",
) -> str:
    kw = tests_df[
        (tests_df["dataset"] == dataset)
        & (tests_df["metric"] == metric)
        & (tests_df["test"] == "kruskal_wallis")
    ]
    if kw.empty:
        return ""
    p = kw.iloc[0]["p_value"]
    sm = summary_df[(summary_df["dataset"] == dataset) if "dataset" in summary_df.columns else True]
    if "dataset" in summary_df.columns:
        sm = sm[sm["dataset"] == dataset]
    ranks = []
    for meth in METHOD_ORDER:
        row = sm[sm["method"] == meth]
        if not row.empty and pd.notna(row.iloc[0].get(f"{metric}_mean")):
            ranks.append((meth, row.iloc[0][f"{metric}_mean"]))
    ranks.sort(key=lambda x: x[1], reverse=True)
    rank_txt = " > ".join(f"{METHOD_LABEL[m]}（{v:.4g}）" for m, v in ranks[:3]) if ranks else ""
    sig = "差异显著" if pd.notna(p) and p < 0.05 else "差异未达显著"
    pairs = tests_df[
        (tests_df["dataset"] == dataset)
        & (tests_df["metric"] == metric)
        & (tests_df["test"] == "mannwhitney_pairwise_BH")
        & (tests_df["p_value"] < 0.05)
    ]
    pair_txt = ""
    if not pairs.empty:
        pair_txt = "；显著两两：" + "、".join(
            f"{r['comparison']} (p={_fmt_p(r['p_value'])})" for _, r in pairs.iterrows()
        )
    return f"**{label}**：{rank_txt}。Kruskal-Wallis p={_fmt_p(p)}（{sig}）{pair_txt}。"


def build_interpretations(
    tests_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    metric_labels: Dict[str, str],
    datasets: List[str] | None = None,
) -> List[str]:
    datasets = datasets or ["all_samples", "host_rat", "host_tick", "host_mosquito"]
    lines: List[str] = []
    for ds in datasets:
        if "dataset" in summary_df.columns and ds not in summary_df["dataset"].unique():
            continue
        prefix = {
            "all_samples": "全队列",
            "exclude_low_depth": "排除低深度",
            "host_rat": "大鼠分层",
            "host_tick": "蜱分层",
            "host_mosquito": "蚊虫分层",
        }.get(ds, ds)
        sub_lines = []
        for m, lbl in metric_labels.items():
            txt = interpret_metric_kw(tests_df, summary_df, m, lbl, ds)
            if txt:
                sub_lines.append(txt)
        if sub_lines:
            lines.append(f"### {prefix}")
            lines.extend(sub_lines)
    return lines
