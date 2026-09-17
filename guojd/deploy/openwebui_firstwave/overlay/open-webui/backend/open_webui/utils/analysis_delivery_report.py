"""Render deterministic user-facing analysis reports."""

# ruff: noqa: E501

from __future__ import annotations

import datetime as dt
import html
from pathlib import Path
from typing import Any

import json
from open_webui.utils.analysis_report_common import routing_summary, stage_timing
from open_webui.utils.ops_specialist_report import inject, render_specialist_html
from open_webui.utils.report_evidence import (
    render_evidence_audit,
    verify_report_evidence,
)
from open_webui.utils.workflow1_delivery_report import (
    render_workflow1_delivery_report,
)


def _escape(value: Any) -> str:
    return html.escape('' if value is None else str(value))


def _number(value: Any, digits: int = 2) -> str:
    if not isinstance(value, (int, float)):
        return '—'
    if isinstance(value, int):
        return f'{value:,}'
    return f'{value:,.{digits}f}'


def _percent(value: Any) -> str:
    return f'{_number(value)}%' if isinstance(value, (int, float)) else '—'


def _ratio_percent(value: Any, digits: int = 2) -> str:
    if not isinstance(value, (int, float)):
        return '—'
    return f'{_number(float(value) * 100, digits)}%'


def _check_value(check: dict[str, Any] | None, *, ratio_digits: int | None = None) -> str:
    if not check:
        return '—'
    formatter = (
        (lambda value: _ratio_percent(value, ratio_digits))
        if ratio_digits is not None
        else (lambda value: _number(value, 0))
    )
    result = '通过' if check.get('passed') is True else '未通过'
    return f'{formatter(check.get("actual"))} / ≥ {formatter(check.get("threshold"))}（{result}）'


