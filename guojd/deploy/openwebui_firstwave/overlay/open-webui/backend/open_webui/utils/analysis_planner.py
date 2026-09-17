"""Internal client for the deterministic BioAgent planner."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from open_webui.models.config import Config


class AnalysisPlannerError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _valid_runtime_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip().rstrip('/')
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return None
    if parsed.hostname == 'api.openai.com':
        return None
    return url


def _connection_config(api_configs: Any, index: int, url: str) -> dict[str, Any]:
    if not isinstance(api_configs, dict):
        return {}
    value = api_configs.get(str(index), api_configs.get(url, {}))
    return value if isinstance(value, dict) else {}


def _is_bioagent(config: dict[str, Any]) -> bool:
    provider = str(config.get('provider') or '').strip().lower()
    model_ids = config.get('model_ids') or []
    if isinstance(model_ids, str):
        model_ids = [model_ids]
    return provider == 'bioagent' or any(
        isinstance(model_id, str) and model_id.strip().lower() == 'bioagent' for model_id in model_ids
    )


async def resolve_analysis_base_url() -> str:
    values = await Config.get_many(
        'openai.enable',
        'openai.api_base_urls',
        'openai.api_configs',
    )
    if values.get('openai.enable') is not True:
        raise AnalysisPlannerError('BioAgent deterministic planner is unavailable', retryable=True)

    api_configs = values.get('openai.api_configs') or {}
    candidates: list[tuple[str, dict[str, Any]]] = []
    for index, raw_url in enumerate(values.get('openai.api_base_urls') or []):
        url = _valid_runtime_url(raw_url)
        if url is None:
            continue
        config = _connection_config(api_configs, index, url)
        if config.get('enable') is False:
            continue
        candidates.append((url, config))

    marked = {url for url, config in candidates if _is_bioagent(config)}
    if len(marked) == 1:
        return marked.pop()

    unmarked = {url for url, config in candidates if not _is_bioagent(config)}
    if not marked and len(candidates) == 1 and len(unmarked) == 1:
        return candidates[0][0]

    raise AnalysisPlannerError(
        'BioAgent deterministic planner connection is not uniquely configured',
        retryable=True,
    )


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    base_url = await resolve_analysis_base_url()
    try:
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.post(f'{base_url}{path}', json=payload)
    except httpx.HTTPError as error:
        raise AnalysisPlannerError(
            'BioAgent deterministic planner is unavailable',
            retryable=True,
        ) from error
    if not response.is_success:
        detail = response.text
        try:
            detail = response.json().get('detail') or detail
        except ValueError:
            pass
        raise AnalysisPlannerError(str(detail))
    value = response.json()
    if not isinstance(value, dict):
        raise AnalysisPlannerError('BioAgent deterministic planner returned an invalid response')
    return value


async def analysis_health() -> dict[str, Any]:
    try:
        base_url = await resolve_analysis_base_url()
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(f'{base_url}/analysis/health')
        response.raise_for_status()
        value = response.json()
        if isinstance(value, dict):
            return value
    except (AnalysisPlannerError, httpx.HTTPError, ValueError):
        pass
    return {
        'deterministic': {'status': 'unavailable'},
        'conversation_model': {'id': 'BioAgent', 'status': 'unavailable'},
        'knowledge': {'status': 'unavailable'},
    }


async def compile_analysis_plan(
    *,
    dataset: dict[str, Any],
    goals: list[str],
    options: dict[str, Any],
    routing: dict[str, Any],
) -> dict[str, Any]:
    return await _post(
        '/analysis/plans/compile',
        {'dataset': dataset, 'goals': goals, 'options': options, 'routing': routing},
    )


async def start_analysis_run(
    *,
    plan: dict[str, Any],
    dataset: dict[str, Any],
    chat_id: str,
    plan_id: str,
    plan_revision: int,
    run_id: str,
) -> dict[str, Any]:
    return await _post(
        '/analysis/runs/start',
        {
            'plan': plan,
            'dataset': dataset,
            'chat_id': chat_id,
            'plan_id': plan_id,
            'plan_revision': plan_revision,
            'run_id': run_id,
        },
    )
