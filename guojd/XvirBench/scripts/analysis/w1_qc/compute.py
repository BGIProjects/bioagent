"""Compute W1 QC tables and sample scores."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from cohort import LOW_DEPTH_READS, load_sampleinfo
from w1_qc.standards import (
    GRADE_SCORE,
    STAGE_WEIGHTS,
    batch_pass,
    grade_contigs_ge1kb,
    grade_merge_depth,
    grade_rrna_retention,
    grade_s1_combined,
    overall_rating,
)


@dataclass
class W1QCResult:
    out_dir: Path
    tables: dict[str, Path]
    sample_scores: pd.DataFrame
    batch_summary: dict[str, Any]


def _batch_root(batch_id: str) -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "batches" / batch_id


def _workflow1_dir(batch_id: str) -> Path:
    return _batch_root(batch_id) / "workflow_results" / "workflow1_upstream"


def _fastp_json_path(wf1: Path, run_id: str) -> Path:
    return wf1 / "filter" / run_id / "01_fastp.json"


def _load_fastp_extra(wf1: Path, run_id: str) -> dict[str, int]:
    p = _fastp_json_path(wf1, run_id)
    out = {
        "too_many_N_reads": 0,
        "low_complexity_reads": 0,
        "adapter_dimer_reads": 0,
        "too_long_reads": 0,
        "corrected_reads": 0,
    }
    if not p.is_file():
        return out
    try:
        fr = json.loads(p.read_text(encoding="utf-8")).get("filtering_result", {})
        for k in out:
            out[k] = int(fr.get(k, 0) or 0)
    except Exception:
        pass
    return out


def _describe_series(s: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return {k: float("nan") for k in ("n", "min", "max", "mean", "median", "std", "q25", "q75")}
    return {
        "n": float(len(s)),
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "q25": float(s.quantile(0.25)),
        "q75": float(s.quantile(0.75)),
    }


def _summary_block(df: pd.DataFrame, metrics: list[str], group: str = "batch") -> pd.DataFrame:
    rows = []
    for m in metrics:
        d = _describe_series(df[m])
        rows.append({"group": group, "metric": m, **d})
    return pd.DataFrame(rows)


def _filter_host(cohort: pd.DataFrame, host: Optional[str]) -> pd.DataFrame:
    if not host:
        return cohort.copy()
    return cohort[cohort["host"] == host].copy()


def build_stage_tables(
    batch_id: str,
    host: Optional[str] = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    batch = _batch_root(batch_id)
    harm = batch / "harmonized" / "workflow1"
    cohort = _filter_host(load_sampleinfo(batch / "cohorts"), host)
    sample_ids = set(cohort["sample_id"])

    runs = pd.read_csv(harm / "qc_upstream_run.tsv", sep="\t")
    runs = runs[runs["sample_id"].isin(sample_ids)].copy()
    samples = pd.read_csv(harm / "qc_upstream_sample.tsv", sep="\t")
    samples = samples[samples["sample_id"].isin(sample_ids)].copy()

    wf1 = _workflow1_dir(batch_id)
    extras = []
    for _, row in runs.iterrows():
        e = _load_fastp_extra(wf1, str(row["run_id"]))
        e["run_id"] = row["run_id"]
        extras.append(e)
    if extras:
        runs = runs.merge(pd.DataFrame(extras), on="run_id", how="left")
    else:
        for c in ("too_many_N_reads", "low_complexity_reads", "adapter_dimer_reads", "too_long_reads", "corrected_reads"):
            runs[c] = 0

    runs["rrna_retention_mean"] = (pd.to_numeric(runs["rrna_retention_r1"], errors="coerce") + pd.to_numeric(runs["rrna_retention_r2"], errors="coerce")) / 2
    runs["rrna_removed_r1"] = pd.to_numeric(runs["fastp_r1_reads"], errors="coerce") - pd.to_numeric(runs["clean_r1_reads"], errors="coerce")
    runs["reads_removed_fastp"] = pd.to_numeric(runs["reads_before"], errors="coerce") - pd.to_numeric(runs["reads_after_fastp"], errors="coerce")
    runs["loss_low_quality"] = pd.to_numeric(runs["low_quality_reads"], errors="coerce").fillna(0)
    runs["loss_too_short"] = pd.to_numeric(runs["too_short_reads"], errors="coerce").fillna(0)
    runs["loss_adapter"] = pd.to_numeric(runs["adapter_trimmed_reads"], errors="coerce").fillna(0)
    runs["loss_accounted"] = (
        runs["loss_low_quality"] + runs["loss_too_short"] + runs["loss_adapter"]
        + runs["too_many_N_reads"] + runs["low_complexity_reads"] + runs["adapter_dimer_reads"] + runs["too_long_reads"]
    )
    runs["loss_unaccounted"] = runs["reads_removed_fastp"] - runs["loss_accounted"]

    # S0 by run
    s0_run = runs[
        ["run_id", "sample_id", "reads_before", "bases_before", "q20_before", "q30_before", "gc_before"]
    ].copy()
    s0_run = s0_run.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s0_sample = (
        runs.groupby("sample_id", as_index=False)
        .agg(
            raw_reads_sum=("reads_before", "sum"),
            raw_bases_sum=("bases_before", "sum"),
            raw_q30_mean=("q30_before", "mean"),
            raw_gc_mean=("gc_before", "mean"),
            n_runs=("run_id", "count"),
        )
    )
    s0_sample = s0_sample.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s0_summary = pd.concat([
        _summary_block(s0_run, ["reads_before", "bases_before", "q30_before", "gc_before"], "batch_run_level"),
        _summary_block(s0_sample, ["raw_reads_sum", "raw_bases_sum", "raw_q30_mean", "raw_gc_mean"], "batch_sample_level"),
    ], ignore_index=True)

    # S1 fastp
    s1_run = runs[
        [
            "run_id", "sample_id", "reads_before", "reads_after_fastp", "read_retention_fastp",
            "q30_after_fastp", "duplication_rate", "reads_removed_fastp",
            "loss_low_quality", "loss_too_short", "loss_adapter",
            "too_many_N_reads", "low_complexity_reads", "adapter_dimer_reads", "too_long_reads",
            "corrected_reads", "loss_accounted", "loss_unaccounted",
        ]
    ].copy()
    s1_run = s1_run.merge(cohort[["sample_id", "host", "method", "method_label"]], on="sample_id", how="left")

    s1_loss_run = s1_run[
        ["run_id", "sample_id", "method", "method_label", "reads_before", "reads_removed_fastp",
         "loss_low_quality", "loss_too_short", "loss_adapter", "too_many_N_reads",
         "low_complexity_reads", "adapter_dimer_reads", "too_long_reads", "loss_unaccounted"]
    ].copy()

    s1_sample = (
        runs.groupby("sample_id", as_index=False)
        .agg(
            reads_before_sum=("reads_before", "sum"),
            reads_after_fastp_sum=("reads_after_fastp", "sum"),
            bases_after_fastp_sum=("bases_after_fastp", "sum"),
            mean_retention_fastp=("read_retention_fastp", "mean"),
            mean_q30_after_fastp=("q30_after_fastp", "mean"),
            mean_dup=("duplication_rate", "mean"),
            removed_sum=("reads_removed_fastp", "sum"),
            loss_low_quality_sum=("loss_low_quality", "sum"),
            loss_too_short_sum=("loss_too_short", "sum"),
            loss_adapter_sum=("loss_adapter", "sum"),
            too_many_N_sum=("too_many_N_reads", "sum"),
            low_complexity_sum=("low_complexity_reads", "sum"),
            adapter_dimer_sum=("adapter_dimer_reads", "sum"),
            too_long_sum=("too_long_reads", "sum"),
            loss_unaccounted_sum=("loss_unaccounted", "sum"),
        )
    )
    s1_sample["read_retention_fastp_agg"] = s1_sample["reads_after_fastp_sum"] / s1_sample["reads_before_sum"]
    s1_sample = s1_sample.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s1_summary = pd.concat([
        _summary_block(runs, ["read_retention_fastp", "q30_after_fastp", "duplication_rate", "reads_removed_fastp"], "batch_run_level"),
        _summary_block(s1_sample, ["read_retention_fastp_agg", "mean_q30_after_fastp", "mean_dup"], "batch_sample_level"),
    ], ignore_index=True)

    # S2 rRNA
    s2_run = runs[
        ["run_id", "sample_id", "fastp_r1_reads", "clean_r1_reads", "rrna_removed_r1",
         "rrna_retention_r1", "rrna_retention_r2", "rrna_retention_mean"]
    ].copy()
    s2_run["rrna_removed_pct"] = 1 - s2_run["rrna_retention_mean"]
    s2_run = s2_run.merge(cohort[["sample_id", "host", "method", "method_label"]], on="sample_id", how="left")

    s2_sample = (
        runs.groupby("sample_id", as_index=False)
        .agg(
            fastp_r1_sum=("fastp_r1_reads", "sum"),
            clean_r1_sum=("clean_r1_reads", "sum"),
            clean_r1_bases_sum=("clean_r1_bases", "sum"),
            mean_rrna_retention=("rrna_retention_mean", "mean"),
            rrna_removed_sum=("rrna_removed_r1", "sum"),
        )
    )
    s2_sample["rrna_removed_pct_agg"] = 1 - s2_sample["mean_rrna_retention"]
    s2_sample = s2_sample.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s2_summary = pd.concat([
        _summary_block(runs, ["rrna_retention_mean", "rrna_removed_r1"], "batch_run_level"),
        _summary_block(s2_sample, ["mean_rrna_retention", "rrna_removed_sum"], "batch_sample_level"),
    ], ignore_index=True)

    # S3 merge
    s3 = samples[
        ["sample_id", "n_runs", "merge_r1_reads", "merge_r1_bases", "merge_r1_q30_pct", "merge_r1_gc_pct",
         "merge_r2_reads", "merge_r2_bases"]
    ].copy()
    s3 = s3.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")
    s3 = s3.merge(s1_sample[["sample_id", "reads_after_fastp_sum"]], on="sample_id", how="left")
    s3["merge_r1_Mreads"] = pd.to_numeric(s3["merge_r1_reads"], errors="coerce") / 1e6
    s3["merge_loss_pct"] = 1 - pd.to_numeric(s3["merge_r1_reads"], errors="coerce") / pd.to_numeric(s3["reads_after_fastp_sum"], errors="coerce")
    s3["low_depth"] = pd.to_numeric(s3["merge_r1_reads"], errors="coerce") < LOW_DEPTH_READS

    s3_summary = _summary_block(s3, ["merge_r1_reads", "merge_r1_Mreads", "merge_r1_q30_pct", "merge_r1_gc_pct", "merge_loss_pct"], "batch_sample_level")

    # S4 assembly
    s4 = samples[
        ["sample_id", "contigs_all_n", "contigs_all_bp", "contigs_avg_len", "contigs_min_len", "contigs_max_len",
         "contigs_ge1kb_n", "contigs_ge1kb_bp", "contigs_ge1kb_avg_len", "contigs_ge1kb_max_len"]
    ].copy()
    s4 = s4.merge(cohort[["sample_id", "host", "method", "method_label", "sn"]], on="sample_id", how="left")

    s4_summary = _summary_block(s4, ["contigs_all_n", "contigs_ge1kb_n", "contigs_avg_len", "contigs_max_len", "contigs_ge1kb_bp"], "batch_sample_level")

    tables = {
        "stage_S0_raw_by_run": s0_run,
        "stage_S0_raw_summary": s0_summary,
        "stage_S0_raw_by_sample": s0_sample,
        "stage_S1_fastp_by_run": s1_run,
        "stage_S1_fastp_loss_by_run": s1_loss_run,
        "stage_S1_fastp_summary": s1_summary,
        "stage_S1_fastp_loss_by_sample": s1_sample,
        "stage_S2_rrna_by_run": s2_run,
        "stage_S2_rrna_summary": s2_summary,
        "stage_S2_rrna_by_sample": s2_sample,
        "stage_S3_merge_sample": s3,
        "stage_S3_merge_summary": s3_summary,
        "stage_S4_assembly_sample": s4,
        "stage_S4_assembly_summary": s4_summary,
    }

    flags, scores = _build_scores(cohort, s1_sample, s2_sample, s3, s4)
    tables["sample_qc_flags"] = flags
    tables["sample_qc_scores"] = scores

    from w1_qc.units import enrich_all_tables
    enrich_all_tables(tables)

    return tables, flags, scores


def _build_scores(
    cohort: pd.DataFrame,
    s1_sample: pd.DataFrame,
    s2_sample: pd.DataFrame,
    s3: pd.DataFrame,
    s4: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = cohort[["sample_id", "host", "method", "method_label", "sn"]].copy()
    df = df.merge(
        s1_sample[["sample_id", "read_retention_fastp_agg", "mean_q30_after_fastp", "mean_dup"]],
        on="sample_id", how="left",
    )
    df = df.merge(s2_sample[["sample_id", "mean_rrna_retention"]], on="sample_id", how="left")
    df = df.merge(s3[["sample_id", "merge_r1_reads", "merge_r1_Mreads", "low_depth"]], on="sample_id", how="left")
    df = df.merge(s4[["sample_id", "contigs_ge1kb_n"]], on="sample_id", how="left")

    flags = df[["sample_id", "host", "method", "method_label", "sn"]].copy()
    flags["grade_S1"] = df.apply(
        lambda r: grade_s1_combined(r["read_retention_fastp_agg"], r["mean_q30_after_fastp"], r["mean_dup"]), axis=1
    )
    flags["grade_S2"] = df["mean_rrna_retention"].map(grade_rrna_retention)
    flags["grade_S3"] = df["merge_r1_reads"].map(grade_merge_depth)
    flags["grade_S4"] = df["contigs_ge1kb_n"].map(grade_contigs_ge1kb)
    flags["low_depth_flag"] = df["low_depth"]

    scores = flags.copy()
    scores["score_S1"] = scores["grade_S1"].map(GRADE_SCORE)
    scores["score_S2"] = scores["grade_S2"].map(GRADE_SCORE)
    scores["score_S3"] = scores["grade_S3"].map(GRADE_SCORE)
    scores["score_S4"] = scores["grade_S4"].map(GRADE_SCORE)
    scores["weighted_score"] = (
        scores["score_S3"] * STAGE_WEIGHTS["S3_depth"]
        + scores["score_S1"] * STAGE_WEIGHTS["S1_quality"]
        + scores["score_S2"] * STAGE_WEIGHTS["S2_rrna"]
        + scores["score_S4"] * STAGE_WEIGHTS["S4_assembly"]
    )
    scores["overall_rating"] = scores["weighted_score"].map(overall_rating)
    return flags, scores


def run_w1_qc_pipeline(batch_id: str, host: Optional[str] = None) -> W1QCResult:
    host_tag = host or "all"
    out_dir = _batch_root(batch_id) / "analysis" / f"w1_qc_{host_tag}"
    tab_dir = out_dir / "tables"
    fig_dir = out_dir / "figures"
    tab_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    tables, flags, scores = build_stage_tables(batch_id, host=host)
    written: dict[str, Path] = {}
    for name, df in tables.items():
        p = tab_dir / f"{name}.tsv"
        df.to_csv(p, sep="\t", index=False)
        written[name] = p

    from w1_qc.plots import generate_all_figures
    from w1_qc.reports import write_reports

    fig_paths = generate_all_figures(tables, fig_dir)
    ratings = scores["overall_rating"].tolist()
    batch_summary = {
        "batch_id": batch_id,
        "host": host_tag,
        "n_samples": len(scores),
        "threshold_version": __import__("w1_qc.standards", fromlist=["THRESHOLD_VERSION"]).THRESHOLD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch_pass": batch_pass(ratings),
        "rating_counts": scores["overall_rating"].value_counts().to_dict(),
        "low_depth_samples": flags.loc[flags["low_depth_flag"] == True, "sample_id"].tolist() if "low_depth_flag" in flags.columns else [],
    }

    write_reports(out_dir, batch_summary, tables, fig_paths, internal=True)
    write_reports(out_dir, batch_summary, tables, fig_paths, internal=False)

    return W1QCResult(out_dir=out_dir, tables=written, sample_scores=scores, batch_summary=batch_summary)
