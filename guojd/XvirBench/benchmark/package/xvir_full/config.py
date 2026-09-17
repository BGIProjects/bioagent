"""Paths, palettes, workflow contracts, and metric dictionary."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PACKAGE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = PACKAGE_DIR.parent
DEFAULT_WORKFLOWS_ROOT = Path("/data/user/guojindan/Projects/Workflows")
DEFAULT_XVIRBENCH_ROOT = Path("/data/user/guojindan/Projects/XvirMind/XvirBench")
DEFAULT_RSCRIPT = Path(
    "/data/user/guojindan/softwares/micromamba_root/envs/metagenome/bin/Rscript"
)

# Okabe–Ito (colorblind-safe, common in Nature/Science figures)
OKABE_ITO = [
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#000000",
]

METHOD_LABEL = {
    "cDNA_Frag_30C5Min": "cDNA 30°C 5 min",
    "RNA_Frag_85C6Min": "RNA 85°C 6 min",
    "RNA_Frag_94C7Min": "RNA 94°C 7 min",
}
METHOD_ORDER = ["cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min"]
METHOD_COLORS = {
    "cDNA_Frag_30C5Min": "#E69F00",
    "RNA_Frag_85C6Min": "#0072B2",
    "RNA_Frag_94C7Min": "#009E73",
}
HOST_LABEL = {"rat": "rat", "tick": "tick", "mosquito": "mosquito", "human": "human"}

GROUP_CANDIDATES = (
    "method",
    "host",
    "group",
    "treatment",
    "condition",
    "library",
    "batch",
)
MISSING_TOKENS = {"", "na", "nan", "none", "null", ".", "-", "NA", "NaN", "None"}

# Post-rRNA / merged R1 below this (reads) is flagged low-depth
LOW_DEPTH_R1_READS = 5_000_000

ID_COLUMNS = {
    "sample_id",
    "run_id",
    "v_id",
    "sn",
    "lane",
    "contig_id",
    "reference_id",
    "clusid",
    "taxonomy_id",
    "name",
    "source_sample",
}


@dataclass(frozen=True)
class WorkflowSpec:
    key: str
    short: str
    title: str
    dirname: str
    extractor_rel: str
    markers: tuple[str, ...]
    extract_tables: tuple[str, ...]
    sample_metrics: tuple[str, ...]
    skip_biology: str
    default_report: bool = True


WORKFLOWS: tuple[WorkflowSpec, ...] = (
    WorkflowSpec(
        key="workflow1_upstream",
        short="W1",
        title="Upstream QC and assembly",
        dirname="workflow1_upstream",
        extractor_rel="workflow1_upstream/scripts/extract_results.py",
        markers=("filter", "merge", "assembly"),
        extract_tables=("run_qc", "samples", "summary"),
        sample_metrics=(
            "merge_r1_reads",
            "merge_r1_bases",
            "merge_r1_q30_pct",
            "contigs_all_n",
            "contigs_all_bp",
            "contigs_avg_len",
            "contigs_ge1kb_n",
            "contigs_ge1kb_bp",
        ),
        skip_biology="缺少 W1，无法判断测序深度、质量和组装产量。",
    ),
    WorkflowSpec(
        key="workflow2_virusid",
        short="W2",
        title="Virus identification",
        dirname="workflow2_virusid",
        extractor_rel="workflow2_virusid/scripts/extract_results.py",
        markers=("downstream", "summary", "output_rna"),
        extract_tables=("contigs", "cluster_members", "cluster_summary", "sample_cluster", "hmm_iterations"),
        sample_metrics=("n_contigs_in_clusters", "n_clusters"),
        skip_biology="缺少 W2，无法报告假定病毒 contig、CheckV 质量与聚类。",
    ),
    WorkflowSpec(
        key="workflow3_hostid",
        short="W3",
        title="Host identification",
        dirname="workflow3_hostid",
        extractor_rel="workflow3_hostid/scripts/extract_results.py",
        markers=("by_sample_v3", "reports", "EukaMarker_Mapping"),
        extract_tables=("host_contig", "host_sample", "host_top_species", "marker_coverage"),
        sample_metrics=("n_species_inferred", "n_genus_inferred", "n_contigs", "mean_marker_count"),
        skip_biology="缺少 W3，无法报告线粒体标记的宿主推断。",
    ),
    WorkflowSpec(
        key="workflow4_kraken_bracken",
        short="W4",
        title="Microbial profile (Kraken2/Bracken)",
        dirname="workflow4_kraken_bracken",
        extractor_rel="workflow4_kraken_bracken/scripts/extract_results.py",
        markers=("results/kraken2", "results/bracken"),
        extract_tables=("sample_qc", "bracken_top15_species", "combined_species"),
        sample_metrics=(
            "kraken_unclassified_frac",
            "kraken_classified_reads",
            "bracken_species_taxa",
            "bracken_species_reads_assigned",
        ),
        skip_biology="缺少 W4，无法报告分类/未分类比例与分类单元丰度。",
    ),
    WorkflowSpec(
        key="workflow5_virus_quantification",
        short="W5",
        title="Virus quantification (RPM)",
        dirname="workflow5_virus_quantification",
        extractor_rel="workflow5_virus_quantification/scripts/extract_results.py",
        markers=("results/summary", "results/coverage"),
        extract_tables=("sample_summary", "rpm_full", "top20_rpm", "cleanreads"),
        sample_metrics=(
            "n_viral_contigs_with_reads",
            "total_mapped_reads",
            "max_rpm",
            "median_rpm",
            "mapping_rate_pct",
            "mean_coverage_pct",
        ),
        skip_biology="缺少 W5，无法比较病毒 RPM 与比对率。",
    ),
    WorkflowSpec(
        key="workflow6_virus_annotation",
        short="W6",
        title="Virus annotation",
        dirname="workflow6_virus_annotation",
        extractor_rel="workflow6_virus_annotation/scripts/extract_results.py",
        markers=("results/checkv", "results/summary", "results/function"),
        extract_tables=("checkv", "annotation_summary", "strategy", "consistency"),
        sample_metrics=(),
        skip_biology="缺少 W6，无法报告基因/AMG/分类一致性注释。",
    ),
    WorkflowSpec(
        key="workflow7_fragmentation_benchmark",
        short="W7",
        title="RNA vs cDNA fragmentation benchmark",
        dirname="workflow7_fragmentation_benchmark",
        extractor_rel="workflow7_fragmentation_benchmark/scripts/extract_results.py",
        markers=("summary", "metrics"),
        extract_tables=("comparison", "method_summary"),
        sample_metrics=("uniquely_mapped_pct", "multi_mapped_pct", "percent_duplication", "chimeric_rate_pct"),
        skip_biology="缺少 W7，无法报告 STAR/Picard 建库方法学指标。",
        default_report=False,
    ),
)

WF_BY_KEY = {w.key: w for w in WORKFLOWS}
WF_BY_SHORT = {w.short: w for w in WORKFLOWS}

# Catalog IDs from Workflows/docs/WORKFLOW_SUMMARY.md
CATALOG_COUNTS = {"W1": 25, "W2": 18, "W3": 11, "W4": 8, "W5": 11, "W6": 10, "W7": 21}

METRIC_LABELS = {
    "merge_r1_reads": "Merged R1 reads",
    "merge_r1_bases": "Merged R1 bases",
    "merge_r1_q30_pct": "Merged R1 Q30 (%)",
    "read_retention_fastp": "fastp read retention",
    "q30_after_fastp": "fastp Q30",
    "duplication_rate": "Duplication rate",
    "rrna_retention_r1": "rRNA-depletion R1 retention",
    "contigs_all_n": "Contigs (all)",
    "contigs_ge1kb_n": "Contigs ≥1 kb (n)",
    "contigs_ge1kb_bp": "Contigs ≥1 kb (bp)",
    "contigs_avg_len": "Mean contig length (bp)",
    "n_putative_viral_contigs": "Putative viral contigs",
    "n_contigs_in_clusters": "Viral contigs in ANI80 clusters",
    "n_clusters": "ANI80 clusters",
    "n_high_quality": "CheckV High-quality contigs",
    "n_species_inferred": "Inferred host species (n)",
    "n_genus_inferred": "Inferred host genera (n)",
    "kraken_unclassified_frac": "Kraken unclassified fraction",
    "bracken_species_taxa": "Bracken species taxa (n)",
    "bracken_species_reads_assigned": "Bracken species assigned reads",
    "n_viral_contigs_with_reads": "Viral contigs with mapped reads",
    "max_rpm": "Max viral RPM",
    "median_rpm": "Median viral RPM",
    "mapping_rate_pct": "Reads mapped to viral contigs (%)",
    "mean_coverage_pct": "Mean viral coverage (%)",
    "uniquely_mapped_pct": "STAR uniquely mapped (%)",
    "percent_duplication": "Picard duplication (%)",
    "chimeric_rate_pct": "Chimeric rate (%)",
}


def default_rscript() -> Optional[Path]:
    candidates = [
        DEFAULT_RSCRIPT,
        Path("/data/user/guojindan/softwares/micromamba_root/envs/rnaseq/bin/Rscript"),
        Path("/data/user/guojindan/softwares/micromamba_root/envs/irma-env/bin/Rscript"),
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None
