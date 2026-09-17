"""Fill result text and biological interpretation from tables; skip absent modules."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import METRIC_LABELS, METHOD_LABEL, WF_BY_SHORT
from .discover import Discovery
from . import biology


def _meta_src(source_files: dict) -> str:
    if not source_files:
        return "未找到 groupinfo/sampleinfo，样本 ID 来自结果表"
    bits = []
    for k, v in source_files.items():
        parts = Path(v).parts
        tail = "/".join(parts[-2:]) if len(parts) >= 2 else Path(v).name
        bits.append(f"{k}={tail}")
    return "；".join(bits)



def _fmt(x, nd=2, pct=False, sci=False) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "NA"
    v = float(x)
    if pct:
        if v <= 1.5:
            v = v * 100
        return f"{v:.2f}%"
    if sci and (abs(v) >= 1e5 or (abs(v) < 1e-2 and v != 0)):
        return f"{v:.3g}"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:.{nd}f}"


def _row(overall: pd.DataFrame, metric: str, dataset="core_cohort") -> Optional[pd.Series]:
    if overall is None or overall.empty:
        return None
    sub = overall[(overall["metric"] == metric)]
    if "dataset" in overall.columns:
        hit = sub[sub["dataset"] == dataset]
        if hit.empty:
            hit = sub
        sub = hit
    if sub.empty:
        return None
    return sub.iloc[0]


def _median_range(master: pd.DataFrame, col: str, pct=False) -> str:
    if col not in master.columns:
        return "（该字段未提取）"
    x = pd.to_numeric(master[col], errors="coerce").dropna()
    if x.empty:
        return "（该字段全部缺失）"
    return f"中位数 {_fmt(x.median(), pct=pct)}（范围 {_fmt(x.min(), pct=pct)}–{_fmt(x.max(), pct=pct)}，n={len(x)}）"


def _kw_sentence(tests: pd.DataFrame, metric: str, dataset="core_cohort") -> str:
    if tests is None or tests.empty:
        return ""
    sub = tests[
        (tests["metric"] == metric)
        & (tests["test"] == "kruskal_wallis")
        & (tests.get("dataset", dataset) == dataset if "dataset" in tests.columns else True)
    ]
    if "dataset" in tests.columns:
        sub = tests[(tests["metric"] == metric) & (tests["test"] == "kruskal_wallis") & (tests["dataset"] == dataset)]
    if sub.empty:
        return ""
    r = sub.iloc[0]
    p = r["p_value"]
    sig = "组间差异达到 α=0.05" if pd.notna(p) and p < 0.05 else "组间差异未达 α=0.05"
    extra = ""
    if pd.notna(r.get("effect")):
        extra = f"，ε²={float(r['effect']):.3f}"
    pairs = tests[
        (tests["metric"] == metric)
        & (tests["test"] == "mannwhitney_bh")
        & (tests.get("dataset", "core_cohort") == dataset if "dataset" in tests.columns else True)
    ]
    if "dataset" in tests.columns:
        pairs = tests[(tests["metric"] == metric) & (tests["test"] == "mannwhitney_bh") & (tests["dataset"] == dataset)]
    sig_pairs = pairs[pairs["p_adj_bh"] < 0.05] if not pairs.empty and "p_adj_bh" in pairs.columns else pd.DataFrame()
    pair_txt = ""
    if not sig_pairs.empty:
        pair_txt = " 显著两两比较：" + "；".join(
            f"{row['comparison']} (p_BH={_fmt(row['p_adj_bh'], nd=3, sci=True)})" for _, row in sig_pairs.iterrows()
        )
    return f"按建库方法 Kruskal–Wallis p={_fmt(p, sci=True)}（{sig}{extra}）。{pair_txt}"


def _present(cov: pd.DataFrame, short: str) -> bool:
    if cov is None or cov.empty:
        return False
    row = cov[cov["workflow"] == short]
    if row.empty:
        return False
    return str(row.iloc[0]["status"]) == "extracted"


def build_sections(
    disc: Discovery,
    master: pd.DataFrame,
    coverage: pd.DataFrame,
    stats_frames: dict[str, pd.DataFrame],
    table_dir: Optional[Path] = None,
) -> list[dict]:
    overall = stats_frames.get("overall_core", pd.DataFrame())
    tests = stats_frames.get("tests", pd.DataFrame())
    group_cols = disc.cohort.group_cols
    core = master[master["in_core_cohort"] == True].copy() if "in_core_cohort" in master.columns else master
    low = core[core["low_depth"] == True]["sample_id"].tolist() if "low_depth" in core.columns else []

    sections = []

    # executive
    n = len(core)
    methods = ""
    if "method" in core.columns:
        vc = core["method"].map(lambda x: METHOD_LABEL.get(str(x), str(x))).value_counts()
        methods = "；".join(f"{k} n={v}" for k, v in vc.items())
    present_w = [w.spec.short for w in disc.workflows if w.present]
    missing_w = [w.spec.short for w in disc.workflows if not w.present]
    exec_txt = [
        f"批次 {disc.batch_id} 核心队列 {n} 个生物学样本。",
        f"已提取流程：{', '.join(present_w) if present_w else '无'}。",
        f"未运行/缺失因而整章跳过：{', '.join(missing_w) if missing_w else '无'}。",
        ("分组因子：" + "、".join(group_cols) + "。同时报告总体与分组比较。")
        if group_cols
        else "无可用分组（或仅单一水平）→ 只做总体描述，不做组间检验。",
        f"低深度样本（合并 R1 < 5×10^6）：{', '.join(low) if low else '无'}。低深度会抬高相对丰度类指标（如 RPM），解读时单独标注。",
        "本报告只解释实际抽出的字段；缺失写成「未提取/未运行」，不写成分析失败。结果仅供科研内部参考，不构成诊断。",
    ]
    sections.append(
        {
            "id": "exec",
            "short": "EXEC",
            "title": "执行摘要",
            "skip": False,
            "results": exec_txt,
            "biology": biology.exec_summary(core, low),
            "figures": [],
        }
    )

    # cohort / coverage
    notes = list(disc.cohort.grouping_notes) + list(disc.extra_notes)
    sections.append(
        {
            "id": "cohort",
            "short": "META",
            "title": "样本 Meta 与提取覆盖",
            "skip": False,
            "results": [
                f"Meta 来源：{_meta_src(disc.cohort.source_files)}。",
                *notes,
                "覆盖矩阵见结构化表 coverage.tsv：status=extracted 才进入该流程章节。",
            ],
            "biology": biology.cohort(core),
            "figures": ["fig01_depth_by_sample"],
        }
    )

    def add_or_skip(short: str, title: str, results: list[str], biology: list[str], figures: list[str]):
        ok = _present(coverage, short)
        spec = WF_BY_SHORT[short]
        if not ok:
            sections.append(
                {
                    "id": short.lower(),
                    "short": short,
                    "title": title,
                    "skip": True,
                    "results": [f"本章跳过：{spec.skip_biology} 覆盖状态见 coverage.tsv。"],
                    "biology": [],
                    "figures": [],
                }
            )
            return
        sections.append(
            {
                "id": short.lower(),
                "short": short,
                "title": title,
                "skip": False,
                "results": results,
                "biology": biology,
                "figures": figures,
            }
        )

    # W1
    w1_res = [
        "原始/质控/去 rRNA/合并/组装指标按样本汇总。" + _median_range(core, "merge_r1_reads"),
        "fastp 保留率 " + _median_range(core, "read_retention_fastp_median", pct=True),
        "fastp 后 Q30 " + _median_range(core, "q30_after_fastp_median", pct=True),
        "rRNA 去除后 R1 保留率 " + _median_range(core, "rrna_retention_r1_median", pct=True),
        "≥1 kb contig 数 " + _median_range(core, "contigs_ge1kb_n"),
    ]
    if group_cols:
        for m in ("merge_r1_reads", "read_retention_fastp_median", "contigs_ge1kb_n"):
            s = _kw_sentence(tests, m)
            if s:
                w1_res.append(METRIC_LABELS.get(m, m) + "：" + s)
    add_or_skip(
        "W1",
        "W1 上游质控与组装",
        w1_res,
        biology.w1(core, tests),
        [
            "fig02_w1_fastp_retention",
            "fig03_w1_q30",
            "fig04_w1_rrna_retention",
            "fig05_w1_depth_vs_contigs",
        ],
    )

    w2_res = [
        "假定病毒 contig 数 " + _median_range(core, "n_putative_viral_contigs"),
        "CheckV High-quality 数 " + _median_range(core, "n_high_quality"),
        "ANI80 聚类数 " + _median_range(core, "n_clusters"),
    ]
    if group_cols:
        s = _kw_sentence(tests, "n_putative_viral_contigs")
        if s:
            w2_res.append("每样本假定病毒 contig：" + s)
    add_or_skip(
        "W2",
        "W2 病毒鉴定",
        w2_res,
        biology.w2(core, table_dir, tests),
        ["fig06_w2_checkv_by_sample", "fig07_w2_contig_length", "fig08_w2_viral_contigs_by_method"],
    )

    w3_res = [
        "推断宿主物种数 " + _median_range(core, "n_species_inferred"),
        "推断宿主属数 " + _median_range(core, "n_genus_inferred"),
    ]
    if "top_host_species" in core.columns:
        vc = core["top_host_species"].dropna().value_counts().head(5)
        if not vc.empty:
            w3_res.append("核心队列最常见推断物种：" + "；".join(f"{k} (n={v})" for k, v in vc.items()))
    n_w3 = int(master["n_species_inferred"].notna().sum()) if "n_species_inferred" in master.columns else 0
    if n_w3 > len(core):
        w3_res.append(
            f"W3 另包含核心队列之外的样本（有宿主指标的样本共 {n_w3} 个）。组间比较仅在有 method/host 标签的核心队列进行。"
        )
    add_or_skip(
        "W3",
        "W3 宿主鉴定",
        w3_res,
        biology.w3(core),
        ["fig09_w3_host_species"],
    )

    w4_res = [
        "Kraken 未分类比例 " + _median_range(core, "kraken_unclassified_frac", pct=True),
        "Bracken 物种数 " + _median_range(core, "bracken_species_taxa"),
        "Bracken 物种级分配 reads " + _median_range(core, "bracken_species_reads_assigned"),
    ]
    if group_cols:
        for m in ("kraken_unclassified_frac", "bracken_species_taxa"):
            s = _kw_sentence(tests, m)
            if s:
                w4_res.append(METRIC_LABELS.get(m, m) + "：" + s)
    add_or_skip(
        "W4",
        "W4 微生物谱（Kraken2/Bracken）",
        w4_res,
        biology.w4(core, table_dir, tests),
        ["fig10_w4_unclassified", "fig11_w4_species_richness", "fig12_w4_top_taxa"],
    )

    w5_res = [
        "有比对 reads 的病毒 contig 数 " + _median_range(core, "n_viral_contigs_with_reads"),
        "病毒 contig 比对率 " + _median_range(core, "mapping_rate_pct", pct=True),
        "最大 RPM " + _median_range(core, "max_rpm"),
        "中位 RPM " + _median_range(core, "median_rpm"),
    ]
    if group_cols:
        for m in ("mapping_rate_pct", "max_rpm"):
            s = _kw_sentence(tests, m)
            if s:
                w5_res.append(METRIC_LABELS.get(m, m) + "：" + s)
    add_or_skip(
        "W5",
        "W5 病毒定量（RPM）",
        w5_res,
        biology.w5(core, tests),
        ["fig13_w5_mapping_rate", "fig14_w5_max_rpm", "fig15_w5_depth_vs_mapping"],
    )

    add_or_skip(
        "W6",
        "W6 病毒注释",
        [],
        [],
        [],
    )
    # W7 is optional and not in the default report

    # cross
    if _present(coverage, "W1") and _present(coverage, "W5"):
        sections.append(
            {
                "id": "cross",
                "short": "CROSS",
                "title": "跨流程衔接",
                "skip": False,
                "results": [
                    "深度（W1）与病毒比对率/RPM（W5）应联合看：深度不足时，高 RPM 优先视为分母效应。",
                    "W2 代表序列是 W5 的参考；W4 未分类比例高与 W5 病毒比对率低可以同时成立，因为二者参考库不同。",
                ],
                "biology": biology.cross(core),
                "figures": ["fig15_w5_depth_vs_mapping"],
            }
        )

    return sections
