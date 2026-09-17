from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from open_webui.internal.db import get_async_session
from open_webui.models.analysis_datasets import AnalysisDatasets
from open_webui.models.analysis_events import AnalysisEvents
from open_webui.models.analysis_plans import AnalysisPlanRevisionModel, AnalysisPlans
from open_webui.models.chat_messages import ChatMessages
from open_webui.models.chats import ChatForm, Chats
from open_webui.utils.analysis_datasets import (
    ARTIFACT_CATALOG,
    DEFAULT_TESTDATA_ROOT,
    DatasetInputError,
    DatasetPreflightQueue,
    build_initial_revision,
    build_manual_revision,
    dataset_provider_context,
    new_dataset_id,
    path_is_allowed,
    revision_fingerprints_match,
    revision_model,
    serialize_revision,
)
from open_webui.utils.ops_service import OpsError, OpsService
from open_webui.utils.ops_rva import job_status as rva_job_status
from open_webui.utils.ops_specialist_report import inject, render_specialist_html
from open_webui.utils.analysis_knowledge import (
    KnowledgeProxyError,
    call_annotate,
    call_classify,
    call_query,
    mcp_health,
)
from open_webui.utils.analysis_delivery_report import (
    render_analysis_delivery_report,
)
from open_webui.utils.analysis_errors import raise_analysis_error
from open_webui.utils.analysis_planner import (
    AnalysisPlannerError,
    analysis_health,
    compile_analysis_plan,
    start_analysis_run,
)
from open_webui.utils.auth import get_verified_user
from open_webui.utils.internal_analysis_report import render_internal_analysis_report
from open_webui.utils.report_evidence import (
    EvidenceValidationError,
    verify_report_evidence,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _analysis_file_root() -> Path:
    return Path(os.getenv('BIOAGENT_RUN_ROOT') or os.getenv('ANALYSIS_FILE_ROOT', '/data/runs')).resolve()


ANALYSIS_FILE_ROOT = _analysis_file_root()

_OPS = OpsService(
    Path(os.getenv('XVIRMIND_OPS_ROOT', '/data/user/guojindan/Projects/XvirMind/xvirmind/runs/ops')),
    Path(os.getenv('BIOAGENT_TESTDATA_ROOT', DEFAULT_TESTDATA_ROOT)),
    Path(os.getenv('XVIRMIND_KNOWLEDGE_ROOT', '/data/user/guojindan/Projects/XvirMind/knowledge')),
)
_RVA_DEMO = Path(os.getenv('XVIRMIND_RVA_DEMO', '/data/user/guojindan/Projects/XvirMind/xvirmind/runs/rva/kp641127'))


def _ops_user(user) -> str:
    return str(getattr(user, 'name', None) or getattr(user, 'email', None) or getattr(user, 'id', None) or 'guojindan')


def _raise_ops(error: OpsError):
    raise HTTPException(status_code=error.status_code, detail=str(error)) from error

DIAGNOSTIC_REPORT_FILENAME = 'diagnostic-opinion.html'
dataset_preflight_queue = DatasetPreflightQueue(ANALYSIS_FILE_ROOT)


class AnalysisFileEntry(BaseModel):
    name: str
    type: str
    path: str
    abs_path: str
    size: int | None = None
    modified: int | None = None
    has_children: bool = False


class AnalysisFilesResponse(BaseModel):
    root: str
    path: str
    abs_path: str
    entries: list[AnalysisFileEntry]
    next_cursor: int | None = None


class AnalysisDatasetCreateRequest(BaseModel):
    paths: list[str] = Field(min_length=1)


class AnalysisDatasetPatchRequest(BaseModel):
    base_revision: int = Field(ge=1)
    artifacts: list[dict[str, Any]] = Field(min_length=1)


class DatasetReference(BaseModel):
    id: str = Field(min_length=1)
    revision: int = Field(ge=1)


AnalysisGoal = Literal[
    'contig_filter',
    'virus_summary',
    'host_summary',
    'microbe_summary',
    'virus_rpm',
    'annotation_delivery',
]


class AnalysisPlanOptions(BaseModel):
    viral_type: Literal['RNA', 'DNA', 'RNA+DNA'] = 'RNA+DNA'


class AnalysisPlanRoutingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    mode: Literal['auto', 'standard', 'emergency'] = 'auto'


class AnalysisPlanCreateRequest(BaseModel):
    chat_id: str | None = None
    dataset: DatasetReference
    goals: list[AnalysisGoal] = Field(min_length=1, max_length=6)
    options: AnalysisPlanOptions = Field(default_factory=AnalysisPlanOptions)
    routing: AnalysisPlanRoutingRequest = Field(default_factory=AnalysisPlanRoutingRequest)
    base_plan_revision: int | None = Field(default=None, ge=1)


class AnalysisPlanPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')

    goals: list[AnalysisGoal] | None = Field(default=None, min_length=1, max_length=6)
    viral_type: Literal['RNA', 'DNA', 'RNA+DNA'] | None = None

    @model_validator(mode='after')
    def require_change(self):
        if self.goals is None and self.viral_type is None:
            raise ValueError('patch must change goals or viral_type')
        if self.goals is not None and len(set(self.goals)) != len(self.goals):
            raise ValueError('goals must be unique')
        return self


class AnalysisProposalCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    base_plan_revision: int = Field(ge=1)
    proposal_id: str | None = Field(default=None, pattern=r'^analysis_patch_[a-f0-9]{32}$')
    patch: AnalysisPlanPatch
    citations: list[str] = Field(default_factory=list, max_length=50)
    model: str | None = Field(default=None, max_length=200)
    message_id: str | None = Field(default=None, max_length=200)


class AnalysisRunTask(BaseModel):
    id: str
    sample: str
    stage: str
    progress: int
    tone: str


class AnalysisRunStatusResponse(BaseModel):
    run_id: str | None = None
    run_dir: str | None = None
    status: str = 'idle'
    current_rule: str | None = None
    completed_steps: int = 0
    total_steps: int = 0
    progress: int = 0
    updated_at: int | None = None
    error: str | None = None
    report_available: bool = False
    internal_report_available: bool | None = None
    routing: dict[str, Any] | None = None
    tasks: list[AnalysisRunTask] = Field(default_factory=list)


class BenchmarkRunRequest(BaseModel):
    case_id: str | None = Field(default=None, max_length=200)
    dataset: DatasetReference
    goals: list[AnalysisGoal] = Field(min_length=1, max_length=6)
    options: AnalysisPlanOptions = Field(default_factory=AnalysisPlanOptions)
    routing: AnalysisPlanRoutingRequest = Field(default_factory=AnalysisPlanRoutingRequest)


BENCHMARK_SCHEMA_VERSION = 2


RULE_RE = re.compile(r'^(?:local)?rule\s+(?P<rule>[A-Za-z0-9_]+):', re.MULTILINE)
JOB_ID_RE = re.compile(r'^\s*jobid:\s*(?P<job_id>\d+)\s*$')
FINISHED_RULE_RE = re.compile(r'Finished jobid:\s*(?P<job_id>\d+)\s*\(Rule:\s*(?P<rule>[A-Za-z0-9_]+)\)')
FINISHED_JOB_RE = re.compile(r'^Finished job\s+(?P<job_id>\d+)\.$')
JOB_STATS_RE = re.compile(r'^(?P<rule>[A-Za-z0-9_]+)\s+(?P<count>\d+)(?:\s+\d+){0,2}\s*$')
LogJob = tuple[int, str]
LogRule = tuple[int, str]


def _testdata_root() -> Path | None:
    raw = os.getenv('BIOAGENT_TESTDATA_ROOT', DEFAULT_TESTDATA_ROOT)
    path = Path(raw)
    if not path.exists():
        return None
    resolved = path.resolve()
    if resolved == ANALYSIS_FILE_ROOT or ANALYSIS_FILE_ROOT in resolved.parents:
        return None
    return resolved


def _is_under_root(path: Path) -> bool:
    return path_is_allowed(path, ANALYSIS_FILE_ROOT)


def _resolve_path(path: str) -> tuple[Path, str]:
    requested = path.strip() or '/'
    root_text = str(ANALYSIS_FILE_ROOT)
    testdata = _testdata_root()

    if testdata is not None:
        testdata_text = str(testdata)
        if requested in {'/testdata', 'testdata', testdata_text}:
            return testdata, 'testdata'
        if requested.startswith('/testdata/'):
            relative_tail = requested[len('/testdata/') :]
            target = (testdata / relative_tail).resolve()
            if not (target == testdata or testdata in target.parents):
                raise HTTPException(status_code=400, detail='Path is outside the testdata root')
            return target, f'testdata/{relative_tail}'
        if requested == testdata_text or requested.startswith(f'{testdata_text}/'):
            relative_tail = requested[len(testdata_text) :].lstrip('/')
            target = (testdata / relative_tail).resolve() if relative_tail else testdata
            if not (target == testdata or testdata in target.parents):
                raise HTTPException(status_code=400, detail='Path is outside the testdata root')
            return target, f'testdata/{relative_tail}' if relative_tail else 'testdata'

    if requested == '/':
        relative = ''
    elif requested == root_text or requested.startswith(f'{root_text}/'):
        relative = requested[len(root_text) :].lstrip('/')
    else:
        relative = requested.lstrip('/')

    target = (ANALYSIS_FILE_ROOT / relative).resolve()
    if not _is_under_root(target):
        raise HTTPException(status_code=400, detail='Path is outside the analysis file root')

    return target, relative


def _diagnostic_report_state(run_dir: str) -> tuple[Path, dict, dict]:
    requested = Path(run_dir)
    if not requested.is_absolute():
        raise HTTPException(status_code=400, detail='Run directory must be absolute')

    target = requested.resolve()
    if not _is_under_root(target):
        raise HTTPException(status_code=400, detail='Run directory is outside the analysis file root')

    state_path = (target / '.bioagent' / 'state.json').resolve()
    if not _is_under_root(state_path) or not state_path.is_file():
        raise HTTPException(status_code=404, detail='Analysis run state not found')
    state_data = _read_json(state_path)
    if state_data.get('version') != 3:
        raise HTTPException(status_code=404, detail='Diagnostic report is not available for this run')
    state_run_dir = state_data.get('run_dir')
    if not isinstance(state_run_dir, str) or Path(state_run_dir).resolve() != target:
        raise HTTPException(status_code=400, detail='Analysis state does not match the run directory')
    if state_data.get('workflow_id') != 'analysis_pipeline':
        raise HTTPException(status_code=404, detail='Diagnostic report workflow is unsupported')
    execution = state_data.get('execution')
    execution_status = execution.get('status') if isinstance(execution, dict) else None
    completed = execution_status == 'completed' and execution.get('ok') is True
    blocked_screen = execution_status == 'blocked' and state_data.get('workflow_id') == 'analysis_pipeline'
    if not (completed or blocked_screen):
        raise HTTPException(status_code=409, detail='Diagnostic report requires a completed screen')
    report = state_data.get('report')
    if not (
        isinstance(report, dict)
        and report.get('status') == 'ready'
        and report.get('available') is True
        and report.get('schema_version') == 4
    ):
        raise HTTPException(status_code=404, detail='Diagnostic report is not available for this run')
    telemetry = _read_optional_json(
        Path(report.get('telemetry') or target / '.bioagent' / 'telemetry.json'),
        target,
    )
    delivery = (telemetry or {}).get('delivery_report')
    if not (
        telemetry
        and telemetry.get('version') == 3
        and isinstance(delivery, dict)
        and delivery.get('schema_version') == 4
        and delivery.get('kind') == 'analysis_pipeline'
        and (not blocked_screen or delivery.get('report_kind') == 'preliminary_screen')
    ):
        raise HTTPException(status_code=409, detail='Diagnostic report telemetry is unavailable')

    return target, state_data, telemetry


def _display_path(relative: str) -> str:
    return '/' if not relative else f'/{relative}'


def _resolve_run_state(run_id: str | None = None, run_dir: str | None = None) -> Path | None:
    if run_dir:
        target = Path(run_dir).resolve()
        if not _is_under_root(target):
            raise HTTPException(status_code=400, detail='Run directory is outside the analysis file root')
        state_path = target / '.bioagent' / 'state.json'
        return state_path if state_path.exists() else None

    if run_id:
        target = (ANALYSIS_FILE_ROOT / run_id / '.bioagent' / 'state.json').resolve()
        if not _is_under_root(target):
            raise HTTPException(status_code=400, detail='Run is outside the analysis file root')
        return target if target.exists() else None

    candidates = []
    try:
        for child in ANALYSIS_FILE_ROOT.iterdir():
            state_path = child / '.bioagent' / 'state.json'
            if state_path.is_file():
                candidates.append(state_path)
    except OSError:
        return None

    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


async def _require_run_owner(state_path: Path, user_id: str) -> dict:
    state_data = _read_json(state_path)
    chat_id = state_data.get('openwebui_chat_id')
    if not isinstance(chat_id, str) or not await Chats.get_chat_by_id_and_user_id(chat_id, user_id):
        raise HTTPException(status_code=404, detail='Analysis run not found')
    return state_data


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=500, detail=f'Unable to read run state: {error}') from error


