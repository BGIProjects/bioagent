"""Generate prose summary for W1 QC reports."""
from __future__ import annotations

from typing import Any

import pandas as pd

from w1_qc.units import BASE_DIVISOR, READ_DIVISOR


def build_narrative(batch_summary: dict[str, Any], tables: dict[str, pd.DataFrame], host_cn: str) -> str:
    s0 = tables["stage_S0_raw_by_sample"]
    s1 = tables["stage_S1_fastp_loss_by_sample"]
    s2 = tables["stage_S2_rrna_by_sample"]
    s4 = tables["stage_S4_assembly_sample"]
    scores = tables["sample_qc_scores"]

    n = batch_summary.get("n_samples", len(scores))
    pass_txt = "达到批次质控要求" if batch_summary.get("batch_pass") else "未达到批次质控要求，建议复核"
    rc = batch_summary.get("rating_counts", {})
    low = batch_summary.get("low_depth_samples", [])
    concern = scores[scores["overall_rating"].isin(["需关注", "不建议下游"])]["sample_id"].tolist()

    raw_mb = pd.to_numeric(s0["raw_reads_sum"], errors="coerce") / READ_DIVISOR
    clean_mb = pd.to_numeric(s2["clean_r1_sum"], errors="coerce") / READ_DIVISOR
    raw_gb = pd.to_numeric(s0["raw_bases_sum"], errors="coerce") / BASE_DIVISOR
    ret = pd.to_numeric(s1["read_retention_fastp_agg"], errors="coerce") * 100
    q30 = pd.to_numeric(s1["mean_q30_after_fastp"], errors="coerce") * 100
    raw_q30 = pd.to_numeric(s0["raw_q30_mean"], errors="coerce") * 100
    rrna = pd.to_numeric(s2["mean_rrna_retention"], errors="coerce") * 100
    contigs = pd.to_numeric(s4["contigs_ge1kb_n"], errors="coerce")

    loss_cols = ["loss_low_quality_sum", "loss_too_short_sum", "loss_adapter_sum", "too_many_N_sum", "loss_unaccounted_sum"]
    loss_tot = s1[loss_cols].sum()
    loss_tot.index = ["低质量", "过短", "接头", "N碱基过多", "未归类"]
    top_loss = loss_tot.idxmax()

    para1 = (
        f"本批次共评估{host_cn}样本 {n} 个（{batch_summary.get('batch_id')}）。"
        f"以样本为单位汇总各 lane 后，单样本原始 reads 中位数为 {raw_mb.median():.2f} Mb"
        f"（范围 {raw_mb.min():.2f}–{raw_mb.max():.2f} Mb），"
        f"原始碱基量中位数为 {raw_gb.median():.2f} Gb（范围 {raw_gb.min():.2f}–{raw_gb.max():.2f} Gb），"
        f"原始 Q30 中位数为 {raw_q30.median():.2f}%。"
    )
    para2 = (
        f"fastp 后样本级 reads 保留率中位数为 {ret.median():.2f}%"
        f"（{ret.min():.2f}%–{ret.max():.2f}%），"
        f"fastp 后 Q30 中位数为 {q30.median():.2f}%。"
        f"剔除 reads 的主要来源为「{top_loss}」。"
    )
    para3 = (
        f"rRNA 去除后平均保留率为 {rrna.mean():.2f}%（中位数 {rrna.median():.2f}%），"
        f"样本级 Post-rRNA R1 深度中位数为 {clean_mb.median():.2f} Mb"
        f"（范围 {clean_mb.min():.2f}–{clean_mb.max():.2f} Mb；本批次与 merge 结果一致）。"
        f"de novo 组装 ≥1 kb contig 中位数为 {contigs.median():,.0f} 条"
        f"（范围 {contigs.min():,.0f}–{contigs.max():,.0f} 条）。"
    )
    para4 = (
        f"综合评级：优 {rc.get('优', 0)} 个、良 {rc.get('良', 0)} 个、"
        f"可接受 {rc.get('可接受', 0)} 个、需关注 {rc.get('需关注', 0)} 个、"
        f"不建议下游 {rc.get('不建议下游', 0)} 个；批次总体{pass_txt}。"
    )
    if low:
        para4 += f" 低深度样本（Post-rRNA R1 < 5 Mb）：{', '.join(low)}。"
    if concern:
        para4 += f" 需重点关注：{', '.join(concern)}。"
    return "".join([para1, para2, para3, para4])