def _table(headers: list[str], rows: list[list[Any]], *, empty: str = '未记录') -> str:
    if not rows:
        return f'<p class="empty">{_escape(empty)}</p>'
    heading = ''.join(f'<th>{_escape(header)}</th>' for header in headers)
    column_classes = [
        'path-col'
        if any(word in header.lower() for word in ('路径', '来源', '定位', '文件'))
        else 'number-col'
        if any(word in header.lower() for word in ('数', '率', '%', 'rpm', '长度', '耗时', '内存', 'cpu'))
        else ''
        for header in headers
    ]
    colgroup = (
        '<colgroup>'
        + ''.join(f'<col class="{column_class}">' if column_class else '<col>' for column_class in column_classes)
        + '</colgroup>'
    )
    body = ''.join(
        '<tr>'
        + ''.join(f'<td class="{column_classes[index]}">{_escape(cell)}</td>' for index, cell in enumerate(row))
        + '</tr>'
        for row in rows
    )
    return (
        f'<div class="table-wrap"><table>{colgroup}<thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def _routing_section(routing: dict[str, Any]) -> str:
    summary = routing_summary(routing)
    rows = []
    chart_rows = []
    for sample in summary['samples']:
        checks = sample['checks']
        rows.append(
            [
                sample.get('sample_id'),
                (sample.get('top_species') or {}).get('name') or '—',
                _check_value(checks.get('top_species_reads')),
                _check_value(checks.get('top_species_sample_fraction'), ratio_digits=4),
                _check_value(checks.get('top_species_viral_fraction'), ratio_digits=2),
                '高' if sample.get('known_virus_high_confidence') else '低',
            ]
        )
        for check in checks.values():
            actual = check.get('actual')
            threshold = check.get('threshold')
            if not isinstance(actual, (int, float)) or not isinstance(threshold, (int, float)) or threshold <= 0:
                continue
            ratio = max(0, min(float(actual) / float(threshold) * 100, 120))
            chart_rows.append(
                f'<div class="threshold-row"><span>{_escape(sample.get("sample_id"))} · {_escape(check.get("metric"))}</span>'
                f'<i><b class="{"passed" if check.get("passed") else "failed"}" style="width:{ratio / 1.2:.2f}%"></b><mark></mark></i>'
                f'<em>{_escape(_number(actual, 4))} / {_escape(_number(threshold, 4))}</em></div>'
            )
    route = f'路径 {summary["route"]}' if summary['route'] else '—'
    return (
        '<section><h2>自适应路由说明</h2>'
        f'<p class="notice">{_escape(summary["explanation"])}</p>'
        f'<p>请求模式：{_escape(summary["mode_label"])} · 最终路径：{_escape(route)}'
        f' · 整体置信度：{_escape(summary["confidence_label"])}</p>'
        + _table(
            ['样本', '最高物种', '命中 reads / 门槛', '抽样占比 / 门槛', '病毒内占比 / 门槛', '置信度'],
            rows,
        )
        + (f'<div class="threshold-chart">{"".join(chart_rows)}</div>' if chart_rows else '')
        + '</section>'
    )


def _upstream_rows(upstream: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for sample in upstream.get('samples', []):
        if not isinstance(sample, dict):
            continue
        input_metrics = (sample.get('input') or {}).get('metrics') or {}
        fastp_after = (sample.get('fastp') or {}).get('after') or {}
        rrna_after = (sample.get('rrna') or {}).get('after') or {}
        assembly = sample.get('assembly') or {}
        final_filter = sample.get('final_filter') or {}
        rows.append(
            [
                sample.get('sample_id'),
                _number(input_metrics.get('reads'), 0),
                _number(fastp_after.get('reads'), 0),
                _number(rrna_after.get('reads'), 0),
                _number(assembly.get('reads'), 0),
                _number(final_filter.get('reads'), 0),
            ]
        )
    return rows


def _classification_bars(representatives: list[dict[str, Any]]) -> str:
    rows = []
    for item in representatives[:30]:
        label = item.get('qseqid') or item.get('sample_id') or '候选序列'
        metrics = (
            ('完整度', item.get('completeness')),
            (
                '证据支持率',
                float(item['approval_rate']) * 100 if isinstance(item.get('approval_rate'), (int, float)) else None,
            ),
        )
        for metric, value in metrics:
            if not isinstance(value, (int, float)):
                continue
            percent = max(0, min(float(value), 100))
            rows.append(
                f'<div class="bar-row"><span>{_escape(label)} · {_escape(metric)}</span>'
                f'<i><b style="width:{percent:.2f}%"></b></i><em>{_number(value)}%</em></div>'
            )
    return f'<div class="bar-chart">{"".join(rows)}</div>' if rows else ''


def _classification_document(
    *,
    state: dict[str, Any],
    telemetry: dict[str, Any],
    run_dir: Path,
) -> str:
    delivery = telemetry['delivery_report']
    classification = delivery.get('classification') or {}
    stages = delivery.get('stages') or []
    representatives = classification.get('representatives') or []
    stage_rows = [
        [
            stage.get('label'),
            stage.get('status'),
            _number(stage_timing(stage).get('elapsed_seconds')),
        ]
        for stage in stages
        if isinstance(stage, dict)
    ]
    representative_rows = [
        [
            item.get('sample_id') or '—',
            item.get('qseqid'),
            _number(item.get('qlen'), 0),
            item.get('viral_type') or '—',
            item.get('checkv_quality') or item.get('miuvig_quality') or '—',
            _percent(item.get('completeness')),
            _percent(item.get('contamination')),
            item.get('nr_svorder') or item.get('rdrpscan_svorder') or item.get('vhdb_svorder') or '—',
            item.get('nr_svfamily') or item.get('nr_vote_vfamily') or item.get('vhdb_svfamily') or '—',
            item.get('nr_svgenus') or '—',
            item.get('nr_sscinames') or item.get('nr_besthit') or item.get('vhdb_svname') or '—',
            _percent(item.get('nr_pident')),
            _ratio_percent(item.get('approval_rate')),
            item.get('clusid') or '—',
        ]
        for item in representatives
        if isinstance(item, dict)
    ]
    artifact_rows = []
    for collection in ('tables', 'artifacts'):
        for label, raw_path in (classification.get(collection) or {}).items():
            if not isinstance(raw_path, str):
                continue
            path = Path(raw_path).resolve()
            if path == run_dir or run_dir in path.parents:
                artifact_rows.append([label, path])

    title = state.get('title') or state.get('run_id') or '病毒分类分析'
    generated_at = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    candidate_count = _number(classification.get('candidate_count'), 0)
    representative_count = _number(classification.get('representative_count'), 0)
    vertebrate_candidate_count = _number(classification.get('vertebrate_candidate_count'), 0)
    vertebrate_representative_count = _number(classification.get('vertebrate_representative_count'), 0)
    representative_headers = [
        '样本',
        'Contig',
        '长度',
        '类型',
        'CheckV',
        '完整度',
        '污染度',
        'Order',
        'Family',
        'Genus',
        '最佳命中',
        '一致性',
        '证据支持率',
        'Cluster',
    ]
    upstream = delivery.get('upstream')
    routing = delivery.get('routing')
    routing_section = _routing_section(routing) if isinstance(routing, dict) else ''
    evidence_audit = render_evidence_audit(delivery)
    quality_chart = _classification_bars([item for item in representatives if isinstance(item, dict)])
    upstream_section = (
        '<section><h2>Reads 预处理与组装</h2>'
        + _table(
            ['样本', '输入 Reads', '质控后', '去 rRNA 后', '组装 Contigs', '过滤后 Contigs'],
            _upstream_rows(upstream),
        )
        + '</section>'
        if isinstance(upstream, dict)
        else ''
    )
    empty_message = '未检出符合流程判定条件的候选'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)} · 病毒分类分析报告</title>