def _expected_job_counts(lines: list[str]) -> dict[LogRule, int]:
    counts: dict[LogRule, int] = {}
    invocation = 0
    reading_table = False
    for line in lines:
        if line.strip() == 'Job stats:':
            invocation += 1
            reading_table = True
            continue
        if not reading_table or not (match := JOB_STATS_RE.match(line.strip())):
            continue
        rule = match.group('rule')
        if rule == 'total':
            reading_table = False
            continue
        if rule != 'job':
            counts[(invocation, rule)] = int(match.group('count'))
    return counts


def _started_jobs(lines: list[str]) -> tuple[dict[LogJob, str], list[LogJob], LogRule | None]:
    job_rules: dict[LogJob, str] = {}
    job_order: list[LogJob] = []
    pending_rule: LogRule | None = None
    invocation = 0
    for line in lines:
        if line.strip() == 'Job stats:':
            invocation += 1
            continue
        if match := RULE_RE.match(line):
            pending_rule = (invocation, match.group('rule'))
            continue
        if not pending_rule or not (match := JOB_ID_RE.match(line)):
            continue
        job = (invocation, match.group('job_id'))
        job_rules[job] = pending_rule[1]
        job_order.append(job)
        pending_rule = None
    return job_rules, job_order, pending_rule


def _finished_jobs(lines: list[str], job_rules: dict[LogJob, str]) -> tuple[dict[LogRule, set[LogJob]], set[LogJob]]:
    jobs_by_rule: dict[LogRule, set[LogJob]] = {}
    jobs: set[LogJob] = set()
    invocation = 0
    for line in lines:
        if line.strip() == 'Job stats:':
            invocation += 1
            continue
        if match := FINISHED_RULE_RE.search(line):
            job = (invocation, match.group('job_id'))
            rule = match.group('rule')
        elif match := FINISHED_JOB_RE.match(line):
            job = (invocation, match.group('job_id'))
            rule = job_rules.get(job)
            if not rule:
                continue
        else:
            continue
        jobs_by_rule.setdefault((invocation, rule), set()).add(job)
        jobs.add(job)
    return jobs_by_rule, jobs


def _parse_log_progress(log_path: Path | None) -> tuple[set[str], str | None]:
    if not log_path or not log_path.exists():
        return set(), None

    try:
        lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return set(), None

    expected_jobs = _expected_job_counts(lines)
    job_rules, job_order, pending_rule = _started_jobs(lines)
    finished_jobs, finished_job_ids = _finished_jobs(lines, job_rules)
    completed_runs = {rule for rule, jobs in finished_jobs.items() if len(jobs) >= expected_jobs.get(rule, 1)}
    completed = {rule for _invocation, rule in completed_runs}
    active_jobs = [job for job in job_order if job not in finished_job_ids]
    current_rule = job_rules.get(active_jobs[-1]) if active_jobs else pending_rule
    if isinstance(current_rule, tuple):
        pending = current_rule
        current_rule = pending[1]
    else:
        pending = None
    if pending in completed_runs:
        current_rule = None

    return completed, current_rule


def _run_tone(status: str, progress: int) -> str:
    if status in {'failed', 'blocked'}:
        return 'red'
    if status == 'done':
        return 'green'
    if progress >= 70:
        return 'amber'
    return 'cyan'


def _status_from_state(state: dict) -> str:
    execution = state.get('execution') or {}
    steps = _steps_from_state(state)
    status = execution.get('status')
    ok = execution.get('ok')

    if status == 'blocked':
        return 'blocked'
    if ok is True or status == 'completed':
        return 'done'
    if ok is False or status == 'failed' or any(step.get('status') == 'failed' for step in steps):
        return 'failed'
    if status == 'planned':
        return 'planned'
    if execution.get('started') or status == 'running' or any(step.get('status') == 'running' for step in steps):
        return 'running'
    return 'idle'


def _steps_from_state(state: dict) -> list[dict]:
    steps = state.get('steps')
    if not isinstance(steps, list):
        return []

    normalized = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        label = step.get('label')
        if not isinstance(label, str) or not label.strip():
            continue
        normalized.append(
            {
                'id': step.get('id') if isinstance(step.get('id'), str) else f'step_{len(normalized) + 1}',
                'label': label.strip(),
                'status': step.get('status') if isinstance(step.get('status'), str) else 'pending',
                'rules': [rule.strip() for rule in step.get('rules', []) if isinstance(rule, str) and rule.strip()],
            }
        )
    return normalized


def _merge_log_progress(steps: list[dict], completed_rules: set[str], current_rule: str | None) -> list[dict]:
    merged = []
    for step in steps:
        merged_step = {**step}
        rules = step['rules']
        if step['status'] not in {'completed', 'failed'}:
            if rules and all(rule in completed_rules for rule in rules):
                merged_step['status'] = 'completed'
            elif current_rule and current_rule in rules:
                merged_step['status'] = 'running'
        merged.append(merged_step)
    return merged


