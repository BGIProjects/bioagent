"""Build self-contained HTML (embedded figures) and landscape A4 PDF."""
from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path

import pandas as pd

from .display import format_dataframe, shorten_user_text

CSS = """
@page { size: A4 landscape; margin: 10mm; }
:root { --ink:#111; --muted:#555; --line:#c8c8c8; --bg:#f7f7f7; --accent:#1f4e79; }
* { box-sizing: border-box; }
body { margin:0; background:#ececec; color:var(--ink);
  font: 12.5px/1.55 "Helvetica Neue", Helvetica, Arial, "Noto Sans CJK SC", sans-serif; }
main { max-width: 1100px; margin: 18px auto 48px; background:#fff; padding: 28px 32px 48px; overflow-x: hidden; }
h1 { font-size: 22px; margin: 0 0 8px; font-weight: 700; }
h2 { font-size: 15px; margin: 28px 0 8px; padding-bottom: 4px; border-bottom: 1.2px solid var(--ink); }
h3 { font-size: 13px; margin: 16px 0 6px; }
.kicker { letter-spacing:.08em; text-transform:uppercase; font-size:10px; color:var(--accent); font-weight:700; }
.meta, figcaption, .muted { color:var(--muted); }
.notice { background:var(--bg); border-left: 3px solid var(--accent); padding:8px 10px; margin:10px 0; }
.warn { border-left-color:#9c3b2e; }
.skip { border-left-color:#888; color:var(--muted); }
.table-wrap { overflow-x: auto; max-width: 100%; margin: 8px 0 14px; border: 0.6px solid var(--line); }
table { border-collapse: collapse; width: max-content; min-width: 100%; font-size:11px; }
th, td { border-top: 0.6px solid var(--line); border-bottom: 0.6px solid var(--line); padding: 3px 6px; text-align:left; vertical-align:top; }
th { border-top: 1.1px solid var(--ink); border-bottom: 1.1px solid var(--ink); background:#fff; font-weight:650; white-space: nowrap; }
td.num { font-variant-numeric: tabular-nums; white-space:nowrap; }
figure { margin: 0; }
figure img { width:100%; max-width:100%; height:auto; display:block; border:0.6px solid var(--line); }
figcaption { margin-top: 4px; font-size: 10.5px; line-height: 1.4; }
table.fig-pair { width: 100% !important; min-width: 0 !important; border: none !important; border-collapse: separate; table-layout: fixed; margin: 10px 0 16px; page-break-inside: avoid; }
table.fig-pair td { width: 50%; border: none !important; background: transparent; padding: 0 1.2%; vertical-align: top; }
table.fig-one { width: 48% !important; min-width: 0 !important; margin: 10px auto 16px !important; border: none !important; border-collapse: separate; table-layout: fixed; page-break-inside: avoid; }
table.fig-one td { border: none !important; background: transparent; padding: 0 !important; vertical-align: top; }
table.fig-one img { width: 100% !important; max-width: 100% !important; height: auto !important; }
nav a { color:var(--accent); text-decoration:none; }
ul { margin: 6px 0 10px 18px; }
li { margin: 3px 0; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:10.5px; }
pre { background:var(--bg); padding:10px; overflow:auto; max-height: 420px; border: 0.6px solid var(--line); }
.tag { display:inline-block; font-size:10px; padding:1px 7px; border: 0.6px solid var(--line); margin-right:6px; }
footer { margin-top: 28px; padding-top: 10px; border-top: 0.6px solid var(--line); font-size:11px; color:var(--muted); }
@media print {
  body { background:#fff; }
  main { margin:0; max-width:none; padding:0; }
  .table-wrap { overflow: visible; border: none; }
  table { font-size: 8px; width: 100%; }
  th, td { padding: 2px 3px; white-space: normal; word-break: break-word; }
  pre { max-height: none; font-size: 7.5px; }
  table.fig-pair { width: 100% !important; min-width: 0 !important; table-layout: fixed !important; }
  table.fig-pair td { width: 50% !important; }
  table.fig-pair img { width: 100% !important; max-width: 125mm !important; height: auto !important; }
  table.fig-one { width: 48% !important; min-width: 0 !important; margin: 10px auto !important; }
  figure img { max-height: none; }
}
"""


def _esc(x) -> str:
    return html.escape("" if x is None else str(x))