<style>
@page {{ size: A4 landscape; margin: 12mm; }}
:root {{ color: #17212b; font: 14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif; }}
body {{ margin: 0; background: #eef2f5; }}
main {{ max-width: 1280px; margin: 20px auto; padding: 28px; background: white; }}
h1 {{ margin: 0 0 4px; font-size: 26px; }} h2 {{ margin: 28px 0 10px; }}
.meta,.muted {{ color: #65727e; }} .summary {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.metric {{ min-width: 160px; padding: 12px 16px; border: 1px solid #d8e0e6; border-radius: 8px; }}
.metric strong {{ display: block; font-size: 22px; }}
.notice {{ padding: 12px 14px; border-left: 4px solid #168aad; background: #f5f8fa; }}
.table-wrap {{ overflow-x: auto; }} table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th,td {{ padding: 7px 8px; border: 1px solid #d9e0e6; text-align: left; vertical-align: top; }}
th {{ background: #f4f7f9; }} .empty {{ padding: 14px; background: #f4f7f9; }}
.evidence-table {{ min-width:760px; }} .evidence-table td:nth-child(3),.evidence-table td:nth-child(4) {{ white-space:nowrap;width:1%; }} .evidence-table td:nth-child(5) {{ max-width:520px;overflow-wrap:anywhere;word-break:break-word; }}
.bar-chart {{ display:grid;gap:6px;margin:10px 0 14px; }} .bar-row {{ display:grid;grid-template-columns:minmax(160px,2fr) minmax(180px,5fr) 72px;gap:8px;align-items:center;font-size:12px; }} .bar-row i {{ height:9px;background:#e5ebef;border-radius:5px;overflow:hidden; }} .bar-row b {{ display:block;height:100%;background:#168aad; }} .bar-row em {{ font-style:normal;text-align:right;white-space:nowrap; }}
.threshold-chart {{ display:grid;gap:6px;margin-top:12px; }} .threshold-row {{ display:grid;grid-template-columns:220px 1fr 150px;gap:8px;align-items:center;font-size:11px; }}
.threshold-row i {{ position:relative;height:8px;background:#e5ebef;border-radius:4px;overflow:hidden; }} .threshold-row b {{ display:block;height:100%; }} .threshold-row b.passed {{ background:#168a68; }} .threshold-row b.failed {{ background:#c75b45; }} .threshold-row mark {{ position:absolute;left:83.33%;top:0;width:1px;height:100%;background:#17212b; }} .threshold-row em {{ font-style:normal;white-space:nowrap; }}
@media print {{ body {{ background: white; }} main {{ margin: 0; padding: 0; max-width: none; }} }}
</style>
</head>
<body><main>
<header>
<h1>病毒分类分析报告</h1>
<div class="meta">任务：{_escape(title)} · run：{_escape(state.get('run_id'))}</div>
<div class="meta">搜索范围：{_escape(classification.get('viral_type'))}
· 输入：{_escape(classification.get('input_type'))} · 生成时间：{_escape(generated_at)}</div>
</header>
<section><h2>结果摘要</h2>
<div class="summary">
<div class="metric"><span>候选病毒 Contigs</span><strong>{candidate_count}</strong></div>
<div class="metric"><span>聚类代表序列</span><strong>{representative_count}</strong></div>
<div class="metric"><span>脊椎动物病毒候选</span><strong>{vertebrate_candidate_count}</strong></div>
<div class="metric"><span>脊椎动物代表序列</span><strong>{vertebrate_representative_count}</strong></div>
</div></section>
{routing_section}
{upstream_section}
{evidence_audit}
<section><h2>分析阶段</h2>{_table(['阶段', '状态', '耗时(s)'], stage_rows)}</section>
<section><h2>候选病原体列表与分类证据</h2>
{_table(representative_headers, representative_rows, empty=empty_message)}
</section>
{f'<section><h2>候选质量与证据支持图</h2>{quality_chart}</section>' if quality_chart else ''}
<section><h2>结果文件</h2>{_table(['类别', '路径'], artifact_rows)}</section>
<section><h2>结果边界</h2>
<p>候选结果来自固定的 HMM、聚类、CheckV 及参考数据库比对规则。分类字段缺失时保留为“—”，不从其他字段推测。</p>
<p>本报告仅用于科研分析，不构成临床诊断、病因学结论或公共卫生处置建议。</p>
</section>
</main></body></html>"""


def _adaptive_alert_document(
    *,
    state: dict[str, Any],
    telemetry: dict[str, Any],
) -> str:
    delivery = telemetry['delivery_report']
    screening = delivery.get('screening') or {}
    routing = delivery.get('routing') or {}
    decision = routing.get('decision') or {}
    high_confidence = decision.get('confidence') == 'high'
    title = '快速初步预警' if high_confidence else '快速初筛报告'
    rows = []
    for sample in screening.get('samples') or []:
        if not isinstance(sample, dict):
            continue
        top = sample.get('top_species') or {}
        rows.append(
            [
                sample.get('sample_id'),
                _number(sample.get('sampled_read_pairs'), 0),
                _number(sample.get('post_filter_read_pairs'), 0),
                _number(sample.get('viral_reads'), 0),
                top.get('name') or '—',
                top.get('taxid') or '—',
                _number(top.get('reads'), 0),
                _ratio_percent(sample.get('top_species_sample_fraction')),
                _ratio_percent(sample.get('top_species_viral_fraction')),
                '高' if sample.get('known_virus_high_confidence') else '低',
            ]
        )
    generated_at = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    routing_section = _routing_section(routing)
    evidence_audit = render_evidence_audit(delivery)
    stage_rows = [
        [
            stage.get('label') or stage.get('id'),
            stage.get('status') or '—',
            _number(stage_timing(stage).get('elapsed_seconds')),
        ]
        for stage in (delivery.get('stages') or telemetry.get('stages') or [])
        if isinstance(stage, dict)
    ]
    if not stage_rows:
        stage_rows = [
            [
                '5% Kraken2 快速初筛',
                'completed',
                _number(routing.get('actual_duration_seconds')),
            ]
        ]
    manifest = delivery.get('manifest') or telemetry.get('manifest') or {}
    artifact_rows = [
        [item.get('path') or '—', _number(item.get('size'), 0)]
        for item in manifest.get('files') or []
        if isinstance(item, dict)
    ]
    if not artifact_rows:
        artifact_rows = [['快速初筛诊断意见书', '当前 HTML']]
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)}</title>
<style>
@page {{ size: A4 landscape; margin: 12mm; }}
:root {{ color:#17212b;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif; }}
body {{ margin:0;background:#eef2f5; }} main {{ max-width:1180px;margin:20px auto;padding:28px;background:white; }}
h1 {{ margin:0 0 4px;font-size:26px; }} h2 {{ margin:26px 0 10px; }} .meta,.muted {{ color:#65727e; }}
.notice {{ padding:14px 16px;border-left:4px solid {'#dc8a00' if high_confidence else '#168aad'};background:#f5f8fa; }}
.table-wrap {{ overflow-x:auto; }} table {{ width:100%;border-collapse:collapse;font-size:12px; }}
th,td {{ padding:7px 8px;border:1px solid #d9e0e6;text-align:left; }} th {{ background:#f4f7f9; }}
.evidence-table {{ min-width:760px; }} .evidence-table td:nth-child(3),.evidence-table td:nth-child(4) {{ white-space:nowrap;width:1%; }} .evidence-table td:nth-child(5) {{ max-width:520px;overflow-wrap:anywhere;word-break:break-word; }}
.threshold-chart {{ display:grid;gap:6px;margin-top:12px; }} .threshold-row {{ display:grid;grid-template-columns:220px 1fr 150px;gap:8px;align-items:center;font-size:11px; }} .threshold-row i {{ position:relative;height:8px;background:#e5ebef;border-radius:4px;overflow:hidden; }} .threshold-row b {{ display:block;height:100%; }} .threshold-row b.passed {{ background:#168a68; }} .threshold-row b.failed {{ background:#c75b45; }} .threshold-row mark {{ position:absolute;left:83.33%;top:0;width:1px;height:100%;background:#17212b; }} .threshold-row em {{ font-style:normal;white-space:nowrap; }}
@media print {{ body {{ background:white; }} main {{ margin:0;padding:0;max-width:none; }} }}
</style></head><body><main>
<header><h1>{_escape(title)}</h1>
<div class="meta">任务：{_escape(state.get('title') or state.get('run_id'))} · run：{_escape(state.get('run_id'))}</div>
<div class="meta">抽样比例：5% · 生成时间：{_escape(generated_at)}</div></header>
{routing_section}
{evidence_audit}
<section><h2>实际执行阶段</h2>{_table(['阶段', '状态', '耗时(s)'], stage_rows)}</section>
<section><h2>样本结果</h2>{
        _table(
            [
                '样本',
                '抽样 read pairs',
                '过滤后',
                '病毒 reads',
                '最高物种',
                'TaxID',
                '命中 reads',
                '样本占比',
                '病毒内占比',
                '置信度',
            ],
            rows,
        )
    }</section>
<section><h2>交付产物</h2>{_table(['路径或产物', '大小'], artifact_rows)}</section>
<section><h2>结果边界</h2>
<p>本报告仅基于 5% reads 的 Kraken2 快速初筛，未执行组装、完整分类证据分析或系统发育建树。</p>
<p>证据不足不代表样本为阴性。</p>
<p>结果仅用于科研初筛，不构成阴性判定、临床诊断、病因学结论或公共卫生处置建议。</p>
</section></main></body></html>"""


def _pipeline_document(*, state: dict[str, Any], telemetry: dict[str, Any]) -> str:
    delivery = telemetry['delivery_report']
    sections = delivery.get('sections') or {}
    stages = delivery.get('stages') or []
    stage_rows = [
        [
            stage.get('label') or stage.get('id'),
            stage.get('status') or '—',
            _number(stage_timing(stage).get('elapsed_seconds')),
            _number(stage_timing(stage).get('effective_cores')),
            _number(stage.get('max_job_rss_mb')),
        ]
        for stage in stages
        if isinstance(stage, dict)
    ]

    manifest_rows = [
        [item.get('path'), item.get('size') or item.get('bytes') or '—']
        for item in (delivery.get('manifest') or {}).get('files', [])
        if isinstance(item, dict)
    ]
    routing = delivery.get('routing') or telemetry.get('routing')
    routing_section = _routing_section(routing) if isinstance(routing, dict) else ''
    evidence_audit = render_evidence_audit(delivery)
    generated_at = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    deliverables_text = ', '.join(delivery.get('deliverables') or [])
    domain_sections: list[str] = []

    upstream = sections.get('upstream')
    if isinstance(upstream, dict):
        domain_sections.append(
            '<section><h2>质控与组装</h2>'
            + _table(
                ['样本', '输入 Reads', '质控后', '去 rRNA 后', '组装 Contigs', '过滤后 Contigs'],
                _upstream_rows(upstream),
            )
            + '</section>'
        )

    classification = sections.get('virus_identification')
    if isinstance(classification, dict):
        pathogen_rows = [
            [
                item.get('sample_id') or '—',
                item.get('qseqid') or '—',
                item.get('nr_sscinames') or item.get('nr_besthit') or item.get('vhdb_svname') or '—',
                item.get('nr_svfamily') or item.get('nr_vote_vfamily') or item.get('vhdb_svfamily') or '—',
                item.get('checkv_quality') or item.get('miuvig_quality') or '—',
                _percent(item.get('completeness')),
                _percent(item.get('contamination')),
                _ratio_percent(item.get('approval_rate')),
            ]
            for item in classification.get('representatives') or []
            if isinstance(item, dict)
        ]
        domain_sections.append(
            '<section><h2>候选病原体列表</h2>'
            '<p class="muted">以下为固定分类流程产生的病毒候选，不额外推断置信分级。</p>'
            + _table(
                ['样本', 'Contig', '最佳分类命中', 'Family', 'CheckV', '完整度', '污染度', '证据支持率'],
                pathogen_rows,
                empty='未检出符合流程判定条件的病毒候选',
            )
            + _classification_bars(
                [item for item in classification.get('representatives') or [] if isinstance(item, dict)]
            )
            + '</section>'
        )

    host = sections.get('host_identification')
    if isinstance(host, dict):
        domain_sections.append(
            '<section><h2>宿主识别</h2>'
            + _table(
                ['样本数', '识别结果数', '结果文件'],
                [
                    [
                        _number(host.get('sample_count'), 0),
                        _number(host.get('identified_result_count'), 0),
                        host.get('report') or '—',
                    ]
                ],
            )
            + '</section>'
        )

    microbial = sections.get('microbial_profile')
    if isinstance(microbial, dict):
        taxa_rows: list[list[Any]] = []
        chart_items: list[tuple[str, float]] = []
        for level in ('species', 'genus', 'family'):
            value = microbial.get(level) or {}
            for sample_id, top in (value.get('top_taxa') or {}).items():
                fraction = top.get('fraction') if isinstance(top, dict) else None
                taxa_rows.append(
                    [
                        level,
                        sample_id,
                        (top or {}).get('name') or '—',
                        (top or {}).get('taxonomy_id') or '—',
                        _ratio_percent(fraction),
                    ]
                )
                if isinstance(fraction, (int, float)):
                    chart_items.append(
                        (f'{sample_id} · {level} · {(top or {}).get("name") or "—"}', float(fraction) * 100)
                    )
        chart = ''.join(
            f'<div class="bar-row"><span>{_escape(label)}</span><i><b style="width:{max(0, min(value, 100)):.2f}%"></b></i><em>{_number(value)}%</em></div>'
            for label, value in chart_items
        )
        domain_sections.append(
            '<section><h2>微生物谱 Top taxa</h2>'
            '<p class="muted">这里展示分类单元与相对丰度，不将一般 taxa 宣称为病原体。</p>'
            + (f'<div class="bar-chart">{chart}</div>' if chart else '')
            + _table(['层级', '样本', 'Taxon', 'TaxID', '相对丰度'], taxa_rows)
            + '</section>'
        )

    quantification = sections.get('virus_quantification')
    if isinstance(quantification, dict):
        records = [item for item in quantification.get('representative_records') or [] if isinstance(item, dict)]
        rpm_rows = [
            [
                item.get('sample_id') or item.get('sample') or '—',
                item.get('reference_id') or item.get('reference') or item.get('seq_id') or '—',
                _number(item.get('RPM') if item.get('RPM') is not None else item.get('rpm')),
            ]
            for item in records
        ]
        max_rpm = max(
            [float(item.get('RPM') or item.get('rpm') or 0) for item in records],
            default=0,
        )
        chart = ''.join(
            f'<div class="bar-row"><span>{_escape(row[0])} · {_escape(row[1])}</span><i><b style="width:{(float(records[index].get("RPM") or records[index].get("rpm") or 0) / max_rpm * 100) if max_rpm else 0:.2f}%"></b></i><em>{_escape(row[2])}</em></div>'
            for index, row in enumerate(rpm_rows[:20])
        )
        domain_sections.append(
            '<section><h2>病毒定量</h2>'
            + (f'<div class="bar-chart">{chart}</div>' if chart else '')
            + _table(['样本', '病毒参考序列', 'RPM'], rpm_rows, empty='未产生可展示的 RPM 记录')
            + '</section>'
        )

    annotation = sections.get('virus_annotation')
    if isinstance(annotation, dict):
        strategy_rows = [
            [key, _number(value, 0)] for key, value in (annotation.get('strategy_distribution') or {}).items()
        ]
        review_rows = [
            [
                item.get('seq_id') or item.get('id') or '—',
                item.get('status') or 'warning',
                item.get('reason') or item.get('message') or item.get('taxonomy_consistent') or '—',
            ]
            for item in annotation.get('review_candidates') or []
            if isinstance(item, dict)
        ]
        domain_sections.append(
            '<section><h2>病毒注释</h2>'
            + _table(
                ['输入序列', '质量筛选后', '功能注释记录', '一致性警告'],
                [
                    [
                        _number(annotation.get('input_sequence_count'), 0),
                        _number(annotation.get('filtered_sequence_count'), 0),
                        _number(annotation.get('functional_annotation_count'), 0),
                        _number(annotation.get('consistency_warning_count'), 0),
                    ]
                ],
            )
            + '<h3>注释策略分布</h3>'
            + _table(['策略', '序列数'], strategy_rows)
            + '<h3>需人工 Review 的候选</h3>'
            + _table(['序列', '状态', '原因'], review_rows, empty='没有流程标记为需人工 review 的候选')
            + '</section>'
        )

    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(state.get('title') or '分析报告')}</title>
<style>
@page {{ size:A4 landscape;margin:12mm; }}
:root {{ color:#17212b;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif; }}
body {{ margin:0;background:#eef2f5; }} main {{ max-width:1280px;margin:20px auto;padding:28px;background:white; }}
h1 {{ margin:0 0 4px;font-size:26px; }} h2 {{ margin:26px 0 10px; }} h3 {{ margin:18px 0 8px; }} .meta,.muted {{ color:#65727e; }}
.table-wrap {{ overflow-x:auto; }} table {{ width:100%;border-collapse:collapse;font-size:12px;table-layout:auto; }}
th,td {{ padding:5px 7px;border:1px solid #d9e0e6;text-align:left;vertical-align:top; }} th {{ background:#f4f7f9;white-space:nowrap; }}
.path-col,td.path-col,code {{ overflow-wrap:anywhere;word-break:break-word; }} .number-col,td.number-col {{ white-space:nowrap;width:1%; }}
.evidence-table {{ min-width:760px; }} .evidence-table td:nth-child(3),.evidence-table td:nth-child(4) {{ white-space:nowrap;width:1%; }}
.threshold-chart {{ display:grid;gap:6px;margin-top:12px; }} .threshold-row {{ display:grid;grid-template-columns:220px 1fr 150px;gap:8px;align-items:center;font-size:11px; }} .threshold-row i {{ position:relative;height:8px;background:#e5ebef;border-radius:4px;overflow:hidden; }} .threshold-row b {{ display:block;height:100%; }} .threshold-row b.passed {{ background:#168a68; }} .threshold-row b.failed {{ background:#c75b45; }} .threshold-row mark {{ position:absolute;left:83.33%;top:0;width:1px;height:100%;background:#17212b; }} .threshold-row em {{ font-style:normal;white-space:nowrap; }}
.bar-chart {{ display:grid;gap:6px;margin:10px 0 14px; }} .bar-row {{ display:grid;grid-template-columns:minmax(160px,2fr) minmax(180px,5fr) 72px;gap:8px;align-items:center;font-size:12px; }}
.bar-row i {{ height:9px;background:#e5ebef;border-radius:5px;overflow:hidden; }} .bar-row b {{ display:block;height:100%;background:#168aad; }} .bar-row em {{ font-style:normal;text-align:right;white-space:nowrap; }}
@media print {{ body {{ background:white; }} main {{ margin:0;padding:0;max-width:none; }} }}
</style></head><body><main><header><h1>分析 Pipeline 报告</h1>
<div class="meta">任务：{_escape(state.get('title') or state.get('run_id'))} · run：{_escape(state.get('run_id'))}</div>
<div class="meta">交付物：{_escape(deliverables_text)} · 生成时间：{_escape(generated_at)}</div></header>
{routing_section}
{''.join(domain_sections)}
<section><h2>阶段状态</h2>{_table(['阶段', '状态', '耗时(s)', '有效 CPU 核', '峰值内存(MB)'], stage_rows)}</section>
<section><h2>交付文件</h2>{_table(['路径', '大小'], manifest_rows)}</section>
{evidence_audit}
<section><h2>结果边界</h2><p>报告仅汇总固定流程产生的确定性结果，不补全缺失分类字段，也不构成临床诊断。</p></section>
</main></body></html>"""


def _review_checklist() -> str:
    return """<section class="review-checklist"><h2>人工审核清单</h2>
<p class="muted">以下项目默认未勾选，请由具备相应背景的审核人完成。</p>
<ul class="checklist">
<li>☐ 核对输入样本、分析目标与实际执行阶段</li>
<li>☐ 核对关键结论对应的证据索引与原始产物</li>
<li>☐ 评估结果边界、缺失数据与异常警告</li>
<li>☐ 如涉及病原候选，复核分类证据、完整度与污染度</li>
<li>☐ 记录审核人、审核时间与后续处置意见</li>
</ul></section>"""


def render_analysis_delivery_report(
    *,
    state: dict[str, Any],
    telemetry: dict[str, Any],
    run_dir: Path,
) -> str:
    delivery = telemetry.get('delivery_report')
    if not isinstance(delivery, dict):
        raise ValueError('unsupported delivery report schema')
    persisted_report = telemetry.get('version') == 3
    if delivery.get('schema_version') != 4:
        raise ValueError('unsupported delivery report schema')
    if delivery.get('kind') != 'analysis_pipeline':
        raise ValueError('unsupported delivery report kind')
    if persisted_report:
        verify_report_evidence(telemetry=telemetry, run_dir=run_dir)
    if delivery.get('report_kind') in {'preliminary_screen', 'preliminary_alert'}:
        if not isinstance(delivery.get('screening'), dict):
            raise ValueError('missing adaptive screening data')
        document = _adaptive_alert_document(state=state, telemetry=telemetry)
    else:
        sections = delivery.get('sections') or {}
        document = None
    if delivery.get('report_kind') not in {'preliminary_screen', 'preliminary_alert'} and set(sections) == {'upstream'}:
        document = render_workflow1_delivery_report(
            state=state,
            telemetry={
                **telemetry,
                'delivery_report': {
                    **sections['upstream'],
                    'evidence': delivery.get('evidence') or [],
                    'conclusions': delivery.get('conclusions') or [],
                },
            },
            run_dir=run_dir,
        )
    elif (
        delivery.get('report_kind') not in {'preliminary_screen', 'preliminary_alert'}
        and set(sections).issubset({'upstream', 'virus_identification'})
        and isinstance(sections.get('virus_identification'), dict)
    ):
        document = _classification_document(
            state=state,
            telemetry={
                **telemetry,
                'delivery_report': {
                    'classification': sections['virus_identification'],
                    'upstream': sections.get('upstream'),
                    'stages': delivery.get('stages') or [],
                    'routing': delivery.get('routing') or telemetry.get('routing'),
                    'evidence': delivery.get('evidence') or [],
                    'conclusions': delivery.get('conclusions') or [],
                },
            },
            run_dir=run_dir,
        )
    elif delivery.get('report_kind') not in {'preliminary_screen', 'preliminary_alert'}:
        document = _pipeline_document(state=state, telemetry=telemetry)
    specialist_html = _specialist_section(run_dir)
    if specialist_html:
        document = inject(document, specialist_html)
    return document.replace('</main>', _review_checklist() + '</main>', 1)


def _specialist_section(run_dir: Path) -> str:
    candidates = [
        run_dir / '.bioagent' / 'specialist.json',
        Path('/data/user/guojindan/Projects/XvirMind/xvirmind/runs/ops/specialist.json'),
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        return render_specialist_html(
            taxonomy=data.get('taxonomy'),
            rva=data.get('rva'),
            citations=data.get('citations'),
            rules=data.get('rules'),
            review=data.get('review'),
        )
    return ''