def _step_progress(steps: list[dict], status: str) -> tuple[int, int, int, dict | None, dict | None]:
    total = len(steps)
    completed = sum(1 for step in steps if step['status'] in {'completed', 'skipped'})
    current_step = next((step for step in steps if step.get('status') == 'running'), None)
    next_step = next((step for step in steps if step.get('status') == 'pending'), None)

    if status == 'failed':
        current_step = current_step or next((step for step in steps if step.get('status') == 'failed'), None)
    if status == 'done' and total:
        completed = total

    progress = round((completed / total) * 100) if total else 0
    if status == 'done':
        progress = 100
    return completed, total, max(0, min(progress, 100)), current_step, next_step


def _stage_from_state(status: str, current_step: dict | None, next_step: dict | None) -> str:
    if status == 'done':
        return '已完成'
    if status == 'failed':
        return '运行失败'
    if status == 'blocked':
        return '资源不足'
    if status == 'planned':
        return '等待启动'
    if current_step:
        return f'{current_step["label"]}中'
    if status == 'running' and next_step:
        return f'{next_step["label"]}待执行'
    if status == 'running':
        return '收尾中'
    return '暂无任务'


def _log_path_from_state(state: dict) -> Path | None:
    execution = state.get('execution') or {}
    log = execution.get('log')
    if not log:
        return None

    path = Path(log).resolve()
    if not _is_under_root(path):
        return None
    return path


def _status_response_from_state(
    state_path: Path,
    *,
    include_internal_report: bool = False,
) -> AnalysisRunStatusResponse:
    state = _read_json(state_path)
    status = _status_from_state(state)
    log_path = _log_path_from_state(state)
    completed_rules, current_rule = _parse_log_progress(log_path)
    steps = _merge_log_progress(_steps_from_state(state), completed_rules, current_rule)
    completed, total, progress, current_step, next_step = _step_progress(steps, status)

    inputs = state.get('inputs') or {}
    run_id = state.get('run_id') or state_path.parent.parent.name
    run_dir = state.get('run_dir') or str(state_path.parent.parent)
    sample = inputs.get('sample_name') or run_id
    stage = _stage_from_state(status, current_step, next_step)
    tone = _run_tone(status, progress)
    execution = state.get('execution') or {}
    error = execution.get('error') or (f'returncode={execution.get("returncode")}' if status == 'failed' else None)
    report = state.get('report')
    report_telemetry = (
        Path(str(report.get('telemetry') or state_path.parent / 'telemetry.json')).resolve()
        if isinstance(report, dict)
        else None
    )

    task = AnalysisRunTask(
        id=run_id,
        sample=sample,
        stage=stage,
        progress=max(0, min(progress, 100)),
        tone=tone,
    )

    return AnalysisRunStatusResponse(
        run_id=run_id,
        run_dir=run_dir,
        status=status,
        current_rule=current_rule,
        completed_steps=completed,
        total_steps=total,
        progress=task.progress,
        updated_at=int(state_path.stat().st_mtime),
        error=error if status in {'failed', 'blocked'} else None,
        report_available=bool(
            state.get('version') == 3
            and status in {'done', 'blocked'}
            and state.get('workflow_id') == 'analysis_pipeline'
            and isinstance(report, dict)
            and report.get('status') == 'ready'
            and report.get('available') is True
            and report.get('schema_version') == 4
            and report_telemetry is not None
            and _is_under_root(report_telemetry)
            and state_path.parent.parent in report_telemetry.parents
            and report_telemetry.is_file()
        ),
        internal_report_available=(
            bool(
                state.get('version') == 3
                and status in {'done', 'failed', 'blocked'}
                and isinstance(state.get('technical_report'), dict)
                and state['technical_report'].get('available') is True
                and state['technical_report'].get('telemetry_version') == 3
            )
            if include_internal_report
            else None
        ),
        routing=state.get('routing') if isinstance(state.get('routing'), dict) else None,
        tasks=[task],
    )


def _has_children(path: Path) -> bool:
    try:
        next(path.iterdir())
        return True
    except (StopIteration, OSError):
        return False


def _entry_from_path(path: Path, relative: str) -> AnalysisFileEntry | None:
    try:
        resolved = path.resolve()
        if not _is_under_root(resolved):
            return None

        stat = path.stat()
        is_dir = path.is_dir()

        return AnalysisFileEntry(
            name=path.name,
            type='directory' if is_dir else 'file',
            path=_display_path(relative),
            abs_path=str(resolved),
            size=None if is_dir else stat.st_size,
            modified=int(stat.st_mtime),
            has_children=_has_children(path) if is_dir else False,
        )
    except OSError:
        return None


@router.get('/files', response_model=AnalysisFilesResponse)
async def list_analysis_files(
    path: str = Query(default='/'),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(get_verified_user),
):
    target, relative = _resolve_path(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail='Path not found')
    if not target.is_dir():
        raise HTTPException(status_code=400, detail='Path is not a directory')

    try:
        children = sorted(
            target.iterdir(),
            key=lambda child: (not child.is_dir(), child.name.lower()),
        )
    except OSError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    page = children[cursor : cursor + limit]
    entries = []
    for child in page:
        child_relative = '/'.join(part for part in (relative, child.name) if part)
        entry = _entry_from_path(child, child_relative)
        if entry:
            entries.append(entry)

    next_cursor = cursor + limit if cursor + limit < len(children) else None

    testdata = _testdata_root()
    if testdata is not None and relative == '' and cursor == 0:
        testdata_entry = AnalysisFileEntry(
            name='testdata',
            type='directory',
            path='/testdata',
            abs_path=str(testdata),
            size=None,
            modified=int(testdata.stat().st_mtime) if testdata.exists() else None,
            has_children=True,
        )
        entries = [testdata_entry, *entries]

    return AnalysisFilesResponse(
        root=str(ANALYSIS_FILE_ROOT),
        path=_display_path(relative),
        abs_path=str(target),
        entries=entries,
        next_cursor=next_cursor,
    )


@router.get('/datasets/catalog')
async def get_analysis_dataset_catalog(user=Depends(get_verified_user)):
    return {
        'check_version': 'fastq-v1',
        'artifacts': [{'type': artifact_type, **contract} for artifact_type, contract in ARTIFACT_CATALOG.items()],
    }


@router.get('/health')
async def get_analysis_health(user=Depends(get_verified_user)):
    return await analysis_health()


@router.post('/datasets')
async def create_analysis_dataset(
    form: AnalysisDatasetCreateRequest,
    user=Depends(get_verified_user),
):
    dataset_id = new_dataset_id()
    try:
        sources, artifacts, dataset_status, checks, issues = build_initial_revision(
            form.paths,
            ANALYSIS_FILE_ROOT,
        )
    except DatasetInputError as error:
        raise_analysis_error(400, 'DATASET_INPUT_INVALID', str(error), field='paths')
    value = revision_model(
        dataset_id,
        1,
        sources,
        artifacts,
        dataset_status,
        checks,
        issues,
    )
    await AnalysisDatasets.create(dataset_id, user.id, value)
    await AnalysisEvents.record(
        user_id=user.id,
        dataset_id=dataset_id,
        kind='dataset_created',
        payload={'revision': 1, 'status': dataset_status, 'issue_codes': [item['code'] for item in issues]},
    )
    if dataset_status == 'checking':
        dataset_preflight_queue.enqueue(dataset_id, 1)
    return serialize_revision(value)


@router.get('/datasets/{dataset_id}')
async def get_analysis_dataset(
    dataset_id: str,
    revision: int | None = Query(default=None, ge=1),
    user=Depends(get_verified_user),
):
    value = await AnalysisDatasets.get(dataset_id, user.id, revision)
    if value is None:
        raise_analysis_error(404, 'DATASET_NOT_FOUND', 'Analysis dataset not found')
    return serialize_revision(value)


@router.patch('/datasets/{dataset_id}')
async def revise_analysis_dataset(
    dataset_id: str,
    form: AnalysisDatasetPatchRequest,
    user=Depends(get_verified_user),
):
    current = await AnalysisDatasets.get(dataset_id, user.id, form.base_revision)
    latest = await AnalysisDatasets.get(dataset_id, user.id)
    if current is None or latest is None:
        raise_analysis_error(404, 'DATASET_NOT_FOUND', 'Analysis dataset not found')
    if latest.revision != form.base_revision:
        raise_analysis_error(409, 'DATASET_REVISION_CONFLICT', 'Analysis dataset revision conflict')
    try:
        sources, artifacts, dataset_status, checks, issues = build_manual_revision(
            form.artifacts,
            current.sources,
            ANALYSIS_FILE_ROOT,
        )
    except DatasetInputError as error:
        raise_analysis_error(400, 'DATASET_PATCH_INVALID', str(error), field='artifacts')
    value = revision_model(
        dataset_id,
        form.base_revision + 1,
        sources,
        artifacts,
        dataset_status,
        checks,
        issues,
    )
    if not await AnalysisDatasets.revise(
        dataset_id,
        user.id,
        form.base_revision,
        value,
    ):
        raise_analysis_error(409, 'DATASET_REVISION_CONFLICT', 'Analysis dataset revision conflict')
    await AnalysisEvents.record(
        user_id=user.id,
        dataset_id=dataset_id,
        kind='dataset_revised',
        payload={
            'base_revision': form.base_revision,
            'revision': value.revision,
            'status': dataset_status,
        },
    )
    if dataset_status == 'checking':
        dataset_preflight_queue.enqueue(dataset_id, value.revision)
    return serialize_revision(value)


