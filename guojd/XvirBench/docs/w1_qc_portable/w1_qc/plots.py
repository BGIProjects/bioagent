"""W1 QC figures (SCI style)."""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from plot_meta import METHOD_ORDER, METHOD_COLORS, METHOD_LABEL
from w1_qc.units import BASE_DIVISOR, READ_DIVISOR, to_reads_mb

DPI = 300
LOSS_COLORS = {
    "Low quality": "#E69F00",
    "Too short": "#56B4E9",
    "Adapter": "#009E73",
    "High N": "#F0E442",
    "Low complexity": "#0072B2",
    "Adapter dimer": "#D55E00",
    "Too long": "#CC79A7",
    "Unassigned": "#999999",
}


def method_codes_order(df: pd.DataFrame, col: str = "method") -> list[str]:
    present = set(df[col].astype(str).unique())
    return [m for m in METHOD_ORDER if m in present]


def apply_sci_theme() -> None:
    mpl.rcParams.update({
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 7,
        "legend.frameon": False,
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)
    return path


def _boxplot_by_method(ax, df: pd.DataFrame, y: str, ylabel: str) -> None:
    order = method_codes_order(df)
    data = [df.loc[df["method"].astype(str) == m, y].dropna().values for m in order]
    bp = ax.boxplot(
        data, patch_artist=True, widths=0.55,
        medianprops=dict(color="black", linewidth=1.2),
        whiskerprops=dict(linewidth=0.8, color="#333"),
        capprops=dict(linewidth=0.8, color="#333"),
        flierprops=dict(marker="o", markersize=3, markerfacecolor="#666", alpha=0.6, linewidth=0),
    )
    for patch, m in zip(bp["boxes"], order):
        patch.set_facecolor(METHOD_COLORS.get(m, "#BBB"))
        patch.set_edgecolor("#333")
        patch.set_alpha(0.85)
    for i, vals in enumerate(data, start=1):
        if len(vals):
            jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(vals))
            ax.scatter(np.full(len(vals), i) + jitter, vals, s=12, c="#333", alpha=0.55, zorder=3, linewidths=0)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels([METHOD_LABEL.get(m, m) for m in order], rotation=20, ha="right")
    ax.set_ylabel(ylabel)


def _stage_boxplot(ax, plot_df: pd.DataFrame, value_col: str, ylabel: str, title: str) -> None:
    stages = list(plot_df["stage"].unique())
    # preserve expected order if present
    pref = ["Raw", "Post-fastp", "Post-rRNA"]
    stages = [s for s in pref if s in set(plot_df["stage"])] or stages
    meth_order = method_codes_order(plot_df)
    width = 0.2
    offsets = np.linspace(-(len(meth_order) - 1) / 2, (len(meth_order) - 1) / 2, len(meth_order)) * 0.22
    for off, meth in zip(offsets, meth_order):
        for i, stage in enumerate(stages):
            vals = plot_df[(plot_df.stage == stage) & (plot_df.method == meth)][value_col].dropna().values
            if len(vals) == 0:
                continue
            bp = ax.boxplot(
                vals, positions=[i + off], widths=width, patch_artist=True,
                medianprops=dict(color="black", linewidth=1.0),
                whiskerprops=dict(linewidth=0.8), capprops=dict(linewidth=0.8),
                flierprops=dict(markersize=2.5, markerfacecolor="#666", alpha=0.5),
            )
            bp["boxes"][0].set_facecolor(METHOD_COLORS.get(meth, "#BBB"))
            bp["boxes"][0].set_edgecolor("#333")
            bp["boxes"][0].set_alpha(0.85)
    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(stages)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    handles = [Patch(facecolor=METHOD_COLORS.get(m, "#BBB"), edgecolor="#333", label=METHOD_LABEL.get(m, m)) for m in meth_order]
    ax.legend(handles=handles, title="Library method", loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC")


def fig01_stage_yield(tables: dict[str, pd.DataFrame], out: Path) -> Path | None:
    """F01: left reads (Mb), right bases (Gb); sample-level stage aggregates."""
    s0 = tables["stage_S0_raw_by_sample"]
    s1 = tables["stage_S1_fastp_loss_by_sample"]
    s2 = tables["stage_S2_rrna_by_sample"]
    read_rows, base_rows = [], []
    # R1-consistent sample-level: Raw≈PE/2, Post-fastp=fastp R1, Post-rRNA=clean R1
    for _, r in s0.iterrows():
        read_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Raw",
                          "value": float(r["raw_reads_sum"]) / 2.0 / READ_DIVISOR})
        base_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Raw",
                          "value": float(r["raw_bases_sum"]) / 2.0 / BASE_DIVISOR})
    for _, r in s2.iterrows():
        read_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Post-fastp",
                          "value": float(r["fastp_r1_sum"]) / READ_DIVISOR})
        read_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Post-rRNA",
                          "value": float(r["clean_r1_sum"]) / READ_DIVISOR})
        if "clean_r1_bases_sum" in r.index and pd.notna(r["clean_r1_bases_sum"]):
            # approximate post-fastp R1 bases from PE after /2 if needed
            base_rows.append({"sample_id": r["sample_id"], "method": str(r["method"]), "stage": "Post-rRNA",
                              "value": float(r["clean_r1_bases_sum"]) / BASE_DIVISOR})
    s1i = s1.set_index("sample_id")
    for _, r in s2.iterrows():
        sid = r["sample_id"]
        if sid in s1i.index and "bases_after_fastp_sum" in s1i.columns:
            base_rows.append({"sample_id": sid, "method": str(r["method"]), "stage": "Post-fastp",
                              "value": float(s1i.loc[sid, "bases_after_fastp_sum"]) / 2.0 / BASE_DIVISOR})
    rdf, bdf = pd.DataFrame(read_rows), pd.DataFrame(base_rows)
    if rdf.empty:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.8))
    _stage_boxplot(axes[0], rdf, "value", "Reads (Mb)", "A. Read depth by stage")
    if not bdf.empty:
        _stage_boxplot(axes[1], bdf, "value", "Bases (Gb)", "B. Base yield by stage")
    else:
        axes[1].text(0.5, 0.5, "No bases data", ha="center", va="center")
        axes[1].set_axis_off()
    fig.suptitle("Fig01 Pipeline yield across stages (sample-level R1)", y=1.02, fontsize=10)
    fig.tight_layout()
    return _save(fig, out)


