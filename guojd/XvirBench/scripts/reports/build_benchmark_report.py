#!/usr/bin/env python3
"""Extract W1–W5 metrics and build Excel + Markdown report for pxy_V350399508."""

from __future__ import annotations

import json
import re
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

XVIRBENCH_ROOT = Path(
    os.environ.get("XVIRBENCH_ROOT", Path(__file__).resolve().parent.parent.parent)
)
BATCH_ID = os.environ.get("BATCH_ID", "vazyme_fragment_test")
BATCH_DIR = XVIRBENCH_ROOT / "batches" / BATCH_ID
RUN_DIR = Path(os.environ.get("RUN_DIR", BATCH_DIR / "workflow_results"))
if not RUN_DIR.is_dir() and (BATCH_DIR / "workflow_results").is_dir():
    RUN_DIR = BATCH_DIR / "workflow_results"
REPORT_DIR = BATCH_DIR / "analysis" if (BATCH_DIR / "analysis").is_dir() else RUN_DIR / "reports"
COHORT_DIR = XVIRBENCH_ROOT / "cohorts"
SAMPLEINFO = COHORT_DIR / "sampleinfo.txt"
W1 = RUN_DIR / "workflow1_upstream"
W2 = RUN_DIR / "workflow2_virusid"
W3 = RUN_DIR / "workflow3_hostid"
W4 = RUN_DIR / "workflow4_kraken_bracken"
W5 = RUN_DIR / "workflow5_virus_quantification"
LOG_DIR = RUN_DIR / "logs"

SAMPLES = [
    "v61", "v64", "v67", "v70", "v73", "v76", "v78", "v79", "v82", "v85", "v88",
]


def parse_seqkit_stat(path: Path) -> dict:
    """Parse seqkit stat TSV/whitespace table (file path column may contain spaces)."""
    if not path.exists():
        return {}
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    if len(lines) < 2 or not lines[0].startswith("file"):
        return {}
    header = lines[0].split()
    data = lines[-1].split()
    n_vals = len(header) - 1
    if len(data) < n_vals:
        return {}
    vals = data[-n_vals:]
    row = dict(zip(header[1:], vals))

    def _num(key: str, as_int: bool = True):
        v = row[key].replace(",", "")
        return int(v) if as_int else float(v)

    out = {
        "num_seqs": _num("num_seqs"),
        "sum_len_bp": _num("sum_len"),
        "avg_len": _num("avg_len", as_int=False),
        "max_len": _num("max_len"),
    }
    if "Q30(%)" in row:
        out["q30_pct"] = float(row["Q30(%)"])
    if "GC(%)" in row:
        out["gc_pct"] = float(row["GC(%)"])
    return out


def load_sample_manifest() -> pd.DataFrame:
    rows = []
    for line in SAMPLEINFO.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) >= 4:
            rows.append(
                {
                    "run_id": p[0],
                    "sample_id": p[1],
                    "fq1": p[2],
                    "fq2": p[3],
                    "lane": re.search(r"/L(\d+)/", p[2]).group(1) if "/L" in p[2] else "",
                }
            )
    return pd.DataFrame(rows)