def _serialize_plan(value: AnalysisPlanRevisionModel, execution: Any = None) -> dict[str, Any]:
    payload = value.payload
    run = {'run_id': execution.run_id} if execution else None
    return {
        'type': 'analysis_plan',
        'id': value.plan_id,
        'revision': value.revision,
        'status': 'completed',
        'title': payload.get('title') or '分析方案',
        'summary': payload.get('summary') or '',
        'ready_to_execute': payload.get('ready_to_execute') is True and execution is None,
        'dataset': {
            'id': value.dataset_id,
            'revision': value.dataset_revision,
            'status': (payload.get('dataset') or {}).get('status'),
        },
        'goals': value.goals,
        'options': value.options,
        'routing': payload.get('routing'),
        'steps': payload.get('steps') or [],
        'resource_estimate': payload.get('resource_estimate'),
        'blocking_reason': payload.get('blocking_reason'),
        'planner_version': value.planner_version,
        'created_at': value.created_at,
        **(
            {
                'execution': {
                    'status': execution.status,
                    'run_id': execution.run_id,
                    'run': run,
                    'error': execution.error,
                    'confirmed_at': execution.confirmed_at,
                },
                **({'run': run} if run else {}),
            }
            if execution
            else {}
        ),
    }


def _serialize_proposal(value: Any) -> dict[str, Any]:
    return {
        'id': value.id,
        'plan_id': value.plan_id,
        'chat_id': value.chat_id,
        'base_plan_revision': value.base_plan_revision,
        'status': value.status,
        'patch': value.patch,
        'citations': value.citations,
        'model': value.model,
        'message_id': value.message_id,
        'created_at': value.created_at,
        'decided_at': value.decided_at,
    }


async def _refresh_terminal_execution(value: tuple[Any, Any] | None):
    if value is None or value[1] is None or not isinstance(value[1].run, dict):
        return value
    state_path = _run_state_path({'run': value[1].run})
    if state_path is None or not state_path.is_file():
        return value
    state = _read_json(state_path)
    state_status = _status_from_state(state)
    stored_status = (
        'failed'
        if state_status in {'failed', 'blocked'}
        else 'completed'
        if state_status == 'done'
        else value[1].status
    )
    if stored_status == value[1].status:
        return value
    execution = await AnalysisPlans.update_execution(
        value[0].plan_id,
        value[0].revision,
        status=stored_status,
        run=value[1].run,
        error=(
            value[1].error
            if stored_status != 'failed'
            else (state.get('execution') or {}).get('error') or 'Analysis runner failed'
        ),
    )
    return (value[0], execution or value[1])


async def _analysis_chat(chat_id: str, user_id: str):
    chat = await Chats.get_chat_by_id_and_user_id(chat_id, user_id)
    if chat is None or (chat.meta or {}).get('source') not in {'analysis', 'benchmark'}:
        raise_analysis_error(404, 'ANALYSIS_CHAT_NOT_FOUND', 'Analysis chat not found')
    return chat


async def _compile_requested_plan(form: AnalysisPlanCreateRequest, user_id: str):
    dataset = await AnalysisDatasets.get(form.dataset.id, user_id, form.dataset.revision)
    if dataset is None:
        raise_analysis_error(404, 'DATASET_NOT_FOUND', 'Analysis dataset not found')
    if not revision_fingerprints_match(dataset):
        await AnalysisDatasets.update_checks(
            dataset.dataset_id,
            dataset.revision,
            status='stale',
            checks={**dataset.checks, 'fingerprint': {'status': 'failed'}},
            issues=[*dataset.issues, {'code': 'FINGERPRINT_CHANGED', 'message': '文件在预检后发生变化。'}],
        )
        raise_analysis_error(409, 'DATASET_STALE', 'Analysis dataset is stale')
    if dataset.status not in {'checking', 'ready'}:
        raise_analysis_error(
            409,
            'DATASET_NOT_PLANNABLE',
            'Analysis dataset cannot be planned',
            context={'status': dataset.status},
        )
    dataset_context = dataset_provider_context(dataset)
    try:
        payload = await compile_analysis_plan(
            dataset=dataset_context,
            goals=list(form.goals),
            options=form.options.model_dump(),
            routing=form.routing.model_dump(exclude_none=True),
        )
    except AnalysisPlannerError as error:
        raise_analysis_error(
            502 if error.retryable else 422,
            'PLANNER_UNAVAILABLE' if error.retryable else 'PLAN_INPUT_INVALID',
            str(error),
            retryable=error.retryable,
        )
    return dataset, dataset_context, payload


async def _resolve_plan_chat(form: AnalysisPlanCreateRequest, user: Any, payload: dict[str, Any]):
    if form.chat_id:
        chat = await _analysis_chat(form.chat_id, user.id)
        chat_id = chat.id
    else:
        if form.base_plan_revision is not None:
            raise_analysis_error(409, 'PLAN_BASE_UNEXPECTED', 'First plan cannot have a base revision')
        chat_id = str(uuid.uuid4())
        chat = await Chats.insert_new_chat(
            chat_id,
            user.id,
            ChatForm(
                chat={
                    'title': payload.get('title') or '分析方案',
                    'models': ['BioAgent'],
                    'history': {'currentId': None, 'messages': {}},
                    'messages': [],
                },
                meta={'source': 'analysis'},
            ),
        )
        if chat is None:
            raise_analysis_error(500, 'ANALYSIS_CHAT_CREATE_FAILED', 'Analysis chat could not be created')
    current = await _refresh_terminal_execution(await AnalysisPlans.latest(chat_id, user.id))
    if (current and form.base_plan_revision != current[0].revision) or (
        not current and form.base_plan_revision is not None
    ):
        raise_analysis_error(409, 'PLAN_REVISION_CONFLICT', 'Analysis plan revision conflict')
    return chat, chat_id, current


@router.post('/plans')
async def create_analysis_plan(
    form: AnalysisPlanCreateRequest,
    user=Depends(get_verified_user),
):
    dataset, dataset_context, payload = await _compile_requested_plan(form, user.id)
    chat, chat_id, current = await _resolve_plan_chat(form, user, payload)
    plan_id = current[0].plan_id if current else f'pl_{uuid.uuid4().hex}'
    revision = current[0].revision + 1 if current else 1
    hash_payload = {
        'dataset': dataset_context,
        'goals': payload.get('goals'),
        'options': payload.get('options'),
        'routing': payload.get('routing'),
    }
    input_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    value = AnalysisPlanRevisionModel(
        plan_id=plan_id,
        revision=revision,
        dataset_id=dataset.dataset_id,
        dataset_revision=dataset.revision,
        goals=payload['goals'],
        options=payload['options'],
        routing=payload['routing'],
        payload=payload,
        input_hash=input_hash,
        planner_version=int(payload.get('planner_version') or 1),
        created_at=int(time.time()),
    )
    saved = await AnalysisPlans.save(
        plan_id=plan_id,
        chat_id=chat_id,
        user_id=user.id,
        base_revision=form.base_plan_revision,
        value=value,
    )
    if saved is None:
        raise_analysis_error(409, 'PLAN_REVISION_CONFLICT', 'Analysis plan revision conflict')

    generated_title = payload.get('title') or '分析方案'
    authoritative_routing = {'mode': payload['routing']['requested_mode']}
    old_generated_title = (chat.meta or {}).get('analysis_generated_title')
    update_title = not current or chat.title == old_generated_title
    updated_chat = {**chat.chat, **({'title': generated_title} if update_title else {})}
    await Chats.update_chat_by_id(
        chat_id,
        updated_chat,
        meta={
            'source': (chat.meta or {}).get('source') or 'analysis',
            'analysis_dataset': form.dataset.model_dump(),
            'analysis_goals': payload['goals'],
            'analysis_options': payload['options'],
            'analysis_routing': authoritative_routing,
            'analysis_plan_summary': {
                'title': payload.get('title'),
                'summary': payload.get('summary'),
                'goals': payload['goals'],
                'options': payload['options'],
                'routing': payload['routing'],
                'steps': payload.get('steps') or [],
                'resource_estimate': payload.get('resource_estimate'),
                'ready_to_execute': payload.get('ready_to_execute') is True,
            },
            'analysis_generated_title': generated_title,
        },
    )
    deterministic_tags = [
        *payload['goals'],
        *sorted({artifact['type'] for artifact in dataset.artifacts if isinstance(artifact, dict)}),
        f'mode-{authoritative_routing["mode"]}',
    ]
    await Chats.update_chat_tags_by_id(chat_id, deterministic_tags, user)
    if current:
        await AnalysisEvents.record(
            user_id=user.id,
            chat_id=chat_id,
            dataset_id=dataset.dataset_id,
            plan_id=plan_id,
            kind='analysis_controls_changed',
            payload={
                'from_revision': current[0].revision,
                'to_revision': saved[0].revision,
                'goals': payload['goals'],
                'options': payload['options'],
                'routing': authoritative_routing,
            },
        )
    await AnalysisEvents.record(
        user_id=user.id,
        chat_id=chat_id,
        dataset_id=dataset.dataset_id,
        plan_id=plan_id,
        kind='plan_compiled',
        payload={
            'revision': saved[0].revision,
            'dataset_revision': dataset.revision,
            'ready_to_execute': payload.get('ready_to_execute') is True,
            'planner_version': value.planner_version,
        },
    )
    return {'chat_id': chat_id, 'plan': _serialize_plan(*saved)}


