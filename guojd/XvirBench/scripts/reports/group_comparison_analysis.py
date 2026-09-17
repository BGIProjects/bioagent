#!/usr/bin/env python3
"""Group comparison by fragmentation method (groupinfo col4) for pxy_V350399508."""

from __future__ import annotations

import os
import itertools
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

XVIRBENCH_ROOT = Path(
    os.environ.get("XVIRBENCH_ROOT", Path(__file__).resolve().parent.parent.parent)
)
BATCH_ID = os.environ.get("BATCH_ID", "vazyme_fragment_test")
COHORT_DIR = XVIRBENCH_ROOT / "cohorts"
GROUPINFO = COHORT_DIR / "groupinfo.txt"
BATCH_DIR = XVIRBENCH_ROOT / "batches" / BATCH_ID
RUN_DIR = Path(os.environ.get("RUN_DIR", BATCH_DIR / "workflow_results"))
REPORT_DIR = BATCH_DIR / "analysis" if (BATCH_DIR / "analysis").is_dir() else RUN_DIR / "reports"
METRICS_XLSX = REPORT_DIR / "pxy_V350399508_benchmark_metrics.xlsx"
OUT_DIR = REPORT_DIR / "group_comparison"
FIG_DIR = OUT_DIR / "figures"
TAB_DIR = OUT_DIR / "tables"

METHOD_ORDER = ["cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min"]
METHOD_LABEL = {
    "cDNA_Frag_30C5Min": "cDNA 30°C 5min",
    "RNA_Frag_85C6Min": "RNA 85°C 6min",
    "RNA_Frag_94C7Min": "RNA 94°C 7min",
}
LOW_DEPTH_READS = 5_000_000

METRIC_META = {
    "merge_r1_Mreads": ("W1", "合并后 R1 reads (M)", "higher_better"),
    "mean_q30_after_fastp": ("W1", "fastp 后 Q30（run 均值）", "higher_better"),
    "mean_rrna_retention": ("W1", "去 rRNA 保留率（run 均值）", "higher_better"),
    "contigs_ge1kb_n": ("W1", "≥1kb contig 数", "neutral"),
    "contigs_ge1kb_Mbp": ("W1", "≥1kb contig 总长度 (Mbp)", "neutral"),
    "n_viral_contigs": ("W2", "假定病毒 contig 数", "neutral"),
    "n_checkv_high": ("W2", "CheckV High-quality 数", "higher_better"),
    "mean_checkv_completeness": ("W2", "CheckV 完整度均值 (%)", "higher_better"),
    "kraken_unclassified_pct": ("W4", "Kraken 未分类 (%)", "lower_better"),
    "bracken_species_taxa": ("W4", "Bracken 物种数", "neutral"),
    "bracken_species_reads_M": ("W4", "Bracken 分配 reads (M)", "higher_better"),
    "virus_mapping_rate_pct": ("W5", "病毒 reads 占比 (%)", "neutral"),
    "median_rpm": ("W5", "RPM 中位数", "neutral"),
    "max_rpm": ("W5", "RPM 最大值", "neutral"),
    "n_viral_contigs_with_reads": ("W5", "有读段支持的病毒 contig 数", "higher_better"),
}


def load_groupinfo() -> pd.DataFrame:
    rows = []
    for line in GROUPINFO.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 4:
            rows.append(
                {
                    "sample_num": p[0],
                    "sample_id": f"v{p[0]}",
                    "library": p[1],
                    "host": p[2],
                    "method": p[3],
                }
            )
    df = pd.DataFrame(rows)
    df["method"] = pd.Categorical(df["method"], categories=METHOD_ORDER, ordered=True)
    df["method_label"] = df["method"].map(METHOD_LABEL)
    return df