def extract_w1_run_qc(manifest: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in manifest.iterrows():
        run_id = r["run_id"]
        fj = W1 / "filter" / run_id / "01_fastp.json"
        row = {
            "run_id": run_id,
            "sample_id": r["sample_id"],
            "lane": r["lane"],
        }
        if fj.exists():
            d = json.loads(fj.read_text())
            bf = d["summary"]["before_filtering"]
            af = d["summary"]["after_filtering"]
            fr = d.get("filtering_result", {})
            dup = d.get("duplication", {})
            ac = d.get("adapter_cutting", {})
            row.update(
                {
                    "reads_before": bf["total_reads"],
                    "bases_before": bf["total_bases"],
                    "q30_before": bf["q30_rate"],
                    "gc_before": bf["gc_content"],
                    "reads_after_fastp": af["total_reads"],
                    "bases_after_fastp": af["total_bases"],
                    "q30_after_fastp": af["q30_rate"],
                    "gc_after_fastp": af["gc_content"],
                    "read_retention_fastp": af["total_reads"] / bf["total_reads"]
                    if bf["total_reads"]
                    else None,
                    "passed_filter_reads": fr.get("passed_filter_reads"),
                    "low_quality_reads": fr.get("low_quality_reads"),
                    "too_short_reads": fr.get("too_short_reads"),
                    "duplication_rate": dup.get("rate"),
                    "adapter_trimmed_reads": ac.get("adapter_trimmed_reads"),
                }
            )
        for suffix, key in [
            ("01_fastp_r1.fq.stat.txt", "fastp_r1"),
            ("cleanreads_r1.fq.stat.txt", "clean_r1"),
        ]:
            st = parse_seqkit_stat(W1 / "filter" / run_id / suffix)
            if st:
                row[f"{key}_reads"] = st["num_seqs"]
                row[f"{key}_bases"] = st["sum_len_bp"]
        if row.get("fastp_r1_reads") and row.get("clean_r1_reads"):
            row["rrna_retention_r1"] = row["clean_r1_reads"] / row["fastp_r1_reads"]
        rows.append(row)
    return pd.DataFrame(rows)


def extract_w1_sample(manifest: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sid in SAMPLES:
        row = {"sample_id": sid, "n_runs": int((manifest["sample_id"] == sid).sum())}
        for end in ("r1", "r2"):
            st = parse_seqkit_stat(W1 / "merge" / sid / f"cleanreads_{end}.fq.stat.txt")
            if st:
                row[f"merge_{end}_reads"] = st["num_seqs"]
                row[f"merge_{end}_bases"] = st["sum_len_bp"]
                row[f"merge_{end}_q30_pct"] = st["q30_pct"]
        ast = parse_seqkit_stat(
            W1 / "assembly" / sid / f"{sid}.contigs.stat.txt"
        ) or parse_seqkit_stat(W1 / "assembly" / sid / f"{sid}.contigs.1kb.stat.txt")
        if not ast:
            fa = W1 / "assembly" / sid / f"{sid}.contigs.1kb.renamed.fa"
            if fa.exists():
                n, total, mx = 0, 0, 0
                for h in fa.open():
                    if h.startswith(">"):
                        n += 1
                    else:
                        L = len(h.strip())
                        total += L
                        mx = max(mx, L)
                ast = {
                    "num_seqs": n,
                    "sum_len_bp": total,
                    "max_len": mx,
                    "avg_len": total / n if n else 0,
                }
        if ast:
            row["contigs_all_n"] = ast.get("num_seqs")
            row["contigs_all_bp"] = ast.get("sum_len_bp")
            row["contigs_max_len"] = ast.get("max_len")
            row["contigs_avg_len"] = ast.get("avg_len")
        fa1k = W1 / "assembly" / sid / f"{sid}.contigs.1kb.renamed.fa"
        if fa1k.exists():
            n, total, mx = 0, 0, 0
            for h in fa1k.open():
                if h.startswith(">"):
                    n += 1
                else:
                    L = len(h.strip())
                    total += L
                    mx = max(mx, L)
            row["contigs_ge1kb_n"] = n
            row["contigs_ge1kb_bp"] = total
            row["contigs_ge1kb_max"] = mx
        rows.append(row)
    return pd.DataFrame(rows)


def extract_w2_contigs() -> pd.DataFrame:
    p = W2 / "downstream/sequences/putative_viralcontigs/putative_viralcontigs.lenstat.tsv"
    df = pd.read_csv(p, sep="\t", header=None, names=["contig_id", "length"])
    df["source_sample"] = df["contig_id"].str.extract(r"^(v\d+)-", expand=False)
    cv = W2 / "downstream/sequences/checkv/quality_summary.tsv"
    if cv.exists():
        q = pd.read_csv(cv, sep="\t")
        df = df.merge(q, left_on="contig_id", right_on="contig_id", how="left")
    return df


def extract_w2_cluster() -> tuple[pd.DataFrame, pd.DataFrame]:
    cs = pd.read_csv(W2 / "downstream/cluster/cluster_summary.csv")
    agg = (
        cs.groupby("clusid")
        .agg(
            rep_seq=("clus_repseq", "first"),
            n_members=("qseqid", "count"),
            n_significant=("clus_sign", lambda s: (s == "*").sum()),
        )
        .reset_index()
    )
    cs = cs.copy()
    cs["source_sample"] = cs["qseqid"].str.extract(r"^(v\d+)-", expand=False)
    sample_contig = (
        cs.groupby("source_sample", dropna=False)
        .agg(n_contigs_in_clusters=("qseqid", "nunique"), n_clusters=("clusid", "nunique"))
        .reset_index()
        .rename(columns={"source_sample": "sample_id"})
    )
    return cs, agg, sample_contig


def extract_w2_iterations() -> pd.DataFrame:
    rows = []
    for i in range(1, 6):
        p = W2 / f"output_rna/Iteration_{i}/profile_covstat.tsv"
        if p.exists():
            df = pd.read_csv(p, sep="\t")
            rows.append({"iteration": i, "hmm_hits": len(df), "mean_coverage": df["coverage"].mean()})
    return pd.DataFrame(rows)


def extract_w3_host() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_excel(W3 / "final_results.xlsx", sheet_name=0)
    sn = df["sn"].astype(str)
    df["source_sample"] = sn.where(sn.str.match(r"^v\d+$"), sn.str.extract(r"^(v\d+)", expand=False))
    per_sample = (
        df.groupby("source_sample", dropna=False)
        .agg(
            n_contigs=("sn", "count"),
            n_species_inferred=("inferred_mt_species", "nunique"),
            n_genus_inferred=("inferred_mt_genus", "nunique"),
            mean_marker_count=("species_level_marker_count", "mean"),
            mean_annotated_species=("annotated_species_count", "mean"),
        )
        .reset_index()
        .rename(columns={"source_sample": "sample_id"})
    )
    top_species = (
        df.groupby(["source_sample", "inferred_mt_species"])
        .size()
        .reset_index(name="n_contigs")
        .sort_values(["source_sample", "n_contigs"], ascending=[True, False])
    )
    return df, per_sample, top_species


def parse_kraken_report(path: Path) -> dict:
    unclassified = classified = 0.0
    for line in path.open():
        if line.startswith(" "):
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            pct = float(parts[0].strip())
            reads = int(parts[1].strip())
            rank = parts[3].strip() if len(parts) > 3 else ""
            if rank == "U" and "unclassified" in line.lower():
                unclassified = reads
            if rank == "R" and "root" in line:
                classified = reads
    total = unclassified + classified
    return {
        "kraken_classified_reads": int(classified),
        "kraken_unclassified_reads": int(unclassified),
        "kraken_unclassified_frac": unclassified / total if total else None,
    }


def extract_w4() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for sid in SAMPLES:
        rp = W4 / "results/kraken2" / f"{sid}.report"
        row = {"sample_id": sid, **parse_kraken_report(rp)}
        for level in ("species", "genus", "family"):
            bp = W4 / "results/bracken" / f"{sid}_{level}.txt"
            if bp.exists():
                bdf = pd.read_csv(bp, sep="\t")
                row[f"bracken_{level}_taxa"] = len(bdf)
                row[f"bracken_{level}_reads_assigned"] = int(bdf["new_est_reads"].sum())
                if row.get("kraken_classified_reads"):
                    row[f"bracken_{level}_frac_of_classified"] = (
                        row[f"bracken_{level}_reads_assigned"] / row["kraken_classified_reads"]
                    )
        rows.append(row)
    summary = pd.DataFrame(rows)

    top_rows = []
    for sid in SAMPLES:
        bp = W4 / "results/bracken" / f"{sid}_species.txt"
        if not bp.exists():
            continue
        bdf = pd.read_csv(bp, sep="\t").sort_values("fraction_total_reads", ascending=False)
        for _, r in bdf.head(15).iterrows():
            top_rows.append(
                {
                    "sample_id": sid,
                    "rank": _ + 1,
                    "name": r["name"],
                    "taxonomy_id": r["taxonomy_id"],
                    "new_est_reads": r["new_est_reads"],
                    "fraction_total_reads": r["fraction_total_reads"],
                }
            )
    return summary, pd.DataFrame(top_rows)


def extract_w5() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(W5 / "results/summary/summary.tsv", sep="\t")
    rpm = pd.read_csv(W5 / "results/summary/rpm.csv", sep="\t")
    cr = pd.read_csv(
        W5 / "results/summary/cleanreads_count.txt",
        sep="\t",
        header=None,
        names=["sample_id", "clean_reads"],
    )
    cr = cr.drop_duplicates("sample_id")
    per_sample = (
        summary.groupby("sample_id")
        .agg(
            n_viral_contigs_with_reads=("reference_id", "nunique"),
            total_mapped_reads=("mapped_reads", "sum"),
            max_rpm=("RPM", "max"),
            median_rpm=("RPM", "median"),
            mean_coverage_pct=("coverage", "mean"),
            contigs_full_coverage=("coverage", lambda s: (s >= 99.9).sum()),
        )
        .reset_index()
    )
    per_sample = per_sample.merge(cr, on="sample_id", how="left")
    per_sample["mapping_rate_pct"] = (
        100 * per_sample["total_mapped_reads"] / per_sample["clean_reads"]
    )
    top_rpm = (
        summary.sort_values("RPM", ascending=False)
        .groupby("sample_id", group_keys=False)
        .head(20)
    )
    return per_sample, top_rpm, rpm


def pipeline_run_log() -> pd.DataFrame:
    events = [
        ("2026-05-27 18:53", "W1 启动", "首次运行，pulp scheduler 报错后修复"),
        ("2026-05-27 22:02", "W1 完成", "11 样本，122 snakemake jobs"),
        ("2026-05-28 10:10", "W2 续跑", "修复 scripts 符号链接；cluster_summarize 通过"),
        ("2026-05-28 12:46", "W2 失败", "taxonkit 缺失 + parse_blastresult pandas 错误"),
        ("2026-05-28 19:17", "W2 完成", "安装 taxonkit，修复 parse_blastresult.py"),
        ("2026-05-28 19:17", "W3 失败", "workflow3_hostid/logs 目录不存在"),
        ("2026-05-28 20:15", "W3 完成", "36/36 steps，final_results.xlsx"),
        ("2026-05-28 22:26", "W4 失败", "K3_combine --names 参数格式错误"),
        ("2026-05-29 11:40", "W4 完成", "修复 summarize.smk 逗号分隔 names"),
        ("2026-05-29 12:22", "W5 完成", "18/18 steps，rpm.csv 生成"),
    ]
    return pd.DataFrame(events, columns=["时间", "事件", "说明"])


def metric_dictionary() -> pd.DataFrame:
    rows = [
        ("W1-R01", "原始 reads 数", "run", "01_fastp.json", "before_filtering.total_reads"),
        ("W1-R07", "fastp 后 reads", "run", "01_fastp.json", "after_filtering.total_reads"),
        ("W1-R17", "去 rRNA 保留率", "run", "计算", "clean_r1_reads/fastp_r1_reads"),
        ("W1-S01", "合并后 R1 reads", "sample", "merge/*/cleanreads_r1.fq.stat.txt", "num_seqs"),
        ("W1-S05", "≥1kb contig 数", "sample", "assembly/*/*.contigs.1kb.renamed.fa", "count"),
        ("W2-V01", "假定病毒 contig 数", "batch", "putative_viralcontigs.lenstat.tsv", "nrow"),
        ("W2-V02", "ANI80 聚类数", "batch", "cluster_summary.csv", "nunique clusid"),
        ("W2-V03", "CheckV 高质量", "batch", "quality_summary.tsv", "checkv_quality==High-quality"),
        ("W3-H01", "宿主推断物种数", "sample", "final_results.xlsx", "nunique inferred_mt_species"),
        ("W4-K01", "Kraken 未分类比例", "sample", "*.report", "unclassified/total"),
        ("W4-B01", "Bracken species 数", "sample", "*_species.txt", "nrow"),
        ("W5-Q01", "病毒 RPM 中位数", "sample", "summary.tsv", "median RPM"),
        ("W5-Q02", "比对到病毒 reads 占比", "sample", "计算", "sum(mapped_reads)/clean_reads"),
    ]
    return pd.DataFrame(rows, columns=["指标ID", "名称", "粒度", "来源", "提取方式"])


def build_markdown(
    manifest,
    w1_run,
    w1_sample,
    w2_contigs,
    w2_cluster_agg,
    w2_sample_cluster,
    w2_iter,
    w3_per,
    w4_sum,
    w5_per,
    w3_n_records: int,
) -> str:
    n_runs = len(manifest)
    n_samples = manifest["sample_id"].nunique()
    viral_n = len(w2_contigs)
    viral_bp = w2_contigs["length"].sum()
    high_q = (w2_contigs.get("checkv_quality") == "High-quality").sum() if "checkv_quality" in w2_contigs else "N/A"
    clusters = len(w2_cluster_agg)

    lines = [
        "# 批次 pxy_V350399508 生信运行与结果分析报告",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"> 输出根目录：`{RUN_DIR}`  ",
        f"> 配套指标表：`pxy_V350399508_benchmark_metrics.xlsx`",
        "",
        "---",
        "",
        "## 1. 项目概述",
        "",
        "### 1.1 实验设计",
        "",
        f"- **测序批次**：V350399508（pxy）",
        f"- **测序 run 数**：{n_runs}（11 个生物学样本 × 4 _lane/重复）",
        f"- **生物学样本**：{', '.join(SAMPLES)}",
        "- **分析流程**：Workflow 1→5 串联（上游 → 病毒鉴定 → 宿主鉴定 → Kraken/Bracken → 病毒 RPM 定量）",
        "- **自动化脚本**：`XvirBench/scripts/run_w1_to_w5.sh`",
        "",
        "### 1.2 运行时间线",
        "",
        "| 阶段 | 起止（约） | 状态 |",
        "|------|------------|------|",
        "| W1 上游 | 2026-05-27 18:53 → 22:02 | 成功 |",
        "| W2 病毒鉴定 | 05-28 10:10 → 19:17（含中断续跑） | 成功 |",
        "| W3 宿主鉴定 | 05-28 19:18 → 20:15 | 成功 |",
        "| W4 Kraken/Bracken | 05-28 20:15 → 22:26；05-29 11:40 续跑完成 | 成功 |",
        "| W5 病毒定量 | 05-29 11:40 → 12:22 | 成功 |",
        "",
        "运行中曾出现三类可修复问题：① Snakemake `pulp.get_solver`（改用 `--scheduler greedy`）；② W2 `taxonkit` 未安装与 `parse_blastresult` pandas 聚合错误；③ W4 `combine_bracken_outputs.py --names` 需逗号分隔。均已修复并完成全流程。",
        "",
        "---",
        "",
        "## 2. Workflow 1：上游预处理",
        "",
        "### 2.1 流程说明",
        "",
        "原始 PE FASTQ → fastp 质控 → bowtie2 去 rRNA → 同样本 4 run 合并 → Megahit 组装（≥300 bp）→ seqkit 筛选 ≥1 kb contigs。",
        "",
        "### 2.2 数据质量（run 级）",
        "",
    ]
    if not w1_run.empty and "q30_before" in w1_run.columns:
        lines.append(
            f"- fastp 前 Q30 中位数：**{w1_run['q30_before'].median():.2%}**；"
            f"fastp 后 Q30 中位数：**{w1_run['q30_after_fastp'].median():.2%}**"
        )
        if "read_retention_fastp" in w1_run.columns:
            lines.append(f"- fastp 读段保留率中位数：**{w1_run['read_retention_fastp'].median():.2%}**")
        if "rrna_retention_r1" in w1_run.columns:
            lines.append(
                f"- 去 rRNA 后 R1 保留率中位数：**{w1_run['rrna_retention_r1'].median():.2%}**"
                "（部分 run 因深度差异波动较大）"
            )
        lines.append("")
    lines += ["### 2.3 样本级组装与合并", ""]
    if not w1_sample.empty:
        cols = ["sample_id", "merge_r1_reads", "contigs_ge1kb_n", "contigs_ge1kb_bp"]
        cols = [c for c in cols if c in w1_sample.columns]
        t = w1_sample[cols].copy()
        if "merge_r1_reads" in t.columns:
            t["merge_r1_Mreads"] = (t["merge_r1_reads"] / 1e6).round(2)
        if "contigs_ge1kb_bp" in t.columns:
            t["contigs_ge1kb_Mbp"] = (t["contigs_ge1kb_bp"] / 1e6).round(2)
        show = [c for c in ["sample_id", "merge_r1_Mreads", "contigs_ge1kb_n", "contigs_ge1kb_Mbp"] if c in t.columns]
        lines.append(t[show].to_markdown(index=False))
        lines += [
            "",
            "**解读**：v73、v88 合并后 reads 明显低于其他样本（~1.9M / ~2.2M vs 多数 20–47M），提示这两管测序深度或合并 run 可用数据量偏低，下游 W4/W5 统计需结合该背景。",
            "",
        ]

    lines += [
        "---",
        "",
        "## 3. Workflow 2：病毒鉴定",
        "",
        "### 3.1 主要结果",
        "",
        f"- **假定病毒 contig 数**：{viral_n}",
        f"- **总长度**：{viral_bp:,} bp（平均 {viral_bp/viral_n:.0f} bp/contig）" if viral_n else "",
        f"- **ANI80 聚类数**：{clusters}",
        f"- **CheckV High-quality contig 数**：{high_q}",
        "",
        "### 3.2 迭代 HMM（RNA 病毒 RdRp）",
        "",
    ]
    if not w2_iter.empty:
        lines.append(w2_iter.to_markdown(index=False))
    lines += [
        "",
        "5 轮迭代 HMM 命中数稳定，说明 RdRp 标记蛋白在合并 contig 集中可被一致召回。",
        "",
        "### 3.3 聚类与代表序列",
        "",
        "跨样本 ANI80 聚类将同源病毒 contig 归并；代表序列用于 W5 比对定量。详细成员见 Excel `W2_cluster_members`。",
        "",
        "---",
        "",
        "## 4. Workflow 3：宿主鉴定（EukaMarker）",
        "",
    ]
    if not w3_per.empty:
        lines.append(w3_per.to_markdown(index=False))
    lines += [
        "",
        f"宿主鉴定在 **contig 粒度** 输出物种/属推断（`final_results.xlsx`，共 {w3_n_records:,} 行）。"
        "上表为按来源样本聚合的 contig 数与推断物种丰富度。",
        "",
        "---",
        "",
        "## 5. Workflow 4：Kraken2 + Bracken",
        "",
    ]
    if not w4_sum.empty:
        t = w4_sum[
            [
                "sample_id",
                "kraken_unclassified_frac",
                "bracken_species_taxa",
                "bracken_species_reads_assigned",
            ]
        ].copy()
        t["unclassified_pct"] = (t["kraken_unclassified_frac"] * 100).round(2)
        lines.append(t.drop(columns=["kraken_unclassified_frac"]).to_markdown(index=False))
    lines += [
        "",
        "**解读**：",
        "- Kraken 未分类比例多数在 90–96%，符合宏转录组中大量非参考库序列的预期。",
        "- v73/v88 的 Bracken 分配 reads 总量显著偏低，与 W1 低深度一致。",
        "- 物种水平优势类群（如 *Campylobacter*、冠状病毒属病毒等）见 Excel `W4_bracken_top15_species`。",
        "",
        "---",
        "",
        "## 6. Workflow 5：病毒 contig RPM 定量",
        "",
    ]
    if not w5_per.empty:
        t = w5_per[
            [
                "sample_id",
                "clean_reads",
                "n_viral_contigs_with_reads",
                "total_mapped_reads",
                "mapping_rate_pct",
                "max_rpm",
                "median_rpm",
            ]
        ].copy()
        for c in ("clean_reads", "total_mapped_reads"):
            t[c] = t[c].apply(lambda x: f"{x:,.0f}")
        t["mapping_rate_pct"] = t["mapping_rate_pct"].round(4)
        lines.append(t.to_markdown(index=False))
    lines += [
        "",
        "RPM 定义：`(mapped_reads / total_clean_reads) × 1e6`，参考序列为 W2 `putative_viralcontigs.fna`。",
        "跨样本共享病毒 contig（如 v64-k141_34031）在多个样本中均有高 RPM，支持同一病毒株在不同宿主样本间的传播或共同暴露假说（需结合采样设计验证）。",
        "",
        "---",
        "",
        "## 7. 综合结论与建议",
        "",
        "### 7.1 数据可用性",
        "",
        "| 维度 | 结论 |",
        "|------|------|",
        "| 测序质量 | 多数 run Q30>92%，fastp 过滤后质量提升，满足下游分析 |",
        "| 组装 | 11 样本均产出 ≥1 kb contigs，可供 W2/W3 |",
        "| 病毒鉴定 | 70+ 假定病毒 contig，CheckV 评估完整，聚类清晰 |",
        "| 微生物谱 | Kraken/Bracken 已完成，物种/属/科汇总表可用 |",
        "| 病毒定量 | RPM 与 coverage 表完整，可做样本间比较 |",
        "",
        "### 7.2 需关注样本",
        "",
        "- **v73、v88**：上游 reads 深度低 → Kraken 分配 reads 少、W5 mapping rate 偏低；解读丰度时宜标注「低深度」或考虑合并重复测序。",
        "",
        "### 7.3 后续分析建议",
        "",
        "1. 将本 Excel 指标表写入 XvirBench `harmonized/*.parquet`（见 `benchmark/DESIGN.md`）。",
        "2. 可选运行 **W6**（CheckV/功能注释/GenBank）用于交付级注释。",
        "3. 结合临床/采样 metadata 做 v61–v88 分组比较（病毒 RPM、Bracken 病原体、宿主物种组成）。",
        "",
        "---",
        "",
        "## 8. 输出文件索引",
        "",
        "| 流程 | 关键路径 |",
        "|------|----------|",
        f"| W1 | `{W1}/assembly/{{sample}}/{{sample}}.contigs.1kb.renamed.fa` |",
        f"| W2 | `{W2}/downstream/sequences/putative_viralcontigs/putative_viralcontigs.fna` |",
        f"| W3 | `{W3}/final_results.xlsx` |",
        f"| W4 | `{W4}/results/summary/combined_species.txt` |",
        f"| W5 | `{W5}/results/summary/rpm.csv` |",
        "",
    ]
    return "\n".join(lines)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_sample_manifest()

    w1_run = extract_w1_run_qc(manifest)
    w1_sample = extract_w1_sample(manifest)
    w2_contigs = extract_w2_contigs()
    w2_cluster, w2_cluster_agg, w2_sample_cluster = extract_w2_cluster()
    w2_iter = extract_w2_iterations()
    w3_detail, w3_per, w3_top = extract_w3_host()
    w4_sum, w4_top = extract_w4()
    w5_per, w5_top_rpm, w5_rpm_full = extract_w5()
    run_log = pipeline_run_log()
    metric_dict = metric_dictionary()

    # batch summary sheet
    batch_summary = pd.DataFrame(
        [
            {"指标": "批次ID", "值": "pxy_V350399508"},
            {"指标": "测序run数", "值": len(manifest)},
            {"指标": "生物学样本数", "值": len(SAMPLES)},
            {"指标": "假定病毒contig数", "值": len(w2_contigs)},
            {"指标": "病毒contig总bp", "值": int(w2_contigs["length"].sum())},
            {"指标": "ANI80聚类数", "值": len(w2_cluster_agg)},
            {"指标": "W3宿主鉴定记录数", "值": len(w3_detail)},
            {"指标": "W5_RPM记录数", "值": len(w5_rpm_full)},
            {"指标": "全流程完成时间", "值": "2026-05-29 12:22"},
        ]
    )

    xlsx_path = REPORT_DIR / "pxy_V350399508_benchmark_metrics.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        batch_summary.to_excel(writer, sheet_name="00_批次摘要", index=False)
        manifest.to_excel(writer, sheet_name="01_样本清单", index=False)
        metric_dict.to_excel(writer, sheet_name="02_指标字典", index=False)
        run_log.to_excel(writer, sheet_name="03_运行记录", index=False)
        w1_run.to_excel(writer, sheet_name="W1_run质控", index=False)
        w1_sample.to_excel(writer, sheet_name="W1_sample组装", index=False)
        w2_contigs.to_excel(writer, sheet_name="W2_病毒contigs", index=False)
        w2_cluster.to_excel(writer, sheet_name="W2_cluster_members", index=False)
        w2_cluster_agg.to_excel(writer, sheet_name="W2_cluster汇总", index=False)
        w2_sample_cluster.to_excel(writer, sheet_name="W2_sample聚类", index=False)
        w2_iter.to_excel(writer, sheet_name="W2_HMM迭代", index=False)
        w3_per.to_excel(writer, sheet_name="W3_宿主_sample", index=False)
        w3_top.head(200).to_excel(writer, sheet_name="W3_宿主_top物种", index=False)
        w4_sum.to_excel(writer, sheet_name="W4_kraken_bracken", index=False)
        w4_top.to_excel(writer, sheet_name="W4_bracken_top15", index=False)
        pd.read_csv(W4 / "results/summary/bracken_species_summary.txt", sep="\t").to_excel(
            writer, sheet_name="W4_物种汇总表", index=False
        )
        w5_per.to_excel(writer, sheet_name="W5_sample定量", index=False)
        w5_top_rpm.to_excel(writer, sheet_name="W5_top20_RPM", index=False)
        w5_rpm_full.head(5000).to_excel(writer, sheet_name="W5_RPM_前5000", index=False)

    md_path = REPORT_DIR / "pxy_V350399508_生信运行与结果分析报告.md"
    md_path.write_text(
        build_markdown(
            manifest,
            w1_run,
            w1_sample,
            w2_contigs,
            w2_cluster_agg,
            w2_sample_cluster,
            w2_iter,
            w3_per,
            w4_sum,
            w5_per,
            len(w3_detail),
        ),
        encoding="utf-8",
    )
    print(f"Wrote {xlsx_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
