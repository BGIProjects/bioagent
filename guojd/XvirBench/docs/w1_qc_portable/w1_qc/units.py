"""Read/base units and display formatting for W1 QC."""
from __future__ import annotations

from typing import Any

import pandas as pd

READ_DIVISOR = 1e6
READ_SUFFIX = "Mb"
BASE_DIVISOR = 1e9
BASE_SUFFIX = "Gb"

READ_COLS = {
    "reads_before", "reads_after_fastp", "reads_removed_fastp", "raw_reads_sum",
    "reads_before_sum", "reads_after_fastp_sum", "removed_sum", "fastp_r1_reads",
    "clean_r1_reads", "fastp_r1_sum", "clean_r1_sum", "merge_r1_reads", "merge_r2_reads",
    "rrna_removed_r1", "rrna_removed_sum", "loss_low_quality", "loss_too_short",
    "loss_adapter", "too_many_N_reads", "low_complexity_reads", "adapter_dimer_reads",
    "too_long_reads", "loss_unaccounted", "loss_low_quality_sum", "loss_too_short_sum",
    "loss_adapter_sum", "too_many_N_sum", "low_complexity_sum", "adapter_dimer_sum",
    "too_long_sum", "loss_unaccounted_sum", "corrected_reads", "passed_filter_reads",
    "bases_after_fastp_sum",  # not a read col - remove later
}

# only actual read counts
READ_COLS = {c for c in READ_COLS if "bases" not in c}

BASE_COLS = {
    "bases_before", "raw_bases_sum", "merge_r1_bases", "merge_r2_bases",
    "contigs_all_bp", "contigs_ge1kb_bp", "bases_after_fastp", "bases_after_fastp_sum",
    "clean_r1_bases", "clean_r1_bases_sum", "fastp_r1_bases", "fastp_r1_bases_sum",
}

# fraction (0-1) → percent columns
PCT_FRAC_COLS = {
    "q30_before", "q20_before", "gc_before", "q30_after_fastp", "q20_after_fastp",
    "gc_after_fastp", "read_retention_fastp", "read_retention_fastp_agg",
    "mean_retention_fastp", "mean_q30_after_fastp", "mean_dup", "duplication_rate",
    "rrna_retention_r1", "rrna_retention_r2", "rrna_retention_mean",
    "mean_rrna_retention", "rrna_removed_pct", "rrna_removed_pct_agg",
    "raw_q30_mean", "raw_gc_mean", "merge_loss_pct",
}

# already stored as percent 0-100
PCT_ALREADY_COLS = {"merge_r1_q30_pct", "merge_r1_gc_pct", "merge_r2_q30_pct", "merge_r2_gc_pct"}

INT_COUNT_COLS = {
    "n", "n_runs", "contigs_all_n", "contigs_ge1kb_n", "contigs_min_len",
    "contigs_max_len", "contigs_ge1kb_max_len",
}

