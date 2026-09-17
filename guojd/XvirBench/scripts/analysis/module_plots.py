"""模块化多面板图表（参考 vazyme fragmentation_test/analysis）。"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from cohort import METHOD_LABEL, METHOD_ORDER
from plot_styles import (
    DPI,
    FACET_H,
    FACET_W,
    HOST_COLORS_HEX,
    HOST_LABEL,
    METHOD_COLORS,
    METHOD_PALETTE,
    PANEL_H,
    PANEL_W,
    QUAD_H,
    QUAD_W,
    WIDE_H,
    WIDE_W,
    apply_theme,
    method_label_order,
    save_close,
)


def _methods_present(df: pd.DataFrame) -> List[str]:
    return [m for m in METHOD_ORDER if m in df["method"].astype(str).unique()]


def _box_strip_ax(ax, df, metric, ylabel, hue: Optional[str] = None, low_depth_col: str = "low_depth"):
    sub = df.dropna(subset=[metric]).copy()
    if sub.empty:
        ax.set_visible(False)
        return
    methods = _methods_present(sub)
    labels = [METHOD_LABEL[m] for m in methods]
    sub["method_label"] = pd.Categorical(
        sub["method"].map(METHOD_LABEL), categories=labels, ordered=True
    )
    palette = {METHOD_LABEL[m]: METHOD_COLORS[m] for m in methods}
    sns.boxplot(
        data=sub, x="method_label", y=metric, order=labels,
        ax=ax, width=0.5, fliersize=0, color="#e8e8e8", zorder=1,
    )
    if hue and hue in sub.columns:
        sns.stripplot(
            data=sub, x="method_label", y=metric, order=labels,
            hue=hue, palette="tab10", ax=ax, size=3.5, alpha=0.85,
            jitter=0.18, dodge=False, zorder=2, legend=False,
        )
    else:
        sns.stripplot(
            data=sub, x="method_label", y=metric, order=labels,
            ax=ax, size=3.5, color="#333333", alpha=0.65, jitter=0.18, zorder=2,
        )
    if low_depth_col in sub.columns:
        low = sub[sub[low_depth_col].fillna(False)]
        for i, meth in enumerate(methods):
            pts = low[low["method"] == meth]
            if not pts.empty:
                ax.scatter(
                    [i] * len(pts), pts[metric], facecolors="none",
                    edgecolors="#c53030", s=36, linewidths=1.2, zorder=4,
                )
    ax.set_xlabel("")
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(axis="x", rotation=18)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")


def plot_quad_panel(
    df: pd.DataFrame,
    metrics: Sequence[str],
    labels: Dict[str, str],
    out: Path,
    suptitle: str = "",
    hue: str = "sn",
) -> Optional[Path]:
    apply_theme()
    fig, axes = plt.subplots(2, 2, figsize=(QUAD_W, QUAD_H))
    for ax, m in zip(axes.flat, metrics[:4]):
        _box_strip_ax(ax, df, m, labels.get(m, m), hue=hue)
        ax.set_title(labels.get(m, m), fontsize=9, fontweight="600")
    if suptitle:
        fig.suptitle(suptitle, fontsize=10, fontweight="700", y=1.02)
    fig.tight_layout()
    save_close(fig, out)
    return out if out.is_file() else None


def plot_faceted_by_host(
    df: pd.DataFrame,
    metric: str,
    label: str,
    out: Path,
) -> Optional[Path]:
    apply_theme()
    hosts = [h for h in ("rat", "tick", "mosquito") if h in df["host"].astype(str).unique()]
    fig, axes = plt.subplots(1, len(hosts), figsize=(FACET_W, FACET_H), sharey=True)
    if len(hosts) == 1:
        axes = [axes]
    for ax, host in zip(axes, hosts):
        sub = df[df["host"] == host]
        _box_strip_ax(ax, sub, metric, label if ax is axes[0] else "")
        ax.set_title(HOST_LABEL.get(host, host), fontsize=9, fontweight="600", color=HOST_COLORS_HEX.get(host, "#333"))
    fig.suptitle(f"{label}（分宿主）", fontsize=10, fontweight="700", y=1.05)
    fig.tight_layout()
    save_close(fig, out)
    return out if out.is_file() else None


def plot_method_bar_se(
    summary_df: pd.DataFrame,
    metrics: Sequence[str],
    labels: Dict[str, str],
    out: Path,
    dataset: str = "all_samples",
) -> Optional[Path]:
    apply_theme()
    sm = summary_df[summary_df["dataset"] == dataset] if "dataset" in summary_df.columns else summary_df
    if sm.empty:
        return None
    n = min(len(metrics), 4)
    fig, axes = plt.subplots(1, n, figsize=(WIDE_W, WIDE_H))
    if n == 1:
        axes = [axes]
    for ax, m in zip(axes, metrics[:n]):
        rows = []
        for meth in _methods_present(sm.rename(columns={"method": "method"})):
            r = sm[sm["method"] == meth]
            if r.empty:
                continue
            rows.append({
                "method_label": METHOD_LABEL[meth],
                "mean": r.iloc[0].get(f"{m}_mean"),
                "se": r.iloc[0].get(f"{m}_sd", 0) / np.sqrt(max(r.iloc[0].get("n", 1), 1)),
            })
        if not rows:
            ax.set_visible(False)
            continue
        d = pd.DataFrame(rows)
        colors = [METHOD_COLORS.get(m, "#999") for m in _methods_present(sm)]
        ax.bar(d["method_label"], d["mean"], yerr=d["se"], capsize=3, color=colors, alpha=0.85, edgecolor="white")
        ax.set_title(labels.get(m, m), fontsize=8.5)
        ax.tick_params(axis="x", rotation=20)
    fig.suptitle("方法均值 ± 标准误", fontsize=10, fontweight="700")
    fig.tight_layout()
    save_close(fig, out)
    return out if out.is_file() else None


def plot_stacked_alignment(df: pd.DataFrame, out: Path) -> Optional[Path]:
    apply_theme()
    if "host_mapped_pct" not in df.columns:
        df = df.copy()
        df["host_mapped_pct"] = pd.to_numeric(df["uniquely_mapped_pct"], errors="coerce") + pd.to_numeric(
            df["multi_mapped_pct"], errors="coerce"
        )
    fig, axes = plt.subplots(1, 2, figsize=(WIDE_W, WIDE_H))
    for ax, metric, title in [
        (axes[0], "host_mapped_pct", "宿主比对率 (%)"),
        (axes[1], "multi_mapped_pct", "多重比对率 (%)"),
    ]:
        _box_strip_ax(ax, df, metric, title, hue="sn")
        ax.set_title(title, fontsize=9)
    fig.tight_layout()
    save_close(fig, out)
    return out if out.is_file() else None


def plot_correlation_heatmap(df: pd.DataFrame, metrics: Sequence[str], out: Path, title: str = "") -> Optional[Path]:
    apply_theme()
    cols = [m for m in metrics if m in df.columns]
    mat = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(mat) < 3:
        return None
    corr = mat.corr()
    fig, ax = plt.subplots(figsize=(PANEL_W + 1.5, PANEL_H + 1.5))
    sns.heatmap(
        corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
        square=True, linewidths=0.4, ax=ax, cbar_kws={"shrink": 0.75},
        annot_kws={"size": 7},
    )
    ax.set_title(title or "指标相关", fontsize=9)
    fig.tight_layout()
    save_close(fig, out)
    return out if out.is_file() else None


def plot_pca_samples(df: pd.DataFrame, metrics: Sequence[str], out: Path) -> Optional[Path]:
    apply_theme()
    cols = [m for m in metrics if m in df.columns]
    mat = df[cols].apply(pd.to_numeric, errors="coerce")
    mask = mat.notna().all(axis=1)
    mat = mat[mask].to_numpy(dtype=float)
    meta = df.loc[mask, ["method", "host", "sample_id"]].copy()
    if len(mat) < 4:
        return None
    X = (mat - mat.mean(axis=0)) / (mat.std(axis=0) + 1e-9)
    _, _, vt = np.linalg.svd(X, full_matrices=False)
    pcs = X @ vt[:2].T
    fig, ax = plt.subplots(figsize=(PANEL_W + 1.2, PANEL_H + 0.8))
    for host in meta["host"].unique():
        for meth in _methods_present(meta.rename(columns={"method": "method"})):
            idx = (meta["host"] == host) & (meta["method"] == meth)
            if not idx.any():
                continue
            ax.scatter(
                pcs[idx, 0], pcs[idx, 1],
                c=METHOD_COLORS.get(meth, "#666"),
                marker={"rat": "o", "tick": "s", "mosquito": "^"}.get(host, "o"),
                s=42, alpha=0.85, edgecolors="white", linewidths=0.4,
                label=f"{HOST_LABEL.get(host, host)}/{METHOD_LABEL[meth]}",
            )
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("样本 PCA（指标空间）", fontsize=9)
    ax.legend(fontsize=6, loc="best", frameon=True, ncol=2)
    fig.tight_layout()
    save_close(fig, out)
    return out if out.is_file() else None


def plot_host_comparison_heatmap(
    summary_df: pd.DataFrame,
    metric: str,
    label: str,
    out: Path,
) -> Optional[Path]:
    """宿主 × 方法 均值热图。"""
    apply_theme()
    if "dataset" not in summary_df.columns:
        return None
    hosts = ["host_rat", "host_tick", "host_mosquito"]
    rows = []
    for ds in hosts:
        host = ds.replace("host_", "")
        sm = summary_df[summary_df["dataset"] == ds]
        for meth in METHOD_ORDER:
            r = sm[sm["method"] == meth]
            if r.empty:
                continue
            rows.append({
                "host": host,
                "method": METHOD_LABEL[meth],
                "value": r.iloc[0].get(f"{metric}_mean"),
            })
    if not rows:
        return None
    d = pd.DataFrame(rows).pivot(index="host", columns="method", values="value")
    fig, ax = plt.subplots(figsize=(PANEL_W + 1.5, PANEL_H))
    sns.heatmap(d, annot=True, fmt=".3g", cmap="YlGnBu", ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title(f"{label}（宿主 × 方法）", fontsize=9)
    ax.set_xlabel("")
    fig.tight_layout()
    save_close(fig, out)
    return out if out.is_file() else None


def plot_w5_virus_panels(
    sample_df: pd.DataFrame,
    rpm_df: pd.DataFrame,
    out_dir: Path,
) -> List[Path]:
    """W5 病毒：检出数 + log10 RPM 箱线图（参考 run_virus_comparison.py）。"""
    apply_theme()
    paths: List[Path] = []
    meta = sample_df[["sample_id", "method", "method_label", "sn", "host"]].drop_duplicates()
    rpm = rpm_df.merge(meta, on="sample_id", how="left")
    rpm["RPM"] = pd.to_numeric(rpm["RPM"], errors="coerce")
    cov = pd.to_numeric(rpm.get("coverage", rpm.get("mean_coverage_pct", 0)), errors="coerce")
    q = rpm[(cov > 20) & (rpm["RPM"] > 1)].copy()
    if q.empty:
        return paths
    q["log10_rpm"] = np.log10(q["RPM"])

    # detection count
    det = q.groupby(["method", "method_label"], observed=True)["reference_id"].nunique().reset_index(name="n")
    fig, ax = plt.subplots(figsize=(PANEL_W + 0.5, PANEL_H))
    order = method_label_order(det)
    sns.barplot(data=det, x="method_label", y="n", order=order, hue="method_label", palette=METHOD_PALETTE, ax=ax, legend=False)
    ax.set_title("各方法检出病毒数（cov>20%, RPM>1）")
    ax.tick_params(axis="x", rotation=15)
    p1 = out_dir / "w5_01_detection_by_method.png"
    save_close(fig, p1)
    paths.append(p1)

    # RPM box + strip by sn
    fig, ax = plt.subplots(figsize=(WIDE_W, PANEL_H + 0.3))
    order = method_label_order(q)
    sns.boxplot(data=q, x="method_label", y="log10_rpm", order=order, color="#ddd", width=0.5, ax=ax, fliersize=0)
    sns.stripplot(data=q, x="method_label", y="log10_rpm", order=order, hue="sn", palette="tab10", size=3.5, ax=ax, dodge=False, jitter=0.2)
    ax.set_title("log10(RPM) 分布（颜色=测序文库 sn）")
    ax.legend(title="测序文库", fontsize=6, loc="upper left", bbox_to_anchor=(1.02, 1))
    p2 = out_dir / "w5_02_rpm_by_method.png"
    save_close(fig, p2)
    paths.append(p2)

    # faceted by host
    fig, axes = plt.subplots(1, 3, figsize=(FACET_W + 1, FACET_H), sharey=True)
    for ax, host in zip(axes, ("rat", "tick", "mosquito")):
        sub = q[q["host"] == host]
        if sub.empty:
            ax.set_visible(False)
            continue
        order = method_label_order(sub)
        sns.boxplot(data=sub, x="method_label", y="log10_rpm", order=order, color="#ddd", width=0.5, ax=ax, fliersize=0)
        sns.stripplot(data=sub, x="method_label", y="log10_rpm", order=order, size=3, color="#444", ax=ax, jitter=0.2)
        ax.set_title(HOST_LABEL.get(host, host))
        ax.tick_params(axis="x", rotation=20)
    fig.suptitle("log10(RPM) 分宿主", fontsize=10)
    fig.tight_layout()
    p3 = out_dir / "w5_03_rpm_by_host.png"
    save_close(fig, p3)
    paths.append(p3)
    return paths
