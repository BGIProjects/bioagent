from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest

from deployment_admission import AdmissionError, read_state, write_state

ROOT = Path(__file__).parents[1]


def test_admission_state_defaults_drains_and_resumes_atomically(tmp_path: Path) -> None:
    path = tmp_path / 'control' / 'admission.json'
    assert read_state(path)['admission'] == 'accepting'

    drained = write_state(path, 'draining', '部署维护', updated_by='operator')
    assert drained['admission'] == 'draining'
    assert drained['reason'] == '部署维护'
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    resumed = write_state(path, 'accepting', '维护完成', updated_by='operator')
    assert resumed['admission'] == 'accepting'
    assert not list(path.parent.glob('.admission-*.tmp'))


def test_admission_state_fails_closed_on_tamper_symlink_and_oversize(
    tmp_path: Path,
) -> None:
    path = tmp_path / 'admission.json'
    write_state(path, 'draining', '部署维护', updated_by='operator')
    value = json.loads(path.read_text())
    value['reason'] = 'changed'
    path.write_text(json.dumps(value))
    with pytest.raises(AdmissionError, match='digest mismatch'):
        read_state(path)

    target = tmp_path / 'target.json'
    write_state(target, 'accepting', '', updated_by='operator')
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(AdmissionError, match='regular file'):
        read_state(path)

    path.unlink()
    path.write_bytes(b'x' * 8193)
    with pytest.raises(AdmissionError, match='size'):
        read_state(path)


def test_cli_uses_profile_state_file_and_rejects_relative_override(
    tmp_path: Path,
) -> None:
    profile = json.loads(
        (ROOT / 'deployment/profiles/cyclone-development.json').read_text()
    )
    state_file = tmp_path / 'admission.json'
    profile['operations']['admission_state_file'] = str(state_file)
    profile_path = tmp_path / 'profile.json'
    profile_path.write_text(json.dumps(profile))

    drained = subprocess.run(
        [
            'python3',
            str(ROOT / 'deployment_admission.py'),
            '--profile',
            str(profile_path),
            'drain',
            '--reason',
            'test maintenance',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(drained.stdout)['admission'] == 'draining'
    subprocess.run(
        [
            'python3',
            str(ROOT / 'deployment_admission.py'),
            '--state-file',
            str(state_file),
            'resume',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert read_state(state_file)['admission'] == 'accepting'

    rejected = subprocess.run(
        [
            'python3',
            str(ROOT / 'deployment_admission.py'),
            '--state-file',
            'relative.json',
            'status',
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 2
    assert 'must be absolute' in rejected.stderr


def test_service_script_drains_and_resumes_without_touching_services(
    tmp_path: Path,
) -> None:
    state_file = tmp_path / 'admission.json'
    environment = {
        'PATH': '/usr/bin:/bin',
        'BIOAGENT_ADMISSION_STATE_FILE': str(state_file),
        'BIOAGENT_PROFILE_PYTHON': 'python3',
    }
    drained = subprocess.run(
        [str(ROOT / 'dev-services.sh'), 'drain', 'test maintenance'],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(drained.stdout)['admission'] == 'draining'
    resumed = subprocess.run(
        [str(ROOT / 'dev-services.sh'), 'resume', 'test complete'],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(resumed.stdout)['admission'] == 'accepting'