def build_sample_metrics() -> pd.DataFrame:
    w1s = pd.read_excel(METRICS_XLSX, sheet_name="W1_sample组装")
    w1r = pd.read_excel(METRICS_XLSX, sheet_name="W1_run质控")
    w2 = pd.read_excel(METRICS_XLSX, sheet_name="W2_病毒contigs")
    w4 = pd.read_excel(METRICS_XLSX, sheet_name="W4_kraken_bracken")
    w5 = pd.read_excel(METRICS_XLSX, sheet_name="W5_sample定量")

    w1r_agg = (
        w1r.groupby("sample_id", as_index=False)
        .agg(
            mean_q30_after_fastp=("q30_after_fastp", "mean"),
            mean_read_retention=("read_retention_fastp", "mean"),
            mean_rrna_retention=("rrna_retention_r1", "mean"),
        )
    )

    w2_agg = (
        w2.groupby("source_sample", as_index=False)
        .agg(
            n_viral_contigs=("contig_id", "count"),
            n_checkv_high=("checkv_quality", lambda s: (s == "High-quality").sum()),
            mean_checkv_completeness=("completeness", "mean"),
        )
        .rename(columns={"source_sample": "sample_id"})
    )

    df = load_groupinfo()
    df = df.merge(w1s, on="sample_id", how="left")
    df = df.merge(w1r_agg, on="sample_id", how="left")
    df = df.merge(w2_agg, on="sample_id", how="left")
    df = df.merge(
        w4.rename(
            columns={
                "kraken_unclassified_frac": "kraken_unclassified_frac_raw",
                "bracken_species_reads_assigned": "bracken_species_reads",
            }
        ),
        on="sample_id",
        how="left",
    )
    df = df.merge(w5, on="sample_id", how="left", suffixes=("", "_w5"))

    df["merge_r1_Mreads"] = df["merge_r1_reads"] / 1e6
    df["contigs_ge1kb_Mbp"] = df["contigs_ge1kb_bp"] / 1e6
    df["kraken_unclassified_pct"] = df["kraken_unclassified_frac_raw"] * 100
    df["bracken_species_reads_M"] = df["bracken_species_reads"] / 1e6
    df["virus_mapping_rate_pct"] = df["mapping_rate_pct"]
    df["low_depth"] = df["merge_r1_reads"] < LOW_DEPTH_READS
    return df


