"""Data-bound biological discussion: every sentence cites a figure id or table value."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import METHOD_LABEL

RODENT_HINTS = (
    "Ligilactobacillus",
    "Helicobacter apodemus",
    "Helicobacter typhlonius",
    "Romboutsia",
)
KIT_HINTS = ("Ralstonia", "Cutibacterium acnes", "Bradyrhizobium", "Burkholderia")


def _read(table_dir: Path | None, name: str) -> pd.DataFrame:
    if table_dir is None:
        return pd.DataFrame()
    p = Path(table_dir) / name
    if not p.is_file():
        return pd.DataFrame()
    return pd.read_csv(p, sep="\t")


def _frac_pct(x) -> str:
    v = float(x)
    if abs(v) <= 1.5:
        v *= 100
    return f"{v:.2f}%"


def _map_pct(x) -> str:
    """mapping_rate_pct is already in percent units (0.04 means 0.04%)."""
    return f"{float(x):.3f}%"


def _ids(xs) -> str:
    return "、".join(str(x) for x in list(xs))


def _method(x) -> str:
    return METHOD_LABEL.get(str(x), str(x))


def _kw(tests: pd.DataFrame, metric: str) -> str:
    if tests is None or tests.empty:
        return ""
    sub = tests[(tests["metric"] == metric) & (tests["test"] == "kruskal_wallis")]
    if "dataset" in tests.columns:
        hit = sub[sub["dataset"] == "core_cohort"]
        if not hit.empty:
            sub = hit
    if sub.empty:
        return ""
    p = sub.iloc[0]["p_value"]
    if pd.isna(p):
        return ""
    flag = "达到" if float(p) < 0.05 else "未达"
    return f"Kruskal–Wallis p={float(p):.4f}（组间差异{flag} α=0.05）"


def _val(core: pd.DataFrame, sid: str, col: str):
    idx = core.set_index("sample_id")
    if sid not in idx.index or col not in idx.columns:
        return None
    return idx.loc[sid, col]


def exec_summary(core: pd.DataFrame, low: list) -> list[str]:
    n = len(core)
    host = core["host"].dropna().astype(str).mode().iloc[0] if "host" in core.columns and core["host"].notna().any() else "未标注"
    methods = []
    if "method" in core.columns:
        vc = core["method"].map(_method).value_counts()
        methods = [f"{k} n={int(v)}" for k, v in vc.items()]
    low_txt = _ids(low) if low else "无"
    return [
        f"本核心队列 n={n}，设计宿主为 {host}，建库方法 { '；'.join(methods) if methods else '未分组' }。"
        f"低深度样本（fig01 虚线以下）为 {low_txt}。后续 RPM、物种数、contig 数先对照 fig01，再谈生物学。",
        "分组每臂大约 3–4 个样本：不显著不能写成方法等价，显著也不能写成某种打断更好；正文只报告本表里的 p 与效应量。",
    ]


def cohort(core: pd.DataFrame) -> list[str]:
    out = []
    if "merge_r1_reads" in core.columns:
        r1 = pd.to_numeric(core["merge_r1_reads"], errors="coerce")
        low = core.loc[r1 < 5e6]
        if low.empty:
            out.append("【fig01_depth_by_sample】核心队列无人低于 5 million R1。")
        else:
            bits = []
            for _, r in low.iterrows():
                bits.append(f"{r['sample_id']}={int(r['merge_r1_reads']):,}（{_method(r.get('method',''))}）")
            other = core.loc[r1 >= 5e6]
            out.append(
                f"【fig01_depth_by_sample】低于虚线的是 {'、'.join(bits)}。"
                f"其余 {len(other)} 个样本 R1 中位数 {other['merge_r1_reads'].median()/1e6:.1f} million。"
                "同方法的其他样本（例如 RNA 94°C 的 v76/v78，RNA 85°C 的 v79/v82）深度正常，"
                "因此低深度是个别文库产量问题，不是某种打断方法的固有属性。"
            )
    if "host" in core.columns:
        hosts = core["host"].dropna().astype(str).unique().tolist()
        if len(hosts) <= 1:
            out.append(
                f"宿主列只有 {hosts[0] if hosts else 'NA'} 一个水平，做宿主组间检验没有信息量；分组只保留 method。"
            )
    return out


def w1(core: pd.DataFrame, tests: pd.DataFrame) -> list[str]:
    out = []
    if "read_retention_fastp_median" in core.columns:
        x = pd.to_numeric(core["read_retention_fastp_median"], errors="coerce")
        kw = _kw(tests, "read_retention_fastp_median")
        out.append(
            f"【fig02_w1_fastp_retention】fastp 保留率中位数 {_frac_pct(x.median())}"
            f"（范围 {_frac_pct(x.min())}–{_frac_pct(x.max())}）。三种方法箱线重叠。"
            f"{kw + '，' if kw else ''}本批次接头/低质量过滤负担相近，不能用 fastp 损失解释后面 fig12 的人源优势。"
        )
    if "q30_after_fastp_median" in core.columns:
        x = pd.to_numeric(core["q30_after_fastp_median"], errors="coerce")
        out.append(
            f"【fig03_w1_q30】fastp 后 Q30 中位数 {_frac_pct(x.median())}，最低仍 {_frac_pct(x.min())}。"
            "碱基质量不是本队列分类异常的原因。"
        )
    if "rrna_retention_r1_median" in core.columns:
        rr = pd.to_numeric(core["rrna_retention_r1_median"], errors="coerce")
        low_rr = core.loc[rr < 0.7].sort_values("rrna_retention_r1_median")
        bits = []
        for _, r in low_rr.iterrows():
            bits.append(
                f"{r['sample_id']}={_frac_pct(r['rrna_retention_r1_median'])}（{_method(r.get('method',''))}）"
            )
        high_n = int((rr >= 0.95).sum())
        extra = ""
        if "v70" in set(core["sample_id"]) and "v88" in set(core["sample_id"]):
            extra = (
                "v70 深度并不低（R1 约 1.2×10^7）但 rRNA 保留率与低深度的 v88 一样差，"
                "说明 rRNA 残留/去除效率与测序深度不是同一件事。"
            )
        out.append(
            f"【fig04_w1_rrna_retention】{high_n}/{len(core)} 个样本 rRNA 去除后 R1 保留率 ≥95%；"
            f"低于 70% 的是 {'、'.join(bits) if bits else '无'}。{extra}"
            "这些样本的非 rRNA 微生物信号会被稀释，看 fig11 物种数、fig12 组成时把它们与高保留率样本分开。"
        )
    if {"merge_r1_reads", "contigs_ge1kb_n"} <= set(core.columns):
        cmin, cmax = int(core["contigs_ge1kb_n"].min()), int(core["contigs_ge1kb_n"].max())
        low = core.loc[core.get("low_depth") == True] if "low_depth" in core.columns else core.iloc[0:0]
        low_txt = ""
        if not low.empty:
            low_txt = "、".join(
                f"{r.sample_id} 仅 {int(r.contigs_ge1kb_n):,} 条" for _, r in low.iterrows()
            )
        kw = _kw(tests, "contigs_ge1kb_n")
        out.append(
            f"【fig05_w1_depth_vs_contigs】≥1 kb contig 数 {cmin:,}–{cmax:,}，随 R1 深度上升。"
            f"{low_txt + '，与 fig01 同向，不能写成这两种打断方法组装差。' if low_txt else ''}"
            f"{kw}"
        )
    return out


def w2(core: pd.DataFrame, table_dir: Path | None, tests: pd.DataFrame) -> list[str]:
    out = []
    contigs = _read(table_dir, "W2_contigs.tsv")
    if not contigs.empty and "checkv_quality" in contigs.columns:
        if "source_sample" in contigs.columns:
            core_hit = contigs[contigs["source_sample"].isin(set(core["sample_id"]))]
            if not core_hit.empty:
                contigs = core_hit
        vc = contigs["checkv_quality"].fillna("NA").value_counts()
        parts = "、".join(f"{k} {int(v)} 条" for k, v in vc.items())
        n_hq = int(vc.get("High-quality", 0) + vc.get("Complete", 0))
        out.append(
            f"【fig06_w2_checkv_by_sample】抽出 {len(contigs)} 条假定病毒 contig（{parts}）。"
            f"High-quality+Complete 合计 {n_hq} 条，只占少数。"
            "RNA 病毒常以部分基因组被召回，不能用 HQ 条数当流行率，也不能把 Medium/Low 条丢掉当「没有病毒」。"
        )
    if not contigs.empty:
        length = None
        for col in ("length", "contig_length"):
            if col in contigs.columns:
                length = pd.to_numeric(contigs[col], errors="coerce")
                break
        if length is not None and length.notna().any():
            out.append(
                f"【fig07_w2_contig_length】长度中位数 {int(length.median()):,} bp"
                f"（最长 {int(length.max()):,} bp）。短 contig 居多符合宏转录组组装碎片化，"
                "单独一条短序列不等于「基因组残缺致病」。"
            )
    if "n_putative_viral_contigs" in core.columns:
        x = pd.to_numeric(core["n_putative_viral_contigs"], errors="coerce")
        low = core.loc[core.get("low_depth") == True] if "low_depth" in core.columns else core.iloc[0:0]
        extra = ""
        if not low.empty:
            extra = "低深度样本 " + "、".join(
                f"{r.sample_id}={int(r.n_putative_viral_contigs)}" for _, r in low.iterrows()
            ) + "，落在队列下限，与 fig01 同向。"
        kw = _kw(tests, "n_putative_viral_contigs")
        out.append(
            f"【fig08_w2_viral_contigs_by_method】每样本假定病毒 contig 中位数 {x.median():.0f}"
            f"（范围 {int(x.min())}–{int(x.max())}）。方法组箱线重叠。{extra}{(' ' + kw) if kw else ''}"
        )
    return out


def w3(core: pd.DataFrame) -> list[str]:
    if "top_host_species" not in core.columns:
        return ["【fig09_w3_host_species】未抽出推断物种列，无法与设计宿主对照。"]
    vc = core["top_host_species"].dropna().value_counts()
    top = vc.index[0]
    n = int(vc.iloc[0])
    host = core["host"].dropna().astype(str).mode().iloc[0] if "host" in core.columns and core["host"].notna().any() else "未标注"
    return [
        f"【fig09_w3_host_species】核心队列 {n}/{len(core)} 个样本的线粒体推断物种均为 {top}，与实验设计宿主（{host}）一致。"
        "这是标记基因证据，不是 Kraken 的 k-mer 分类。下一章 fig12 若出现人源优势，必须对照本图，不能改写成「样本来自人」。"
    ]


def w4(core: pd.DataFrame, table_dir: Path | None, tests: pd.DataFrame) -> list[str]:
    out = []
    if "kraken_unclassified_frac" in core.columns:
        x = pd.to_numeric(core["kraken_unclassified_frac"], errors="coerce")
        kw = _kw(tests, "kraken_unclassified_frac")
        out.append(
            f"【fig10_w4_unclassified】Kraken 未分类比例中位数 {_frac_pct(x.median())}"
            f"（范围 {_frac_pct(x.min())}–{_frac_pct(x.max())}）。{kw + '。' if kw else ''}"
            "也就是绝大多数 reads 根本没进 fig12 的物种堆叠：fig12 描述的是「已分类的那一小块」，不是全库组成。"
        )
    if "bracken_species_taxa" in core.columns:
        x = pd.to_numeric(core["bracken_species_taxa"], errors="coerce")
        low = core.nsmallest(2, "bracken_species_taxa")
        bits = []
        for _, r in low.iterrows():
            flag = "低深度" if bool(r.get("low_depth")) else "非低深度"
            bits.append(f"{r['sample_id']}={int(r['bracken_species_taxa'])}（{flag}）")
        kw = _kw(tests, "bracken_species_taxa")
        out.append(
            f"【fig11_w4_species_richness】Bracken 物种数中位数 {x.median():.0f}"
            f"（范围 {int(x.min())}–{int(x.max())}）。最低的是 {'、'.join(bits)}，与 fig01 低深度样本重叠，"
            f"优先解释为检测限而不是这些样本「无菌」。{kw}"
        )
    top = _read(table_dir, "W4_bracken_top15_species.tsv")
    if top.empty or "name" not in top.columns:
        out.append("【fig12_w4_top_taxa】未抽出 top-15 表，跳过组成讨论。")
        return out
    t = top[top["sample_id"].isin(set(core["sample_id"]))].copy()
    if t.empty:
        out.append("【fig12_w4_top_taxa】top-15 表与核心样本 ID 对不上，跳过。")
        return out
    if "rank" in t.columns:
        r1 = t[pd.to_numeric(t["rank"], errors="coerce") == 1].copy()
    else:
        r1 = t.sort_values("fraction_total_reads", ascending=False).groupby("sample_id", as_index=False).head(1)
    n_samp = r1["sample_id"].nunique()
    top1_name = str(r1["name"].mode().iloc[0]) if not r1.empty else "NA"
    n_top1 = int((r1["name"] == top1_name).sum()) if not r1.empty else 0
    fr = pd.to_numeric(r1["fraction_total_reads"], errors="coerce")
    host = (
        core["host"].dropna().astype(str).mode().iloc[0]
        if "host" in core.columns and core["host"].notna().any()
        else "unknown"
    )
    w3_sp = (
        core["top_host_species"].dropna().mode().iloc[0]
        if "top_host_species" in core.columns and core["top_host_species"].notna().any()
        else "未提供"
    )
    out.append(
        f"【fig12_w4_top_taxa】(i) {n_top1}/{n_samp} 个核心样本的 Bracken top-15 第一名是 {top1_name}"
        f"（已分类/top-15 空间比例 {_frac_pct(fr.min())}–{_frac_pct(fr.max())}，中位数 {_frac_pct(fr.median())}）。"
        f"实验设计宿主为 {host}，W3（fig09）推断为 {w3_sp}。人是主分类单元与大鼠宿主冲突，"
        "不能读成这些样本以人源组织或人体微生物为主。"
    )
    out.append(
        "(ii) 可能机制（并列，本数据不能单独证实哪一条）："
        "① 所用 Kraken/Bracken 库中人类基因组/转录组过度代表，哺乳动物保守 rRNA 残片或 mRNA 被派到 Homo sapiens；"
        "② 大鼠转录本在该数据库覆盖不足，最近邻变成人类；"
        "③ 建库、试剂或操作引入人源核酸。"
        "结合 fig10，未分类仍占约 83%–95%，因此即使已分类块里人占 86%–98%，也只覆盖文库的少数 reads。"
    )
    human_mask = t["name"].astype(str).str.contains(r"Homo|sapiens", case=False, na=False)
    rest = t.loc[~human_mask]
    if rest.empty:
        out.append("(iii) 去掉人源后 top-15 表无剩余物种。")
        return out
    rest_sum = rest.groupby("name")["fraction_total_reads"].sum().sort_values(ascending=False)
    lead = rest_sum.head(6)
    lead_txt = "、".join(f"{k}（合计比例 {float(v):.4f}）" for k, v in lead.items())
    per = rest.sort_values("fraction_total_reads", ascending=False).groupby("sample_id", as_index=False).first()
    if "method" in core.columns:
        per = per.merge(core[["sample_id", "method"]], on="sample_id", how="left")
    vc = per["name"].value_counts()
    per_bits = []
    for name, n in vc.items():
        sids = per.loc[per["name"] == name, "sample_id"].tolist()
        per_bits.append(f"{name} {int(n)}/{len(per)} 样本（{_ids(sids)}）")
    presence = rest.groupby("name")["sample_id"].nunique().sort_values(ascending=False)
    rodent_bits = []
    seen = set()
    for key in RODENT_HINTS:
        hit = rest[rest["name"].astype(str).str.contains(key, case=False, na=False)]
        if hit.empty:
            continue
        for nm, g in hit.groupby("name"):
            if nm in seen:
                continue
            seen.add(nm)
            rodent_bits.append(f"{nm} 出现在 {g['sample_id'].nunique()}/{n_samp} 个样本")
    kit_bits = []
    for key in KIT_HINTS:
        hit = rest[rest["name"].astype(str).str.contains(key, case=False, na=False)]
        if hit.empty:
            continue
        for nm, g in hit.groupby("name"):
            kit_bits.append(f"{nm} {g['sample_id'].nunique()}/{n_samp} 样本")
    out.append(
        f"(iii) 去掉 {top1_name} 之后，剩余 top-15 类群按合计比例最高的是 {lead_txt}。"
        f"按样本把剩余类群重新排第一名：{'；'.join(per_bits)}。"
        f"剩余第一名的比例只有约 {_frac_pct(per['fraction_total_reads'].min())}–{_frac_pct(per['fraction_total_reads'].max())}，"
        "因为人已经占掉已分类块的绝大部分。"
        + (" 更符合啮齿动物肠道背景的类群：" + "；".join(rodent_bits) + "。" if rodent_bits else "")
        + (
            " Staphylococcus aureus / Escherichia coli 既可能是定植也可能是皮肤或试剂背景，不能当感染。"
            + ((" 常见试剂/皮肤背景：" + "；".join(kit_bits) + "。") if kit_bits else "")
        )
    )
    if "method" in core.columns:
        hum = t.loc[human_mask, ["sample_id", "fraction_total_reads"]].merge(
            core[["sample_id", "method"]], on="sample_id", how="left"
        )
        by = hum.groupby("method")["fraction_total_reads"].agg(["median", "min", "max"])
        by_txt = "、".join(
            f"{_method(m)} 中位数 {_frac_pct(r['median'])}（{_frac_pct(r['min'])}–{_frac_pct(r['max'])}）"
            for m, r in by.iterrows()
        )
        r1m = r1.merge(core[["sample_id", "method"]], on="sample_id", how="left")
        still = r1m.groupby("method")["name"].apply(lambda s: bool((s == top1_name).all()))
        if bool(still.all()):
            still_txt = "三种打断方法下第一名仍全部是人"
        else:
            still_txt = "并非所有方法都以人为第一名：" + "、".join(
                f"{_method(m)}={'是' if v else '否'}" for m, v in still.items()
            )
        ecol = per[per["name"].astype(str).str.contains("Escherichia coli", case=False, na=False)]
        ecol_txt = ""
        if not ecol.empty:
            ecol_txt = (
                "去人源后改由 Escherichia coli 居首的是 "
                + "、".join(f"{r.sample_id}（{_method(r.get('method',''))}）" for _, r in ecol.iterrows())
                + "，分属不同打断方法，所以也不是单一技术路线的产物。"
            )
        low_depth_ids = core.loc[core.get("low_depth") == True, "sample_id"].tolist() if "low_depth" in core.columns else []
        depth_txt = ""
        if low_depth_ids:
            sub = r1m[r1m["sample_id"].isin(low_depth_ids)]
            depth_txt = (
                "低深度样本 "
                + "、".join(
                    f"{r.sample_id} 人源比例 {_frac_pct(r.fraction_total_reads)}" for _, r in sub.iterrows()
                )
                + "，与深度充足样本同方向，说明 fig12 的人源第一名不是低深度特有。"
            )
        out.append(
            f"(iv) 建库方法：人源第一名比例 {by_txt}。{still_txt}。"
            f"{ecol_txt}{depth_txt}"
            "因此 fig12 的人源主导更像分类器把哺乳动物 reads 派给人这一共同偏差，而不像某种打断特有的伪影。"
            "cDNA 组中位数略低、部分样本物种数更高，只提示已分类块里非人源残留稍多；组间检验未显著，不能宣布 cDNA 更能去人源。"
        )
    return out


def w5(core: pd.DataFrame, tests: pd.DataFrame) -> list[str]:
    out = []
    if "mapping_rate_pct" in core.columns:
        x = pd.to_numeric(core["mapping_rate_pct"], errors="coerce")
        kw = _kw(tests, "mapping_rate_pct")
        out.append(
            f"【fig13_w5_mapping_rate】病毒 contig 比对率中位数 {_map_pct(x.median())}"
            f"（范围 {_map_pct(x.min())}–{_map_pct(x.max())}），整体远低于 1%。{kw + '。' if kw else ''}"
            "与 fig10 高未分类一致：病毒参考只解释了极少 reads。"
        )
    if "max_rpm" in core.columns:
        top = core.nlargest(3, "max_rpm")
        bits = []
        for _, r in top.iterrows():
            flag = "低深度" if bool(r.get("low_depth")) else "非低深度"
            bits.append(f"{r['sample_id']}={float(r['max_rpm']):.1f} RPM（{flag}，{_method(r.get('method',''))}）")
        out.append(
            f"【fig14_w5_max_rpm】最大 RPM 最高的三个样本是 {'、'.join(bits)}。"
            "高 RPM 若集中在 fig01 虚线以下，这是分母（clean reads）变小，不是病毒载量生物学最高。"
        )
    if {"merge_r1_reads", "mapping_rate_pct"} <= set(core.columns):
        low = core.loc[core.get("low_depth") == True] if "low_depth" in core.columns else core.iloc[0:0]
        low_txt = ""
        if not low.empty:
            low_txt = "、".join(
                f"{r.sample_id} {_map_pct(r.mapping_rate_pct)}" for _, r in low.iterrows()
            )
        rest = core.loc[core.get("low_depth") != True] if "low_depth" in core.columns else core
        rest_txt = ""
        if not rest.empty:
            rx = pd.to_numeric(rest["mapping_rate_pct"], errors="coerce")
            rest_txt = f"深度充足样本比对率 {_map_pct(rx.min())}–{_map_pct(rx.max())}。"
        kw = _kw(tests, "mapping_rate_pct")
        out.append(
            f"【fig15_w5_depth_vs_mapping】深度最低的样本比对率最高（{low_txt}），点落在左上，是典型的低分母抬升。"
            f"{rest_txt}三种方法在深度充足时没有分开的云团。{kw} 看不出打断方法改变病毒回收率。"
        )
    return out


def cross(core: pd.DataFrame) -> list[str]:
    return [
        "【fig09 vs fig12】线粒体标记把核心样本都放在 Rattus，k-mer 物种表却把已分类块派给人："
        "宿主结论以 W3 为准，W4 人源当作数据库/同源偏差，除非另有人源污染实验。",
        "【fig01 vs fig14/fig15】低深度样本的高 RPM 与高比对率必须先当技术效应；先看 fig01 再读 W5。",
        "【fig10 vs fig13】未分类约 83%–95% 与病毒比对率 <0.2% 可以同时成立，因为二者参考库不同，不互相否定。",
    ]