METRIC_LABELS = {
    "reads_before_Mb": "reads_before (Mb)",
    "reads_after_fastp_Mb": "reads_after_fastp (Mb)",
    "reads_after_fastp_sum_Mb": "reads_after_sum (Mb)",
    "reads_removed_fastp_Mb": "reads_removed_fastp (Mb)",
    "raw_reads_sum_Mb": "raw_reads_sum (Mb)",
    "raw_bases_sum_Gb": "raw_bases_sum (Gb)",
    "bases_before_Gb": "bases_before (Gb)",
    "bases_after_fastp_sum_Gb": "bases_after_fastp_sum (Gb)",
    "clean_r1_bases_sum_Gb": "clean_r1_bases_sum (Gb)",
    "reads_before_sum_Mb": "reads_before_sum (Mb)",
    "removed_sum_Mb": "removed_sum (Mb)",
    "merge_r1_reads_Mb": "merge_r1_reads (Mb)",
    "merge_r1_Mreads": "merge_r1_reads (Mb)",
    "merge_r1_bases_Gb": "merge_r1_bases (Gb)",
    "rrna_removed_sum_Mb": "rrna_removed_sum (Mb)",
    "rrna_removed_r1_Mb": "rrna_removed_r1 (Mb)",
    "fastp_r1_sum_Mb": "fastp_r1_sum (Mb)",
    "clean_r1_sum_Mb": "clean_r1_sum (Mb)",
    "contigs_ge1kb_Mbp": "contigs_ge1kb_bp (Mb)",
    "contigs_ge1kb_bp_Gb": "contigs_ge1kb_bp (Gb)",
    "contigs_all_bp_Gb": "contigs_all_bp (Gb)",
    "loss_low_quality_sum_Mb": "loss_low_quality_sum (Mb)",
    "loss_too_short_sum_Mb": "loss_too_short_sum (Mb)",
    "loss_adapter_sum_Mb": "loss_adapter_sum (Mb)",
    "loss_unaccounted_sum_Mb": "loss_unaccounted_sum (Mb)",
    "too_many_N_sum_Mb": "too_many_N_sum (Mb)",
    "q30_before_pct": "q30_before (%)",
    "gc_before_pct": "gc_before (%)",
    "raw_q30_mean_pct": "raw_q30_mean (%)",
    "raw_gc_mean_pct": "raw_gc_mean (%)",
    "q30_after_fastp_pct": "q30_after_fastp (%)",
    "mean_q30_after_fastp_pct": "mean_q30_after_fastp (%)",
    "read_retention_fastp_pct": "read_retention_fastp (%)",
    "read_retention_fastp_agg_pct": "read_retention_fastp_agg (%)",
    "duplication_rate_pct": "duplication_rate (%)",
    "mean_dup_pct": "mean_dup (%)",
    "rrna_retention_mean_pct": "rrna_retention_mean (%)",
    "mean_rrna_retention_pct": "mean_rrna_retention (%)",
    "merge_r1_q30_pct": "merge_r1_q30 (%)",
    "merge_r1_gc_pct": "merge_r1_gc (%)",
    "merge_loss_pct_pct": "merge_loss (%)",
}