def fig02_fastp_qc(tables: dict[str, pd.DataFrame], out: Path) -> Path | None:
    """Fig02: fastp retention + loss composition (all samples)."""
    df = tables["stage_S1_fastp_loss_by_sample"].copy()
    if df.empty:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), gridspec_kw={"width_ratios": [1, 1.35]})

    # Left: F02
    ax = axes[0]
    _boxplot_by_method(ax, df, "read_retention_fastp_agg", "Retention (%)")
    # convert to percent on plot
    order = method_codes_order(df)
    data = [df.loc[df["method"].astype(str) == m, "read_retention_fastp_agg"].dropna().values * 100 for m in order]
    ax.clear()
    bp = ax.boxplot(
        data, patch_artist=True, widths=0.55,
        medianprops=dict(color="black", linewidth=1.2),
        whiskerprops=dict(linewidth=0.8, color="#333"),
        capprops=dict(linewidth=0.8, color="#333"),
        flierprops=dict(marker="o", markersize=3, markerfacecolor="#666", alpha=0.6, linewidth=0),
    )
    for patch, m in zip(bp["boxes"], order):
        patch.set_facecolor(METHOD_COLORS.get(m, "#BBB"))
        patch.set_edgecolor("#333")
        patch.set_alpha(0.85)
    for i, vals in enumerate(data, start=1):
        if len(vals):
            jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(vals))
            ax.scatter(np.full(len(vals), i) + jitter, vals, s=12, c="#333", alpha=0.55, zorder=3, linewidths=0)
    ax.axhline(85, ls="--", c="#666", lw=0.9, zorder=0)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels([METHOD_LABEL.get(m, m) for m in order], rotation=20, ha="right")
    ax.set_ylabel("Retention (%)")
    ax.set_title("A. fastp read retention")

    # Right: F03 all samples
    ax = axes[1]
    cols = {
        "loss_low_quality_sum": "Low quality", "loss_too_short_sum": "Too short",
        "loss_adapter_sum": "Adapter", "too_many_N_sum": "High N",
        "low_complexity_sum": "Low complexity", "adapter_dimer_sum": "Adapter dimer",
        "too_long_sum": "Too long", "loss_unaccounted_sum": "Unassigned",
    }
    all_df = df.sort_values("sample_id").set_index("sample_id")
    samples = all_df.index.tolist()
    count_mat = np.column_stack([
        pd.to_numeric(all_df.get(col, 0), errors="coerce").fillna(0).values for col in cols
    ])
    row_sum = count_mat.sum(axis=1, keepdims=True)
    row_sum = np.where(row_sum > 0, row_sum, 1)
    pct_mat = 100 * count_mat / row_sum
    y_pos = np.arange(len(samples))
    left = np.zeros(len(samples))
    for j, (_, label) in enumerate(cols.items()):
        ax.barh(y_pos, pct_mat[:, j], left=left, color=LOSS_COLORS.get(label, "#AAA"),
                edgecolor="white", linewidth=0.2, label=label, height=0.78)
        left += pct_mat[:, j]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(samples, fontsize=5.5)
    ax.set_xlabel("Fraction of removed reads (%)")
    ax.set_xlim(0, 100)
    ax.set_title("B. fastp loss composition (all samples)")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)

    fig.suptitle("Fig02 fastp QC", y=1.01, fontsize=10)
    fig.tight_layout()
    return _save(fig, out)