def _png_data_uri(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _table_note(prefix: str) -> str:
    if not prefix:
        return ""
    return f'<p class="muted">路径前缀：<code>{_esc(prefix)}</code>（表内仅保留相对尾路径）。</p>'


def _df_html(df: pd.DataFrame, max_rows: int = 80) -> str:
    if df is None or df.empty:
        return '<p class="muted">（无表）</p>'
    view, prefix = format_dataframe(df.head(max_rows))
    thead = "".join(f"<th>{_esc(c)}</th>" for c in view.columns)
    body = []
    for _, row in view.iterrows():
        tds = []
        for c, v in row.items():
            tds.append(f"<td>{_esc(v)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    extra = f'<p class="muted">显示前 {len(view)} / {len(df)} 行；完整表见 <code>tables/</code>。</p>' if len(df) > max_rows else ""
    table = f"<div class='table-wrap'><table><thead><tr>{thead}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    return _table_note(prefix) + table + extra


def _fig_block(fig_dir: Path, stem: str, caption: str) -> str:
    png = fig_dir / f"{stem}.png"
    if not png.is_file():
        return ""
    uri = _png_data_uri(png)
    return (
        f"<figure id='{html.escape(stem)}'><img src='{uri}' alt='{html.escape(caption)}' style='width:100%;max-width:100%;height:auto;display:block'/>"
        f"<figcaption><strong>{html.escape(stem)}</strong> {html.escape(caption)} "
        f"绘图脚本 <code>r/make_figures.R</code>。"
        f"</figcaption></figure>"
    )


def _fig_rows(fig_dir: Path, stems: list[str]) -> str:
    blocks = []
    for stem in stems or []:
        html_fig = _fig_block(fig_dir, stem, CAPTIONS.get(stem, stem))
        if html_fig:
            blocks.append(html_fig)
    if not blocks:
        return ""
    rows = []
    i = 0
    while i < len(blocks):
        if i + 1 < len(blocks):
            rows.append(
                "<table class='fig-pair'><tr><td>"
                + blocks[i]
                + "</td><td>"
                + blocks[i + 1]
                + "</td></tr></table>"
            )
            i += 2
        else:
            rows.append("<table class='fig-one'><tr><td>" + blocks[i] + "</td></tr></table>")
            i += 1
    return "<h3>图</h3>" + "".join(rows)


CAPTIONS = {
    "fig01_depth_by_sample": "各样本合并后 R1 深度。虚线为 5 million reads 低深度阈值。",
    "fig02_w1_fastp_retention": "fastp 读段保留率（按建库方法）。箱线为中位数与四分位，点为样本。",
    "fig03_w1_q30": "fastp 后 Q30。",
    "fig04_w1_rrna_retention": "去 rRNA 后 R1 保留率。",
    "fig05_w1_depth_vs_contigs": "测序深度与 >=1 kb contig 数。",
    "fig06_w2_checkv_by_sample": "各样本假定病毒 contig 的 CheckV 质量组成。",
    "fig07_w2_contig_length": "假定病毒 contig 长度分布。",
    "fig08_w2_viral_contigs_by_method": "每样本假定病毒 contig 数（按方法）。",
    "fig09_w3_host_species": "核心队列推断线粒体物种频次。",
    "fig10_w4_unclassified": "Kraken 未分类比例。",
    "fig11_w4_species_richness": "Bracken 物种分类单元数。",
    "fig12_w4_top_taxa": "Bracken top-15 已分类空间的优势分类单元组成（不是全库相对丰度）。",
    "fig13_w5_mapping_rate": "比对到病毒 contig 的 reads 比例。",
    "fig14_w5_max_rpm": "每样本最大病毒 RPM（对数轴）。",
    "fig15_w5_depth_vs_mapping": "深度与病毒比对率：低深度样本的高相对定量需谨慎。",
}


def _clean_extract_log(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    keep = [c for c in ("workflow", "short", "ok", "skipped", "n_tables", "error") if c in df.columns]
    out = df[keep].copy()
    if "error" in out.columns:
        out["error"] = out["error"].fillna("").astype(str).str.split("/").str[-1]
    return out


def build_html(
    batch_id: str,
    out_dir: Path,
    fig_dir: Path,
    sections: list[dict],
    master: pd.DataFrame,
    coverage: pd.DataFrame,
    overall: pd.DataFrame,
    tests: pd.DataFrame,
    extract_log: pd.DataFrame,
    r_source: str,
    grouping_notes: list[str],
) -> Path:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    toc = []
    body = []
    for i, sec in enumerate(sections, 1):
        toc.append(f"<a href='#{sec['id']}'>{i}. {_esc(sec['title'])}</a>")
        body.append(f"<section id='{sec['id']}'><h2>{i}. {_esc(sec['title'])}</h2>")
        if sec.get("skip"):
            msg = shorten_user_text(sec["results"][0]) if sec.get("results") else "跳过"
            body.append(f"<div class='notice skip'>{_esc(msg)}</div></section>")
            continue
        if sec.get("results"):
            items = "".join(f"<li>{_esc(shorten_user_text(x))}</li>" for x in sec["results"])
            body.append("<h3>结果</h3><ul>" + items + "</ul>")
        figs = _fig_rows(fig_dir, sec.get("figures") or [])
        if figs:
            body.append(figs)
        if sec.get("biology"):
            body.append("<h3>生物学意义</h3><ul>" + "".join(f"<li>{_esc(x)}</li>" for x in sec["biology"]) + "</ul>")
        body.append("</section>")

    cov_html = _df_html(coverage)
    master_show = master.drop(columns=[c for c in master.columns if str(c).lower() in {"raw_id"}], errors="ignore")
    # drop likely path columns from master if any
    html_doc = f"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>全流程分析报告 · {html.escape(batch_id)}</title>
<style>{CSS}</style>
</head><body><main>
<header>
<div class="kicker">XvirBench full-pipeline analysis · v1.0</div>
<h1>{html.escape(batch_id)} 工作流完成后分析报告</h1>
<p class="meta">生成 {html.escape(now)} · 指标口径对齐 extract_results.py 与 WORKFLOW_SUMMARY.md · 图已嵌入本文件</p>
<p>
<span class="tag">总体分析</span>
<span class="tag">缺失则跳过</span>
<span class="tag">SCI 风格 ggplot2</span>
<span class="tag">自包含 HTML</span>
<span class="tag">不构成诊断</span>
</p>
</header>
<nav class="muted">{" · ".join(toc)}</nav>
<div class="notice warn">缺失流程或字段不判为失败。Kraken/BLAST 物种名不是 ICTV 定种。低深度样本的 RPM 与物种数不可单独解读为生物学差异。本 HTML 图为内嵌 PNG，复制单文件即可打开。</div>
{''.join(body)}
<section id="tables">
<h2>结构化表</h2>
<h3>提取覆盖</h3>
{cov_html}
<h3>核心样本主表</h3>
{_df_html(master_show)}
<h3>核心队列描述统计</h3>
{_df_html(overall if overall is not None else pd.DataFrame())}
<h3>组间检验（若有分组）</h3>
{_df_html(tests if tests is not None else pd.DataFrame())}
<h3>提取状态</h3>
{_df_html(_clean_extract_log(extract_log))}
<p class="muted">完整数值表见运行目录下 <code>tables/</code>（相对本报告）。</p>
</section>
<section id="methods">
<h2>方法学摘要</h2>
<ul>
<li>提取：各流程 extract_results.py；失败时回退已有 benchmark xlsx。</li>
<li>描述统计：n、mean、SD、median、IQR、min、max。</li>
<li>分组：仅当某因子 ≥2 水平且至少两个水平 n≥2。检验用 Kruskal–Wallis 与 Mann–Whitney，p 值 BH 校正；效应量为 ε² 与 rank-biserial。</li>
<li>低深度：合并 R1 &lt; 5×10<sup>6</sup> reads。另给出剔除低深度后的敏感性统计。</li>
<li>图：ggplot2 classic、Okabe–Ito；报告内为嵌入 PNG；磁盘另存 PDF 矢量图。</li>
<li>数字：计数为整数；百分比 2 位；0–1 比例与效应量 4 位；p 值 4 位。</li>
</ul>
<p class="muted">分组备注：{" ".join(_esc(x) for x in grouping_notes)}</p>
</section>
<section id="rscripts">
<h2>附录：R 绘图脚本</h2>
<p class="muted">主题 <code>r/00_sci_theme.R</code>；作图 <code>r/make_figures.R</code>。下列为本次运行复制的脚本正文。</p>
<pre>{html.escape(r_source[:20000])}</pre>
</section>
<footer>
本结果仅限科研实验室内部参考，不得作为临床诊断或公共卫生干预的直接决策依据。<br/>
规范与提示词：XvirBench/benchmark/FULL_PIPELINE_ANALYSIS_SYSTEM.md
</footer>
</main></body></html>
"""
    out = out_dir / "report.html"
    out.write_text(html_doc, encoding="utf-8")
    return out


def build_pdf(html_path: Path, pdf_path: Path) -> Path:
    """Bake the self-contained HTML into a landscape A4 PDF."""
    from weasyprint import HTML

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(filename=str(html_path), base_url=str(html_path.parent)).write_pdf(str(pdf_path))
    return pdf_path