def to_reads_mb(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") / READ_DIVISOR


def to_bases_gb(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") / BASE_DIVISOR


def frac_to_pct(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") * 100.0


def format_number(val: Any, *, as_pct: bool = False, as_int: bool = False) -> str:
    """Unify display: Mb/Gb → 2 decimals; percent → XX.XX%; integers → thousands sep."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    try:
        x = float(val)
    except (TypeError, ValueError):
        return str(val)
    if as_pct:
        return f"{x:.2f}%"
    if as_int or (abs(x - round(x)) < 1e-9 and abs(x) >= 1):
        return f"{int(round(x)):,}"
    return f"{x:.2f}"


def format_cell(col: str, val: Any) -> str:
    c = str(col)
    if c.endswith("_pct") or c.endswith(" (%)") or "(%)" in c or c in PCT_ALREADY_COLS:
        # already percent units
        if pd.isna(val):
            return ""
        return f"{float(val):.2f}%"
    if c in INT_COUNT_COLS or c.endswith("_n") and "Mb" not in c and "Gb" not in c:
        return format_number(val, as_int=True)
    if c in ("n", "group", "metric", "sample_id", "run_id", "method", "method_label", "host", "sn"):
        if c == "n":
            return format_number(val, as_int=True)
        return "" if pd.isna(val) else str(val)
    # floats Mb/Gb/lengths
    try:
        x = float(val)
    except (TypeError, ValueError):
        return str(val)
    if abs(x - round(x)) < 1e-9 and ("len" in c or c.endswith("_n") or c in INT_COUNT_COLS):
        return f"{int(round(x)):,}"
    return f"{x:.2f}"


def add_unit_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for c in READ_COLS:
        if c in out.columns:
            out[f"{c}_{READ_SUFFIX}"] = to_reads_mb(out[c])
    for c in BASE_COLS:
        if c in out.columns:
            out[f"{c}_{BASE_SUFFIX}"] = to_bases_gb(out[c])
    for c in PCT_FRAC_COLS:
        if c in out.columns:
            out[f"{c}_pct"] = frac_to_pct(out[c])
    return out


def _describe(vals: pd.Series) -> dict:
    s = pd.to_numeric(vals, errors="coerce").dropna()
    if s.empty:
        return {k: float("nan") for k in ("n", "min", "max", "mean", "median", "std", "q25", "q75")}
    return {
        "n": float(len(s)), "min": float(s.min()), "max": float(s.max()),
        "mean": float(s.mean()), "median": float(s.median()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "q25": float(s.quantile(0.25)), "q75": float(s.quantile(0.75)),
    }


def summary_with_units(summary: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if summary is None or summary.empty:
        return summary
    mapping = {
        "reads_before": ("stage_S0_raw_by_run", "reads_before", READ_SUFFIX),
        "bases_before": ("stage_S0_raw_by_run", "bases_before", BASE_SUFFIX),
        "raw_reads_sum": ("stage_S0_raw_by_sample", "raw_reads_sum", READ_SUFFIX),
        "raw_bases_sum": ("stage_S0_raw_by_sample", "raw_bases_sum", BASE_SUFFIX),
        "reads_removed_fastp": ("stage_S1_fastp_by_run", "reads_removed_fastp", READ_SUFFIX),
        "reads_before_sum": ("stage_S1_fastp_loss_by_sample", "reads_before_sum", READ_SUFFIX),
        "reads_after_fastp_sum": ("stage_S1_fastp_loss_by_sample", "reads_after_fastp_sum", READ_SUFFIX),
        "removed_sum": ("stage_S1_fastp_loss_by_sample", "removed_sum", READ_SUFFIX),
        "rrna_removed_r1": ("stage_S2_rrna_by_run", "rrna_removed_r1", READ_SUFFIX),
        "rrna_removed_sum": ("stage_S2_rrna_by_sample", "rrna_removed_sum", READ_SUFFIX),
        "merge_r1_reads": ("stage_S3_merge_sample", "merge_r1_reads", READ_SUFFIX),
        "merge_r1_bases": ("stage_S3_merge_sample", "merge_r1_bases", BASE_SUFFIX),
        "contigs_ge1kb_bp": ("stage_S4_assembly_sample", "contigs_ge1kb_bp", BASE_SUFFIX),
        "contigs_ge1kb_Mbp": ("stage_S4_assembly_sample", "contigs_ge1kb_bp", BASE_SUFFIX),
        # percent conversions
        "q30_before": ("stage_S0_raw_by_run", "q30_before", "pct"),
        "gc_before": ("stage_S0_raw_by_run", "gc_before", "pct"),
        "raw_q30_mean": ("stage_S0_raw_by_sample", "raw_q30_mean", "pct"),
        "raw_gc_mean": ("stage_S0_raw_by_sample", "raw_gc_mean", "pct"),
        "q30_after_fastp": ("stage_S1_fastp_by_run", "q30_after_fastp", "pct"),
        "mean_q30_after_fastp": ("stage_S1_fastp_loss_by_sample", "mean_q30_after_fastp", "pct"),
        "read_retention_fastp": ("stage_S1_fastp_by_run", "read_retention_fastp", "pct"),
        "read_retention_fastp_agg": ("stage_S1_fastp_loss_by_sample", "read_retention_fastp_agg", "pct"),
        "duplication_rate": ("stage_S1_fastp_by_run", "duplication_rate", "pct"),
        "mean_dup": ("stage_S1_fastp_loss_by_sample", "mean_dup", "pct"),
        "rrna_retention_mean": ("stage_S2_rrna_by_run", "rrna_retention_mean", "pct"),
        "mean_rrna_retention": ("stage_S2_rrna_by_sample", "mean_rrna_retention", "pct"),
        "merge_loss_pct": ("stage_S3_merge_sample", "merge_loss_pct", "pct"),
    }
    rows = []
    for _, r in summary.iterrows():
        metric = r["metric"]
        if metric == "merge_r1_Mreads":
            r = r.copy()
            r["metric"] = "merge_r1_reads (Mb)"
            rows.append(r)
            continue
        if metric in mapping:
            tname, col, suf = mapping[metric]
            src = tables.get(tname)
            if src is not None and not src.empty:
                enriched = add_unit_columns(src)
                sc = f"{col}_{suf}"
                if sc in enriched.columns:
                    r = r.copy()
                    r["metric"] = METRIC_LABELS.get(sc, f"{metric} ({'%' if suf == 'pct' else suf})")
                    r.update(_describe(enriched[sc]))
        rows.append(r)
    return pd.DataFrame(rows)


def enrich_all_tables(tables: dict[str, pd.DataFrame]) -> None:
    for key in list(tables.keys()):
        if key.endswith("_summary") or key.startswith("sample_qc"):
            continue
        tables[key] = add_unit_columns(tables[key])
    for key in [k for k in tables if k.endswith("_summary")]:
        tables[key] = summary_with_units(tables[key], tables)


def display_columns_for_report(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    meta = {"sample_id", "run_id", "method", "method_label", "host", "sn", "stage"}
    out_cols = []
    for c in cols:
        if c not in df.columns and f"{c}_{READ_SUFFIX}" not in df.columns and f"{c}_pct" not in df.columns:
            # allow alias
            aliases = {
                "reads_after_sum": "reads_after_fastp_sum",
            }
            c = aliases.get(c, c)
        if c in meta:
            if c in df.columns:
                out_cols.append(c)
            continue
        if f"{c}_{READ_SUFFIX}" in df.columns:
            out_cols.append(f"{c}_{READ_SUFFIX}")
        elif f"{c}_{BASE_SUFFIX}" in df.columns:
            out_cols.append(f"{c}_{BASE_SUFFIX}")
        elif f"{c}_pct" in df.columns:
            out_cols.append(f"{c}_pct")
        elif c in df.columns:
            out_cols.append(c)
    sub = df[out_cols].copy()
    rename = {c: METRIC_LABELS.get(c, c) for c in out_cols if c not in meta}
    # special alias for report column name
    rename["reads_after_fastp_sum_Mb"] = "reads_after_sum (Mb)"
    return sub.rename(columns=rename)


def _is_num(v: Any) -> bool:
    try:
        x = float(v)
        return not pd.isna(x)
    except Exception:
        return False


def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return string-formatted dataframe for HTML/markdown."""
    if df is None or df.empty:
        return df
    text_cols = {
        "group", "metric", "sample_id", "run_id", "method", "method_label",
        "host", "sn", "overall_rating", "grade_S1", "grade_S2", "grade_S3", "grade_S4",
        "low_depth_flag",
    }
    out = pd.DataFrame(index=df.index)
    for c in df.columns:
        if c in text_cols:
            out[c] = ["" if pd.isna(v) else str(v) for v in df[c]]
            continue
        if c == "n":
            out[c] = [format_number(v, as_int=True) if _is_num(v) else str(v) for v in df[c]]
            continue
        if c == "weighted_score":
            out[c] = [f"{float(v):.2f}" if _is_num(v) else str(v) for v in df[c]]
            continue
        if c in ("min", "max", "mean", "median", "std", "q25", "q75") and "metric" in df.columns:
            vals = []
            for m, v in zip(df["metric"], df[c]):
                if not _is_num(v):
                    vals.append("" if pd.isna(v) else str(v))
                    continue
                ms = str(m)
                if "(%)" in ms or ms.endswith("%"):
                    vals.append(f"{float(v):.2f}%")
                elif any(k in ms for k in ("contigs_all_n", "contigs_ge1kb_n", "contigs_min_len", "contigs_max_len")) and "Gb" not in ms and "Mb" not in ms and "avg" not in ms:
                    vals.append(format_number(v, as_int=True))
                else:
                    vals.append(f"{float(v):.2f}")
            out[c] = vals
            continue
        # general column
        if "(%)" in str(c) or str(c).endswith("_pct") or str(c).endswith(" (%)"):
            out[c] = [f"{float(v):.2f}%" if _is_num(v) else ("" if pd.isna(v) else str(v)) for v in df[c]]
        elif any(str(c).endswith(s) for s in ("_n", "_len")) and "Mb" not in str(c) and "Gb" not in str(c) and "avg" not in str(c):
            out[c] = [format_number(v, as_int=True) if _is_num(v) else ("" if pd.isna(v) else str(v)) for v in df[c]]
        else:
            out[c] = [f"{float(v):.2f}" if _is_num(v) else ("" if pd.isna(v) else str(v)) for v in df[c]]
    return out
