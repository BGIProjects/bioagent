#!/usr/bin/env python3
"""Build detailed Excel benchmark workbook from harmonized TSV + analysis tables."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

METHOD_LABEL = {
    "cDNA_Frag_30C5Min": "cDNA 30°C 5min",
    "RNA_Frag_85C6Min": "RNA 85°C 6min",
    "RNA_Frag_94C7Min": "RNA 94°C 7min",
}


def _read_tsv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, sep="\t")


def _attach_meta(df: pd.DataFrame, cohort: pd.DataFrame, sample_col: str = "sample_id") -> pd.DataFrame:
    if df.empty:
        return df
    meta = cohort[["id", "sample_id", "sn", "host", "method"]].copy()
    meta = meta.rename(columns={"sample_id": "v_id"})
    key = sample_col
    if key not in df.columns and "v_id" in df.columns:
        key = "v_id"
    if key not in df.columns:
        return df
    return df.merge(meta, left_on=key, right_on="v_id", how="left", suffixes=("", "_meta"))


def load_cohort(batch_dir: Path) -> pd.DataFrame:
    cohort = _read_tsv(batch_dir / "cohorts" / "sampleinfo.tsv")
    cohort = cohort.rename(columns={"id": "id"})
    cohort["sample_id"] = cohort["id"].map(lambda x: f"v{int(x)}")
    cohort["method_label"] = cohort["method"].map(METHOD_LABEL)
    return cohort


def build_main_table(cohort: pd.DataFrame, harm: Path, merged: pd.DataFrame) -> pd.DataFrame:
    w1 = _read_tsv(harm / "workflow1" / "qc_upstream_sample.tsv")
    w2s = _read_tsv(harm / "workflow2" / "virus_identification_sample.tsv")
    w2c = _read_tsv(harm / "workflow2" / "virus_identification_contigs.tsv")
    w3 = _read_tsv(harm / "workflow3" / "host_identification_contig.tsv").rename(columns={"sn": "sample_id"})
    w4 = _read_tsv(harm / "workflow4" / "microbiome_bracken_sample.tsv")
    w5 = _read_tsv(harm / "workflow5" / "virus_quantification_sample.tsv")
    w7 = _read_tsv(harm / "workflow7" / "fragmentation_benchmark.tsv")

    # W2 contig-level aggregates
    w2_extra = pd.DataFrame()
    if not w2c.empty:
        w2_extra = (
            w2c.groupby("source_sample")
            .agg(
                n_high_quality=("checkv_quality", lambda s: (s == "High-quality").sum()),
                mean_completeness=("completeness", "mean"),
            )
            .reset_index()
            .rename(columns={"source_sample": "sample_id"})
        )

    base = cohort[["id", "sample_id", "sn", "host", "method"]].copy()
    base = base.rename(columns={"sample_id": "v_id"})

    def pick(df: pd.DataFrame, cols: dict[str, str], on: str = "sample_id") -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        sub = df.copy()
        if on not in sub.columns and "v_id" in sub.columns:
            on = "v_id"
        keep = [on] + [c for c in cols if c in sub.columns]
        sub = sub[keep].rename(columns=cols)
        key = "v_id" if "v_id" in base.columns else "sample_id"
        return base.merge(sub, left_on="v_id", right_on=on, how="left").drop(columns=[on], errors="ignore")

    out = base.copy()
    if not w1.empty:
        w1p = w1[["sample_id", "merge_r1_reads", "merge_r1_q30_pct", "contigs_ge1kb_n", "contigs_ge1kb_bp"]].copy()
        w1p["merge_r1_Mreads"] = w1p["merge_r1_reads"] / 1e6
        w1p["contigs_ge1kb_Mbp"] = w1p["contigs_ge1kb_bp"] / 1e6
        w1p["w1_status"] = "已完成"
        out = out.merge(
            w1p.rename(columns={"sample_id": "v_id"})[
                ["v_id", "w1_status", "merge_r1_Mreads", "contigs_ge1kb_n", "contigs_ge1kb_Mbp"]
            ],
            on="v_id",
            how="left",
        )
    if not w2s.empty:
        w2p = w2s[["sample_id", "n_contigs", "n_clusters"]].copy()
        w2p = w2p.rename(columns={"sample_id": "v_id", "n_contigs": "n_viral_contigs"})
        w2p["w2_status"] = "已完成"
        out = out.merge(w2p, on="v_id", how="left")
    if not w2_extra.empty:
        w2e = w2_extra.rename(columns={"sample_id": "v_id"})
        out = out.merge(w2e, on="v_id", how="left")
    if not w3.empty:
        w3p = w3[
            [
                "sample_id",
                "inferred_mt_species",
                "inferred_mt_genus",
                "species_level_marker_count",
                "annotated_species_count",
                "COI_pident",
                "CYTB_pident",
                "ND1_pident",
            ]
        ].rename(columns={"sample_id": "v_id"})
        w3p["w3_status"] = "已完成"
        out = out.merge(w3p, on="v_id", how="left")
    if not w4.empty:
        w4p = w4[
            [
                "sample_id",
                "kraken_unclassified_frac",
                "kraken_classified_reads",
                "bracken_species_taxa",
                "bracken_species_reads_assigned",
                "bracken_species_frac_of_classified",
            ]
        ].rename(
            columns={
                "sample_id": "v_id",
                "bracken_species_reads_assigned": "bracken_species_reads",
            }
        )
        w4p["w4_status"] = "已完成"
        out = out.merge(w4p, on="v_id", how="left")
    if not w5.empty:
        w5p = w5[
            [
                "sample_id",
                "n_viral_contigs_with_reads",
                "total_mapped_reads",
                "max_rpm",
                "median_rpm",
                "mean_coverage_pct",
                "clean_reads",
                "mapping_rate_pct",
            ]
        ].rename(
            columns={
                "sample_id": "v_id",
                "n_viral_contigs_with_reads": "n_viral_with_reads",
                "mapping_rate_pct": "virus_mapping_rate_pct",
            }
        )
        w5p["w5_status"] = "已完成"
        out = out.merge(w5p, on="v_id", how="left")
    if not w7.empty:
        w7p = w7[
            [
                "sample_id",
                "uniquely_mapped_pct",
                "multi_mapped_pct",
                "median_cv_coverage",
                "percent_duplication",
                "chimeric_rate_pct",
            ]
        ].copy()
        w7p = w7p.rename(columns={"sample_id": "v_id"})
        w7p["host_mapped_pct"] = w7["uniquely_mapped_pct"].values + w7["multi_mapped_pct"].values
        w7p["w7_status"] = "已完成"
        out = out.merge(w7p, on="v_id", how="left")

    # fill from analysis merged if available
    if not merged.empty and "sample_id" in merged.columns:
        m = merged.rename(columns={"sample_id": "v_id"})
        for c in m.columns:
            if c.startswith("workflow") and c not in out.columns:
                out = out.merge(m[["v_id", c]], on="v_id", how="left")

    return out


def w2_batch_summary(harm: Path) -> pd.DataFrame:
    contigs = _read_tsv(harm / "workflow2" / "virus_identification_contigs.tsv")
    clusters = _read_tsv(harm / "workflow2" / "virus_identification_clusters.tsv")
    rows = [
        ("假定病毒 contig 数", len(contigs)),
        ("ANI80 聚类数", clusters["clusid"].nunique() if not clusters.empty else 0),
        ("CheckV High-quality contig 数", (contigs["checkv_quality"] == "High-quality").sum() if not contigs.empty else 0),
        ("宿主分组", ", ".join(sorted(contigs["host_group"].dropna().unique())) if not contigs.empty else ""),
    ]
    return pd.DataFrame(rows, columns=["指标", "值"])


def w7_method_summary(strat: pd.DataFrame, host: str) -> pd.DataFrame:
    sub = strat[strat["dataset"] == f"host_{host}"].copy()
    if sub.empty:
        return pd.DataFrame()
    metrics = [
        "host_mapped_pct",
        "uniquely_mapped_pct",
        "multi_mapped_pct",
        "percent_duplication",
        "median_cv_coverage",
        "chimeric_rate_pct",
        "median_5prime_to_3prime_bias",
        "splice_junctions_novel",
    ]
    rows = []
    for m in metrics:
        for _, r in sub.iterrows():
            rows.append(
                {
                    "metric": m,
                    "method": r["method"],
                    "method_label": METHOD_LABEL.get(r["method"], r["method"]),
                    "n": r["n"],
                    "mean": r.get(f"{m}_mean"),
                    "sd": r.get(f"{m}_sd"),
                    "median": r.get(f"{m}_median"),
                }
            )
    return pd.DataFrame(rows)


def build_group_w1_w7(merged: pd.DataFrame) -> pd.DataFrame:
    if merged.empty:
        return pd.DataFrame()
    metrics = [
        ("workflow1_merge_r1_Mreads", "merge_r1_Mreads"),
        ("workflow1_mean_q30_after_fastp", "mean_q30_after_fastp"),
        ("workflow1_mean_rrna_retention", "mean_rrna_retention"),
        ("workflow1_contigs_ge1kb_n", "contigs_ge1kb_n"),
        ("workflow2_n_viral_contigs", "n_viral_contigs"),
        ("workflow2_n_checkv_high", "n_checkv_high"),
        ("workflow2_mean_checkv_completeness", "mean_checkv_completeness"),
        ("workflow4_kraken_unclassified_pct", "kraken_unclassified_pct"),
        ("workflow4_bracken_species_taxa", "bracken_species_taxa"),
        ("workflow4_bracken_species_reads_M", "bracken_species_reads_M"),
        ("workflow5_mapping_rate_pct", "virus_mapping_rate_pct"),
        ("workflow5_median_rpm", "median_rpm"),
        ("workflow5_n_viral_contigs_with_reads", "n_viral_contigs_with_reads"),
    ]
    rows = []
    for method, g in merged.groupby("method"):
        row = {
            "method": method,
            "method_label": METHOD_LABEL.get(method, method),
            "n": len(g),
        }
        for src, alias in metrics:
            if src not in g.columns:
                continue
            s = pd.to_numeric(g[src], errors="coerce").dropna()
            row[f"{alias}_mean"] = s.mean()
            row[f"{alias}_sd"] = s.std()
            row[f"{alias}_median"] = s.median()
        rows.append(row)
    return pd.DataFrame(rows)


def project_summary(batch_id: str) -> pd.DataFrame:
    rows = [
        ("项目", "Vazyme RNA vs cDNA 打断建库 benchmark（XvirBench）"),
        ("批次 ID", batch_id),
        ("样本总数", 60),
        ("测序 run 数", 240),
        ("宿主", "rat 30 / tick 24 / mosquito 6"),
        ("建库方法", "cDNA_Frag_30C5Min (24) / RNA_Frag_85C6Min (24) / RNA_Frag_94C7Min (12)"),
        ("生成日期", str(date.today())),
        ("数据来源", "batches/{id}/harmonized/ + analysis/tables/"),
        ("文档", "docs/HARMONIZED_METRICS_REFERENCE.md"),
    ]
    return pd.DataFrame(rows, columns=["指标", "值"])


def workflow_status(batch_dir: Path) -> pd.DataFrame:
    manifest_note = str(batch_dir / "workflow_results")
    rows = [
        ("W1 上游预处理", "workflow1_upstream", "已完成", 60, "harmonized/workflow1/"),
        ("W2 病毒鉴定", "workflow2_virusid", "已完成", 60, "按宿主分 3 批；646 contigs"),
        ("W3 宿主鉴定", "workflow3_hostid", "已完成", 60, "EukaMarker V3 逐样本"),
        ("W4 Kraken/Bracken", "workflow4_kraken_bracken", "已完成", 60, manifest_note),
        ("W5 病毒定量", "workflow5_virus_quantification", "已完成", 60, "按宿主参考 RPM"),
        ("W6 病毒注释", "workflow6_virus_annotation", "未运行", 0, ""),
        ("W7 建库 benchmark", "workflow7_fragmentation_benchmark", "已完成", 60, "STAR/Picard/RSeQC"),
    ]
    return pd.DataFrame(rows, columns=["流程", "目录", "状态", "完成样本数", "备注"])


def build_workbook(batch_id: str, output: Path) -> None:
    batch_dir = ROOT / "batches" / batch_id
    harm = batch_dir / "harmonized"
    analysis = batch_dir / "analysis" / "tables"
    cohort = load_cohort(batch_dir)
    merged = _read_tsv(analysis / "sample_metrics_merged.tsv")
    w7_strat = _read_tsv(analysis / "workflow7_method_summary_stratified.tsv")

    sheets: dict[str, pd.DataFrame] = {}

    sheets["00_项目摘要"] = project_summary(batch_id)
    sheets["01_流程完成状态"] = workflow_status(batch_dir)
    sheets["02_样本元信息"] = cohort[["id", "sn", "host", "method", "fq1", "fq2"]].assign(
        v_id=cohort["sample_id"]
    )[["id", "sn", "host", "method", "fq1", "fq2", "v_id"]]
    sheets["03_主指标表"] = build_main_table(cohort, harm, merged)

    # W1
    w1s = _read_tsv(harm / "workflow1" / "qc_upstream_sample.tsv")
    w1s = _attach_meta(w1s, cohort)
    if not w1s.empty:
        w1s["w1_status"] = "已完成"
        w1s["merge_r1_Mreads"] = w1s["merge_r1_reads"] / 1e6
        w1s["contigs_ge1kb_Mbp"] = w1s["contigs_ge1kb_bp"] / 1e6
        sheets["W1_上游QC"] = w1s[
            [
                "id",
                "v_id",
                "sn",
                "host",
                "method",
                "w1_status",
                "merge_r1_reads",
                "merge_r1_Mreads",
                "merge_r1_q30_pct",
                "contigs_ge1kb_n",
                "contigs_ge1kb_Mbp",
                "contigs_ge1kb_max_len",
            ]
        ]
    w1r = _read_tsv(harm / "workflow1" / "qc_upstream_run.tsv")
    w1r = _attach_meta(w1r, cohort, sample_col="sample_id")
    if not w1r.empty:
        sheets["W1_run_QC"] = w1r

    # W2
    sheets["W2_批次摘要"] = w2_batch_summary(harm)
    w2s = _read_tsv(harm / "workflow2" / "virus_identification_sample.tsv")
    w2c = _read_tsv(harm / "workflow2" / "virus_identification_contigs.tsv")
    if not w2s.empty:
        w2x = w2s.copy()
        if not w2c.empty:
            agg = (
                w2c.groupby("source_sample")
                .agg(
                    n_high_quality=("checkv_quality", lambda s: (s == "High-quality").sum()),
                    mean_completeness=("completeness", "mean"),
                )
                .reset_index()
            )
            w2x = w2x.merge(agg, left_on="sample_id", right_on="source_sample", how="left")
        w2x = _attach_meta(w2x, cohort)
        w2x["w2_status"] = "已完成"
        if "n_contigs" in w2x.columns:
            w2x = w2x.rename(columns={"n_contigs": "n_viral_contigs"})
        if "v_id" not in w2x.columns and "sample_id" in w2x.columns:
            w2x["v_id"] = w2x["sample_id"]
        sheets["W2_病毒鉴定"] = w2x[
            ["v_id", "n_viral_contigs", "n_clusters", "n_high_quality", "mean_completeness", "w2_status", "host", "method"]
        ]
    if not w2c.empty:
        sheets["W2_病毒contigs"] = w2c[
            ["contig_id", "length", "source_sample", "checkv_quality", "completeness", "host_group", "viral_genes", "host_genes"]
        ]
    w2cl = _read_tsv(harm / "workflow2" / "virus_identification_clusters.tsv")
    if not w2cl.empty:
        sheets["W2_病毒clusters"] = w2cl

    # W3
    w3c = _read_tsv(harm / "workflow3" / "host_identification_contig.tsv")
    if not w3c.empty:
        w3c = w3c.rename(columns={"sn": "v_id"})
        w3c = _attach_meta(w3c, cohort, sample_col="v_id")
        w3c["w3_status"] = "已完成"
        sheets["W3_宿主鉴定"] = w3c[
            [
                "id",
                "v_id",
                "host",
                "method",
                "w3_status",
                "inferred_mt_species",
                "inferred_mt_genus",
                "species_level_marker_count",
                "annotated_species_count",
                "COI_pident",
                "CYTB_pident",
                "ND1_pident",
            ]
        ]
        sheets["W3_宿主明细"] = w3c

    # W4
    w4 = _read_tsv(harm / "workflow4" / "microbiome_bracken_sample.tsv")
    w4 = _attach_meta(w4, cohort)
    if not w4.empty:
        w4["w4_status"] = "已完成"
        w4 = w4.rename(columns={"sample_id": "v_id"})
        sheets["W4_Kraken_Bracken"] = w4[
            [
                "id",
                "v_id",
                "sn",
                "host",
                "method",
                "w4_status",
                "kraken_unclassified_frac",
                "kraken_classified_reads",
                "bracken_species_taxa",
                "bracken_species_reads_assigned",
                "bracken_species_frac_of_classified",
            ]
        ].rename(columns={"bracken_species_reads_assigned": "bracken_species_reads"})
    w4t = _read_tsv(harm / "workflow4" / "microbiome_bracken_top15.tsv")
    w4t = _attach_meta(w4t, cohort)
    if not w4t.empty:
        sheets["W4_Bracken_top15"] = w4t

    # W5
    w5 = _read_tsv(harm / "workflow5" / "virus_quantification_sample.tsv")
    w5 = _attach_meta(w5, cohort)
    if not w5.empty:
        w5["w5_status"] = "已完成"
        w5 = w5.rename(columns={"sample_id": "v_id"})
        sheets["W5_病毒定量"] = w5[
            [
                "id",
                "v_id",
                "sn",
                "host",
                "method",
                "w5_status",
                "n_viral_contigs_with_reads",
                "total_mapped_reads",
                "max_rpm",
                "median_rpm",
                "mean_coverage_pct",
                "clean_reads",
                "mapping_rate_pct",
            ]
        ].rename(
            columns={
                "n_viral_contigs_with_reads": "n_viral_with_reads",
                "mapping_rate_pct": "virus_mapping_rate_pct",
            }
        )
    w5r = _read_tsv(harm / "workflow5" / "virus_quantification_rpm.tsv")
    if not w5r.empty:
        sheets["W5_RPM明细"] = w5r

    # W7
    w7 = _read_tsv(harm / "workflow7" / "fragmentation_benchmark.tsv")
    if not w7.empty:
        w7 = w7.merge(
            cohort[["id", "sample_id", "sn", "host"]],
            on="sample_id",
            how="left",
        )
        w7["v_id"] = w7["sample_id"]
        if "method" not in w7.columns:
            w7 = w7.merge(cohort[["sample_id", "method"]], on="sample_id", how="left")
        w7["host_mapped_pct"] = w7["uniquely_mapped_pct"] + w7["multi_mapped_pct"]
        w7["w7_status"] = "已完成"
        w7["method_meta"] = w7["method"]
        sheets["W7_建库benchmark"] = w7

    for host in ("rat", "tick", "mosquito"):
        sm = w7_method_summary(w7_strat, host)
        if not sm.empty:
            sheets[f"W7_{host}_method"] = sm

    sheets["W1-W7_group"] = build_group_w1_w7(merged)

    # Analysis supplements
    for wf in range(1, 8):
        for kind in ("method_summary", "method_summary_stratified", "stat_tests", "sample_metrics"):
            p = analysis / f"workflow{wf}_{kind}.tsv"
            df = _read_tsv(p)
            if not df.empty:
                sheets[f"分析_W{wf}_{kind}"] = df

    coh = _read_tsv(analysis / "cohort_overview.tsv")
    if not coh.empty:
        sheets["分析_队列概览"] = coh
    if not merged.empty:
        sheets["分析_样本指标合并"] = merged

    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            # Excel sheet name max 31 chars
            sheet = name[:31]
            df.to_excel(writer, sheet_name=sheet, index=False)

    print(f"Wrote {output} ({len(sheets)} sheets)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch-id", default="vazyme_fragment_test")
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "vazyme_benchmark_metrics.xlsx",
    )
    args = p.parse_args()
    build_workbook(args.batch_id, args.output)


if __name__ == "__main__":
    main()
