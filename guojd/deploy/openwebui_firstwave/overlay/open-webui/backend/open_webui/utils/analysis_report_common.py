"""Shared normalization for deterministic analysis reports."""

from __future__ import annotations

import datetime as dt
from typing import Any

LEGACY_CONFIDENCE_THRESHOLDS = {
    'top_species_reads': 1_000,
    'top_species_sample_fraction': 0.01,
    'top_species_viral_fraction': 0.80,
}
CHECK_LABELS = {
    'top_species_reads': '最高物种命中 reads',
    'top_species_sample_fraction': '占抽样 read pairs',
    'top_species_viral_fraction': '占病毒 reads',
}
REASON_LABELS = {
    'USER_FORCED_STANDARD': '用户指定标准模式',
    'EMERGENCY_HIGH_CONFIDENCE': '紧急模式获得高置信信号',
    'EMERGENCY_LOW_CONFIDENCE_REPORT': '紧急模式在低置信初筛后直接出具报告',
    'KNOWN_VIRUS_HIGH_CONFIDENCE': '已知病毒信号满足高置信门槛',
    'KNOWN_VIRUS_CONFIDENCE_INSUFFICIENT': '已知病毒信号未满足全部高置信门槛',
    'TOP_SPECIES_READS_BELOW_MINIMUM': '最高物种命中 reads 未达门槛',
    'TOP_SPECIES_SAMPLE_FRACTION_BELOW_MINIMUM': '最高物种占抽样 read pairs 比例未达门槛',
    'TOP_SPECIES_VIRAL_FRACTION_BELOW_MINIMUM': '最高物种占病毒 reads 比例未达门槛',
    'CPU_HIGH': 'CPU 负载过高',
    'THREADS_INSUFFICIENT': '可用线程不足',
    'MEMORY_INSUFFICIENT': '可用内存不足',
}
MODE_LABELS = {
    'auto': '智能',
    'emergency': '紧急',
    'standard': '标准',
}


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = dt.datetime.strptime(value, '%a %b %d %H:%M:%S %Y')
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed


def normalized_timestamp(value: Any) -> Any:
    parsed = parse_timestamp(value)
    return parsed.isoformat(timespec='seconds') if parsed else value


def stage_timing(stage: dict[str, Any]) -> dict[str, Any]:
    jobs = [job for job in stage.get('jobs') or [] if isinstance(job, dict)]
    starts = [parse_timestamp(job.get('started_at')) for job in jobs]
    finishes = [parse_timestamp(job.get('finished_at')) for job in jobs]
    starts = [value for value in starts if value is not None]
    finishes = [value for value in finishes if value is not None]
    started = min(starts) if starts else parse_timestamp(stage.get('started_at'))
    finished = max(finishes) if finishes else parse_timestamp(stage.get('finished_at'))
    elapsed = (
        max(0.0, (finished - started).total_seconds())
        if started is not None and finished is not None
        else stage.get('wall_seconds')
    )
    job_wall = stage.get('job_wall_seconds')
    if not isinstance(job_wall, (int, float)):
        job_wall = stage.get('wall_seconds')
    cpu_time = stage.get('cpu_time_seconds')
    effective_cores = (
        float(cpu_time) / float(elapsed)
        if isinstance(cpu_time, (int, float)) and isinstance(elapsed, (int, float)) and elapsed
        else stage.get('effective_cores')
    )
    return {
        'started_at': started.isoformat(timespec='seconds') if started else None,
        'finished_at': finished.isoformat(timespec='seconds') if finished else None,
        'elapsed_seconds': elapsed,
        'job_wall_seconds': job_wall,
        'effective_cores': effective_cores,
    }


def confidence_checks(sample: dict[str, Any], screening: dict[str, Any]) -> list[dict[str, Any]]:
    stored = sample.get('confidence_checks')
    if isinstance(stored, list) and stored:
        return [check for check in stored if isinstance(check, dict)]
    thresholds = screening.get('confidence_thresholds') or LEGACY_CONFIDENCE_THRESHOLDS
    actuals = {
        'top_species_reads': int((sample.get('top_species') or {}).get('reads') or 0),
        'top_species_sample_fraction': sample.get('top_species_sample_fraction') or 0.0,
        'top_species_viral_fraction': sample.get('top_species_viral_fraction') or 0.0,
    }
    return [
        {
            'metric': metric,
            'actual': actuals[metric],
            'threshold': threshold,
            'operator': '>=',
            'passed': actuals[metric] >= threshold,
        }
        for metric, threshold in thresholds.items()
        if metric in actuals and isinstance(threshold, (int, float))
    ]


def routing_summary(routing: dict[str, Any]) -> dict[str, Any]:
    request = routing.get('request') or {}
    decision = routing.get('decision') or {}
    screening = routing.get('screening') or {}
    samples = []
    failed_labels: list[str] = []
    for sample in screening.get('samples') or []:
        if not isinstance(sample, dict):
            continue
        checks = confidence_checks(sample, screening)
        by_metric = {check.get('metric'): check for check in checks}
        failed_labels.extend(
            CHECK_LABELS.get(str(check.get('metric')), str(check.get('metric')))
            for check in checks
            if check.get('passed') is False
        )
        samples.append({**sample, 'checks': by_metric})

    mode = request.get('mode')
    route = decision.get('selected_route')
    confidence = decision.get('confidence')
    failed_text = '、'.join(dict.fromkeys(failed_labels))
    if mode == 'auto' and route == 'B':
        explanation = (
            f'智能模式要求所有样本均通过三项高置信门槛；因{failed_text}未达到门槛，选择路径 B（完整标准分析）。'
            if failed_text
            else '智能模式因快速初筛置信度不足，选择路径 B（完整标准分析）。'
        )
    elif mode == 'auto' and route == 'A':
        explanation = '智能模式下快速初筛满足全部高置信门槛，选择路径 A（快速预警）。'
    elif mode == 'standard':
        explanation = '用户指定标准模式，快速初筛仅记录指标，固定选择路径 B（完整标准分析）。'
    elif mode == 'emergency':
        explanation = '用户指定紧急模式，快速初筛后选择路径 A 并直接生成初筛报告。'
    else:
        explanation = '未记录完整的自适应路由结论。'
    return {
        'mode': mode,
        'mode_label': MODE_LABELS.get(mode, mode or '—'),
        'route': route,
        'confidence': confidence,
        'confidence_label': '高' if confidence == 'high' else ('低' if confidence == 'low' else '—'),
        'reason_codes': decision.get('reason_codes') or [],
        'reason_labels': [REASON_LABELS.get(str(code), str(code)) for code in decision.get('reason_codes') or []],
        'explanation': explanation,
        'samples': samples,
    }
