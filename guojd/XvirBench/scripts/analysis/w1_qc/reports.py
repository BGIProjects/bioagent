"""HTML and Markdown W1 QC reports."""
from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

import pandas as pd

from w1_qc.narrative import build_narrative
from w1_qc.scoring_doc import scoring_criteria_html
from w1_qc.units import (
    METRIC_LABELS,
    display_columns_for_report,
    format_cell,
    format_dataframe,
    format_number,
    summary_with_units,
)

HOST_LABEL = {"rat": "大鼠", "tick": "蜱", "mosquito": "蚊虫"}

FIG_ORDER = [
    "fig01_stage_yield",
    "fig02_fastp_qc",
    "fig03_rrna_qc",
    "fig04_assembly",
]


def _df_html(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df is None or df.empty:
        return "<p><em>无数据</em></p>"
    sub = df if max_rows is None else df.head(max_rows)
    # rename then format
    rename = {c: METRIC_LABELS.get(c, c) for c in sub.columns}
    view = sub.rename(columns=rename)
    fmt = format_dataframe(view)
    return fmt.to_html(index=False, border=0, classes="dataframe", escape=True)


def _img_embed(path: Path, alt: str = "") -> str:
    if not path.is_file():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    label = alt or path.stem
    return (
        f'<figure style="margin:18px 0">'
        f'<img src="data:image/png;base64,{data}" alt="{html.escape(label)}" '
        f'style="max-width:100%;height:auto;border:1px solid #e0e0e0"/>'
        f'<figcaption style="font-size:12px;color:#666;margin-top:4px">{html.escape(label)}</figcaption>'
        f"</figure>"
    )


def _summary_stats_table(summary: pd.DataFrame, metrics: list[str], tables: dict[str, pd.DataFrame]) -> str:
    sub = summary_with_units(summary, tables)
    keys = set(metrics)
    for m in metrics:
        keys.add(METRIC_LABELS.get(m, m))
        keys.add(f"{m} (%)")
        keys.add(f"{m}_pct")
    # match scaled names
    mask = sub["metric"].apply(
        lambda x: any(
            k == x or k in str(x) or str(x).startswith(k.split(" ")[0])
            for k in metrics
        ) or x in keys or any(METRIC_LABELS.get(m, m) == x for m in metrics)
    )
    # simpler: select by original metric names after conversion
    want_labels = set()
    for m in metrics:
        want_labels.add(m)
        want_labels.add(METRIC_LABELS.get(m, m))
        want_labels.add(METRIC_LABELS.get(f"{m}_Mb", ""))
        want_labels.add(METRIC_LABELS.get(f"{m}_Gb", ""))
        want_labels.add(METRIC_LABELS.get(f"{m}_pct", ""))
        want_labels.add(f"{m} (%)")
        want_labels.add(f"{m} (Mb)")
        want_labels.add(f"{m} (Gb)")
    want_labels.discard("")
    picked = sub[sub["metric"].isin(want_labels)].copy()
    if picked.empty:
        # fallback fuzzy
        picked = sub[sub["metric"].apply(lambda x: any(m in str(x) for m in metrics))].copy()
    return _df_html(picked)


def write_reports(
    out_dir: Path,
    batch_summary: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    fig_paths: dict[str, Path],
    internal: bool = True,
) -> Path:
    host = batch_summary.get("host", "all")
    host_cn = HOST_LABEL.get(host, host)
    scores = tables["sample_qc_scores"]
    s1_sum = tables["stage_S1_fastp_summary"]
    s3_sum = tables["stage_S3_merge_summary"]
    s4_sum = tables["stage_S4_assembly_summary"]
    pass_txt = "通过" if batch_summary.get("batch_pass") else "需复核"
    rating_counts = batch_summary.get("rating_counts", {})
    low_depth = batch_summary.get("low_depth_samples", [])
    concern = scores[scores["overall_rating"].isin(["需关注", "不建议下游"])]["sample_id"].tolist()
    narrative = html.escape(build_narrative(batch_summary, tables, host_cn))
    scoring_block = scoring_criteria_html()

    s1_loss_display = display_columns_for_report(
        tables["stage_S1_fastp_loss_by_sample"],
        [
            "sample_id", "method_label",
            "reads_before_sum", "reads_after_fastp_sum", "removed_sum",
            "loss_low_quality_sum", "loss_too_short_sum", "loss_adapter_sum",
            "too_many_N_sum", "loss_unaccounted_sum",
        ],
    )

    fig_block = "".join(
        _img_embed(fig_paths[k] if k in fig_paths else out_dir / "figures" / f"{k}.png", k)
        for k in FIG_ORDER
        if (k in fig_paths) or (out_dir / "figures" / f"{k}.png").exists()
    )

    if internal:
        title = f"W1 上游 QC 内部报告 — {batch_summary['batch_id']} ({host_cn})"
        fname = out_dir / "report_internal.html"
        loss_run = display_columns_for_report(
            tables["stage_S1_fastp_loss_by_run"],
            ["run_id", "sample_id", "method_label", "reads_before", "reads_removed_fastp",
             "loss_low_quality", "loss_too_short", "loss_adapter", "too_many_N_reads", "loss_unaccounted"],
        )
        extra = f"""
        <h2>附录</h2>
        <p>阈值版本: {batch_summary.get('threshold_version')} · 生成时间: {batch_summary.get('generated_at')}</p>
        <p>命令: <code>python3 scripts/analysis/run_w1_qc_report.py --batch-id {batch_summary['batch_id']} --host {host}</code></p>
        <p>说明: 图片已 Base64 内嵌；reads 统一 Mb（×10⁶），bases 统一 Gb（×10⁹）；比例类指标以百分比显示（保留 2 位小数）；数值保留 2 位小数；整数使用千分位。</p>
        <p>说明: 本批次各样本 merge R1 reads 与 rRNA 去除后 clean R1 一致，深度图以样本级 Post-rRNA 汇总为准（raw/fastp/rRNA 已按 run 合并到样本）。</p>
        <h3>逐 run fastp 剔除明细</h3>
        {_df_html(loss_run, None)}
        """
    else:
        title = f"W1 上游数据质量报告 — {host_cn}样本"
        fname = out_dir / "report_delivery.html"
        extra = ""

    body = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<style>
body{{font-family:"Noto Sans CJK SC",sans-serif;max-width:1180px;margin:24px auto;padding:0 16px;line-height:1.5;color:#222}}
h1{{border-bottom:2px solid #1565c0;padding-bottom:8px}}
h2{{color:#1565c0;margin-top:28px}}
table.dataframe{{border-collapse:collapse;width:100%;font-size:12px}}
table.dataframe th,table.dataframe td{{border:1px solid #ddd;padding:4px 6px;text-align:right}}
table.dataframe th:first-child,table.dataframe td:first-child,
table.dataframe th:nth-child(2),table.dataframe td:nth-child(2){{text-align:left}}
table.dataframe th{{background:#e3f2fd}}
code{{background:#f5f5f5;padding:2px 4px}}
.summary-box{{background:#f8f9fa;border-left:4px solid #1565c0;padding:12px 16px;margin:16px 0}}
.narrative{{text-indent:2em}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="summary-box">
<p><strong>批次总体评价：</strong> {pass_txt}</p>
<p><strong>样本数：</strong> {batch_summary.get('n_samples')} · <strong>等级分布：</strong> {html.escape(str(rating_counts))}</p>
<p><strong>低深度样本：</strong> {', '.join(low_depth) or '无'}</p>
<p><strong>需关注样本：</strong> {', '.join(concern) or '无'}</p>
</div>

<h2>1. 执行摘要</h2>
<p class="narrative">{narrative}</p>
<p>本报告覆盖 Workflow1 上游：原始测序 (S0)、fastp 质控 (S1)、rRNA 去除 (S2)、样本级汇总/加测合并 (S3)、de novo 组装 (S4)。
reads 以 Mb、bases 以 Gb 计；Q30/GC/保留率为百分比。</p>

<h2>2. S0 原始数据</h2>
{_summary_stats_table(tables['stage_S0_raw_summary'], ['reads_before','bases_before','q30_before','gc_before','raw_reads_sum','raw_bases_sum','raw_q30_mean','raw_gc_mean'], tables)}

<h2>3. S1 fastp 质控</h2>
<p>剔除原因包括：低质量、过短、接头、N 过多、低复杂度、接头二聚体、过长及未归类（reads 以 Mb 计）。</p>
{_summary_stats_table(s1_sum, ['read_retention_fastp','q30_after_fastp','duplication_rate','read_retention_fastp_agg','mean_q30_after_fastp','reads_removed_fastp','mean_dup'], tables)}
<h3>样本级剔除汇总（全部样本）</h3>
{_df_html(s1_loss_display, None)}

<h2>4. S2 rRNA 去除</h2>
<p><strong>rrna_retention 计算：</strong>保留率 = clean_r1_reads / fastp_r1_reads（分母为 <em>fastp 质控后</em> 的 R1 reads，不是 raw data）。</p>
{_summary_stats_table(tables['stage_S2_rrna_summary'], ['rrna_retention_mean','mean_rrna_retention','rrna_removed_sum','rrna_removed_r1'], tables)}

<h2>5. S3 样本汇总 / 加测合并</h2>
<p>S3 为样本级结果文件合并（应对加测）。本批次 merge 与 rRNA 去除后 clean reads 一致，以下为样本级统计。</p>
{_summary_stats_table(s3_sum, ['merge_r1_reads','merge_r1_Mreads','merge_r1_bases','merge_r1_q30_pct','merge_r1_gc_pct','merge_loss_pct'], tables)}

<h2>6. S4 组装</h2>
<p><strong>指标区分：</strong>
<code>contigs_ge1kb_n</code> = 长度 ≥1 kb 的 contig <em>条数</em>；
<code>contigs_ge1kb_bp</code>（报告中 Gb）= 这些 ≥1 kb contig 的 <em>总碱基数</em>。
二者不是同一量纲：前者计条目数，后者计碱基总量。</p>
{_summary_stats_table(s4_sum, ['contigs_all_n','contigs_ge1kb_n','contigs_avg_len','contigs_max_len','contigs_ge1kb_bp'], tables)}

<h2>7. 样本综合 QC</h2>
{_df_html(scores[['sample_id','method_label','grade_S1','grade_S2','grade_S3','grade_S4','weighted_score','overall_rating']], None)}

{scoring_block}
<h2>8. 图件</h2>
{fig_block}
{extra}
</body></html>"""
    fname.write_text(body, encoding="utf-8")

    if not internal:
        md = _delivery_markdown(batch_summary, tables, host_cn, pass_txt, rating_counts, low_depth, concern)
        (out_dir / "report_delivery.md").write_text(md, encoding="utf-8")
    return fname


def _delivery_markdown(batch_summary, tables, host_cn, pass_txt, rating_counts, low_depth, concern) -> str:
    s3 = summary_with_units(tables["stage_S3_merge_summary"], tables)
    s1 = summary_with_units(tables["stage_S1_fastp_summary"], tables)
    s0 = summary_with_units(tables["stage_S0_raw_summary"], tables)
    lines = [
        f"# W1 上游数据质量报告（{host_cn}）",
        "",
        f"- **批次**: {batch_summary['batch_id']}",
        f"- **样本数**: {batch_summary.get('n_samples')}",
        f"- **批次评价**: {pass_txt}",
        f"- **等级分布**: {rating_counts}",
        f"- **低深度样本**: {', '.join(low_depth) or '无'}",
        f"- **需关注样本**: {', '.join(concern) or '无'}",
        "",
        "> reads=Mb，bases=Gb；百分比用 % 且保留 2 位小数；其他数值保留 2 位小数；整数用千分位。HTML 图件已内嵌。",
        "",
        "## 数据描述",
        "",
        build_narrative(batch_summary, tables, host_cn),
        "",
        "## S0 原始数据摘要",
        "",
        format_dataframe(s0).to_markdown(index=False),
        "",
        "## S1 fastp 摘要",
        "",
        format_dataframe(s1).to_markdown(index=False),
        "",
        "## S3 样本汇总",
        "",
        format_dataframe(s3).to_markdown(index=False),
        "",
        "## 结论与建议",
        "",
        "1. 样本级 Post-rRNA 深度与 fastp 后 Q30 是下游病毒发现的质量基础。",
        "2. rRNA 保留率异常需结合宿主背景解读。",
        "3. 低深度或「需关注」样本建议谨慎进入定量比较。",
        "",
        "## 图件",
        "",
        "- fig01_stage_yield — 各阶段 R1 reads(Mb) / bases(Gb)",
        "- fig02_fastp_qc — fastp 保留率 + 全样本剔除组成",
        "- fig03_rrna_qc — rRNA 保留率（分母=fastp）+ Post-rRNA 深度",
        "- fig04_assembly — 组装散点/条数/平均长度/≥1kb 占比",
        "",
    ]
    return "\n".join(lines)