def fig03_rrna_qc(tables: dict[str, pd.DataFrame], out: Path) -> Path | None:
    """Fig03: rRNA retention (denom=fastp R1) + post-rRNA depth."""
    df = tables["stage_S2_rrna_by_sample"].copy()
    if df.empty:
        return None
    s3 = tables["stage_S3_merge_sample"]
    merged = df.merge(s3[["sample_id", "merge_r1_reads"]], on="sample_id", how="left")
    unequal = (pd.to_numeric(merged["merge_r1_reads"], errors="coerce") - pd.to_numeric(merged["clean_r1_sum"], errors="coerce")).abs()
    use_note = "Post-rRNA R1 reads (equal to merge in this batch)" if (unequal.fillna(0) < 1).all() else "Post-rRNA R1 reads (sample-level)"

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.0), gridspec_kw={"width_ratios": [1, 1.5]})

    # Left retention as %
    ax = axes[0]
    order = method_codes_order(df)
    data = [df.loc[df["method"].astype(str) == m, "mean_rrna_retention"].dropna().values * 100 for m in order]
    bp = ax.boxplot(
        data, patch_artist=True, widths=0.55,
        medianprops=dict(color="black", linewidth=1.2),
        whiskerprops=dict(linewidth=0.8, color="#333"),
        capprops=dict(linewidth=0.8, color="#333"),
        flierprops=dict(marker="o", markersize=3, markerfacecolor="#666", alpha=0.6, linewidth=0),
    )
    for patch, m in zip(bp["boxes"], order):
        patch.set_facecolor(METHOD_COLORS.get(m, "#BBB"))
        patch.set_edgecolor("#333")
        patch.set_alpha(0.85)
    for i, vals in enumerate(data, start=1):
        if len(vals):
            jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(vals))
            ax.scatter(np.full(len(vals), i) + jitter, vals, s=12, c="#333", alpha=0.55, zorder=3, linewidths=0)
    ax.axhspan(75, 98, alpha=0.08, color="#009E73", zorder=0)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels([METHOD_LABEL.get(m, m) for m in order], rotation=20, ha="right")
    ax.set_ylabel("rRNA retention (%)")
    ax.set_title("A. rRNA removal efficiency")

    # Right bars
    ax = axes[1]
    d = df.sort_values("sample_id").copy()
    d["reads_Mb"] = to_reads_mb(d["clean_r1_sum"])
    colors = [METHOD_COLORS.get(str(m), "#BBB") for m in d["method"]]
    ax.bar(d["sample_id"], d["reads_Mb"], color=colors, edgecolor="#333", linewidth=0.3, width=0.82)
    ax.axhline(5.0, ls="--", c="#666", lw=0.9)
    low = d[d["reads_Mb"] < 5]
    if not low.empty:
        ax.scatter(low["sample_id"], low["reads_Mb"], s=45, facecolors="none", edgecolors="#000", linewidths=1.2, zorder=4)
    ax.set_ylabel("Post-rRNA R1 reads (Mb)")
    ax.set_xlabel("Sample")
    ax.set_title(f"B. {use_note}")
    ax.tick_params(axis="x", rotation=90, labelsize=5.5)
    meth_handles = [Patch(facecolor=METHOD_COLORS.get(m, "#BBB"), edgecolor="#333", label=METHOD_LABEL.get(m, m)) for m in order]
    extra = [Line2D([0], [0], color="#666", ls="--", lw=0.9, label="5 Mb threshold")]
    if not low.empty:
        extra.append(Line2D([0], [0], marker="o", linestyle="None", markerfacecolor="none", markeredgecolor="#000", markersize=6, label="Low depth (<5 Mb)"))
    ax.legend(handles=meth_handles + extra, loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)

    fig.suptitle("Fig03 rRNA removal (retention = clean / fastp)", y=1.01, fontsize=10)
    fig.tight_layout()
    return _save(fig, out)