@router.get('/plans/{chat_id}/latest')
async def get_latest_analysis_plan(chat_id: str, user=Depends(get_verified_user)):
    await _analysis_chat(chat_id, user.id)
    value = await AnalysisPlans.latest(chat_id, user.id)
    if value is None:
        raise_analysis_error(404, 'PLAN_NOT_FOUND', 'Analysis plan not found')
    return {'chat_id': chat_id, 'plan': _serialize_plan(*value)}


@router.get('/plans/{chat_id}/proposals/pending')
async def get_pending_analysis_proposal(chat_id: str, user=Depends(get_verified_user)):
    await _analysis_chat(chat_id, user.id)
    value = await AnalysisPlans.pending_proposal(chat_id, user.id)
    return {'proposal': _serialize_proposal(value) if value else None}


@router.post('/plans/{chat_id}/proposals')
async def register_analysis_proposal(
    chat_id: str,
    form: AnalysisProposalCreateRequest,
    user=Depends(get_verified_user),
):
    await _analysis_chat(chat_id, user.id)
    if form.proposal_id:
        existing = await AnalysisPlans.get_proposal(form.proposal_id, user.id)
        if existing:
            if existing.chat_id != chat_id:
                raise_analysis_error(409, 'PROPOSAL_ID_CONFLICT', 'Analysis proposal ID conflict')
            return {'proposal': _serialize_proposal(existing)}
    current = await AnalysisPlans.latest(chat_id, user.id)
    if current is None:
        raise_analysis_error(409, 'PLAN_REQUIRED', 'Create a deterministic plan before proposing changes')
    if current[0].revision != form.base_plan_revision:
        raise_analysis_error(409, 'PLAN_REVISION_CONFLICT', 'Analysis plan revision conflict')
    patch = form.patch.model_dump(exclude_none=True)
    if patch.get('goals', current[0].goals) == current[0].goals and patch.get(
        'viral_type', current[0].options.get('viral_type')
    ) == current[0].options.get('viral_type'):
        raise_analysis_error(422, 'PATCH_NO_CHANGE', 'The proposed patch does not change the plan')
    value = await AnalysisPlans.register_proposal(
        proposal_id=form.proposal_id or f'pp_{uuid.uuid4().hex}',
        chat_id=chat_id,
        user_id=user.id,
        base_plan_revision=form.base_plan_revision,
        patch=patch,
        citations=form.citations,
        model=form.model,
        message_id=form.message_id,
    )
    if value is None:
        raise_analysis_error(409, 'PLAN_REVISION_CONFLICT', 'Analysis plan revision conflict')
    await AnalysisEvents.record(
        user_id=user.id,
        chat_id=chat_id,
        plan_id=value.plan_id,
        proposal_id=value.id,
        kind='plan_patch_proposed',
        payload={'base_plan_revision': value.base_plan_revision, 'patch': value.patch},
    )
    return {'proposal': _serialize_proposal(value)}


@router.post('/proposals/{proposal_id}/reject')
async def reject_analysis_proposal(proposal_id: str, user=Depends(get_verified_user)):
    value = await AnalysisPlans.decide_proposal(proposal_id, user.id, 'rejected')
    if value is None:
        raise_analysis_error(409, 'PROPOSAL_NOT_PENDING', 'Analysis proposal is not pending')
    await AnalysisEvents.record(
        user_id=user.id,
        chat_id=value.chat_id,
        plan_id=value.plan_id,
        proposal_id=value.id,
        kind='plan_patch_rejected',
        payload={'base_plan_revision': value.base_plan_revision, 'patch': value.patch},
    )
    return {'proposal': _serialize_proposal(value)}


@router.post('/proposals/{proposal_id}/accept')
async def accept_analysis_proposal(proposal_id: str, user=Depends(get_verified_user)):
    proposal = await AnalysisPlans.get_proposal(proposal_id, user.id)
    if proposal is None or proposal.status != 'pending':
        raise_analysis_error(409, 'PROPOSAL_NOT_PENDING', 'Analysis proposal is not pending')
    found = await AnalysisPlans.get(
        proposal.plan_id,
        proposal.base_plan_revision,
        user.id,
    )
    if found is None or found[2] != proposal.base_plan_revision:
        raise_analysis_error(409, 'PROPOSAL_STALE', 'Analysis proposal is based on an old plan revision')
    plan = found[0]
    patch = proposal.patch
    response = await create_analysis_plan(
        AnalysisPlanCreateRequest(
            chat_id=proposal.chat_id,
            dataset=DatasetReference(id=plan.dataset_id, revision=plan.dataset_revision),
            goals=patch.get('goals', plan.goals),
            options=AnalysisPlanOptions(viral_type=patch.get('viral_type', plan.options.get('viral_type', 'RNA+DNA'))),
            routing=AnalysisPlanRoutingRequest(
                mode=plan.routing.get('requested_mode', 'auto'),
            ),
            base_plan_revision=proposal.base_plan_revision,
        ),
        user=user,
    )
    decided = await AnalysisPlans.decide_proposal(proposal_id, user.id, 'accepted')
    if decided is None:
        raise_analysis_error(409, 'PROPOSAL_DECISION_CONFLICT', 'Analysis proposal changed while accepting')
    await AnalysisEvents.record(
        user_id=user.id,
        chat_id=proposal.chat_id,
        plan_id=proposal.plan_id,
        proposal_id=proposal.id,
        kind='plan_patch_accepted',
        payload={
            'base_plan_revision': proposal.base_plan_revision,
            'new_plan_revision': response['plan']['revision'],
            'patch': proposal.patch,
        },
    )
    return {**response, 'proposal': _serialize_proposal(decided)}


