#!/usr/bin/env python3
"""Generate docs/HARMONIZED_METRICS_REFERENCE.md from harmonized TSV outputs."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WF_SUMMARY = ROOT.parent / "Workflows" / "docs" / "WORKFLOW_SUMMARY.md"

COL_MAP = {
    "reads_before": "W1-R01",
    "bases_before": "W1-R02",
    "q30_before": "W1-R04",
    "reads_after_fastp": "W1-R07",
    "bases_after_fastp": "W1-R08",
    "q30_after_fastp": "W1-R09",
    "passed_filter_reads": "W1-R10",
    "low_quality_reads": "W1-R11",
    "duplication_rate": "W1-R12",
    "adapter_trimmed_reads": "W1-R13",
    "fastp_r1_reads": "W1-R14",
    "clean_r1_reads": "W1-R15",
    "clean_r1_bases": "W1-R16",
    "rrna_retention_r1": "W1-R17",
    "merge_r1_reads": "W1-R18",
    "merge_r2_reads": "W1-R19",
    "merge_r1_q30_pct": "W1-R09",
    "contigs_all_n": "W1-R20",
    "contigs_all_bp": "W1-R21",
    "contigs_avg_len": "W1-R22",
    "contigs_max_len": "W1-R23",
    "contigs_ge1kb_n": "W1-R24",
    "contigs_ge1kb_bp": "W1-R25",
    "n_contigs": "W2-V01",
    "n_clusters": "W2-V10",
    "length": "W2-V03",
    "contig_length": "W2-V03",
    "checkv_quality": "W2-V05",
    "completeness": "W2-V04",
    "contamination": "W2-V06",
    "viral_genes": "W2-V07",
    "host_genes": "W2-V07",
    "miuvig_quality": "W2-V05",
    "clusid": "W2-V11",
    "rep_seq": "W2-V11",
    "n_members": "W2-V10",
    "n_significant": "W2-V10",
    "inferred_mt_species": "W3-H04",
    "inferred_mt_genus": "W3-H05",
    "species_level_marker_count": "W3-H06",
    "annotated_species_count": "W3-H07",
    "known_species": "W3-H08",
    "COI_pident": "W3-H09",
    "CYTB_pident": "W3-H09",
    "ND1_pident": "W3-H09",
    "COI_species": "W3-H09",
    "CYTB_species": "W3-H09",
    "ND1_species": "W3-H09",
    "notbest_genus": "W3-H10",
    "n_species_inferred": "W3-H04",
    "n_genus_inferred": "W3-H05",
    "n_records": "W3-H07",
    "kraken_unclassified_frac": "W4-K01",
    "kraken_classified_reads": "W4-K02",
    "kraken_unclassified_reads": "W4-K01",
    "bracken_species_taxa": "W4-K08",
    "bracken_species_reads_assigned": "W4-K03",
    "bracken_species_frac_of_classified": "W4-K04",
    "bracken_genus_taxa": "W4-K08",
    "bracken_genus_reads_assigned": "W4-K03",
    "bracken_family_taxa": "W4-K08",
    "new_est_reads": "W4-K03",
    "fraction_total_reads": "W4-K04",
    "name": "W4-K05",
    "taxonomy_id": "W4-K05",
    "rank": "W4-K05",
    "n_viral_contigs_with_reads": "W5-Q09",
    "total_mapped_reads": "W5-Q02",
    "max_rpm": "W5-Q10",
    "median_rpm": "W5-Q08",
    "mean_coverage_pct": "W5-Q04",
    "clean_reads": "W5-Q01",
    "mapping_rate_pct": "W5-Q02",
    "reference_id": "W5-Q11",
    "mapped_reads": "W5-Q02",
    "covbases": "W5-Q03",
    "coverage": "W5-Q04",
    "mean_depth": "W5-Q05",
    "mean_baseq": "W5-Q06",
    "mean_mapq": "W5-Q07",
    "RPM": "W5-Q08",
    "total_clean_reads": "W5-Q01",
    "total_reads_x": "W7-F01",
    "uniquely_mapped_pct": "W7-F02",
    "multi_mapped_pct": "W7-F03",
    "unmapped_pct": "W7-F04",
    "median_5prime_to_3prime_bias": "W7-F05",
    "median_cv_coverage": "W7-F06",
    "percent_duplication": "W7-F07",
    "total_reads_y": "W7-F08",
    "chimeric_reads": "W7-F09",
    "chimeric_rate_pct": "W7-F10",
    "splice_junctions_total": "W7-F11",
    "splice_junctions_known": "W7-F12",
    "splice_junctions_novel": "W7-F13",
    "method": "W7-F14",
}

COL_DESC = {
    "batch_id": "XvirBench 批次 ID",
    "sample_id": "生物学样本 ID（v61–v120）",
    "run_id": "测序 run ID（lane 级）",
    "global_sample_id": "跨批次全局样本 ID（batch_id__sample_id）",
    "extracted_at": "指标抽取 UTC 时间戳",
    "host_group": "宿主分组（rat / tick / mosquito）；W2/W5/W7 按宿主参考分别计算",
    "source_sample": "contig 来源样本 ID",
    "sn": "W3 宿主鉴定内部样本编号（同 sample_id）",
    "n_runs": "该样本合并的 sequencing run 数（通常 4）",
    "run_ids": "合并的 run ID 列表",
    "fastp_json_exists": "fastp JSON 是否存在（QC 门禁）",
    "cleanreads_stat_exists": "clean reads stat 文件是否存在",
    "merge_r1_fq_path": "合并后 R1 FASTQ 路径",
    "assembly_fa_path": "Megahit 组装 FASTA 路径",
    "assembly_fa_1kb_renamed_path": "≥1 kb 重命名 contig FASTA 路径",
    "gene_count": "CheckV 预测基因总数",
    "completeness_method": "CheckV 完整度估算方法",
    "kmer_freq": "CheckV k-mer 频率",
    "warnings": "CheckV 质量警告",
    "proviral_length": "前病毒区段长度（bp）",
    "provirus": "是否为前病毒（CheckV provirus 标记）",
    "start_pos": "RPM 比对起始位置",
    "end_pos": "RPM 比对终止位置",
    "contig_id": "病毒 contig 唯一 ID",
    "q20_before": "原始 Q20 比例（fastp before_filtering）",
    "gc_before": "原始 GC 含量",
    "q20_after_fastp": "fastp 后 Q20 比例",
    "gc_after_fastp": "fastp 后 GC 含量",
    "read_retention_fastp": "fastp 读段保留率（after/before reads）",
    "too_short_reads": "过短 reads 剔除数",
    "rrna_retention_r2": "R2 去 rRNA 保留率",
    "merge_r1_bases": "合并后 R1 碱基数",
    "merge_r1_gc_pct": "合并后 R1 GC 含量（%）",
    "merge_r2_bases": "合并后 R2 碱基数",
    "merge_r2_q30_pct": "合并后 R2 Q30（%）",
    "merge_r2_gc_pct": "合并后 R2 GC 含量（%）",
    "contigs_ge1kb_avg_len": "≥1 kb contig 平均长度",
    "contigs_ge1kb_max_len": "≥1 kb contig 最长序列",
    "contigs_min_len": "组装最短 contig 长度",
    "merged_reads_r1": "汇总表：合并 R1 reads",
    "merged_reads_r2": "汇总表：合并 R2 reads",
    "merged_read_pairs": "汇总表：read pairs 数",
    "merged_reads_total": "汇总表：双端总 reads",
    "merged_bases_total": "汇总表：双端总碱基",
}

ANALYSIS_METRICS = {
    "workflow1": ["merge_r1_reads", "merge_r1_q30_pct", "rrna_retention_r1", "contigs_ge1kb_n"],
    "workflow2": ["n_contigs", "n_clusters"],
    "workflow3": ["n_species_inferred", "n_genus_inferred"],
    "workflow4": ["kraken_unclassified_frac", "bracken_species_taxa", "bracken_species_reads_assigned"],
    "workflow5": ["mapping_rate_pct", "median_rpm", "n_viral_contigs_with_reads", "mean_coverage_pct"],
    "workflow7": [
        "uniquely_mapped_pct",
        "multi_mapped_pct",
        "median_cv_coverage",
        "percent_duplication",
        "chimeric_rate_pct",
    ],
}

WORKFLOWS = [
    ("workflow1", "W1 上游 QC 与组装", "complete", 60, [
        ("qc_upstream_run.tsv", "run", "240 run（60 样本 × 4 lane）"),
        ("qc_upstream_sample.tsv", "sample", "60 样本"),
        ("qc_upstream_summary.tsv", "sample", "60 样本（精简汇总）"),
    ]),
    ("workflow2", "W2 病毒鉴定", "complete", 60, [
        ("virus_identification_sample.tsv", "sample", "60 样本"),
        ("virus_identification_contigs.tsv", "contig", "646 条假定病毒 contig"),
        ("virus_identification_clusters.tsv", "cluster", "72 个 ANI80 聚类"),
    ]),
    ("workflow3", "W3 宿主鉴定", "complete", 60, [
        ("host_identification_sample.tsv", "sample", "60 样本"),
        ("host_identification_contig.tsv", "sample", "60 样本（EukaMarker 汇总行）"),
    ]),
    ("workflow4", "W4 Kraken/Bracken 微生物谱", "complete", 60, [
        ("microbiome_bracken_sample.tsv", "sample", "60 样本"),
        ("microbiome_bracken_top15.tsv", "sample×taxon", "895 行（每样本 Top15 物种）"),
    ]),
    ("workflow5", "W5 病毒 RPM 定量", "complete", 60, [
        ("virus_quantification_sample.tsv", "sample", "60 样本"),
        ("virus_quantification_rpm.tsv", "sample×ref", "695 行（样本 × 病毒 contig）"),
    ]),
    ("workflow6", "W6 病毒注释", "skipped", 0, []),
    ("workflow7", "W7 建库方法学 benchmark", "complete", 60, [
        ("fragmentation_benchmark.tsv", "sample", "60 样本"),
        ("fragmentation_method_summary.tsv", "method×host", "8 行（method × 宿主分层汇总）"),
    ]),
]


def load_metric_dict(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (W[1-7]-[A-Z]\d+) \| (.+?) \| (.+?) \|", line)
        if m:
            mid, name, gran = m.group(1), m.group(2).strip(), m.group(3).strip()
            out[mid] = {"name": name, "granularity": gran}
    return out


def stat_series(s: pd.Series) -> str:
    if s.dtype == object or s.dtype.name == "bool":
        vals = s.dropna().astype(str).unique()[:3]
        return f"示例: {', '.join(vals)}" if len(vals) else "—"
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return "—"
    return f"min={s.min():.4g}, median={s.median():.4g}, max={s.max():.4g} (n={len(s)})"


def metric_info(col: str, metric_dict: dict, default_gran: str) -> tuple[str, str, str]:
    mid = COL_MAP.get(col, "—")
    if mid != "—" and mid in metric_dict:
        return mid, metric_dict[mid]["name"], metric_dict[mid]["granularity"]
    if col in COL_DESC:
        return mid, COL_DESC[col], default_gran
    return mid, "—", default_gran


def generate(batch_id: str, output: Path) -> None:
    harm = ROOT / "batches" / batch_id / "harmonized"
    metric_dict = load_metric_dict(WF_SUMMARY)
    lines: list[str] = []

    lines += [
        f"# XvirBench Harmonized 指标参考（{batch_id}）",
        "",
        f"> 生成日期：{date.today()}  ",
        f"> 示例批次：`{batch_id}`  ",
        "> 指标字典：[WORKFLOW_SUMMARY.md](../../Workflows/docs/WORKFLOW_SUMMARY.md)  ",
        "> Excel 对照：[vazyme_benchmark_metrics.xlsx](vazyme_benchmark_metrics.xlsx)  ",
        f"> harmonized 路径：`batches/{batch_id}/harmonized/workflowN/`",
        "",
        "---",
        "",
        "## 1. 项目摘要",
        "",
        "| 项目 | 值 |",
        "| --- | --- |",
        f"| 批次 ID | `{batch_id}` |",
        "| 抽取命令 | `python3 scripts/extract_metrics.py --batch-id "
        f"{batch_id} --all` |",
        "",
        "### 1.1 流程完成状态",
        "",
        "| Workflow | harmonized 目录 | 状态 | 完成样本 | 输出表数 |",
        "| --- | --- | --- | --- | --- |",
    ]

    for wf_dir, title, status, n, tables in WORKFLOWS:
        st = "✅ 已完成" if status == "complete" else "⏸ 未运行"
        lines.append(
            f"| {title.split()[0]} | `{wf_dir}/` | {st} | {n if n else '—'} | {len(tables)} |"
        )

    lines += [
        "",
        "### 1.2 与 Excel 交付表对应关系",
        "",
        "| Excel sheet | harmonized 对应 |",
        "| --- | --- |",
        "| `03_主指标表` | 各 workflow sample 表 join |",
        "| `W1_上游QC` | `workflow1/qc_upstream_sample.tsv` |",
        "| `W2_病毒鉴定` | `workflow2/virus_identification_sample.tsv` |",
        "| `W2_病毒contigs` | `workflow2/virus_identification_contigs.tsv` |",
        "| `W3_宿主鉴定` | `workflow3/host_identification_contig.tsv` |",
        "| `W4_Kraken_Bracken` | `workflow4/microbiome_bracken_sample.tsv` |",
        "| `W5_病毒定量` | `workflow5/virus_quantification_sample.tsv` |",
        "| `W5_RPM明细` | `workflow5/virus_quantification_rpm.tsv` |",
        "| `W7_建库benchmark` | `workflow7/fragmentation_benchmark.tsv` |",
        "",
        "---",
        "",
    ]

    sec = 2
    for wf_dir, title, status, _n, tables in WORKFLOWS:
        if status != "complete":
            lines += [f"## {sec}. {title}", "", "本批次 **未运行** W6，无 harmonized 输出。", "", "---", ""]
            sec += 1
            continue

        lines += [
            f"## {sec}. {title}",
            "",
            f"**目录**：`batches/{batch_id}/harmonized/{wf_dir}/`",
            "",
            "### 输出文件",
            "",
            "| 文件 | 粒度 | 行数 |",
            "| --- | --- | --- |",
        ]
        for fname, gran, note in tables:
            fpath = harm / wf_dir / fname
            nrows = sum(1 for _ in open(fpath)) - 1 if fpath.exists() else 0
            lines.append(f"| `{fname}` | {gran} | {nrows}（{note}） |")

        lines += ["", "### 字段说明", ""]
        for fname, gran, _ in tables:
            fpath = harm / wf_dir / fname
            if not fpath.exists():
                continue
            df = pd.read_csv(fpath, sep="\t")
            lines += [
                f"#### `{fname}`",
                "",
                "| 列名 | metric_id | 指标含义 | 粒度 | 本批次数值范围 |",
                "| --- | --- | --- | --- | --- |",
            ]
            skip_stat = {"run_ids", "extracted_at", "global_sample_id", "batch_id"}
            for col in df.columns:
                mid, meaning, g = metric_info(col, metric_dict, gran)
                rng = "—" if col in skip_stat else stat_series(df[col])
                lines.append(f"| `{col}` | {mid} | {meaning} | {g} | {rng} |")
            lines.append("")

        am = ANALYSIS_METRICS.get(wf_dir, [])
        if am:
            lines += [
                "### 分组比较分析使用的核心指标",
                "",
                "用于 `scripts/analysis/run_analysis.py`：",
                "",
            ]
            for c in am:
                mid, meaning, _ = metric_info(c, metric_dict, "sample")
                lines.append(f"- `{c}`（{mid}）：{meaning}")
            lines.append("")

        lines += ["---", ""]
        sec += 1

    lines += [
        f"## {sec}. 附录：尚未抽取的 WORKFLOW_SUMMARY 指标",
        "",
        "| Workflow | 未抽取示例 |",
        "| --- | --- |",
        "| W1 | W1-R03 Q20、部分 run 级 seqkit 字段 |",
        "| W2 | W2-V08–V18 HMM/BLAST/迭代详情 |",
        "| W3 | W3-H01–H03 标记基因深度 |",
        "| W4 | W4-K06–K07 跨样本矩阵 |",
        "| W6 | 全部（本批次未运行） |",
        "| W7 | W7-F15–F21 Preseq、gene body |",
        "",
    ]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch-id", default="vazyme_fragment_test")
    p.add_argument("--output", type=Path, default=ROOT / "docs" / "HARMONIZED_METRICS_REFERENCE.md")
    args = p.parse_args()
    generate(args.batch_id, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
