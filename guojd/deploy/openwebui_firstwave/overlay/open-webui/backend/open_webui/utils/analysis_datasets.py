"""Deterministic dataset construction, FASTQ pairing, and preflight checks."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import os
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from open_webui.models.analysis_datasets import (
    AnalysisDatasetRevisionModel,
    AnalysisDatasets,
)
from open_webui.models.analysis_events import AnalysisEvents

CHECK_VERSION = 'fastq-v1'
QUICK_RECORD_LIMIT = 1_000
QUICK_BYTE_LIMIT = 8 * 1024 * 1024
PAIRED_READ_TYPES = {
    'raw_paired_reads',
    'qc_paired_reads',
    'clean_run_paired_reads',
    'clean_sample_paired_reads',
}
SAFE_ID_RE = re.compile(r'^[A-Za-z0-9_.-]+$')
LANE_RE = re.compile(r'(?:^|[._-])L\d{3}(?:$|[._-])', re.IGNORECASE)
FASTQ_EXTENSION_RE = re.compile(r'(?i)(\.fastq|\.fq)(\.gz)?$')


def _artifact(
    label: str,
    roles: tuple[str, ...],
    identities: tuple[str, ...] = ('sample_id',),
    collection: bool = True,
    directories: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        'label': label,
        'roles': [{'name': role, 'kind': 'directory' if role in directories else 'file'} for role in roles],
        'identity_fields': list(identities),
        'collection': collection,
    }


# Mirrors agent/workflow_catalog.py. A parity test protects this executable UI contract.
ARTIFACT_CATALOG: dict[str, dict[str, Any]] = {
    'raw_paired_reads': _artifact('原始双端 reads', ('read1', 'read2'), ('run_id', 'sample_id')),
    'qc_paired_reads': _artifact('质控后双端 reads', ('read1', 'read2'), ('run_id', 'sample_id')),
    'clean_run_paired_reads': _artifact('去 rRNA run reads', ('read1', 'read2'), ('run_id', 'sample_id')),
    'clean_sample_paired_reads': _artifact('样本合并 reads', ('read1', 'read2'), ('sample_id',)),
    'assembled_contigs': _artifact('组装 contigs', ('fasta',)),
    'filtered_contigs': _artifact('过滤后 contigs', ('fasta',)),
    'contigs_fasta': _artifact('外部 contigs', ('fasta',)),
    'virus_prepared_sequences': _artifact('病毒搜索序列', ('contigs', 'orfs'), (), False),
    'virus_search_results': _artifact('病毒候选搜索目录', ('workspace',), (), False, ('workspace',)),
    'virus_candidates': _artifact('病毒候选序列', ('contigs', 'proteins', 'coverage', 'nucl2prot'), (), False),
    'virus_evidence_bundle': _artifact('病毒证据目录', ('workspace',), (), False, ('workspace',)),
    'virus_summary_bundle': _artifact('病毒识别汇总', ('fasta', 'table'), (), False),
    'host_alignment_bundle': _artifact('宿主比对目录', ('workspace', 'sample_list'), (), False, ('workspace',)),
    'host_coverage_bundle': _artifact('宿主覆盖度目录', ('workspace', 'sample_list'), (), False, ('workspace',)),
    'host_blast_bundle': _artifact('宿主 BLAST 目录', ('workspace', 'sample_list'), (), False, ('workspace',)),
    'host_evidence_bundle': _artifact('宿主证据目录', ('workspace', 'sample_list'), (), False, ('workspace',)),
    'host_summary_bundle': _artifact('宿主识别报告', ('report',), (), False),
    'kraken_profiles': _artifact('Kraken profiles', ('workspace', 'sample_list'), (), False, ('workspace',)),
    'bracken_profiles': _artifact('Bracken profiles', ('workspace', 'sample_list'), (), False, ('workspace',)),
    'microbe_summary_bundle': _artifact('微生物谱目录', ('workspace',), (), False, ('workspace',)),
    'virus_reference_fasta': _artifact('病毒参考序列', ('fasta',), (), False),
    'virus_mapping_bundle': _artifact(
        '病毒定量比对目录', ('workspace', 'sample_list', 'reference'), (), False, ('workspace',)
    ),
    'virus_coverage_bundle': _artifact('病毒覆盖度目录', ('workspace', 'sample_list'), (), False, ('workspace',)),
    'virus_quantification_bundle': _artifact('病毒定量汇总', ('rpm', 'summary'), (), False),
    'virus_taxonomy': _artifact('病毒分类表', ('taxonomy',), (), False),
    'virus_quality_bundle': _artifact('病毒质量目录', ('workspace', 'taxonomy'), (), False, ('workspace',)),
    'annotation_strategy_bundle': _artifact('注释策略目录', ('workspace', 'taxonomy'), (), False, ('workspace',)),
    'structure_annotation_bundle': _artifact('结构注释目录', ('workspace', 'taxonomy'), (), False, ('workspace',)),
    'functional_annotation_bundle': _artifact('功能注释目录', ('workspace', 'taxonomy'), (), False, ('workspace',)),
    'annotation_delivery_bundle': _artifact('病毒注释交付目录', ('workspace',), (), False, ('workspace',)),
}


class DatasetInputError(ValueError):
    pass


class _QuickLimitReached(Exception):
    pass


def issue(code: str, message: str, **context: Any) -> dict[str, Any]:
    return {'code': code, 'message': message, **context}


def fingerprint(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {
        'device': stat.st_dev,
        'inode': stat.st_ino,
        'size': stat.st_size,
        'mtime_ns': stat.st_mtime_ns,
    }


DEFAULT_TESTDATA_ROOT = '/data/user/guojindan/Projects/XvirMind/testdata'


def analysis_allowed_roots(primary: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    if primary is not None:
        roots.append(primary.resolve())
    extra = os.getenv('BIOAGENT_TESTDATA_ROOT', DEFAULT_TESTDATA_ROOT)
    if extra:
        path = Path(extra)
        if path.exists():
            resolved = path.resolve()
            if resolved not in roots:
                roots.append(resolved)
    return roots


def path_is_allowed(path: Path, primary: Path | None = None) -> bool:
    resolved = path.resolve()
    for root in analysis_allowed_roots(primary):
        if resolved == root or root in resolved.parents:
            return True
    return False


def resolve_source(raw_path: str, root: Path, *, expected_kind: str | None = None) -> dict[str, Any]:
    path = Path(raw_path)
    if not path.is_absolute():
        raise DatasetInputError('Analysis dataset paths must be absolute')
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise DatasetInputError(f'Analysis dataset path is unavailable: {raw_path}') from error
    root = root.resolve()
    if not path_is_allowed(resolved, root):
        raise DatasetInputError('Analysis dataset path is outside the analysis file root')
    kind = 'directory' if resolved.is_dir() else 'file' if resolved.is_file() else 'other'
    if kind == 'other' or (expected_kind and kind != expected_kind):
        raise DatasetInputError(f'Analysis dataset path has the wrong kind: {raw_path}')
    if not os.access(resolved, os.R_OK):
        raise DatasetInputError(f'Analysis dataset path is not readable: {raw_path}')
    return {'path': str(resolved), 'kind': kind, 'fingerprint': fingerprint(resolved)}


def resolve_sources(paths: list[str], root: Path) -> list[dict[str, Any]]:
    if not paths:
        raise DatasetInputError('At least one analysis dataset path is required')
    sources = [resolve_source(path, root) for path in paths]
    canonical = [source['path'] for source in sources]
    if len(canonical) != len(set(canonical)):
        raise DatasetInputError('The same resolved path cannot be selected more than once')
    return sources


@dataclass(frozen=True)
class MateName:
    side: int
    key: str
    display_key: str


def parse_mate_name(path: Path) -> MateName | dict[str, Any] | None:
    extension = FASTQ_EXTENSION_RE.search(path.name)
    if extension is None:
        return None
    stem = path.name[: extension.start()]
    matches = list(re.finditer(r'(^|[._-])(R[12])(?=$|[._-])', stem, re.IGNORECASE))
    if not matches:
        matches = list(re.finditer(r'(^|[._-])([12])(?=$|[._-])', stem))
    if len(matches) != 1:
        return issue(
            'MATE_TOKEN_AMBIGUOUS',
            '文件名必须包含且仅包含一个明确的 mate token。',
            path=str(path),
        )
    match = matches[0]
    token = match.group(2).upper()
    side = 1 if token in {'R1', '1'} else 2
    start, end = match.span(2)
    normalized = f'{stem[:start]}{{mate}}{stem[end:]}'
    return MateName(side=side, key=f'{path.parent}\0{normalized}', display_key=normalized)


def _safe_stable_id(prefix: str, value: str) -> str:
    ascii_value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^A-Za-z0-9_.-]+', '-', ascii_value.replace('{mate}', '')).strip('._-')
    slug = slug[:48] or prefix
    digest = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f'{slug}-{digest}'


def pair_fastq_sources(  # noqa: C901
    sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    parsed: list[tuple[dict[str, Any], MateName]] = []
    issues: list[dict[str, Any]] = []
    for source in sources:
        if source['kind'] != 'file':
            issues.append(issue('FILE_ROLE_REQUIRED', '目录必须通过结构化角色表单指定。', path=source['path']))
            continue
        value = parse_mate_name(Path(source['path']))
        if value is None:
            issues.append(issue('FILE_ROLE_REQUIRED', '非 FASTQ 文件必须指定 artifact 与角色。', path=source['path']))
        elif isinstance(value, dict):
            issues.append(value)
        else:
            parsed.append((source, value))
    groups: dict[str, dict[int, list[tuple[dict[str, Any], MateName]]]] = {}
    cross_directory: dict[str, set[Path]] = {}
    for source, value in parsed:
        groups.setdefault(value.key, {1: [], 2: []})[value.side].append((source, value))
        cross_directory.setdefault(value.display_key, set()).add(Path(source['path']).parent)
    for key, directories in cross_directory.items():
        same_name = [group for group in groups if group.endswith(f'\0{key}')]
        sides = {side for group in same_name for side, candidates in groups[group].items() if candidates}
        if (
            len(directories) > 1
            and sides == {1, 2}
            and all(not (groups[group][1] and groups[group][2]) for group in same_name)
        ):
            issues.append(issue('CROSS_DIRECTORY_PAIR', '自动配对不跨目录。', pair_key=key))

    records: list[dict[str, Any]] = []
    requires_grouping = False
    for key in sorted(groups):
        sides = groups[key]
        display_key = next(iter(sides[1] or sides[2]))[1].display_key
        for side in (1, 2):
            if not sides[side]:
                issues.append(issue('MATE_MISSING', f'配对缺少 R{side}。', pair_key=display_key))
            elif len(sides[side]) > 1:
                issues.append(issue('MATE_DUPLICATE', f'配对存在多个 R{side}。', pair_key=display_key))
        if len(sides[1]) != 1 or len(sides[2]) != 1:
            continue
        run_id = _safe_stable_id('run', display_key)
        requires_grouping = requires_grouping or bool(LANE_RE.search(display_key))
        records.append(
            {
                'record_id': f'rec-{hashlib.sha256(key.encode()).hexdigest()[:12]}',
                'run_id': run_id,
                'sample_id': run_id,
                'files': {'read1': sides[1][0][0], 'read2': sides[2][0][0]},
            }
        )
    if len(records) > 1:
        requires_grouping = True
    if requires_grouping and not any(item['code'] == 'SAMPLE_GROUPING_REQUIRED' for item in issues):
        issues.append(issue('SAMPLE_GROUPING_REQUIRED', '请确认每个 run 所属的 biological sample。'))
    return records, issues, requires_grouping


def _canonical_read_id(header: bytes) -> bytes:
    identifier = header[1:].strip().split(None, 1)[0]
    return re.sub(rb'/[12]$', b'', identifier)


def _open_fastq(path: Path) -> BinaryIO:
    with path.open('rb') as raw:
        magic = raw.read(2)
    compressed = path.name.lower().endswith('.gz')
    if compressed != (magic == b'\x1f\x8b'):
        raise DatasetInputError('COMPRESSION_MISMATCH')
    return gzip.open(path, 'rb') if compressed else path.open('rb')


def _read_record(handle: BinaryIO, byte_limit: int | None = None) -> tuple[list[bytes] | None, int]:
    lines = []
    remaining = byte_limit
    for _ in range(4):
        if remaining is not None and remaining <= 0:
            raise _QuickLimitReached
        available = remaining
        line = handle.readline() if remaining is None else handle.readline(remaining)
        if remaining is not None:
            remaining -= len(line)
            if line and len(line) == available and not line.endswith((b'\n', b'\r')):
                raise _QuickLimitReached
        lines.append(line)
    byte_count = sum(len(line) for line in lines)
    if not lines[0]:
        return None, byte_count
    if any(not line for line in lines[1:]):
        raise DatasetInputError('FASTQ_TRUNCATED_RECORD')
    if not lines[0].startswith(b'@'):
        raise DatasetInputError('FASTQ_HEADER_INVALID')
    if not lines[2].startswith(b'+'):
        raise DatasetInputError('FASTQ_PLUS_INVALID')
    if len(lines[1].rstrip(b'\r\n')) != len(lines[3].rstrip(b'\r\n')):
        raise DatasetInputError('FASTQ_LENGTH_MISMATCH')
    return lines, byte_count


def check_fastq_pair(read1: Path, read2: Path, *, full: bool) -> dict[str, Any]:
    limit = None if full else QUICK_RECORD_LIMIT
    records = 0
    uncompressed = [0, 0]
    try:
        with _open_fastq(read1) as left, _open_fastq(read2) as right:
            while limit is None or records < limit:
                left_record, left_bytes = _read_record(
                    left,
                    None if full else QUICK_BYTE_LIMIT - uncompressed[0],
                )
                right_record, right_bytes = _read_record(
                    right,
                    None if full else QUICK_BYTE_LIMIT - uncompressed[1],
                )
                uncompressed[0] += left_bytes
                uncompressed[1] += right_bytes
                if left_record is None or right_record is None:
                    if left_record is not None or right_record is not None:
                        raise DatasetInputError('RECORD_COUNT_MISMATCH')
                    break
                if _canonical_read_id(left_record[0]) != _canonical_read_id(right_record[0]):
                    raise DatasetInputError('MATE_ID_MISMATCH')
                records += 1
                if not full and max(uncompressed) >= QUICK_BYTE_LIMIT:
                    break
    except _QuickLimitReached:
        pass
    except DatasetInputError:
        raise
    except (OSError, EOFError, gzip.BadGzipFile, UnicodeError) as error:
        raise DatasetInputError('COMPRESSION_MISMATCH') from error
    return {
        'records': records,
        'compressed_bytes': [read1.stat().st_size, read2.stat().st_size],
        'uncompressed_bytes': uncompressed,
    }


def _paired_records(artifacts: list[dict[str, Any]]):
    for artifact in artifacts:
        if artifact.get('type') in PAIRED_READ_TYPES:
            for record in artifact.get('records', []):
                yield artifact, record


def quick_check_artifacts(artifacts: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results = []
    issues = []
    for artifact, record in _paired_records(artifacts):
        try:
            result = check_fastq_pair(
                Path(record['files']['read1']['path']),
                Path(record['files']['read2']['path']),
                full=False,
            )
            results.append({'artifact_id': artifact['id'], 'record_id': record.get('record_id'), **result})
            if result['records'] == 0:
                issues.append(
                    issue(
                        'EMPTY_FASTQ',
                        _issue_message('EMPTY_FASTQ'),
                        artifact_id=artifact['id'],
                        record_id=record.get('record_id'),
                    )
                )
        except DatasetInputError as error:
            code = str(error)
            issues.append(
                issue(code, _issue_message(code), artifact_id=artifact['id'], record_id=record.get('record_id'))
            )
    return {'status': 'failed' if issues else 'passed', 'records': results}, issues


def _issue_message(code: str) -> str:
    return {
        'COMPRESSION_MISMATCH': '压缩格式、gzip 完整性或文件扩展名不一致。',
        'FASTQ_TRUNCATED_RECORD': 'FASTQ 末尾存在不完整 record。',
        'FASTQ_HEADER_INVALID': 'FASTQ header 必须以 @ 开始。',
        'FASTQ_PLUS_INVALID': 'FASTQ 第三行必须以 + 开始。',
        'FASTQ_LENGTH_MISMATCH': 'sequence 与 quality 长度不一致。',
        'MATE_ID_MISMATCH': 'R1/R2 的 mate ID 不一致。',
        'RECORD_COUNT_MISMATCH': 'R1/R2 的 record 数不一致。',
        'EMPTY_FASTQ': 'R1/R2 FASTQ 不能是空文件。',
        'FINGERPRINT_CHANGED': '文件在预检期间发生变化。',
    }.get(code, code)


def normalize_artifacts(  # noqa: C901
    raw_artifacts: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not raw_artifacts:
        raise DatasetInputError('At least one artifact is required')
    allowed = {source['path'] for source in sources}
    normalized = []
    used_types: set[str] = set()
    used_ids: set[str] = set()
    used_paths: set[str] = set()
    for artifact_index, raw in enumerate(raw_artifacts):
        artifact_type = raw.get('type')
        contract = ARTIFACT_CATALOG.get(artifact_type)
        if contract is None or artifact_type in used_types:
            raise DatasetInputError('Artifact types must be supported and unique')
        used_types.add(artifact_type)
        artifact_id = raw.get('id')
        if not isinstance(artifact_id, str) or not SAFE_ID_RE.fullmatch(artifact_id) or artifact_id in used_ids:
            raise DatasetInputError('Artifact id must contain only letters, digits, ._-')
        used_ids.add(artifact_id)
        records = raw.get('records')
        if not isinstance(records, list) or not records:
            raise DatasetInputError('Artifact records must not be empty')
        if not contract['collection'] and len(records) != 1:
            raise DatasetInputError(f'{artifact_type} requires exactly one record')
        normalized_records = []
        identities: set[tuple[str, ...]] = set()
        for record_index, record in enumerate(records):
            value: dict[str, Any] = {}
            record_id = record.get('record_id') or f'rec-{artifact_index + 1}-{record_index + 1}'
            if not isinstance(record_id, str) or not SAFE_ID_RE.fullmatch(record_id):
                raise DatasetInputError('Record id must contain only letters, digits, ._-')
            value['record_id'] = record_id
            for field in contract['identity_fields']:
                identity_value = record.get(field)
                if not isinstance(identity_value, str) or not SAFE_ID_RE.fullmatch(identity_value):
                    raise DatasetInputError(f'{field} must contain only letters, digits, ._-')
                value[field] = identity_value
            identity = tuple(value[field] for field in contract['identity_fields'])
            if identity and identity in identities:
                raise DatasetInputError(f'{artifact_type} contains duplicate record identities')
            identities.add(identity)
            files = record.get('files')
            if not isinstance(files, dict):
                raise DatasetInputError('Artifact record files must be an object')
            normalized_files = {}
            for role in contract['roles']:
                raw_file = files.get(role['name'])
                path_value = raw_file.get('path') if isinstance(raw_file, dict) else raw_file
                if not isinstance(path_value, str) or path_value not in allowed:
                    raise DatasetInputError('Artifact roles may only use the selected dataset sources')
                source = resolve_source(path_value, root, expected_kind=role['kind'])
                if source['path'] in used_paths:
                    raise DatasetInputError('The same path cannot fill more than one artifact role')
                used_paths.add(source['path'])
                normalized_files[role['name']] = source
            value['files'] = normalized_files
            normalized_records.append(value)
        normalized.append({'id': artifact_id, 'type': artifact_type, 'records': normalized_records})
    return normalized, sources


def build_initial_revision(paths: list[str], root: Path) -> tuple[list, list, str, dict, list]:
    sources = resolve_sources(paths, root)
    records, pairing_issues, requires_grouping = pair_fastq_sources(sources)
    artifacts = [{'id': 'primary', 'type': 'raw_paired_reads', 'records': records}] if records else []
    quick = {'status': 'not_applicable', 'records': []}
    quick_issues: list[dict[str, Any]] = []
    if artifacts:
        quick, quick_issues = quick_check_artifacts(artifacts)
    issues = [*pairing_issues, *quick_issues]
    if quick_issues:
        status = 'invalid'
    elif not artifacts or pairing_issues or requires_grouping:
        status = 'needs_review'
    else:
        status = 'checking'
    checks = {'quick': quick, 'full': {'status': 'pending' if status == 'checking' else 'not_started'}}
    return sources, artifacts, status, checks, issues


def build_manual_revision(
    raw_artifacts: list[dict[str, Any]],
    previous_sources: list[dict[str, Any]],
    root: Path,
) -> tuple[list, list, str, dict, list]:
    refreshed_sources = [resolve_source(source['path'], root) for source in previous_sources]
    artifacts, sources = normalize_artifacts(raw_artifacts, refreshed_sources, root)
    quick, issues = quick_check_artifacts(artifacts)
    has_fastq = any(artifact['type'] in PAIRED_READ_TYPES for artifact in artifacts)
    status = 'invalid' if issues else 'checking' if has_fastq else 'ready'
    checks = {
        'quick': quick if has_fastq else {'status': 'not_applicable', 'records': []},
        'full': {'status': 'pending' if status == 'checking' else 'not_applicable'},
    }
    return sources, artifacts, status, checks, issues


def revision_model(
    dataset_id: str,
    revision: int,
    sources: list,
    artifacts: list,
    status: str,
    checks: dict,
    issues: list,
) -> AnalysisDatasetRevisionModel:
    now = int(time.time())
    return AnalysisDatasetRevisionModel(
        dataset_id=dataset_id,
        revision=revision,
        status=status,
        sources=sources,
        artifacts=artifacts,
        checks=checks,
        issues=issues,
        check_version=CHECK_VERSION,
        created_at=now,
        updated_at=now,
    )


def serialize_revision(value: AnalysisDatasetRevisionModel) -> dict[str, Any]:
    result = value.model_dump()
    result['actions'] = {
        'can_edit': value.status in {'needs_review', 'invalid', 'stale'},
        'can_plan': value.status in {'checking', 'ready'},
        'can_execute': value.status == 'ready',
    }
    return result


def dataset_provider_context(value: AnalysisDatasetRevisionModel) -> dict[str, Any]:
    summary_artifacts = []
    for artifact in value.artifacts:
        summary_artifacts.append(
            {
                'id': artifact['id'],
                'type': artifact['type'],
                'records': [
                    {key: record[key] for key in ('record_id', 'run_id', 'sample_id') if key in record}
                    for record in artifact.get('records', [])
                ],
            }
        )
    summary_issues = [
        {key: item[key] for key in ('code', 'message', 'artifact_id', 'record_id', 'pair_key') if key in item}
        for item in value.issues
        if isinstance(item, dict)
    ]
    return {
        'id': value.dataset_id,
        'revision': value.revision,
        'status': value.status,
        'check_version': value.check_version,
        'summary': {
            'dataset_id': value.dataset_id,
            'revision': value.revision,
            'status': value.status,
            'artifacts': summary_artifacts,
            'checks': value.checks,
            'issues': summary_issues,
        },
        'artifacts': value.artifacts,
        'checks': value.checks,
        'issues': value.issues,
    }


def _cache_key(value: AnalysisDatasetRevisionModel) -> str:
    fingerprints = [
        record['files'][role]['fingerprint']
        for _artifact, record in _paired_records(value.artifacts)
        for role in ('read1', 'read2')
    ]
    payload = json.dumps({'version': CHECK_VERSION, 'fingerprints': fingerprints}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _fingerprints_match(value: AnalysisDatasetRevisionModel) -> bool:
    try:
        return all(fingerprint(Path(source['path'])) == source['fingerprint'] for source in value.sources)
    except OSError:
        return False


def revision_fingerprints_match(value: AnalysisDatasetRevisionModel) -> bool:
    return _fingerprints_match(value)


def _full_check(value: AnalysisDatasetRevisionModel) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    if not _fingerprints_match(value):
        code = 'FINGERPRINT_CHANGED'
        return 'stale', {}, [issue(code, _issue_message(code))]
    results = []
    issues = []
    for artifact, record in _paired_records(value.artifacts):
        try:
            result = check_fastq_pair(
                Path(record['files']['read1']['path']),
                Path(record['files']['read2']['path']),
                full=True,
            )
            results.append({'artifact_id': artifact['id'], 'record_id': record.get('record_id'), **result})
            if result['records'] == 0:
                issues.append(
                    issue(
                        'EMPTY_FASTQ',
                        _issue_message('EMPTY_FASTQ'),
                        artifact_id=artifact['id'],
                        record_id=record.get('record_id'),
                    )
                )
        except DatasetInputError as error:
            code = str(error)
            issues.append(
                issue(code, _issue_message(code), artifact_id=artifact['id'], record_id=record.get('record_id'))
            )
    if not _fingerprints_match(value):
        code = 'FINGERPRINT_CHANGED'
        return 'stale', {}, [issue(code, _issue_message(code))]
    return (
        ('invalid' if issues else 'ready'),
        {
            'pairs': len(results),
            'record_count': sum(result['records'] for result in results),
            'compressed_bytes': sum(sum(result['compressed_bytes']) for result in results),
            'uncompressed_bytes': sum(sum(result['uncompressed_bytes']) for result in results),
            'records': results,
        },
        issues,
    )


class DatasetPreflightQueue:
    def __init__(self, run_root: Path):
        self.run_root = run_root
        self.queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self.queued: set[tuple[str, int]] = set()
        self.workers: list[asyncio.Task] = []
        self.owner = f'preflight-{os.getpid()}-{uuid.uuid4().hex}'

    async def start(self) -> None:
        if self.workers:
            return
        concurrency = max(1, int(os.getenv('ANALYSIS_DATASET_PREFLIGHT_CONCURRENCY', '1')))
        self.workers = [asyncio.create_task(self._worker(), name=f'dataset-preflight-{i}') for i in range(concurrency)]
        for value in await AnalysisDatasets.checking():
            self.enqueue(value.dataset_id, value.revision)

    async def stop(self) -> None:
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []
        self.queued.clear()
        self.queue = asyncio.Queue()

    def enqueue(self, dataset_id: str, revision: int) -> None:
        key = (dataset_id, revision)
        if key not in self.queued:
            self.queued.add(key)
            self.queue.put_nowait(key)

    def _runner_active(self) -> bool:
        try:
            for state_path in self.run_root.glob('*/.bioagent/state.json'):
                try:
                    state = json.loads(state_path.read_text(encoding='utf-8'))
                except (OSError, json.JSONDecodeError):
                    continue
                if (state.get('execution') or {}).get('status') == 'running':
                    return True
        except OSError:
            pass
        return False

    def _retry(self, dataset_id: str, revision: int) -> None:
        if self.workers:
            self.enqueue(dataset_id, revision)

    async def _renew_claim(self, dataset_id: str, revision: int) -> None:
        while True:
            await asyncio.sleep(30)
            if not await AnalysisDatasets.renew_preflight(dataset_id, revision, self.owner):
                return

    @staticmethod
    def _stale_result() -> dict[str, Any]:
        code = 'FINGERPRINT_CHANGED'
        return {
            'status': 'stale',
            'details': {},
            'issues': [issue(code, _issue_message(code))],
        }

    async def _preflight_result(self, value: AnalysisDatasetRevisionModel) -> dict[str, Any]:
        if not _fingerprints_match(value):
            return self._stale_result()
        cache_key = _cache_key(value)
        cached = await AnalysisDatasets.get_cache(cache_key)
        if cached is not None:
            return cached if _fingerprints_match(value) else self._stale_result()

        status_value, details, issues = await asyncio.to_thread(_full_check, value)
        if not _fingerprints_match(value):
            return self._stale_result()
        result = {'status': status_value, 'details': details, 'issues': issues}
        if status_value in {'ready', 'invalid'}:
            await AnalysisDatasets.set_cache(cache_key, result)
        return result

    async def _process_claim(self, dataset_id: str, revision: int) -> None:
        value = await self._get_revision(dataset_id, revision)
        if value is None or value.status != 'checking':
            return
        result = await self._preflight_result(value)
        checks = {
            **value.checks,
            'full': {
                'status': 'passed' if result['status'] == 'ready' else 'failed',
                'completed_at': int(time.time()),
                'check_version': CHECK_VERSION,
                **result['details'],
            },
        }
        await AnalysisDatasets.update_checks(
            dataset_id,
            revision,
            status=result['status'],
            checks=checks,
            issues=[*value.issues, *result['issues']],
            expected_status='checking',
        )
        user_id = await AnalysisDatasets.owner(dataset_id)
        if user_id:
            await AnalysisEvents.record(
                user_id=user_id,
                dataset_id=dataset_id,
                kind='dataset_preflight_completed',
                payload={
                    'revision': revision,
                    'status': result['status'],
                    'check_version': CHECK_VERSION,
                },
            )

    async def _worker(self) -> None:
        while True:
            dataset_id, revision = await self.queue.get()
            claimed = False
            retry = False
            heartbeat: asyncio.Task | None = None
            try:
                while self._runner_active():
                    await asyncio.sleep(5)
                claimed = await AnalysisDatasets.claim_preflight(dataset_id, revision, self.owner)
                if not claimed:
                    retry = True
                    continue
                heartbeat = asyncio.create_task(self._renew_claim(dataset_id, revision))
                await self._process_claim(dataset_id, revision)
            finally:
                if heartbeat:
                    heartbeat.cancel()
                    await asyncio.gather(heartbeat, return_exceptions=True)
                if claimed:
                    await AnalysisDatasets.release_preflight(dataset_id, revision, self.owner)
                self.queued.discard((dataset_id, revision))
                self.queue.task_done()
                if retry:
                    asyncio.get_running_loop().call_later(10, self._retry, dataset_id, revision)

    @staticmethod
    async def _get_revision(dataset_id: str, revision: int) -> AnalysisDatasetRevisionModel | None:
        # Workers do not need owner access; resolve the revision directly through its cacheable row.
        from open_webui.internal.db import get_async_db
        from open_webui.models.analysis_datasets import AnalysisDatasetRevision
        from sqlalchemy import select

        async with get_async_db() as session:
            row = (
                await session.execute(
                    select(AnalysisDatasetRevision).where(
                        AnalysisDatasetRevision.dataset_id == dataset_id,
                        AnalysisDatasetRevision.revision == revision,
                    )
                )
            ).scalar_one_or_none()
            return AnalysisDatasetRevisionModel.model_validate(row) if row else None


def new_dataset_id() -> str:
    return f'ds_{uuid.uuid4().hex}'
