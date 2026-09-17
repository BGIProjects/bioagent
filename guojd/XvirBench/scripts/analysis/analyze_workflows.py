"""各 workflow harmonized 表的分组比较分析（分层 + 多面板图）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from cohort import LOW_DEPTH_READS, METHOD_LABEL, METHOD_ORDER, load_sampleinfo
from interpretation import build_interpretations
from module_plots import (
    plot_correlation_heatmap,
    plot_faceted_by_host,
    plot_host_comparison_heatmap,
    plot_method_bar_se,
    plot_pca_samples,
    plot_quad_panel,
    plot_stacked_alignment,
    plot_w5_virus_panels,
)
from plot_styles import apply_theme
from stratified_stats import run_multi_level_tests
from stats_lib import method_summary, run_all_tests


@dataclass
class FigureGroup:
    title: str
    path: Path
    caption: str
    layout: str = "panel"  # panel | facet | wide | heatmap | compact
    interpretation: str = ""


@dataclass
class WorkflowAnalysis:
    wf_id: str
    title: str
    objective: str
    metrics: List[str]
    metric_labels: Dict[str, str]
    sample_df: pd.DataFrame
    summary_df: pd.DataFrame
    tests_df: pd.DataFrame
    notes: List[str] = field(default_factory=list)
    figures: List[Path] = field(default_factory=list)
    figure_groups: List[FigureGroup] = field(default_factory=list)
    stratified_summary_df: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    interpretations: List[str] = field(default_factory=list)


def _read_harm(harm_dir: Path, name: str) -> pd.DataFrame:
    p = harm_dir / name
    return pd.read_csv(p, sep="\t") if p.is_file() else pd.DataFrame()


def _merge_cohort(cohort: pd.DataFrame, df: pd.DataFrame, on: str = "sample_id") -> pd.DataFrame:
    if df.empty:
        return cohort.copy()
    drop = [c for c in df.columns if c in cohort.columns and c != on]
    return cohort.merge(df.drop(columns=drop, errors="ignore"), on=on, how="left")


def _add_low_depth(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "merge_r1_reads" in df.columns:
        df["low_depth"] = pd.to_numeric(df["merge_r1_reads"], errors="coerce") < LOW_DEPTH_READS
    elif "total_reads_x" in df.columns:
        df["low_depth"] = pd.to_numeric(df["total_reads_x"], errors="coerce") < LOW_DEPTH_READS
    else:
        df["low_depth"] = False
    return df


def _finalize(
    wf_id: str,
    title: str,
    objective: str,
    metrics: List[str],
    labels: Dict[str, str],
    df: pd.DataFrame,
    fig_groups: List[FigureGroup],
    notes: List[str],
    tests_df: pd.DataFrame,
    strat_summ: pd.DataFrame,
) -> WorkflowAnalysis:
    interps = build_interpretations(tests_df, strat_summ, labels)
    figs = [g.path for g in fig_groups if g.path.is_file()]
    return WorkflowAnalysis(
        wf_id, title, objective, metrics, labels, df,
        method_summary(df, metrics),
        tests_df,
        notes,
        figs,
        fig_groups,
        strat_summ,
        interps,
    )


def analyze_w1(cohort: pd.DataFrame, harm: Path, fig_dir: Path) -> WorkflowAnalysis:
    sample = _read_harm(harm, "qc_upstream_sample.tsv")
    runs = _read_harm(harm, "qc_upstream_run.tsv")
    run_agg = (
        runs.groupby("sample_id", as_index=False).agg(
            mean_q30_after_fastp=("q30_after_fastp", "mean"),
            mean_rrna_retention=("rrna_retention_r1", "mean"),
        )
        if not runs.empty else pd.DataFrame()
    )
    df = _merge_cohort(cohort, sample)
    if not run_agg.empty:
        df = df.merge(run_agg, on="sample_id", how="left")
    df["merge_r1_Mreads"] = pd.to_numeric(df["merge_r1_reads"], errors="coerce") / 1e6
    df["contigs_ge1kb_Mbp"] = pd.to_numeric(df["contigs_ge1kb_bp"], errors="coerce") / 1e6
    df = _add_low_depth(df)

    metrics = ["merge_r1_Mreads", "mean_q30_after_fastp", "mean_rrna_retention", "contigs_ge1kb_n"]
    labels = {
        "merge_r1_Mreads": "合并 R1 (M reads)",
        "mean_q30_after_fastp": "fastp 后 Q30",
        "mean_rrna_retention": "rRNA 保留率",
        "contigs_ge1kb_n": "≥1kb contigs",
    }
    tests, strat_summ = run_multi_level_tests(df, metrics)
    groups: List[FigureGroup] = []
    p = fig_dir / "w1_M0_upstream_quad.png"
    if plot_quad_panel(df, metrics, labels, p, "M0 上游质控四联图"):
        groups.append(FigureGroup("M0 上游质控", p, "测序深度、Q30、rRNA、组装规模", "panel"))
    p = fig_dir / "w1_depth_by_host.png"
    if plot_faceted_by_host(df, "merge_r1_Mreads", labels["merge_r1_Mreads"], p):
        groups.append(FigureGroup("测序深度（分宿主）", p, "按 rat/tick/mosquito 分层比较建库方法", "facet"))
    low = df.loc[df["low_depth"], "sample_id"].tolist()
    notes = [
        "M0：fastp 质控 + 合并 + 组装指标。",
        f"低深度（R1<{LOW_DEPTH_READS/1e6:.0f}M）：{', '.join(low) or '无'}（空心圈标记）。",
        "宿主间测序深度差异大，method 比较建议分宿主解读。",
    ]
    return _finalize("workflow1", "W1 上游 QC 与组装", "评估 clean reads、碱基质量、rRNA 去除与组装。", metrics, labels, df, groups, notes, tests, strat_summ)


def analyze_w2(cohort: pd.DataFrame, harm: Path, fig_dir: Path) -> WorkflowAnalysis:
    sample = _read_harm(harm, "virus_identification_sample.tsv")
    contigs = _read_harm(harm, "virus_identification_contigs.tsv")
    cagg = (
        contigs.groupby("source_sample", as_index=False).agg(
            n_checkv_high=("checkv_quality", lambda s: (s == "High-quality").sum()),
            mean_checkv_completeness=("completeness", "mean"),
        ).rename(columns={"source_sample": "sample_id"})
        if not contigs.empty else pd.DataFrame()
    )
    df = _merge_cohort(cohort, sample.rename(columns={"n_contigs": "n_viral_contigs"}))
    if not cagg.empty:
        df = df.merge(cagg, on="sample_id", how="left")
    df = _add_low_depth(df)
    metrics = ["n_viral_contigs", "n_clusters", "n_checkv_high", "mean_checkv_completeness"]
    labels = {
        "n_viral_contigs": "病毒 contig 数",
        "n_clusters": "病毒 cluster 数",
        "n_checkv_high": "CheckV High-quality",
        "mean_checkv_completeness": "CheckV 完整度 (%)",
    }
    tests, strat_summ = run_multi_level_tests(df, metrics)
    groups: List[FigureGroup] = []
    p = fig_dir / "w2_virus_quad.png"
    if plot_quad_panel(df, metrics, labels, p, "M6 病毒发现（W2）"):
        groups.append(FigureGroup("病毒检出四联图", p, "contig/cluster 数与 CheckV 质量", "panel"))
    p = fig_dir / "w2_contigs_by_host.png"
    if plot_faceted_by_host(df, "n_viral_contigs", labels["n_viral_contigs"], p):
        groups.append(FigureGroup("病毒 contig（分宿主）", p, "宿主参考与背景不同，需分层", "facet"))
    p = fig_dir / "w2_host_method_heatmap.png"
    if plot_host_comparison_heatmap(strat_summ, "n_viral_contigs", labels["n_viral_contigs"], p):
        groups.append(FigureGroup("宿主×方法热图", p, "各宿主内方法均值", "heatmap"))
    return _finalize(
        "workflow2", "W2 病毒鉴定",
        "病毒 contig 检出与 CheckV 质量，按宿主分批运行后合并。",
        metrics, labels, df, groups,
        ["W2 按 rat/tick/mosquito 分 3 批；跨宿主比较为探索性。"],
        tests, strat_summ,
    )


def analyze_w3(cohort: pd.DataFrame, harm: Path, fig_dir: Path) -> WorkflowAnalysis:
    sample = _read_harm(harm, "host_identification_sample.tsv")
    df = _merge_cohort(cohort, sample)
    df = _add_low_depth(df)
    metrics = ["n_species_inferred", "n_genus_inferred"]
    labels = {"n_species_inferred": "推断物种数", "n_genus_inferred": "推断属数"}
    tests, strat_summ = run_multi_level_tests(df, metrics)
    groups: List[FigureGroup] = []
    p = fig_dir / "w3_hostid_quad.png"
    if plot_quad_panel(df, metrics + metrics[:1], labels, p, "M? 宿主鉴定（W3）"):
        groups.append(FigureGroup("宿主鉴定", p, "线粒体 marker 推断丰富度", "panel"))
    p = fig_dir / "w3_species_by_host.png"
    if plot_faceted_by_host(df, "n_species_inferred", labels["n_species_inferred"], p):
        groups.append(FigureGroup("物种数（分宿主）", p, "质控层：宿主背景应稳定", "facet"))
    return _finalize(
        "workflow3", "W3 宿主鉴定",
        "线粒体 marker 宿主推断；异常高物种数提示污染或组装问题。",
        metrics, labels, df, groups, ["V3 逐样本 H4。"], tests, strat_summ,
    )


def analyze_w4(cohort: pd.DataFrame, harm: Path, fig_dir: Path) -> WorkflowAnalysis:
    bracken = _read_harm(harm, "microbiome_bracken_sample.tsv")
    df = _merge_cohort(cohort, bracken)
    df["kraken_unclassified_pct"] = pd.to_numeric(df["kraken_unclassified_frac"], errors="coerce") * 100
    df["bracken_species_reads_M"] = pd.to_numeric(df["bracken_species_reads_assigned"], errors="coerce") / 1e6
    df = _add_low_depth(df)
    metrics = ["kraken_unclassified_pct", "bracken_species_taxa", "bracken_species_reads_M"]
    labels = {
        "kraken_unclassified_pct": "Kraken 未分类 (%)",
        "bracken_species_taxa": "Bracken 物种数",
        "bracken_species_reads_M": "Bracken reads (M)",
    }
    tests, strat_summ = run_multi_level_tests(df, metrics)
    groups: List[FigureGroup] = []
    p = fig_dir / "w4_microbiome_quad.png"
    if plot_quad_panel(df, metrics + [metrics[0]], labels, p, "M5 微生物群落（W4）"):
        groups.append(FigureGroup("微生物群落四联图", p, "Kraken/Bracken 样本级汇总", "panel"))
    p = fig_dir / "w4_species_by_host.png"
    if plot_faceted_by_host(df, "bracken_species_taxa", labels["bracken_species_taxa"], p):
        groups.append(FigureGroup("物种丰富度（分宿主）", p, "宿主与环境微生物背景不同", "facet"))
    return _finalize(
        "workflow4", "W4 微生物群落",
        "Kraken2 + Bracken 非宿主微生物组成与分类效率。",
        metrics, labels, df, groups, ["Top15 物种见 harmonized/microbiome_bracken_top15.tsv。"],
        tests, strat_summ,
    )


def analyze_w5(cohort: pd.DataFrame, harm: Path, fig_dir: Path) -> WorkflowAnalysis:
    sample = _read_harm(harm, "virus_quantification_sample.tsv")
    rpm = _read_harm(harm, "virus_quantification_rpm.tsv")
    df = _merge_cohort(cohort, sample)
    df = _add_low_depth(df)
    metrics = ["mapping_rate_pct", "median_rpm", "n_viral_contigs_with_reads", "mean_coverage_pct"]
    labels = {
        "mapping_rate_pct": "病毒 reads 占比 (%)",
        "median_rpm": "RPM 中位数",
        "n_viral_contigs_with_reads": "有 reads 的病毒 contig",
        "mean_coverage_pct": "平均覆盖度 (%)",
    }
    tests, strat_summ = run_multi_level_tests(df, metrics)
    groups: List[FigureGroup] = []
    for i, path in enumerate(plot_w5_virus_panels(df, rpm, fig_dir)):
        titles = ["病毒检出数", "RPM 分布（按 sn）", "RPM 分宿主"]
        caps = ["coverage>20% & RPM>1", "log10 RPM，颜色=测序文库", "rat/tick/mosquito 分层"]
        layouts = ["compact", "wide", "facet"]
        groups.append(FigureGroup(titles[i], path, caps[i], layouts[i]))
    p = fig_dir / "w5_mapping_quad.png"
    if plot_quad_panel(df, metrics, labels, p, "M7 病毒定量（W5）样本级"):
        groups.append(FigureGroup("病毒定量四联图", p, "样本级 RPM/mapping", "panel"))
    return _finalize(
        "workflow5", "W5 病毒定量",
        "宿主参考比对 RPM；参考 run_virus_comparison 过滤 cov>20%、RPM>1。",
        metrics, labels, df, groups,
        ["按宿主使用不同参考基因组；method 效应与 host 部分混杂。"],
        tests, strat_summ,
    )


def analyze_w7(cohort: pd.DataFrame, harm: Path, fig_dir: Path) -> WorkflowAnalysis:
    bench = _read_harm(harm, "fragmentation_benchmark.tsv")
    df = _merge_cohort(cohort, bench)
    df["host_mapped_pct"] = (
        pd.to_numeric(df["uniquely_mapped_pct"], errors="coerce")
        + pd.to_numeric(df["multi_mapped_pct"], errors="coerce")
    )
    df = _add_low_depth(df)
    metrics = [
        "host_mapped_pct", "uniquely_mapped_pct", "multi_mapped_pct",
        "percent_duplication", "median_cv_coverage", "chimeric_rate_pct",
        "median_5prime_to_3prime_bias", "splice_junctions_novel",
    ]
    labels = {
        "host_mapped_pct": "宿主比对率 (%)",
        "uniquely_mapped_pct": "唯一比对率 (%)",
        "multi_mapped_pct": "多重比对率 (%)",
        "percent_duplication": "PCR 重复率",
        "median_cv_coverage": "覆盖 CV",
        "chimeric_rate_pct": "嵌合体率 (%)",
        "median_5prime_to_3prime_bias": "5'→3' 偏好",
        "splice_junctions_novel": "Novel junction 数",
    }
    tests, strat_summ = run_multi_level_tests(df, metrics)
    groups: List[FigureGroup] = []
    core4 = ["host_mapped_pct", "percent_duplication", "chimeric_rate_pct", "median_cv_coverage"]
    p = fig_dir / "w7_01_core_qc_quad.png"
    if plot_quad_panel(df, core4, labels, p, "核心 QC 四联图（对齐 RAT 图01）"):
        groups.append(FigureGroup(
            "核心 QC 四联图", p,
            "宿主比对、重复率、嵌合体、覆盖 CV；红圈=低深度",
            "panel",
        ))
    p = fig_dir / "w7_02_alignment.png"
    if plot_stacked_alignment(df, p):
        groups.append(FigureGroup("比对与剪接", p, "宿主比对率 + 多重比对率", "wide"))
    p = fig_dir / "w7_03_unique_by_host.png"
    if plot_faceted_by_host(df, "uniquely_mapped_pct", labels["uniquely_mapped_pct"], p):
        groups.append(FigureGroup("唯一比对率（分宿主）", p, "PRIMARY：宿主内 method 比较", "facet"))
    p = fig_dir / "w7_04_method_bar_se.png"
    if plot_method_bar_se(strat_summ, core4[:4], labels, p):
        groups.append(FigureGroup("方法均值 ± SE", p, "四核心指标柱状图", "wide"))
    p = fig_dir / "w7_05_host_method_heatmap.png"
    if plot_host_comparison_heatmap(strat_summ, "uniquely_mapped_pct", labels["uniquely_mapped_pct"], p):
        groups.append(FigureGroup("唯一比对率热图", p, "宿主 × 方法均值", "heatmap"))
    p = fig_dir / "w7_06_correlation.png"
    if plot_correlation_heatmap(df, core4 + ["splice_junctions_novel"], p, "W7 指标相关"):
        groups.append(FigureGroup("指标相关热图", p, "Pearson 相关", "heatmap"))
    p = fig_dir / "w7_07_pca.png"
    if plot_pca_samples(df, core4, p):
        groups.append(FigureGroup("样本 PCA", p, "颜色=方法，形状=宿主", "compact"))
    notes = [
        "W7 PRIMARY endpoint；harmonized 数据与 vazyme/results/*/comparison_summary.tsv 一致。",
        "全队列混合宿主会 confound method 效应，请优先看分宿主结果。",
        "蚊虫仅 cDNA vs RNA_85 两种方法（无 RNA_94）。",
    ]
    res = _finalize(
        "workflow7", "W7 建库方法 Benchmark",
        "STAR 比对宿主参考，评估碎片化方法对文库质量的影响。",
        metrics, labels, df, groups, notes, tests, strat_summ,
    )
    return res


ANALYZERS = {
    "workflow1": analyze_w1, "workflow2": analyze_w2, "workflow3": analyze_w3,
    "workflow4": analyze_w4, "workflow5": analyze_w5, "workflow7": analyze_w7,
}

CLI_ALIASES = {
    "w1": "workflow1", "1": "workflow1", "workflow1": "workflow1",
    "w2": "workflow2", "2": "workflow2", "workflow2": "workflow2",
    "w3": "workflow3", "3": "workflow3", "workflow3": "workflow3",
    "w4": "workflow4", "4": "workflow4", "workflow4": "workflow4",
    "w5": "workflow5", "5": "workflow5", "workflow5": "workflow5",
    "w7": "workflow7", "7": "workflow7", "workflow7": "workflow7",
}


def run_analyses(batch_dir: Path, workflows: Optional[List[str]] = None) -> tuple[pd.DataFrame, Dict[str, WorkflowAnalysis]]:
    apply_theme()
    cohort = load_sampleinfo(batch_dir / "cohorts")
    harm_root = batch_dir / "harmonized"
    out_root = batch_dir / "analysis"
    tab_dir, fig_dir = out_root / "tables", out_root / "figures"
    tab_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    results: Dict[str, WorkflowAnalysis] = {}
    for wf in (workflows or list(ANALYZERS.keys())):
        fn = ANALYZERS.get(wf)
        if not fn:
            continue
        res = fn(cohort, harm_root / f"workflow{wf.replace('workflow', '')}", fig_dir)
        results[wf] = res
        res.sample_df.to_csv(tab_dir / f"{wf}_sample_metrics.tsv", sep="\t", index=False)
        res.summary_df.to_csv(tab_dir / f"{wf}_method_summary.tsv", sep="\t", index=False)
        if not res.tests_df.empty:
            res.tests_df.to_csv(tab_dir / f"{wf}_stat_tests.tsv", sep="\t", index=False)
        if not res.stratified_summary_df.empty:
            res.stratified_summary_df.to_csv(tab_dir / f"{wf}_method_summary_stratified.tsv", sep="\t", index=False)
        if res.interpretations:
            (out_root / "text" / f"{wf}_interpretation.md").parent.mkdir(parents=True, exist_ok=True)
            (out_root / "text" / f"{wf}_interpretation.md").write_text("\n\n".join(res.interpretations), encoding="utf-8")

    merged = cohort.copy()
    for wf, res in results.items():
        cols = ["sample_id"] + [c for c in res.metrics if c in res.sample_df.columns]
        sub = res.sample_df[cols].rename(columns={c: f"{wf}_{c}" for c in cols if c != "sample_id"})
        merged = merged.merge(sub, on="sample_id", how="left")
    merged.to_csv(tab_dir / "sample_metrics_merged.tsv", sep="\t", index=False)
    return merged, results
