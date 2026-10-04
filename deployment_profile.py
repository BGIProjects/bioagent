#!/usr/bin/env python3
"""Validate a secret-free BioAgent DeploymentProfile and export runtime env."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = 3
WORKFLOW_KEYS = tuple(f'workflow{index}' for index in range(1, 7))
COMPONENTS = {'services', 'agent', 'backend', 'all'}
SAFE_ENV_KEY = re.compile(r'^[A-Z][A-Z0-9_]*$')
SAFE_SSH_HOST = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$')


class ProfileError(ValueError):
    pass


def _mapping(value: Any, name: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProfileError(f'{name} must contain exactly: {", ".join(sorted(keys))}')
    return value


def _text(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ProfileError(f'{name} must be a non-empty string')
    if any(character in value for character in ('\0', '\n', '\r', '=')):
        raise ProfileError(f'{name} contains an unsafe environment character')
    return value


def _absolute(value: Any, name: str) -> str:
    text = _text(value, name)
    if not PurePosixPath(text).is_absolute():
        raise ProfileError(f'{name} must be an absolute POSIX path')
    return text


def _positive_int(value: Any, name: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProfileError(f'{name} must be a positive integer')
    if maximum is not None and value > maximum:
        raise ProfileError(f'{name} must not exceed {maximum}')
    return value


def _positive_number(value: Any, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ProfileError(f'{name} must be a positive number')
    return value


def _url(value: Any, name: str, port: int) -> str:
    text = _text(value, name)
    parsed = urlparse(text)
    try:
        parsed_port = parsed.port
    except ValueError as error:
        raise ProfileError(f'{name} contains an invalid port') from error
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed_port != port:
        raise ProfileError(f'{name} must be an HTTP(S) URL using port {port}')
    if parsed.path not in {'', '/'} or parsed.query or parsed.fragment or parsed.username:
        raise ProfileError(f'{name} must be an origin URL without credentials or a path')
    return text.rstrip('/')


def load_profile(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileError('deployment profile is unavailable or invalid JSON') from error
    profile = _mapping(
        value,
        'profile',
        {
            'schema_version',
            'profile_id',
            'deployment_kind',
            'services',
            'storage',
            'compute',
            'model',
            'operations',
            'resources',
        },
    )
    if profile['schema_version'] != SCHEMA_VERSION:
        raise ProfileError(f'unsupported deployment profile schema: {profile["schema_version"]}')
    _text(profile['profile_id'], 'profile_id')
    if profile['deployment_kind'] not in {'development', 'independent_target'}:
        raise ProfileError('deployment_kind must be development or independent_target')

    services = _mapping(profile['services'], 'services', {'frontend', 'backend', 'agent'})
    ports = []
    for name in ('frontend', 'backend', 'agent'):
        service = _mapping(services[name], f'services.{name}', {'bind_host', 'port', 'url'})
        _text(service['bind_host'], f'services.{name}.bind_host')
        port = _positive_int(service['port'], f'services.{name}.port', maximum=65_535)
        service['url'] = _url(service['url'], f'services.{name}.url', port)
        ports.append(port)
    if len(set(ports)) != len(ports):
        raise ProfileError('service ports must be unique')

    storage = _mapping(
        profile['storage'],
        'storage',
        {'application_root', 'asset_root', 'data_root', 'allowed_data_roots', 'run_root', 'worker_root'},
    )
    for key in ('application_root', 'asset_root', 'data_root', 'run_root', 'worker_root'):
        storage[key] = _absolute(storage[key], f'storage.{key}')
    roots = storage['allowed_data_roots']
    if not isinstance(roots, list) or not roots:
        raise ProfileError('storage.allowed_data_roots must be a non-empty list')
    storage['allowed_data_roots'] = [
        _absolute(item, f'storage.allowed_data_roots[{index}]')
        for index, item in enumerate(roots)
    ]
    if len(set(storage['allowed_data_roots'])) != len(storage['allowed_data_roots']):
        raise ProfileError('storage.allowed_data_roots must be unique')
    if storage['data_root'] not in storage['allowed_data_roots']:
        raise ProfileError('storage.data_root must be explicitly allowed')

    compute = _mapping(
        profile['compute'],
        'compute',
        {
            'transport',
            'ssh_host',
            'python',
            'control_python',
            'tmux',
            'snakemake',
            'seqkit',
            'report_python',
            'rscript',
            'weasyprint',
            'workflow_sources',
        },
    )
    if compute['transport'] != 'ssh':
        raise ProfileError('only the validated ssh compute transport is supported')
    ssh_host = _text(compute['ssh_host'], 'compute.ssh_host')
    if not SAFE_SSH_HOST.fullmatch(ssh_host):
        raise ProfileError('compute.ssh_host must be a safe SSH host alias')
    for key in (
        'python',
        'control_python',
        'tmux',
        'snakemake',
        'seqkit',
        'report_python',
        'rscript',
        'weasyprint',
    ):
        compute[key] = _absolute(compute[key], f'compute.{key}')
    workflows = _mapping(
        compute['workflow_sources'],
        'compute.workflow_sources',
        set(WORKFLOW_KEYS),
    )
    for key in WORKFLOW_KEYS:
        workflows[key] = _absolute(workflows[key], f'compute.workflow_sources.{key}')

    model = _mapping(
        profile['model'],
        'model',
        {'policy', 'model_id', 'provider_model', 'base_url', 'credential_env', 'taxonagent_mcp_url'},
    )
    if model['policy'] not in {'local_only', 'minimax_explicit'}:
        raise ProfileError('model.policy must be local_only or minimax_explicit')
    _text(model['model_id'], 'model.model_id')
    _text(model['provider_model'], 'model.provider_model')
    model_base_url = _text(model['base_url'], 'model.base_url')
    parsed_model_url = urlparse(model_base_url)
    try:
        model_port = parsed_model_url.port
    except ValueError as error:
        raise ProfileError('model.base_url contains an invalid port') from error
    if (
        parsed_model_url.scheme != 'https'
        or not parsed_model_url.hostname
        or model_port != 443
        or parsed_model_url.path != '/anthropic'
        or parsed_model_url.query
        or parsed_model_url.fragment
        or parsed_model_url.username
    ):
        raise ProfileError(
            'model.base_url must be an HTTPS URL on port 443 with path /anthropic'
        )
    model['base_url'] = model_base_url.rstrip('/')
    credential = _text(model['credential_env'], 'model.credential_env')
    if not SAFE_ENV_KEY.fullmatch(credential) or credential != 'MINIMAX_API_KEY':
        raise ProfileError('model.credential_env must name MINIMAX_API_KEY without storing its value')
    _text(model['taxonagent_mcp_url'], 'model.taxonagent_mcp_url', allow_empty=True)

    operations = _mapping(
        profile['operations'],
        'operations',
        {
            'business_db',
            'backup_root',
            'backup_retention_count',
            'admission_state_file',
        },
    )
    operations['business_db'] = _absolute(
        operations['business_db'], 'operations.business_db'
    )
    operations['backup_root'] = _absolute(
        operations['backup_root'], 'operations.backup_root'
    )
    operations['admission_state_file'] = _absolute(
        operations['admission_state_file'], 'operations.admission_state_file'
    )
    _positive_int(
        operations['backup_retention_count'], 'operations.backup_retention_count'
    )

    resources = _mapping(
        profile['resources'],
        'resources',
        {'queue_aging_hours', 'snakemake_cores', 'log_warn_mib', 'backup_max_gib'},
    )
    _positive_number(resources['queue_aging_hours'], 'resources.queue_aging_hours')
    _positive_int(resources['snakemake_cores'], 'resources.snakemake_cores')
    _positive_int(resources['log_warn_mib'], 'resources.log_warn_mib')
    _positive_int(resources['backup_max_gib'], 'resources.backup_max_gib')
    profile['profile_sha256'] = hashlib.sha256(raw).hexdigest()
    return profile


def environment(profile: dict[str, Any], component: str) -> dict[str, str]:
    if component not in COMPONENTS:
        raise ProfileError(f'component must be one of: {", ".join(sorted(COMPONENTS))}')
    services = profile['services']
    storage = profile['storage']
    operations = profile['operations']
    values = {
        'BIOAGENT_PROFILE_ID': profile['profile_id'],
        'BIOAGENT_APPLICATION_ROOT': storage['application_root'],
        'BIOAGENT_ASSET_ROOT': storage['asset_root'],
        'AGENT_HOST': services['agent']['bind_host'],
        'AGENT_PORT': str(services['agent']['port']),
        'AGENT_URL': services['agent']['url'],
        'BACKEND_HOST': services['backend']['bind_host'],
        'BACKEND_PORT': str(services['backend']['port']),
        'BACKEND_URL': services['backend']['url'],
        'PORT': str(services['backend']['port']),
        'FRONTEND_HOST': services['frontend']['bind_host'],
        'FRONTEND_PORT': str(services['frontend']['port']),
        'FRONTEND_URL': services['frontend']['url'],
        'VITE_WEBUI_PORT': str(services['backend']['port']),
        'VITE_WEBUI_BASE_URL': services['backend']['url'],
        'OPENAI_API_BASE_URLS': f'{services["agent"]["url"]}/v1',
        'BIOAGENT_LOG_WARN_MIB': str(profile['resources']['log_warn_mib']),
        'BIOAGENT_BACKUP_MAX_GIB': str(profile['resources']['backup_max_gib']),
        'BIOAGENT_BACKUP_ROOT': operations['backup_root'],
        'BIOAGENT_BACKUP_RETENTION_COUNT': str(operations['backup_retention_count']),
        'BIOAGENT_BUSINESS_DB': operations['business_db'],
        'BIOAGENT_ADMISSION_STATE_FILE': operations['admission_state_file'],
        'BIOAGENT_SSH_HOST': profile['compute']['ssh_host'],
    }
    if component in {'agent', 'all'}:
        compute = profile['compute']
        model = profile['model']
        values.update(
            {
                'BIOAGENT_MODEL_POLICY': model['policy'],
                'BIOAGENT_MODEL_ID': model['model_id'],
                'BIOAGENT_PROVIDER_MODEL': model['provider_model'],
                'BIOAGENT_MODEL_BASE_URL': model['base_url'],
                'TAXONAGENT_MCP_URL': model['taxonagent_mcp_url'],
                'BIOAGENT_REMOTE_PYTHON': compute['python'],
                'BIOAGENT_REMOTE_CONTROL_PYTHON': compute['control_python'],
                'BIOAGENT_REMOTE_TMUX': compute['tmux'],
                'BIOAGENT_REMOTE_WORKER_ROOT': storage['worker_root'],
                'BIOAGENT_DATA_ROOT': storage['data_root'],
                'BIOAGENT_DATA_ALLOWED_ROOTS': ':'.join(storage['allowed_data_roots']),
                'BIOAGENT_RUN_ROOT': storage['run_root'],
                'BIOAGENT_QUEUE_AGING_HOURS': str(profile['resources']['queue_aging_hours']),
                'BIOAGENT_SNAKEMAKE': compute['snakemake'],
                'BIOAGENT_SEQKIT': compute['seqkit'],
                'BIOAGENT_SNAKEMAKE_CORES': str(profile['resources']['snakemake_cores']),
                'BIOAGENT_REPORT_PYTHON': compute['report_python'],
                'BIOAGENT_RSCRIPT': compute['rscript'],
                'BIOAGENT_WEASYPRINT': compute['weasyprint'],
                **{
                    f'BIOAGENT_WORKFLOW{index}_SOURCE': compute['workflow_sources'][f'workflow{index}']
                    for index in range(1, 7)
                },
            }
        )
    if component in {'backend', 'all'}:
        values.update(
            {
                'BIOAGENT_REMOTE_DATA': 'true',
                'BIOAGENT_DATA_ROOT': profile['storage']['data_root'],
                'BIOAGENT_RUN_ROOT': profile['storage']['run_root'],
                'DATABASE_URL': f'sqlite:///{operations["business_db"]}',
            }
        )
    return dict(sorted(values.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    validate = subparsers.add_parser('validate')
    validate.add_argument('profile', type=Path)
    env = subparsers.add_parser('env')
    env.add_argument('profile', type=Path)
    env.add_argument('component', choices=sorted(COMPONENTS))
    args = parser.parse_args(argv)
    try:
        profile = load_profile(args.profile)
        if args.command == 'validate':
            print(f'{profile["profile_id"]} {profile["profile_sha256"]}')
        else:
            for key, value in environment(profile, args.component).items():
                print(f'{key}={value}')
    except ProfileError as error:
        parser.exit(2, f'DeploymentProfile invalid: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