async def _reject_execution_admission(
    *,
    user_id: str,
    chat_id: str,
    plan_id: str,
    code: str,
    message: str,
    revision: int,
    status_code: int = 409,
    dataset_id: str | None = None,
    proposal_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    await AnalysisEvents.record(
        user_id=user_id,
        chat_id=chat_id,
        dataset_id=dataset_id,
        plan_id=plan_id,
        proposal_id=proposal_id,
        kind='execution_admission_rejected',
        payload={'code': code, 'revision': revision, **(context or {})},
    )
    raise_analysis_error(status_code, code, message, context=context)


async def _execution_dataset(value: AnalysisPlanRevisionModel, user_id: str, chat_id: str, revision: int):
    dataset = await AnalysisDatasets.get(value.dataset_id, user_id, value.dataset_revision)
    if dataset is None:
        await _reject_execution_admission(
            user_id=user_id,
            chat_id=chat_id,
            plan_id=value.plan_id,
            code='DATASET_NOT_FOUND',
            message='Analysis dataset not found',
            revision=revision,
            status_code=404,
            dataset_id=value.dataset_id,
        )
    if dataset.status != 'ready' or not revision_fingerprints_match(dataset):
        if dataset.status == 'ready':
            await AnalysisDatasets.update_checks(
                dataset.dataset_id,
                dataset.revision,
                status='stale',
                checks={**dataset.checks, 'fingerprint': {'status': 'failed'}},
                issues=[*dataset.issues, {'code': 'FINGERPRINT_CHANGED', 'message': '文件在预检后发生变化。'}],
            )
        await _reject_execution_admission(
            user_id=user_id,
            chat_id=chat_id,
            plan_id=value.plan_id,
            code='DATASET_NOT_READY',
            message='Analysis dataset is not ready',
            revision=revision,
            dataset_id=value.dataset_id,
            context={'status': dataset.status},
        )
    if value.payload.get('ready_to_execute') is not True:
        await _reject_execution_admission(
            user_id=user_id,
            chat_id=chat_id,
            plan_id=value.plan_id,
            code='PLAN_NOT_EXECUTABLE',
            message='Analysis plan is not executable',
            revision=revision,
            dataset_id=value.dataset_id,
        )
    return dataset


@router.post('/plans/{plan_id}/revisions/{revision}/execute')
async def execute_analysis_plan(
    plan_id: str,
    revision: int,
    user=Depends(get_verified_user),
):
    found = await AnalysisPlans.get(plan_id, revision, user.id)
    if found is None:
        raise_analysis_error(404, 'PLAN_NOT_FOUND', 'Analysis plan not found')
    value, existing, latest_revision, chat_id = found
    if revision != latest_revision:
        await _reject_execution_admission(
            user_id=user.id,
            chat_id=chat_id,
            plan_id=plan_id,
            code='PLAN_NOT_LATEST',
            message='Only the latest analysis plan can be executed',
            revision=revision,
            context={'latest_revision': latest_revision},
        )
    routing = value.routing if isinstance(value.routing, dict) else {}
    if routing.get('requested_mode') not in {'auto', 'standard', 'emergency'} or 'deadline_seconds' in routing:
        await _reject_execution_admission(
            user_id=user.id,
            chat_id=chat_id,
            plan_id=plan_id,
            code='PLAN_ROUTING_OBSOLETE',
            message='Recompile this historical plan with the current routing contract',
            revision=revision,
        )
    pending = await AnalysisPlans.pending_proposal(chat_id, user.id)
    if pending is not None:
        await _reject_execution_admission(
            user_id=user.id,
            chat_id=chat_id,
            plan_id=plan_id,
            proposal_id=pending.id,
            code='PATCH_PENDING',
            message='Resolve the pending plan patch before execution',
            revision=revision,
        )
    if existing and existing.status in {'running', 'starting'} and existing.run:
        return {'chat_id': chat_id, 'plan': _serialize_plan(value, existing)}
    if existing and existing.status == 'failed':
        await _reject_execution_admission(
            user_id=user.id,
            chat_id=chat_id,
            plan_id=plan_id,
            code='EXECUTION_PREVIOUSLY_FAILED',
            message='Failed plan execution requires a new plan revision',
            revision=revision,
        )

    dataset = await _execution_dataset(value, user.id, chat_id, revision)

    run_id = existing.run_id if existing else f'analysis-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:8]}'
    reservation = existing or await AnalysisPlans.reserve(
        plan_id=plan_id,
        revision=revision,
        user_id=user.id,
        run_id=run_id,
    )
    if reservation is None:
        await _reject_execution_admission(
            user_id=user.id,
            chat_id=chat_id,
            plan_id=plan_id,
            code='PLAN_REVISION_CONFLICT',
            message='Analysis plan is no longer current',
            revision=revision,
            dataset_id=value.dataset_id,
        )
    await AnalysisEvents.record(
        user_id=user.id,
        chat_id=chat_id,
        dataset_id=value.dataset_id,
        plan_id=plan_id,
        kind='execution_confirmed',
        payload={'plan_revision': revision, 'run_id': reservation.run_id},
    )
    events = await AnalysisEvents.for_scope(
        chat_id=chat_id,
        user_id=user.id,
        dataset_id=value.dataset_id,
        plan_id=plan_id,
    )
    plan_for_run = {
        **value.payload,
        'decision_trace': [
            *(value.payload.get('decision_trace') or []),
            *[{'kind': event.kind, 'timestamp': event.created_at, **event.payload} for event in events],
        ],
    }
    try:
        result = await start_analysis_run(
            plan=plan_for_run,
            dataset=dataset_provider_context(dataset),
            chat_id=chat_id,
            plan_id=plan_id,
            plan_revision=revision,
            run_id=reservation.run_id,
        )
    except AnalysisPlannerError as error:
        if not error.retryable:
            await AnalysisPlans.update_execution(
                plan_id,
                revision,
                status='failed',
                error=str(error),
            )
        await AnalysisEvents.record(
            user_id=user.id,
            chat_id=chat_id,
            dataset_id=value.dataset_id,
            plan_id=plan_id,
            kind='execution_admission_rejected',
            payload={
                'code': 'RUNNER_UNAVAILABLE' if error.retryable else 'RUNNER_ADMISSION_FAILED',
                'revision': revision,
            },
        )
        raise_analysis_error(
            502 if error.retryable else 409,
            'RUNNER_UNAVAILABLE' if error.retryable else 'RUNNER_ADMISSION_FAILED',
            str(error),
            retryable=error.retryable,
        )
    execution = await AnalysisPlans.update_execution(
        plan_id,
        revision,
        status=str(result.get('status') or 'running'),
        run=result.get('run') if isinstance(result.get('run'), dict) else None,
    )
    await AnalysisEvents.record(
        user_id=user.id,
        chat_id=chat_id,
        dataset_id=value.dataset_id,
        plan_id=plan_id,
        kind='execution_started',
        payload={'plan_revision': revision, 'run_id': reservation.run_id},
    )
    return {'chat_id': chat_id, 'plan': _serialize_plan(value, execution)}


def _benchmark_urls(benchmark_run_id: str) -> dict[str, str]:
    base = f'/api/v1/analysis/benchmark/runs/{benchmark_run_id}'
    return {'status': base, 'result': f'{base}/result'}


def _raw_message_id(chat_id: str, message: Any) -> str:
    return str(message.id).removeprefix(f'{chat_id}-')


def _serialize_benchmark_message(chat_id: str, message: Any) -> dict[str, Any]:
    return {
        'id': _raw_message_id(chat_id, message),
        'role': message.role,
        'parent_id': message.parent_id,
        'content': message.content,
        'output': message.output,
        'files': message.files,
        'done': message.done,
        'error': message.error,
        'usage': message.usage,
        'model': message.model_id,
        'created_at': message.created_at,
        'updated_at': message.updated_at,
    }


def _conversation_action_metrics(messages: list[Any]) -> dict[str, Any]:
    traces = [
        item
        for message in messages
        for item in (message.output or [])
        if isinstance(item, dict) and item.get('type') == 'conversation_action_trace'
    ]
    valid = sum(item.get('schema_valid') is True for item in traces)
    invalid = len(traces) - valid
    forbidden = sum(str(item.get('error_code', '')).endswith('_FORBIDDEN') for item in traces)
    latencies = [item['latency_ms'] for item in traces if isinstance(item.get('latency_ms'), (int, float))]
    total = valid + invalid
    return {
        'model_calls': sum(int(item.get('model_calls') or 0) for item in traces),
        'schema_valid_actions': valid,
        'schema_invalid_actions': invalid,
        'schema_valid_rate': valid / total if total else None,
        'forbidden_patch_rejections': forbidden,
        'privilege_rejection_rate': forbidden / len(traces) if traces else None,
        'model_latency_ms': {
            'count': len(latencies),
            'average': sum(latencies) / len(latencies) if latencies else None,
            'maximum': max(latencies) if latencies else None,
        },
    }


def _run_state_path(item: dict[str, Any] | None) -> Path | None:
    run = item.get('run') if isinstance(item, dict) else None
    value = run.get('state_path') if isinstance(run, dict) else None
    if not isinstance(value, str):
        return None
    path = Path(value).resolve()
    if not _is_under_root(path) or path.name != 'state.json' or path.parent.name != '.bioagent':
        return None
    return path


def _benchmark_error(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        content = value.get('content') or value.get('message') or value.get('detail')
        return content if isinstance(content, str) else json.dumps(value, ensure_ascii=False)
    return str(value) if value is not None else None


async def _benchmark_status(
    request: Request,
    benchmark_run_id: str,
    user: Any,
) -> tuple[dict[str, Any], Any]:
    chat = await Chats.get_chat_by_id_and_user_id(benchmark_run_id, user.id)
    if not chat or (chat.meta or {}).get('source') != 'benchmark':
        raise HTTPException(status_code=404, detail='Benchmark run not found')
    stored = await AnalysisPlans.latest(benchmark_run_id, user.id)
    if stored is None:
        raise HTTPException(status_code=409, detail='Benchmark plan is unavailable')
    plan_value, execution = stored
    plan = _serialize_plan(plan_value, execution)
    run_item = {'run': execution.run} if execution and execution.run else None
    state_path = _run_state_path(run_item)
    run_status = None
    if state_path and state_path.is_file():
        run_status = _status_response_from_state(
            state_path,
            include_internal_report=True,
        )

    if run_status:
        benchmark_status = {
            'done': 'completed',
            'blocked': 'blocked',
            'failed': 'failed',
            'running': 'running',
            'planned': 'starting',
            'idle': 'starting',
        }.get(run_status.status, run_status.status)
        error = run_status.error
    elif execution and execution.status == 'failed':
        benchmark_status = 'failed'
        error = execution.error
    elif plan.get('ready_to_execute') is not True and execution is None:
        benchmark_status = 'blocked'
        error = _benchmark_error(plan.get('blocking_reason'))
    elif execution:
        benchmark_status = 'starting'
        error = None
    else:
        benchmark_status = 'planning'
        error = None

    benchmark_meta = (chat.meta or {}).get('benchmark') or {}
    urls = _benchmark_urls(benchmark_run_id)
    result = {
        'schema_version': BENCHMARK_SCHEMA_VERSION,
        'benchmark_run_id': benchmark_run_id,
        'case_id': benchmark_meta.get('case_id'),
        'chat_id': benchmark_run_id,
        'status': benchmark_status,
        'created_at': chat.created_at,
        'updated_at': chat.updated_at,
        'run_id': run_status.run_id if run_status else None,
        'run_dir': run_status.run_dir if run_status else None,
        'progress': run_status.progress if run_status else 0,
        'completed_steps': run_status.completed_steps if run_status else 0,
        'total_steps': run_status.total_steps if run_status else 0,
        'error': error,
        'report_available': run_status.report_available if run_status else False,
        'internal_report_available': (run_status.internal_report_available if run_status else False),
        'status_url': urls['status'],
        'result_url': urls['result'],
    }
    messages = await ChatMessages.get_messages_by_chat_id(benchmark_run_id)
    return result, SimpleNamespace(
        chat=chat,
        messages=messages,
        plan=plan,
        decision_trace=plan_value.payload.get('decision_trace') or [],
        run_item=run_item,
    )


@router.post(
    '/benchmark/runs',
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_benchmark_run(
    request: Request,
    form_data: BenchmarkRunRequest,
    user=Depends(get_verified_user),
):
    dataset = await AnalysisDatasets.get(
        form_data.dataset.id,
        user.id,
        form_data.dataset.revision,
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail='Analysis dataset not found')
    if dataset.status != 'ready':
        raise HTTPException(status_code=409, detail='Analysis dataset is not ready')

    chat_id = str(uuid.uuid4())
    chat = await Chats.insert_new_chat(
        chat_id,
        user.id,
        ChatForm(
            chat={
                'title': '结构化分析 benchmark',
                'models': [],
                'history': {'currentId': None, 'messages': {}},
                'messages': [],
            },
            meta={
                'source': 'benchmark',
                'benchmark': {
                    'schema_version': BENCHMARK_SCHEMA_VERSION,
                    'case_id': form_data.case_id,
                    'request': form_data.model_dump(),
                    'model_calls': 0,
                },
            },
        ),
    )
    if chat is None:
        raise HTTPException(status_code=500, detail='Benchmark chat could not be created')
    planned = await create_analysis_plan(
        AnalysisPlanCreateRequest(
            chat_id=chat_id,
            dataset=form_data.dataset,
            goals=form_data.goals,
            options=form_data.options,
            routing=form_data.routing,
        ),
        user=user,
    )
    await execute_analysis_plan(
        planned['plan']['id'],
        planned['plan']['revision'],
        user=user,
    )
    urls = _benchmark_urls(chat_id)
    return {
        'schema_version': BENCHMARK_SCHEMA_VERSION,
        'benchmark_run_id': chat_id,
        'chat_id': chat_id,
        'case_id': form_data.case_id,
        'status': 'starting',
        'status_url': urls['status'],
        'result_url': urls['result'],
    }


@router.get('/benchmark/runs/{benchmark_run_id}')
async def get_benchmark_run_status(
    benchmark_run_id: str,
    request: Request,
    user=Depends(get_verified_user),
):
    result, _context = await _benchmark_status(request, benchmark_run_id, user)
    return result


@router.get('/benchmark/runs/{benchmark_run_id}/result')
async def get_benchmark_run_result(
    benchmark_run_id: str,
    request: Request,
    user=Depends(get_verified_user),
):
    benchmark_status, context = await _benchmark_status(request, benchmark_run_id, user)
    if benchmark_status['status'] not in {'completed', 'blocked', 'failed'}:
        raise HTTPException(status_code=409, detail='Benchmark run has not reached a terminal state')

    state_path = _run_state_path(context.run_item)
    state_data = _read_json(state_path) if state_path and state_path.is_file() else None
    run_dir = state_path.parent.parent if state_path else None
    telemetry = None
    agent_trace: list[dict[str, Any]] = []
    if state_data and run_dir:
        technical = state_data.get('technical_report') or {}
        telemetry_path = Path(technical.get('telemetry') or run_dir / '.bioagent' / 'telemetry.json')
        telemetry = _read_optional_json(telemetry_path, run_dir)
        trace_path = Path(technical.get('agent_trace') or run_dir / '.bioagent' / 'agent-trace.jsonl')
        agent_trace = _read_agent_trace(trace_path, run_dir)

    report = state_data.get('report') if state_data else None
    diagnostic_available = bool(
        isinstance(report, dict)
        and report.get('available') is True
        and isinstance(telemetry, dict)
        and isinstance(telemetry.get('delivery_report'), dict)
    )
    verification: dict[str, Any] = {'ok': False, 'error': 'Diagnostic report is unavailable'}
    if diagnostic_available and run_dir:
        try:
            verification = {
                'ok': True,
                **verify_report_evidence(telemetry=telemetry, run_dir=run_dir),
            }
        except EvidenceValidationError as error:
            verification = {'ok': False, 'error': str(error)}

    technical = state_data.get('technical_report') if state_data else None
    internal_available = bool(
        isinstance(technical, dict) and technical.get('available') is True and isinstance(telemetry, dict)
    )
    diagnostic_url = None
    internal_url = None
    if run_dir and diagnostic_available and verification.get('ok') is True:
        diagnostic_url = '/api/v1/analysis/runs/report?' + urlencode({'run_dir': str(run_dir)})
    if run_dir and internal_available:
        internal_url = '/api/v1/analysis/runs/internal-report?' + urlencode(
            {'chat_id': benchmark_run_id, 'run_dir': str(run_dir)}
        )

    benchmark_meta = (context.chat.meta or {}).get('benchmark') or {}
    decision_events = await AnalysisEvents.for_scope(
        chat_id=benchmark_run_id,
        user_id=user.id,
        dataset_id=context.plan.get('dataset', {}).get('id') if isinstance(context.plan, dict) else None,
        plan_id=context.plan.get('id') if isinstance(context.plan, dict) else None,
    )
    event_kinds = [event.kind for event in decision_events]
    conversation_metrics = _conversation_action_metrics(context.messages)
    proposed = sum(kind == 'plan_patch_proposed' for kind in event_kinds)
    accepted = sum(kind == 'plan_patch_accepted' for kind in event_kinds)
    delivery = telemetry.get('delivery_report') if isinstance(telemetry, dict) else None
    return {
        'schema_version': BENCHMARK_SCHEMA_VERSION,
        'benchmark_run_id': benchmark_run_id,
        'case_id': benchmark_meta.get('case_id'),
        'chat_id': benchmark_run_id,
        'status': benchmark_status['status'],
        'created_at': context.chat.created_at,
        'updated_at': context.chat.updated_at,
        'request': benchmark_meta.get('request'),
        'model_calls': conversation_metrics['model_calls'],
        'metrics': {
            **conversation_metrics,
            'patches_proposed': proposed,
            'patches_accepted': accepted,
            'patch_acceptance_rate': accepted / proposed if proposed else None,
            'deterministic_decision_events': len(decision_events),
        },
        'conversation': [_serialize_benchmark_message(benchmark_run_id, message) for message in context.messages],
        'analysis': {
            'plan': context.plan,
            'decision_trace': context.decision_trace,
            'decision_events': [event.model_dump(exclude={'user_id'}) for event in decision_events],
            'dataset': (
                (state_data or {}).get('dataset')
                or (context.plan or {}).get('dataset')
                or (context.chat.meta or {}).get('analysis_dataset')
            ),
            'run_id': state_data.get('run_id') if state_data else None,
            'run_dir': state_data.get('run_dir') if state_data else None,
            'execution': state_data.get('execution') if state_data else None,
            'routing': (
                (telemetry or {}).get('routing')
                or (state_data or {}).get('routing')
                or (context.plan or {}).get('routing')
            ),
        },
        'reports': {
            'diagnostic': {
                'available': diagnostic_available,
                'schema_version': delivery.get('schema_version') if isinstance(delivery, dict) else None,
                'kind': delivery.get('kind') if isinstance(delivery, dict) else None,
                'report_kind': delivery.get('report_kind') if isinstance(delivery, dict) else None,
                'validation': verification,
                'data': delivery,
                'html_url': diagnostic_url,
            },
            'internal': {
                'available': internal_available,
                'telemetry_version': telemetry.get('version') if isinstance(telemetry, dict) else None,
                'state': state_data,
                'telemetry': telemetry,
                'agent_trace': agent_trace,
                'html_url': internal_url,
            },
        },
    }


@router.get(
    '/runs/status',
    response_model=AnalysisRunStatusResponse,
    response_model_exclude_none=True,
)
async def get_analysis_run_status(
    run_id: str | None = Query(default=None),
    run_dir: str | None = Query(default=None),
    user=Depends(get_verified_user),
):
    state_path = _resolve_run_state(run_id=run_id, run_dir=run_dir)
    if not state_path:
        return AnalysisRunStatusResponse()

    await _require_run_owner(state_path, user.id)

    return _status_response_from_state(
        state_path,
        include_internal_report=True,
    )


@router.get('/runs/report')
async def download_diagnostic_report(
    run_dir: str = Query(),
    user=Depends(get_verified_user),
):
    resolved_run_dir, state_data, telemetry = _diagnostic_report_state(run_dir)
    await _require_run_owner(resolved_run_dir / '.bioagent' / 'state.json', user.id)
    try:
        document = render_analysis_delivery_report(
            state=state_data,
            telemetry=telemetry,
            run_dir=resolved_run_dir,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail='Diagnostic report data is invalid',
        ) from error
    safe_run_id = re.sub(
        r'[^A-Za-z0-9_.-]',
        '-',
        str(state_data.get('run_id') or resolved_run_dir.name),
    )
    return Response(
        content=document,
        media_type='text/html; charset=utf-8',
        headers={
            'Content-Disposition': (f'attachment; filename="{safe_run_id}-{DIAGNOSTIC_REPORT_FILENAME}"'),
            'X-Content-Type-Options': 'nosniff',
        },
    )


def _internal_report_state(run_dir: str, chat_id: str) -> tuple[Path, dict]:
    requested = Path(run_dir)
    if not requested.is_absolute():
        raise HTTPException(status_code=400, detail='Run directory must be absolute')
    resolved = requested.resolve()
    if not _is_under_root(resolved):
        raise HTTPException(status_code=400, detail='Run directory is outside the analysis file root')

    state_path = (resolved / '.bioagent' / 'state.json').resolve()
    if not _is_under_root(state_path) or not state_path.is_file():
        raise HTTPException(status_code=404, detail='Analysis run state not found')
    state_data = _read_json(state_path)
    if state_data.get('version') != 3:
        raise HTTPException(status_code=404, detail='Internal report is not available for this run')
    state_run_dir = state_data.get('run_dir')
    if not isinstance(state_run_dir, str) or Path(state_run_dir).resolve() != resolved:
        raise HTTPException(status_code=400, detail='Analysis state does not match the run directory')
    if state_data.get('openwebui_chat_id') != chat_id:
        raise HTTPException(status_code=400, detail='Analysis run does not belong to this chat')

    report = state_data.get('technical_report')
    if not isinstance(report, dict) or report.get('available') is not True:
        raise HTTPException(status_code=409, detail='Internal report is not ready')
    if report.get('telemetry_version') != 3:
        raise HTTPException(status_code=404, detail='Internal report telemetry version is unsupported')
    if _status_from_state(state_data) not in {'done', 'failed', 'blocked'}:
        raise HTTPException(status_code=409, detail='Analysis run has not reached a terminal state')
    return resolved, state_data


def _read_optional_json(path: Path, run_dir: Path) -> dict | None:
    resolved = path.resolve()
    if run_dir not in resolved.parents or not resolved.is_file():
        return None
    try:
        value = json.loads(resolved.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_agent_trace(path: Path, run_dir: Path) -> list[dict]:
    resolved = path.resolve()
    if run_dir not in resolved.parents or not resolved.is_file():
        return []
    events = []
    try:
        lines = resolved.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        return []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


@router.get('/runs/internal-report')
async def download_internal_analysis_report(
    chat_id: str = Query(),
    run_dir: str = Query(),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    resolved_run_dir, state_data = _internal_report_state(run_dir, chat_id)
    chat = await Chats.get_chat_by_id_and_user_id(chat_id, user.id, db=db)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Chat not found')

    messages = await ChatMessages.get_messages_by_chat_id(chat_id, db=db)
    report_meta = state_data['technical_report']
    telemetry = _read_optional_json(
        Path(report_meta.get('telemetry') or resolved_run_dir / '.bioagent' / 'telemetry.json'),
        resolved_run_dir,
    )
    if not telemetry or telemetry.get('version') != 3:
        raise HTTPException(status_code=409, detail='Internal report telemetry is unavailable')
    delivery = telemetry.get('delivery_report')
    public_report = state_data.get('report')
    if isinstance(delivery, dict) and isinstance(public_report, dict) and public_report.get('available') is True:
        try:
            verify_report_evidence(telemetry=telemetry, run_dir=resolved_run_dir)
        except EvidenceValidationError as error:
            raise HTTPException(
                status_code=409,
                detail='Internal report evidence validation failed',
            ) from error
    trace = _read_agent_trace(
        Path(report_meta.get('agent_trace') or resolved_run_dir / '.bioagent' / 'agent-trace.jsonl'),
        resolved_run_dir,
    )
    chat_owner_id = getattr(chat, 'user_id', None)
    plan_revisions = await AnalysisPlans.revisions(chat_id, chat_owner_id, db=db) if chat_owner_id else []
    state_dataset = state_data.get('dataset') if isinstance(state_data.get('dataset'), dict) else {}
    state_plan_ref = state_data.get('plan_ref') if isinstance(state_data.get('plan_ref'), dict) else {}
    decision_events = (
        await AnalysisEvents.for_scope(
            chat_id=chat_id,
            user_id=chat_owner_id,
            dataset_id=state_dataset.get('id'),
            plan_id=state_plan_ref.get('id'),
            db=db,
        )
        if chat_owner_id
        else []
    )
    document = render_internal_analysis_report(
        chat=chat,
        messages=messages,
        state=state_data,
        telemetry=telemetry,
        agent_trace=trace,
        plan_revisions=plan_revisions,
        decision_events=decision_events,
    )
    safe_run_id = re.sub(r'[^A-Za-z0-9_.-]', '-', str(state_data.get('run_id') or resolved_run_dir.name))
    return Response(
        content=document,
        media_type='text/html; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{safe_run_id}-internal-technical-report.html"',
            'X-Content-Type-Options': 'nosniff',
        },
    )


class KnowledgeQueryRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSpecialistRequest(BaseModel):
    genome: str = Field(min_length=1, max_length=4000)
    family: str | None = Field(default=None, max_length=200)
    confirm: bool = False


def _knowledge_error(error: KnowledgeProxyError):
    raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.get('/knowledge/health')
async def get_analysis_knowledge_health(user=Depends(get_verified_user)):
    return mcp_health()


@router.post('/knowledge/query')
async def post_analysis_knowledge_query(
    form: KnowledgeQueryRequest,
    user=Depends(get_verified_user),
):
    try:
        return call_query(form.tool, form.arguments)
    except KnowledgeProxyError as error:
        _knowledge_error(error)


@router.post('/knowledge/classify')
async def post_analysis_knowledge_classify(
    form: KnowledgeSpecialistRequest,
    user=Depends(get_verified_user),
):
    try:
        return call_classify(
            {'genome': form.genome, 'family': form.family, 'confirm': form.confirm}
        )
    except KnowledgeProxyError as error:
        _knowledge_error(error)


@router.post('/knowledge/annotate')
async def post_analysis_knowledge_annotate(
    form: KnowledgeSpecialistRequest,
    user=Depends(get_verified_user),
):
    try:
        return call_annotate(
            {'genome': form.genome, 'family': form.family, 'confirm': form.confirm}
        )
    except KnowledgeProxyError as error:
        _knowledge_error(error)

class OpsMemberRequest(BaseModel):
    user: str
    role: str = 'viewer'


class OpsUploadInitRequest(BaseModel):
    project_id: str = 'proj-testdata'
    filename: str
    size: int
    sha256: str | None = None


class OpsJobRequest(BaseModel):
    project_id: str = 'proj-testdata'
    kind: str
    priority: str = 'standard'
    payload: dict[str, Any] | None = None


class OpsReviewRequest(BaseModel):
    project_id: str = 'proj-testdata'
    run_id: str
    decision: str
    reason: str = ''
    findings: list[dict[str, Any]] | None = None


class OpsRulesRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(default_factory=list)


@router.get('/ops/snapshot')
async def ops_snapshot(user=Depends(get_verified_user)):
    data = _OPS.snapshot()
    data['rva_demo'] = rva_job_status(_RVA_DEMO)
    return data


@router.get('/ops/projects')
async def ops_projects(user=Depends(get_verified_user)):
    return {'projects': _OPS.list_projects()}


@router.post('/ops/projects/{project_id}/members')
async def ops_add_member(project_id: str, form: OpsMemberRequest, user=Depends(get_verified_user)):
    try:
        return _OPS.add_member(_ops_user(user), project_id, form.user, form.role)
    except OpsError as error:
        _raise_ops(error)


@router.post('/ops/uploads/init')
async def ops_upload_init(form: OpsUploadInitRequest, user=Depends(get_verified_user)):
    try:
        return _OPS.init_upload(_ops_user(user), form.project_id, form.filename, form.size, form.sha256)
    except OpsError as error:
        _raise_ops(error)


@router.post('/ops/jobs')
async def ops_enqueue(form: OpsJobRequest, user=Depends(get_verified_user)):
    try:
        return _OPS.enqueue(_ops_user(user), form.project_id, form.kind, form.priority, form.payload)
    except OpsError as error:
        _raise_ops(error)


@router.post('/ops/jobs/{job_id}/pause')
async def ops_pause(job_id: str, user=Depends(get_verified_user)):
    try:
        return _OPS.pause(_ops_user(user), job_id)
    except OpsError as error:
        _raise_ops(error)


@router.post('/ops/jobs/{job_id}/recover')
async def ops_recover(job_id: str, user=Depends(get_verified_user)):
    try:
        return _OPS.recover(_ops_user(user), job_id)
    except OpsError as error:
        _raise_ops(error)


@router.post('/ops/rules/evaluate')
async def ops_rules(form: OpsRulesRequest, user=Depends(get_verified_user)):
    return _OPS.evaluate_candidates(form.candidates)


@router.post('/ops/reviews')
async def ops_reviews(form: OpsReviewRequest, user=Depends(get_verified_user)):
    try:
        return _OPS.submit_review(
            _ops_user(user), form.project_id, form.run_id, form.decision, form.reason, form.findings
        )
    except OpsError as error:
        _raise_ops(error)


@router.get('/ops/rva')
async def ops_rva(user=Depends(get_verified_user)):
    return rva_job_status(_RVA_DEMO)


@router.get('/ops/estimates')
async def ops_estimates(user=Depends(get_verified_user)):
    return _OPS.estimates()


@router.post('/ops/uploads/{upload_id}/chunk')
async def ops_upload_chunk(
    upload_id: str,
    index: int = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
):
    payload = await file.read()
    try:
        return _OPS.put_chunk(upload_id, int(index), payload)
    except OpsError as error:
        _raise_ops(error)


@router.post('/ops/uploads/{upload_id}/complete')
async def ops_upload_complete(upload_id: str, user=Depends(get_verified_user)):
    try:
        return _OPS.complete_upload(upload_id)
    except OpsError as error:
        _raise_ops(error)