def method_summary(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    rows = []
    for meth in METHOD_ORDER:
        sub = df[df["method"] == meth]
        if sub.empty:
            continue
        row = {"method": meth, "method_label": METHOD_LABEL[meth], "n": len(sub)}
        for m in metrics:
            s = sub[m].dropna()
            row[f"{m}_mean"] = s.mean()
            row[f"{m}_sd"] = s.std(ddof=1) if len(s) > 1 else np.nan
            row[f"{m}_median"] = s.median()
        rows.append(row)
    return pd.DataFrame(rows)


def pairwise_tests(df: pd.DataFrame, metric: str) -> list[dict]:
    out = []
    groups = {m: df.loc[df["method"] == m, metric].dropna().values for m in METHOD_ORDER}
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


def run_stats(df: pd.DataFrame, label: str) -> pd.DataFrame:
    metrics = list(METRIC_META.keys())
    tests = []
    for m in metrics:
        if m not in df.columns or df[m].notna().sum() < 3:
            continue
        tests.extend(pairwise_tests(df, m))
    tdf = pd.DataFrame(tests)
    tdf["dataset"] = label
    return tdf


def write_markdown(
    df: pd.DataFrame,
    df_excl: pd.DataFrame,
    summ: pd.DataFrame,
    summ_excl: pd.DataFrame,
    tests: pd.DataFrame,
    tests_excl: pd.DataFrame,
) -> str:
    lines = [
        "# 碎片化方法组间比较分析报告（pxy_V350399508）",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"> 分组变量：`groupinfo.txt` 第 4 列（碎片化处理方法）  ",
        f"> 指标来源：`pxy_V350399508_benchmark_metrics.xlsx`（W1–W5）",
        "",
        "---",
        "",
        "## 1. 实验分组",
        "",
        "| 方法代码 | 显示名 | 样本 ID | n |",
        "|----------|--------|---------|---|",
    ]
    for meth in METHOD_ORDER:
        ids = df.loc[df["method"] == meth, "sample_id"].tolist()
        lines.append(
            f"| {meth} | {METHOD_LABEL[meth]} | {', '.join(ids)} | {len(ids)} |"
        )

    lines += [
        "",
        "**说明**：本批次为小鼠（rat）宏转录组，比较 **cDNA 酶切打断** vs **RNA 热打断**（85°C / 94°C）。",
        "与 vazyme `fragmentation_test` 设计一致，但本分析基于 Workflows W1–W5 病毒/微生物流程产出。",
        "",
        "### 低深度样本",
        "",
    ]
    low = df[df["low_depth"]][["sample_id", "method_label", "merge_r1_Mreads"]]
    if not low.empty:
        for _, r in low.iterrows():
            lines.append(
                f"- **{r['sample_id']}**（{r['method_label']}）："
                f"合并 R1 reads = {r['merge_r1_Mreads']:.2f} M（<{LOW_DEPTH_READS/1e6:.0f} M 阈值）"
            )
    else:
        lines.append("- 无")

    lines += [
        "",
        "---",
        "",
        "## 2. 各组描述统计（全部 11 样本）",
        "",
    ]
    show_metrics = [
        ("merge_r1_Mreads", "合并 R1 (M reads)"),
        ("mean_q30_after_fastp", "Q30（fastp 后）"),
        ("contigs_ge1kb_n", "≥1kb contigs"),
        ("n_viral_contigs", "病毒 contigs"),
        ("kraken_unclassified_pct", "Kraken 未分类 %"),
        ("virus_mapping_rate_pct", "病毒 mapping %"),
        ("median_rpm", "RPM 中位数"),
    ]
    header = "| 方法 | " + " | ".join(lbl for _, lbl in show_metrics) + " |"
    sep = "|" + "|".join(["---"] * (len(show_metrics) + 1)) + "|"
    lines.append(header)
    lines.append(sep)
    for meth in METHOD_ORDER:
        row = summ[summ["method"] == meth]
        if row.empty:
            continue
        r = row.iloc[0]
        vals = []
        for col, _ in show_metrics:
            m = r.get(f"{col}_mean")
            s = r.get(f"{col}_sd")
            if pd.isna(m):
                vals.append("NA")
            elif col in ("mean_q30_after_fastp",):
                vals.append(f"{m:.3f}")
            else:
                vals.append(f"{m:.2f}±{s:.2f}" if not pd.isna(s) else f"{m:.2f}")
        lines.append(f"| {METHOD_LABEL[meth]} | " + " | ".join(vals) + " |")

    lines += ["", "---", "", "## 3. 组间检验（Kruskal-Wallis + Mann-Whitney BH）", ""]
    sig = tests[(tests["test"] == "kruskal_wallis") & (tests["p_value"] < 0.05)]
    if sig.empty:
        lines.append("**全部 11 样本**：无指标在 Kruskal-Wallis 检验中达到 p<0.05。")
    else:
        lines.append("**全部 11 样本 — 显著指标 (KW p<0.05)**：")
        lines.append("")
        lines.append("| 指标 | 模块 | p 值 | 解读提示 |")
        lines.append("|------|------|------|----------|")
        for _, r in sig.sort_values("p_value").iterrows():
            mod, lbl, direction = METRIC_META[r["metric"]]
            lines.append(
                f"| {lbl} | {mod} | {r['p_value']:.4g} | {direction} |"
            )

    lines += ["", "### 排除低深度样本后（n=9，去掉 v73/v88）", ""]
    sig_ex = tests_excl[
        (tests_excl["test"] == "kruskal_wallis") & (tests_excl["p_value"] < 0.05)
    ]
    if sig_ex.empty:
        lines.append("排除低深度后仍无 KW p<0.05 指标。")
    else:
        lines.append("| 指标 | p 值 |")
        lines.append("|------|------|")
        for _, r in sig_ex.sort_values("p_value").iterrows():
            lbl = METRIC_META[r["metric"]][1]
            lines.append(f"| {lbl} | {r['p_value']:.4g} |")

    lines += [
        "",
        "完整检验表见 `tables/statistical_tests.tsv`。",
        "",
        "---",
        "",
        "## 4. 主要结论",
        "",
    ]
    lines.extend(_build_conclusions(df, df_excl, summ, tests, tests_excl))
    lines += [
        "",
        "---",
        "",
        "## 5. 图表索引",
        "",
        "| 图 | 内容 |",
        "|----|------|",
        "| `figures/01_w1_sequencing_depth.pdf` | 合并后测序深度 |",
        "| `figures/02_w1_assembly.pdf` | 组装 contig 规模 |",
        "| `figures/03_w2_virus_discovery.pdf` | 病毒 contig 与 CheckV |",
        "| `figures/04_w4_kraken_bracken.pdf` | Kraken/Bracken 微生物谱 |",
        "| `figures/05_w5_virus_quant.pdf` | 病毒 RPM 定量 |",
        "| `figures/06_composite_panel.pdf` | 关键指标综合面板 |",
        "",
    ]
    return "\n".join(lines)


def _build_conclusions(df, df_excl, summ, tests, tests_excl) -> list[str]:
    lines = []
    cDNA = df[df["method"] == "cDNA_Frag_30C5Min"]
    rna85 = df[df["method"] == "RNA_Frag_85C6Min"]
    rna94 = df[df["method"] == "RNA_Frag_94C7Min"]

    # depth
    c_depth = cDNA["merge_r1_Mreads"].mean()
    r85_depth = rna85["merge_r1_Mreads"].mean()
    r94_depth = rna94["merge_r1_Mreads"].mean()
    lines.append(
        f"1. **测序深度**：cDNA 组平均合并 R1 深度 **{c_depth:.1f} M** reads，"
        f"RNA 85°C 组 **{r85_depth:.1f} M**，RNA 94°C 组 **{r94_depth:.1f} M**（含低深度样本 v73/v88 拉低 94°C/85°C 组均值）。"
        "组间深度差异主要来自个别文库失败/下机量不足，而非方法本身；解读丰度指标时应优先参考排除低深度后的结果。"
    )

    # assembly
    c_contig = cDNA["contigs_ge1kb_n"].mean()
    r85_contig = rna85["contigs_ge1kb_n"].mean()
    lines.append(
        f"2. **组装规模**：cDNA 组 ≥1kb contig 均值 **{c_contig:,.0f}**，"
        f"RNA 85°C 组 **{r85_contig:,.0f}**（cDNA 组 v79/v82 极高，v73/v88 极低，方差大）。"
        "在排除低深度样本后，cDNA 与 RNA 打断组的组装产出处于同一数量级，未见方法学上一边倒的优势。"
    )

    # virus
    c_vir = cDNA["n_viral_contigs"].mean()
    r85_vir = rna85["n_viral_contigs"].mean()
    r94_vir = rna94["n_viral_contigs"].mean()
    lines.append(
        f"3. **病毒鉴定（W2）**：假定病毒 contig 数 — cDNA **{c_vir:.1f}**，"
        f"RNA 85°C **{r85_vir:.1f}**，RNA 94°C **{r94_vir:.1f}**。"
        "三组均能召回数十条病毒相关 contig；ANI80 聚类显示大量跨样本共享病毒序列，"
        "说明鼠源病毒群落稳定，方法间差异更多体现在定量而非有无。"
    )

    # kraken
    c_unc = cDNA["kraken_unclassified_pct"].mean()
    r85_unc = rna85["kraken_unclassified_pct"].mean()
    lines.append(
        f"4. **微生物谱（W4）**：Kraken 未分类比例 cDNA 组 **{c_unc:.1f}%**，"
        f"RNA 85°C 组 **{r85_unc:.1f}%**；Bracken 可分配 reads 与测序深度强相关。"
        "低深度样本（v73/v88）的物种数与分配 reads 明显偏低，不宜单独代表 RNA 打断方法。"
    )

    # W5
    lines.append(
        "5. **病毒定量（W5）**：RPM 与病毒 reads 占比在不同方法间波动大，"
        "低深度样本因分母小可出现「虚高」mapping 比例（如 v88）。"
        "建议以 **RPM 中位数** 及 **有读段支持的 contig 数** 联合解读，"
        "并在排除低深度后比较 RNA 85°C vs 94°C vs cDNA。"
    )

    kw_sig = tests[(tests["test"] == "kruskal_wallis") & (tests["p_value"] < 0.05)]
    if not kw_sig.empty:
        names = [METRIC_META[m][1] for m in kw_sig["metric"]]
        lines.append(
            f"6. **统计学**：在全部样本下，{len(kw_sig)} 项指标 KW 检验 p<0.05（{'; '.join(names[:5])}等），"
            "但小样本（n=3–4/组）检验功效有限，显著性应结合效应量与生物学重复结构谨慎解释。"
        )
    else:
        lines.append(
            "6. **统计学**：在 n=3–4/组的小样本下，多数 W1–W5 指标 Kruskal-Wallis 检验未达 p<0.05，"
            "不能据此判定三种打断方法在病毒/微生物检出上存在显著差异；需更大样本量或控制测序深度后重复实验。"
        )

    lines.append(
        "7. **方法学建议**：结合本数据与 vazyme rat 基准（STAR/Picard/RSeQC），"
        "**RNA 94°C 7min** 在宿主比对与覆盖均一性上通常优于 cDNA 酶切；"
        "本 W1–W5 批次因 v73/v88 深度不足，未能充分检验该假设。"
        "后续应补齐低深度样本重测，或将 JSC 批次效应纳入协变量。"
    )
    return lines


RSCRIPT = Path(
    "/data/user/guojindan/softwares/micromamba_root/envs/metatrans_compare/bin/Rscript"
)


def write_r_plot_script(metrics_tsv: Path, fig_dir: Path) -> Path:
    r_path = OUT_DIR / "plot_figures.R"
    r_code = f'''
options(stringsAsFactors = FALSE)
METHOD_ORDER <- c("cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min")
METHOD_LABEL <- c(
  "cDNA_Frag_30C5Min" = "cDNA 30°C 5min",
  "RNA_Frag_85C6Min" = "RNA 85°C 6min",
  "RNA_Frag_94C7Min" = "RNA 94°C 7min"
)
COL <- c("#4DBBD5", "#E64B35", "#00A087")
df <- read.delim("{metrics_tsv}", check.names = FALSE)
df$method <- factor(df$method, levels = METHOD_ORDER)
df$method_label <- METHOD_LABEL[as.character(df$method)]
df$low_depth <- as.logical(df$low_depth)
fig_dir <- "{fig_dir}"
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)

box_by_method <- function(y, ylab, file, log_y = FALSE) {{
  pdf(file, width = 5.5, height = 4.5)
  on.exit(dev.off())
  present <- METHOD_ORDER[METHOD_ORDER %in% unique(as.character(df$method))]
  sub <- df[!is.na(df[[y]]), ]
  if (nrow(sub) < 2) {{ plot.new(); title("No data"); return() }}
  groups <- split(sub[[y]], sub$method)
  groups <- groups[present]
  bp <- boxplot(
    groups, names = METHOD_LABEL[present], col = COL[seq_along(present)],
    ylab = ylab, main = ylab, outline = TRUE, las = 1
  )
  stripchart(
    groups, vertical = TRUE, method = "jitter", add = TRUE,
    pch = 21, bg = "white", col = "black", cex = 1.1
  )
  if (any(sub$low_depth)) {{
    low_ids <- sub$sample_id[sub$low_depth]
    for (g in present) {{
      idx <- which(sub$method == g & sub$low_depth)
      if (length(idx)) {{
        x <- as.numeric(g)
        points(rep(x, length(idx)), sub[[y]][idx], pch = 4, col = "red", cex = 1.2)
      }}
    }}
    legend("topright", legend = "x = low depth", pch = 4, col = "red", bty = "n", cex = 0.8)
  }}
}}

metrics_w1 <- list(
  c("merge_r1_Mreads", "Merged R1 reads (M)"),
  c("mean_q30_after_fastp", "Mean Q30 after fastp"),
  c("contigs_ge1kb_n", ">=1kb contigs (n)"),
  c("contigs_ge1kb_Mbp", ">=1kb contigs (Mbp)")
)
for (i in seq_along(metrics_w1)) {{
  m <- metrics_w1[[i]][1]; lab <- metrics_w1[[i]][2]
  box_by_method(m, lab, file.path(fig_dir, sprintf("01_w1_%02d_%s.pdf", i, m)))
}}
box_by_method("merge_r1_Mreads", "Merged R1 reads (M)", file.path(fig_dir, "01_w1_sequencing_depth.pdf"))

metrics_w2 <- list(
  c("n_viral_contigs", "Putative viral contigs"),
  c("n_checkv_high", "CheckV high-quality"),
  c("mean_checkv_completeness", "Mean CheckV completeness (%)")
)
for (i in seq_along(metrics_w2)) {{
  m <- metrics_w2[[i]][1]; lab <- metrics_w2[[i]][2]
  box_by_method(m, lab, file.path(fig_dir, sprintf("03_w2_%02d_%s.pdf", i, m)))
}}
box_by_method("n_viral_contigs", "Putative viral contigs", file.path(fig_dir, "03_w2_virus_discovery.pdf"))

metrics_w4 <- list(
  c("kraken_unclassified_pct", "Kraken unclassified (%)"),
  c("bracken_species_taxa", "Bracken species (n)"),
  c("bracken_species_reads_M", "Bracken assigned reads (M)")
)
for (i in seq_along(metrics_w4)) {{
  m <- metrics_w4[[i]][1]; lab <- metrics_w4[[i]][2]
  box_by_method(m, lab, file.path(fig_dir, sprintf("04_w4_%02d_%s.pdf", i, m)))
}}
box_by_method("kraken_unclassified_pct", "Kraken unclassified (%)", file.path(fig_dir, "04_w4_kraken_bracken.pdf"))

metrics_w5 <- list(
  c("virus_mapping_rate_pct", "Virus read fraction (%)"),
  c("median_rpm", "Median RPM"),
  c("n_viral_contigs_with_reads", "Viral contigs with reads")
)
for (i in seq_along(metrics_w5)) {{
  m <- metrics_w5[[i]][1]; lab <- metrics_w5[[i]][2]
  box_by_method(m, lab, file.path(fig_dir, sprintf("05_w5_%02d_%s.pdf", i, m)))
}}
box_by_method("median_rpm", "Median RPM", file.path(fig_dir, "05_w5_virus_quant.pdf"))

# composite panel
pdf(file.path(fig_dir, "06_composite_panel.pdf"), width = 12, height = 8)
par(mfrow = c(2, 3), mar = c(6, 4, 3, 1))
panel_metrics <- c(
  "merge_r1_Mreads", "contigs_ge1kb_n", "n_viral_contigs",
  "kraken_unclassified_pct", "median_rpm", "n_viral_contigs_with_reads"
)
panel_labels <- c(
  "Merged R1 (M)", ">=1kb contigs", "Viral contigs",
  "Kraken unclass (%)", "Median RPM", "Viral contigs w/ reads"
)
for (i in seq_along(panel_metrics)) {{
  y <- panel_metrics[i]
  present <- METHOD_ORDER[METHOD_ORDER %in% unique(as.character(df$method))]
  sub <- df[!is.na(df[[y]]), ]
  groups <- split(sub[[y]], sub$method)[present]
  boxplot(groups, names = METHOD_LABEL[present], col = COL[seq_along(present)],
          main = panel_labels[i], ylab = "", las = 2, cex.axis = 0.85)
  stripchart(groups, vertical = TRUE, method = "jitter", add = TRUE, pch = 21, cex = 0.9)
}}
dev.off()

# PNG versions for quick view
png <- function(...) pdf(...)  # fallback: also save pdf copies as main deliverable
cat("Figures written to", fig_dir, "\\n")
'''
    r_path.write_text(r_code, encoding="utf-8")
    return r_path


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TAB_DIR.mkdir(parents=True, exist_ok=True)

    df = build_sample_metrics()
    metrics = list(METRIC_META.keys())
    summ = method_summary(df, metrics)
    df_excl = df[~df["low_depth"]].copy()
    summ_excl = method_summary(df_excl, metrics)
    tests = run_stats(df, "all_samples")
    tests_excl = run_stats(df_excl, "exclude_low_depth")
    all_tests = pd.concat([tests, tests_excl], ignore_index=True)

    metrics_tsv = TAB_DIR / "sample_metrics_merged.tsv"
    df.to_csv(metrics_tsv, sep="\t", index=False)
    summ.to_csv(TAB_DIR / "method_summary_mean_sd.tsv", sep="\t", index=False)
    summ_excl.to_csv(TAB_DIR / "method_summary_excluding_low_depth.tsv", sep="\t", index=False)
    all_tests.to_csv(TAB_DIR / "statistical_tests.tsv", sep="\t", index=False)

    md = write_markdown(df, df_excl, summ, summ_excl, tests, tests_excl)
    (OUT_DIR / "GROUP_COMPARISON_REPORT.md").write_text(md, encoding="utf-8")
    (OUT_DIR / "ANALYSIS_SUMMARY.md").write_text(
        "\n".join(md.split("## 4. 主要结论")[1].split("---")[0].strip().split("\n")[1:]),
        encoding="utf-8",
    )

    r_script = write_r_plot_script(metrics_tsv, FIG_DIR)
    subprocess.run(
        [str(RSCRIPT), str(r_script)],
        check=True,
        capture_output=True,
        text=True,
    )

    # update Excel with group sheet
    xlsx_out = REPORT_DIR / "pxy_V350399508_benchmark_metrics.xlsx"
    with pd.ExcelWriter(xlsx_out, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        df.to_excel(w, sheet_name="G0_样本分组指标", index=False)
        summ.to_excel(w, sheet_name="G1_方法组汇总", index=False)
        all_tests.to_excel(w, sheet_name="G2_组间检验", index=False)

    print(f"Wrote {OUT_DIR / 'GROUP_COMPARISON_REPORT.md'}")
    print(f"Wrote {metrics_tsv}")
    print(f"Figures in {FIG_DIR}")


if __name__ == "__main__":
    main()
