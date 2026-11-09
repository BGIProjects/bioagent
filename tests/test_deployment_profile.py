from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from deployment_profile import ProfileError, environment, load_profile

ROOT = Path(__file__).parents[1]
PROFILES = ROOT / 'deployment' / 'profiles'


@pytest.mark.parametrize('name', ['cyclone-development.json', 'independent-target.json'])
def test_profiles_are_valid_secret_free_and_complete(name: str) -> None:
    profile = load_profile(PROFILES / name)
    serialized = json.dumps(profile)

    assert len(profile['profile_sha256']) == 64
    assert 'MINIMAX_API_KEY' in serialized
    assert 'sk-' not in serialized
    assert set(profile['compute']['workflow_sources']) == {
        f'workflow{index}' for index in range(1, 7)
    }
    agent = environment(profile, 'agent')
    backend = environment(profile, 'backend')
    assert agent['BIOAGENT_PROFILE_ID'] == profile['profile_id']
    assert agent['BIOAGENT_ASSET_ROOT'] == profile['storage']['asset_root']
    assert (
        agent['BIOAGENT_ADMISSION_STATE_FILE']
        == profile['operations']['admission_state_file']
    )
    assert (
        agent['BIOAGENT_ASSET_RELEASE_STORE']
        == profile['operations']['asset_release_store']
    )
    assert agent['BIOAGENT_MODEL_ID'] == 'MiniMax-M3'
    assert agent['BIOAGENT_MODEL_BASE_URL'].endswith(':443/anthropic')
    assert 'MINIMAX_API_KEY' not in agent
    assert backend['BIOAGENT_REMOTE_DATA'] == 'true'
    assert backend['OPENAI_API_BASE_URLS'].endswith('/v1')
    assert backend['DATABASE_URL'].endswith(profile['operations']['business_db'])


def test_profile_rejects_unknown_fields_paths_ports_and_embedded_credentials(
    tmp_path: Path,
) -> None:
    base = json.loads((PROFILES / 'cyclone-development.json').read_text())
    mutations = []
    unknown = copy.deepcopy(base)
    unknown['secret'] = 'forbidden'
    mutations.append(unknown)
    relative = copy.deepcopy(base)
    relative['storage']['run_root'] = 'relative/runs'
    mutations.append(relative)
    duplicate_port = copy.deepcopy(base)
    duplicate_port['services']['backend']['port'] = duplicate_port['services']['agent']['port']
    duplicate_port['services']['backend']['url'] = duplicate_port['services']['agent']['url']
    mutations.append(duplicate_port)
    credential = copy.deepcopy(base)
    credential['model']['credential_env'] = 'actual-secret-value'
    mutations.append(credential)
    relative_database = copy.deepcopy(base)
    relative_database['operations']['business_db'] = 'relative/webui.db'
    mutations.append(relative_database)
    zero_backup_limit = copy.deepcopy(base)
    zero_backup_limit['resources']['backup_max_gib'] = 0
    mutations.append(zero_backup_limit)
    unsafe_host = copy.deepcopy(base)
    unsafe_host['compute']['ssh_host'] = 'Cyclone;other-command'
    mutations.append(unsafe_host)

    for index, value in enumerate(mutations):
        path = tmp_path / f'invalid-{index}.json'
        path.write_text(json.dumps(value))
        with pytest.raises(ProfileError):
            load_profile(path)


def test_shell_loader_exports_profile_without_eval() -> None:
    script = f'''
set -euo pipefail
unset MINIMAX_API_KEY
source {ROOT / "deployment/load-profile.sh"}
BIOAGENT_DEPLOYMENT_PROFILE=deployment/profiles/independent-target.json
bioagent_load_profile agent
test "$BIOAGENT_PROFILE_ID" = independent-target
test "$AGENT_PORT" = 18001
test "$BIOAGENT_RUN_ROOT" = /srv/bioagent/runs
test "$BIOAGENT_MODEL_POLICY" = minimax_explicit
test -z "${{MINIMAX_API_KEY:-}}"
'''
    subprocess.run(
        ['bash', '-c', script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_service_entrypoint_uses_explicit_profile_without_starting() -> None:
    script = f'''
set -euo pipefail
export BIOAGENT_DEPLOYMENT_PROFILE=deployment/profiles/independent-target.json
source {ROOT / "dev-services.sh"}
test "$AGENT_URL" = http://127.0.0.1:18001
test "$BACKEND_URL" = http://127.0.0.1:18080
test "$FRONTEND_URL" = http://bioagent.local:15173
test "$BIOAGENT_SSH_HOST" = bioagent-compute
test "$LOG_WARN_BYTES" = 104857600
'''
    subprocess.run(
        ['bash', '-c', script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


@pytest.mark.parametrize(
    'script',
    [
        ROOT / 'dev-services.sh',
        ROOT / 'deployment/load-profile.sh',
        ROOT / 'agent/start.sh',
        ROOT / 'open-webui/backend/dev.sh',
    ],
)
def test_profile_integrated_shell_scripts_parse(script: Path) -> None:
    subprocess.run(['bash', '-n', script], check=True, capture_output=True, text=True)
