"""Build coverage matrix and a sample-level master metrics table."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from .config import LOW_DEPTH_R1_READS, WORKFLOWS
from .discover import Cohort, Discovery, _normalize_sid


def _read(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path, sep="\t")


def _sid_col(df: pd.DataFrame) -> Optional[str]:
    for c in ("sample_id", "source_sample", "sn", "v_id"):
        if c in df.columns:
            return c
    return None


def coverage_matrix(extract_dir: Path, disc: Discovery) -> pd.DataFrame:
    rows = []
    discovered_keys = {w.spec.key for w in disc.workflows}
    for spec in WORKFLOWS:
        if not spec.default_report and spec.key not in discovered_keys:
            continue
        d = extract_dir / spec.short
        present_dir = any(w.spec.key == spec.key and w.present for w in disc.workflows)
        tables = {}
        if d.is_dir():
            for tsv in sorted(d.glob("*.tsv")):
                df = _read(tsv)
                tables[tsv.stem] = len(df)
        n_ok = sum(1 for n in tables.values() if n > 0)
        status = "extracted" if n_ok else ("missing_workflow" if not present_dir else "extracted_empty")
        rows.append(
            {
                "workflow": spec.short,
                "title": spec.title,
                "status": status,
                "n_nonempty_tables": n_ok,
                "tables": ";".join(f"{k}:{v}" for k, v in tables.items()) if tables else "",
                "skip_if_absent": spec.skip_biology,
            }
        )
    return pd.DataFrame(rows)


def _prep_sample_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    col = _sid_col(df)
    if not col:
        return pd.DataFrame()
    out = df.copy()
    out["sample_id"] = out[col].map(_normalize_sid)
    return out.dropna(subset=["sample_id"])


def master_sample_table(extract_dir: Path, cohort: Cohort) -> pd.DataFrame:
    base = cohort.samples.copy() if cohort.samples is not None else pd.DataFrame()
    if base.empty:
        base = pd.DataFrame(columns=["sample_id"])
    else:
        base = base.copy()
        if "sample_id" not in base.columns:
            base["sample_id"] = None

    w1s = _prep_sample_df(_read(extract_dir / "W1" / "samples.tsv"))
    if not w1s.empty:
        keep = [
            c
            for c in [
                "sample_id",
                "n_runs",
                "merge_r1_reads",
                "merge_r1_bases",
                "merge_r1_q30_pct",
                "merge_r2_reads",
                "merge_r2_bases",
                "merge_r2_q30_pct",
                "contigs_all_n",
                "contigs_all_bp",
                "contigs_avg_len",
                "contigs_max_len",
                "contigs_ge1kb_n",
                "contigs_ge1kb_bp",
                "contigs_ge1kb_max_len",
                "contigs_ge1kb_max",
            ]
            if c in w1s.columns
        ]
        base = base.merge(w1s[keep], on="sample_id", how="outer", suffixes=("", "_w1dup"))

    w1r = _read(extract_dir / "W1" / "run_qc.tsv")
    if not w1r.empty:
        if "sample_id" not in w1r.columns:
            w1r["sample_id"] = w1r.get("run_id", pd.Series(dtype=str)).map(_normalize_sid)
        else:
            w1r["sample_id"] = w1r["sample_id"].map(_normalize_sid)
        agg_map = {}
        for src, dst, how in [
            ("reads_before", "reads_before_sum", "sum"),
            ("reads_after_fastp", "reads_after_fastp_sum", "sum"),
            ("q30_after_fastp", "q30_after_fastp_median", "median"),
            ("q30_before", "q30_before_median", "median"),
            ("read_retention_fastp", "read_retention_fastp_median", "median"),
            ("duplication_rate", "duplication_rate_median", "median"),
            ("rrna_retention_r1", "rrna_retention_r1_median", "median"),
            ("clean_r1_reads", "clean_r1_reads_sum", "sum"),
        ]:
            if src in w1r.columns:
                agg_map[dst] = (src, how)
        if agg_map:
            g = w1r.groupby("sample_id").agg(**agg_map).reset_index()
            base = base.merge(g, on="sample_id", how="left")

    w2s = _prep_sample_df(_read(extract_dir / "W2" / "sample_cluster.tsv"))
    if not w2s.empty:
        if "n_contigs" in w2s.columns and "n_contigs_in_clusters" not in w2s.columns:
            w2s = w2s.rename(columns={"n_contigs": "n_contigs_in_clusters"})
        keep = [c for c in ["sample_id", "n_contigs_in_clusters", "n_clusters"] if c in w2s.columns]
        base = base.merge(w2s[keep], on="sample_id", how="left")

    w2c = _prep_sample_df(_read(extract_dir / "W2" / "contigs.tsv"))
    if not w2c.empty:
        g = w2c.groupby("sample_id")
        extra = g.size().rename("n_putative_viral_contigs").reset_index()
        if "length" in w2c.columns:
            extra = extra.merge(g["length"].sum().rename("viral_contig_bp").reset_index(), on="sample_id")
        if "checkv_quality" in w2c.columns:
            hq = (
                w2c.assign(_hq=w2c["checkv_quality"].eq("High-quality"))
                .groupby("sample_id")["_hq"]
                .sum()
                .rename("n_high_quality")
                .reset_index()
            )
            extra = extra.merge(hq, on="sample_id")
        base = base.merge(extra, on="sample_id", how="left")

    w3s = _prep_sample_df(_read(extract_dir / "W3" / "host_sample.tsv"))
    if not w3s.empty:
        keep = [
            c
            for c in [
                "sample_id",
                "n_contigs",
                "n_records",
                "n_species_inferred",
                "n_genus_inferred",
                "mean_marker_count",
                "mean_annotated_species",
            ]
            if c in w3s.columns
        ]
        w3s = w3s[keep].rename(columns={"n_contigs": "host_n_contigs", "n_records": "host_n_records"})
        base = base.merge(w3s, on="sample_id", how="left")

    w3t = _prep_sample_df(_read(extract_dir / "W3" / "host_top_species.tsv"))
    if not w3t.empty and "inferred_mt_species" in w3t.columns:
        top = (
            w3t.sort_values(["sample_id", "n_contigs"] if "n_contigs" in w3t.columns else ["sample_id"])
            .drop_duplicates("sample_id")[["sample_id", "inferred_mt_species"]]
            .rename(columns={"inferred_mt_species": "top_host_species"})
        )
        base = base.merge(top, on="sample_id", how="left")

    w4 = _prep_sample_df(_read(extract_dir / "W4" / "sample_qc.tsv"))
    if not w4.empty:
        keep = ["sample_id"] + [
            c
            for c in w4.columns
            if c.startswith("kraken_") or c.startswith("bracken_")
        ]
        base = base.merge(w4[keep], on="sample_id", how="left")

    w5 = _prep_sample_df(_read(extract_dir / "W5" / "sample_summary.tsv"))
    if not w5.empty:
        keep = ["sample_id"] + [
            c
            for c in [
                "n_viral_contigs_with_reads",
                "total_mapped_reads",
                "max_rpm",
                "median_rpm",
                "mean_coverage_pct",
                "clean_reads",
                "mapping_rate_pct",
                "contigs_full_coverage",
            ]
            if c in w5.columns
        ]
        base = base.merge(w5[keep], on="sample_id", how="left")

    w7 = _prep_sample_df(_read(extract_dir / "W7" / "comparison.tsv"))
    if not w7.empty:
        extra_cols = [c for c in w7.columns if c not in base.columns or c == "sample_id"]
        base = base.merge(w7[extra_cols], on="sample_id", how="left")

    # drop duplicate suffix cols
    drop = [c for c in base.columns if c.endswith("_w1dup") or c.endswith("_x") or c.endswith("_y")]
    # keep sample_id
    base = base.drop(columns=[c for c in drop if c != "sample_id"], errors="ignore")
    base = base.drop_duplicates("sample_id")

    depth_col = None
    for c in ("merge_r1_reads", "clean_r1_reads_sum", "clean_reads"):
        if c in base.columns:
            depth_col = c
            break
    if depth_col:
        base["low_depth"] = pd.to_numeric(base[depth_col], errors="coerce") < LOW_DEPTH_R1_READS
    else:
        base["low_depth"] = False

    # core cohort: samples that have groupinfo method/host
    if "method" in base.columns:
        base["in_core_cohort"] = base["method"].notna() & (base["method"].astype(str).str.len() > 0)
    else:
        base["in_core_cohort"] = True
    return base.reset_index(drop=True)
