"""Scoring criteria HTML block for reports."""
from __future__ import annotations

from w1_qc.standards import STAGE_WEIGHTS, THRESHOLD_VERSION


def scoring_criteria_html() -> str:
    w = STAGE_WEIGHTS
    return f"""
<h2>评分标准（阈值版本 {THRESHOLD_VERSION}）</h2>
<h3>单指标等级（A–F）</h3>
<table class="dataframe">
<thead><tr><th>阶段</th><th>指标</th><th>A（优）</th><th>B（良）</th><th>C（可接受）</th><th>D（需关注）</th><th>F（不合格）</th></tr></thead>
<tbody>
<tr><td>S3 合并深度</td><td>merge R1 reads</td><td>≥15 Mb</td><td>≥10 Mb</td><td>≥5 Mb</td><td>≥2 Mb</td><td>&lt;2 Mb</td></tr>
<tr><td>S1 fastp</td><td>read 保留率</td><td>≥0.85</td><td>≥0.80</td><td>≥0.70</td><td>≥0.60</td><td>&lt;0.60</td></tr>
<tr><td>S1 fastp</td><td>Q30（过滤后）</td><td>≥0.92</td><td>≥0.90</td><td>≥0.85</td><td>≥0.80</td><td>&lt;0.80</td></tr>
<tr><td>S1 fastp</td><td>PCR 重复率</td><td>≤0.15</td><td>≤0.20</td><td>≤0.30</td><td>≤0.40</td><td>&gt;0.40</td></tr>
<tr><td>S2 rRNA</td><td>保留率</td><td>0.75–0.98</td><td>0.65–0.99</td><td>0.50–0.99</td><td>0.40–0.99</td><td>&lt;0.40 或 &gt;0.99</td></tr>
<tr><td>S4 组装</td><td>≥1 kb contigs</td><td>≥8000</td><td>≥5000</td><td>≥3000</td><td>≥1000</td><td>&lt;1000</td></tr>
</tbody>
</table>
<h3>样本综合评级（加权）</h3>
<p>S1 质量（保留率+Q30+重复率均值）权重 {w['S1_quality']:.0%}；
S2 rRNA 权重 {w['S2_rrna']:.0%}；
S3 深度权重 {w['S3_depth']:.0%}；
S4 组装权重 {w['S4_assembly']:.0%}。
各子项 A=4、B=3、C=2、D=1、F=0，加权均分映射为：
<strong>优</strong> ≥3.5、<strong>良</strong> 3.0–3.49、<strong>可接受</strong> 2.0–2.99、
<strong>需关注</strong> 1.0–1.99、<strong>不建议下游</strong> &lt;1.0。</p>
<h3>批次通过标准</h3>
<p>≥80% 样本为「良」及以上，且「不建议下游」占比 ≤10%。</p>
<h3>单位约定</h3>
<p>reads 统一为 <strong>Mb</strong>（×10⁶ reads）；bases 统一为 <strong>Gb</strong>（×10⁹ bp）；比例类指标以 <strong>%</strong> 显示（保留 2 位小数）；其他数值保留 2 位小数；整数使用千分位。</p>
"""