def fig04_assembly(tables: dict[str, pd.DataFrame], out: Path) -> Path | None:
    """Fig04: 2x2 assembly — scatter, contig counts, mean length, >=1kb percent."""
    s4 = tables["stage_S4_assembly_sample"].copy()
    s2 = tables["stage_S2_rrna_by_sample"][["sample_id", "clean_r1_sum", "method"]].copy()
    df = s4.merge(s2, on="sample_id", how="left", suffixes=("", "_s2"))
    if "method_s2" in df.columns:
        df["method"] = df["method"].fillna(df["method_s2"])
    df["reads_Mb"] = to_reads_mb(df["clean_r1_sum"])
    df["low_depth"] = df["reads_Mb"] < 5
    df["ge1kb_pct"] = 100.0 * pd.to_numeric(df["contigs_ge1kb_n"], errors="coerce") / pd.to_numeric(df["contigs_all_n"], errors="coerce").replace(0, pd.NA)
    df["avg_len"] = pd.to_numeric(df["contigs_avg_len"], errors="coerce")
    if df.empty:
        return None

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.2))

    # A: scatter
    ax = axes[0, 0]
    for meth in method_codes_order(df):
        sub = df[df.method.astype(str) == meth]
        ax.scatter(sub["reads_Mb"], sub["contigs_ge1kb_n"], s=36, alpha=0.82,
                   c=METHOD_COLORS.get(meth, "#BBB"), edgecolors="#333", linewidths=0.4,
                   label=METHOD_LABEL.get(meth, meth))
    low = df[df["low_depth"]]
    if not low.empty:
        ax.scatter(low["reads_Mb"], low["contigs_ge1kb_n"], s=60, facecolors="none",
                   edgecolors="#000", linewidths=1.2, label="Low depth (<5 Mb)")
    ax.set_xlabel("Post-rRNA R1 reads (Mb)")
    ax.set_ylabel("Contigs >= 1 kb (n)")
    ax.set_title("A. Assembly yield vs depth")
    ax.legend(loc="lower right", frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # B: counts
    ax = axes[0, 1]
    d = df.sort_values("sample_id")
    x = np.arange(len(d))
    w = 0.38
    ax.bar(x - w / 2, d["contigs_all_n"], width=w, color="#56B4E9", edgecolor="#333", linewidth=0.2, label="All contigs (n)")
    ax.bar(x + w / 2, d["contigs_ge1kb_n"], width=w, color="#009E73", edgecolor="#333", linewidth=0.2, label="Contigs >= 1 kb (n)")
    ax.set_xticks(x)
    ax.set_xticklabels(d["sample_id"], rotation=90, fontsize=5.5)
    ax.set_ylabel("Count")
    ax.set_title("B. Contig counts per sample")
    ax.legend(loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # C: mean length
    ax = axes[1, 0]
    colors = [METHOD_COLORS.get(str(m), "#BBB") for m in d["method"]]
    ax.bar(d["sample_id"], d["avg_len"], color=colors, edgecolor="#333", linewidth=0.3, width=0.82)
    ax.set_ylabel("Mean contig length (bp)")
    ax.set_xlabel("Sample")
    ax.set_title("C. Mean contig length per sample")
    ax.tick_params(axis="x", rotation=90, labelsize=5.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    meth_handles = [Patch(facecolor=METHOD_COLORS.get(m, "#BBB"), edgecolor="#333", label=METHOD_LABEL.get(m, m))
                    for m in method_codes_order(d)]
    ax.legend(handles=meth_handles, loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)

    # D: >=1kb percent
    ax = axes[1, 1]
    ax.bar(d["sample_id"], d["ge1kb_pct"], color=colors, edgecolor="#333", linewidth=0.3, width=0.82)
    ax.set_ylabel("Contigs >= 1 kb (%)")
    ax.set_xlabel("Sample")
    ax.set_title("D. Percent of contigs >= 1 kb")
    ax.tick_params(axis="x", rotation=90, labelsize=5.5)
    ax.set_ylim(0, max(100.0, float(d["ge1kb_pct"].max()) * 1.1))
    ax.legend(handles=meth_handles, loc="upper right", frameon=True, fancybox=False, edgecolor="#CCC", fontsize=6)

    fig.suptitle("Fig04 Assembly", y=1.01, fontsize=10)
    fig.tight_layout()
    return _save(fig, out)


def generate_all_figures(tables: dict[str, pd.DataFrame], fig_dir: Path) -> dict[str, Path]:
    apply_sci_theme()
    mapping = {
        "fig01_stage_yield": fig01_stage_yield,
        "fig02_fastp_qc": fig02_fastp_qc,
        "fig03_rrna_qc": fig03_rrna_qc,
        "fig04_assembly": fig04_assembly,
    }
    # remove any previous figure files in this directory
    if fig_dir.is_dir():
        for old in fig_dir.glob("*.png"):
            try:
                old.unlink()
            except OSError:
                pass
    out: dict[str, Path] = {}
    for key, fn in mapping.items():
        p = fig_dir / f"{key}.png"
        try:
            res = fn(tables, p)
            if res:
                out[key] = res
        except Exception as e:
            print(f"warn: figure {key} failed: {e}")
    return out
