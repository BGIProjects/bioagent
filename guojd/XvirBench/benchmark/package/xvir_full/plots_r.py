"""Stage TSVs, copy R scripts, run ggplot2 figures; optional matplotlib fallback."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import PACKAGE_DIR, default_rscript

R_DIR = PACKAGE_DIR / "r"

STAGE_MAP = {
    "W1/samples.tsv": "W1_samples.tsv",
    "W1/run_qc.tsv": "W1_run_qc.tsv",
    "W2/contigs.tsv": "W2_contigs.tsv",
    "W2/sample_cluster.tsv": "W2_sample_cluster.tsv",
    "W2/cluster_summary.tsv": "W2_cluster_summary.tsv",
    "W2/hmm_iterations.tsv": "W2_hmm_iterations.tsv",
    "W3/host_sample.tsv": "W3_host_sample.tsv",
    "W3/host_top_species.tsv": "W3_host_top_species.tsv",
    "W4/sample_qc.tsv": "W4_sample_qc.tsv",
    "W4/bracken_top15_species.tsv": "W4_bracken_top15_species.tsv",
    "W5/sample_summary.tsv": "W5_sample_summary.tsv",
    "W5/top20_rpm.tsv": "W5_top20_rpm.tsv",
}


def stage_tables(extract_dir: Path, table_dir: Path, master: pd.DataFrame, coverage: pd.DataFrame) -> None:
    table_dir.mkdir(parents=True, exist_ok=True)
    master.to_csv(table_dir / "master_sample_metrics.tsv", sep="\t", index=False)
    coverage.to_csv(table_dir / "coverage.tsv", sep="\t", index=False)
    for src_rel, dst_name in STAGE_MAP.items():
        src = extract_dir / src_rel
        if src.is_file():
            shutil.copy2(src, table_dir / dst_name)


def _copy_r(out_r: Path) -> None:
    out_r.mkdir(parents=True, exist_ok=True)
    for name in ("00_sci_theme.R", "make_figures.R"):
        shutil.copy2(R_DIR / name, out_r / name)


def run_r_figures(table_dir: Path, fig_dir: Path, out_r: Path, rscript: Optional[Path] = None) -> dict:
    fig_dir.mkdir(parents=True, exist_ok=True)
    _copy_r(out_r)
    rs = rscript or default_rscript()
    log = {"rscript": str(rs) if rs else None, "ok": False, "returncode": None, "stderr_tail": ""}
    if rs is None:
        log["stderr_tail"] = "Rscript not found"
        _matplotlib_fallback(table_dir, fig_dir)
        return log
    cmd = [
        str(rs),
        str(out_r / "make_figures.R"),
        str(table_dir),
        str(fig_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log["returncode"] = proc.returncode
    log["stdout_tail"] = (proc.stdout or "")[-2000:]
    log["stderr_tail"] = (proc.stderr or "")[-4000:]
    log["ok"] = proc.returncode == 0
    pngs = list(fig_dir.glob("*.png"))
    if not pngs:
        _matplotlib_fallback(table_dir, fig_dir)
        log["fallback"] = "matplotlib"
    return log


def _matplotlib_fallback(table_dir: Path, fig_dir: Path) -> None:
    """Minimal SCI-style fallback if ggplot2 run produced nothing."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return
    master_p = table_dir / "master_sample_metrics.tsv"
    if not master_p.is_file():
        return
    df = pd.read_csv(master_p, sep="\t")
    if "merge_r1_reads" not in df.columns:
        return
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 8,
        "axes.linewidth": 0.6,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": False,
    })
    fig, ax = plt.subplots(figsize=(4.5, 3.5), dpi=300)
    x = np.arange(len(df))
    ax.bar(x, df["merge_r1_reads"] / 1e6, color="#0072B2", edgecolor="black", linewidth=0.3)
    ax.axhline(5, ls="--", lw=0.6, color="#D55E00")
    ax.set_xticks(x)
    ax.set_xticklabels(df["sample_id"], rotation=45, ha="right")
    ax.set_ylabel("Merged R1 reads (millions)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig01_depth_by_sample.png")
    fig.savefig(fig_dir / "fig01_depth_by_sample.pdf")
    plt.close(fig)
