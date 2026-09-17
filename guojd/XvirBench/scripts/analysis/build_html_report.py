"""生成 Phase 3 HTML 全流程报告。"""
from __future__ import annotations

import base64
import html
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from analyze_workflows import FigureGroup, WorkflowAnalysis
from cohort import METHOD_LABEL, METHOD_ORDER, load_sampleinfo
from report_theme import REPORT_CSS, REPORT_JS


def _df_html(df: pd.DataFrame, max_rows: int = 200) -> str:
    if df.empty:
        return "<p><em>无数据</em></p>"
    show = df.head(max_rows).copy()
    for c in show.select_dtypes(include="float").columns:
        show[c] = show[c].map(lambda x: f"{x:.4g}" if pd.notna(x) else "")
    return show.to_html(index=False, border=0, escape=True)


def _host_method_table(cohort: pd.DataFrame) -> str:
    pt = (
        cohort.groupby(["method_label", "host"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    return pt.to_html(index=False, border=0, escape=True)


def _sig_badge(p: float) -> str:
    if pd.isna(p):
        return ""
    if p < 0.001:
        return '<span class="sig sig3">***</span>'
    if p < 0.01:
        return '<span class="sig sig2">**</span>'
    if p < 0.05:
        return '<span class="sig sig1">*</span>'
    return '<span class="sig ns">ns</span>'


def _md_inline(s: str) -> str:
    s = html.escape(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def _tests_html(tests: pd.DataFrame, metrics: Dict[str, str], show_dataset: bool = True) -> str:
    if tests.empty:
        return "<p><em>样本量不足，未做检验</em></p>"
    kw = tests[tests["test"] == "kruskal_wallis"].copy()
    if kw.empty:
        return _df_html(tests)
    hdr = "<table><thead><tr>"
    if show_dataset:
        hdr += "<th>数据集</th>"
    hdr += "<th>指标</th><th>Kruskal-Wallis p</th><th>显著性</th></tr></thead><tbody>"
    rows = [hdr]
    ds_label = {
        "all_samples": "全队列",
        "exclude_low_depth": "排除低深度",
        "host_rat": "大鼠",
        "host_tick": "蜱",
        "host_mosquito": "蚊虫",
    }
    for _, r in kw.iterrows():
        lbl = metrics.get(r["metric"], r["metric"])
        p = r["p_value"]
        p_str = f"{p:.4g}" if pd.notna(p) else "NA"
        ds = ds_label.get(r.get("dataset", ""), r.get("dataset", ""))
        row = "<tr>"
        if show_dataset:
            row += f'<td><span class="dataset-tag">{html.escape(str(ds))}</span></td>'
        row += f"<td>{html.escape(lbl)}</td><td>{p_str}</td><td>{_sig_badge(p)}</td></tr>"
        rows.append(row)
    rows.append("</tbody></table>")
    return "\n".join(rows)


def _summary_table_html(summary: pd.DataFrame, metrics: Dict[str, str]) -> str:
    if summary.empty:
        return "<p><em>无汇总</em></p>"
    hdr = "<table><thead><tr><th>方法</th>"
    for m in metrics:
        hdr += f"<th>{html.escape(metrics[m])}<br><small>mean ± sd</small></th>"
    hdr += "</tr></thead><tbody>"
    rows = [hdr]
    for _, r in summary.iterrows():
        meth = r["method"]
        lbl = METHOD_LABEL.get(meth, meth)
        cells = [f"<td><strong>{html.escape(lbl)}</strong><br><small>n={int(r['n'])}</small></td>"]
        for m in metrics:
            mean = r.get(f"{m}_mean", float("nan"))
            sd = r.get(f"{m}_sd", float("nan"))
            if pd.notna(mean):
                sd_str = f"{sd:.4g}" if pd.notna(sd) else "—"
                cells.append(f"<td>{mean:.4g} ± {sd_str}</td>")
            else:
                cells.append("<td>—</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def _img_data_uri(fp: Path) -> str:
    if not fp.is_file():
        return ""
    mime = "image/png"
    if fp.suffix.lower() in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    b64 = base64.b64encode(fp.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _figure_gallery(groups: List[FigureGroup]) -> str:
    if not groups:
        return ""
    cards = []
    for g in groups:
        src = _img_data_uri(g.path)
        if not src:
            continue
        cards.append(
            f'<div class="fig-card layout-{html.escape(g.layout)}">'
            f"<h4>{html.escape(g.title)}</h4>"
            f'<figure><img class="report-figure" src="{src}" alt="{html.escape(g.title)}"></figure>'
            f'<p class="caption">{html.escape(g.caption)}</p>'
            f"</div>"
        )
    return f'<div class="fig-gallery">{"".join(cards)}</div>'


def _interpretation_html(lines: List[str]) -> str:
    if not lines:
        return ""
    parts = ['<div class="interp-block">', "<h4>自动解读</h4>"]
    for line in lines:
        if line.startswith("### "):
            parts.append(f"<p><strong>{html.escape(line[4:])}</strong></p>")
        else:
            parts.append(f"<p>{_md_inline(line)}</p>")
    parts.append("</div>")
    return "\n".join(parts)


def _toc_link(href: str, label: str, children: Optional[List[tuple]] = None) -> str:
    sub = ""
    if children:
        items = []
        for item in children:
            h, l = item[0], item[1]
            c = item[2] if len(item) > 2 else None
            items.append(_toc_link(h, l, c))
        sub = "<ul>" + "".join(items) + "</ul>"
    return f'<li><a href="#{html.escape(href)}">{html.escape(label)}</a>{sub}</li>'


def _build_toc(results: Dict[str, WorkflowAnalysis]) -> str:
    items = [
        _toc_link("overview", "实验概览", [
            ("overview-design", "比较设计", None),
            ("overview-method", "建库方法", None),
            ("overview-host", "宿主组成", None),
        ])
    ]
    for wf, res in results.items():
        items.append(_toc_link(wf, res.title, [
            (f"{wf}-interp", "解读", None),
            (f"{wf}-figs", "图表", None),
            (f"{wf}-stats", "描述统计", None),
            (f"{wf}-tests", "分层检验", None),
        ]))
    items.append(_toc_link("files", "输出文件", None))
    return "<ul>" + "".join(items) + "</ul>"


def _workflow_section(wf: str, res: WorkflowAnalysis) -> str:
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in res.notes)
    gallery = _figure_gallery(res.figure_groups)
    interp = _interpretation_html(res.interpretations)
    core_metrics = list(res.metric_labels.keys())[:6]
    return f"""
<h2 id="{wf}">{html.escape(res.title)}</h2>
<blockquote><strong>分析目标：</strong>{html.escape(res.objective)}</blockquote>
<ul class="meta-muted">{notes}</ul>
<h3 id="{wf}-interp">结果解读</h3>
{interp}
<h3 id="{wf}-figs">图表</h3>
{gallery or "<p><em>无图</em></p>"}
<h3 id="{wf}-stats">全队列描述统计</h3>
{_summary_table_html(res.summary_df, {k: res.metric_labels[k] for k in core_metrics if k in res.metric_labels})}
<h3 id="{wf}-tests">分层组间检验（Kruskal-Wallis）</h3>
<p class="meta-muted">比较维度：<span class="dataset-tag">全队列</span>
<span class="dataset-tag">排除低深度</span><span class="dataset-tag">分宿主</span></p>
{_tests_html(res.tests_df, res.metric_labels)}
<p class="meta-muted">表：<code>tables/{wf}_method_summary_stratified.tsv</code>、
<code>tables/{wf}_stat_tests.tsv</code>、<code>text/{wf}_interpretation.md</code></p>
<hr />
"""


def build_html_report(batch_dir: Path, batch_id: str, results: Dict[str, WorkflowAnalysis]) -> Path:
    out_path = batch_dir / "analysis" / "report.html"
    cohort = load_sampleinfo(batch_dir / "cohorts")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    method_rows = "".join(
        f"<tr><td>{html.escape(METHOD_LABEL[m])}</td><td><code>{m}</code></td>"
        f"<td>{len(cohort[cohort['method'] == m])}</td></tr>"
        for m in METHOD_ORDER
    )
    host_rows = "".join(
        f"<tr><td>{h}</td><td>{len(cohort[cohort['host'] == h])}</td></tr>"
        for h in cohort["host"].cat.categories
    )

    report_title = "宏转录组建库方法学全流程分组比较报告"
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes" />
<title>{html.escape(report_title)} — {html.escape(batch_id)}</title>
<style id="report-custom">{REPORT_CSS}</style>
</head>
<body>
<div class="report-layout">
  <aside class="report-sidebar">
    <div class="sidebar-title">目录</div>
    <nav id="TOC" role="doc-toc">{_build_toc(results)}</nav>
  </aside>
  <main class="report-main">
    <header id="title-block-header">
      <h1 class="title">{html.escape(report_title)}</h1>
    </header>
    <h1 id="report-title">{html.escape(batch_id)}</h1>
    <p>
      <strong>文档类型</strong>：全流程分组比较报告（参考 vazyme fragmentation_test）<br />
      <strong>分析日期</strong>：{stamp}<br />
      <strong>样本规模</strong>：{len(cohort)} 样本 · 宿主 rat/tick/mosquito<br />
      <strong>比较设计</strong>：建库方法（3 组）× 宿主分层 × 测序文库（sn）配对<br />
      <strong>数据</strong>：<code>cohorts/</code> + <code>harmonized/</code>（W7 与 vazyme comparison_summary 一致）
    </p>
    <hr />
    <h2 id="overview">实验概览</h2>
    <h3 id="overview-design">比较设计</h3>
    <p>参考 <code>vazyme/fragmentation_test/analysis/</code>：宿主内比较碎片化方法（PRIMARY）；
    全队列混合比较仅作探索。低深度样本（&lt;5M reads）以红圈标记，并提供排除后的敏感性分析。
    蚊虫仅含 cDNA 与 RNA_85 两种方法。</p>
    <h3 id="overview-method">建库方法分组</h3>
    <table><thead><tr><th>显示名</th><th>代码</th><th>n</th></tr></thead><tbody>{method_rows}</tbody></table>
    <h3 id="overview-host">宿主组成</h3>
    <table><thead><tr><th>宿主</th><th>n</th></tr></thead><tbody>{host_rows}</tbody></table>
    <h3 id="overview-cross">方法 × 宿主</h3>
    {_host_method_table(cohort)}
    <hr />
    {"".join(_workflow_section(wf, res) for wf, res in results.items())}
    <h2 id="files">结构化输出</h2>
    <ul>
      <li><code>analysis/tables/*_method_summary_stratified.tsv</code> — 全队列 / 排除低深度 / 分宿主汇总</li>
      <li><code>analysis/tables/*_stat_tests.tsv</code> — 分层 Kruskal-Wallis + 两两检验</li>
      <li><code>analysis/text/*_interpretation.md</code> — 自动解读</li>
      <li><code>analysis/figures/</code> — 多面板图（已 base64 内嵌本 HTML）</li>
    </ul>
    <p class="meta-muted">XvirBench · {html.escape(batch_id)} · {stamp}</p>
  </main>
</div>
<script>{REPORT_JS}</script>
</body>
</html>"""
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path
