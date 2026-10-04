from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from deployment_preflight import (
    PreflightError,
    inspect_source_locks,
    load_install_manifest,
    readiness,
    verify_media,
)

ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / 'deployment/offline-install-manifest.json'


def test_repository_source_locks_are_exact_and_content_identified() -> None:
    manifest = load_install_manifest(MANIFEST_PATH)
    result = inspect_source_locks(manifest, ROOT)

    assert result['status'] == 'ready'
    assert result['python_version'] == '3.11'
    assert result['node_version'] == '22.23.2'
    assert [item['component'] for item in result['files']] == [
        'agent-python',
        'backend-python',
        'frontend-node',
    ]
    assert result['files'][0]['packages'] == 48
    assert result['files'][1]['artifact_hashes'] >= result['files'][1]['packages']
    assert result['files'][2]['artifact_identities'] == result['files'][2]['packages']
    assert all(len(item['sha256']) == 64 for item in result['files'])


def _media(tmp_path: Path, manifest: dict) -> Path:
    media = tmp_path / 'media'
    media.mkdir(parents=True)
    files = []
    for index, item in enumerate(manifest['required_media']):
        path = media / f'payload-{index}.tar.zst'
        content = f'{item["component"]}\n'.encode()
        path.write_bytes(content)
        files.append(
            {
                'component': item['component'],
                'path': path.name,
                'size': len(content),
                'sha256': hashlib.sha256(content).hexdigest(),
            }
        )
    (media / 'media-manifest.json').write_text(
        json.dumps(
            {
                'schema_version': 1,
                'platform': 'linux',
                'architecture': 'x86_64',
                'created_at': '2026-10-04T18:00:00+08:00',
                'files': files,
            }
        )
    )
    return media


def test_complete_media_is_deterministic_ready_but_external_model_blocks_offline(
    tmp_path: Path,
) -> None:
    manifest = load_install_manifest(MANIFEST_PATH)
    media = _media(tmp_path, manifest)

    verified = verify_media(manifest, media)
    assert verified['status'] == 'ready'
    assert verified['components'] == 7
    result = readiness(manifest, ROOT, media)
    assert result['deterministic_install_ready'] is True
    assert result['full_offline_ready'] is False
    assert result['blockers'] == ['MODEL_NOT_OFFLINE_CAPABLE']


def test_media_tamper_extra_file_and_symlink_fail_closed(tmp_path: Path) -> None:
    manifest = load_install_manifest(MANIFEST_PATH)
    media = _media(tmp_path, manifest)
    (media / 'payload-0.tar.zst').write_text('changed')
    with pytest.raises(PreflightError, match='identity mismatch'):
        verify_media(manifest, media)

    media = _media(tmp_path / 'second', manifest)
    (media / 'extra').write_text('unexpected')
    with pytest.raises(PreflightError, match='unexpected'):
        verify_media(manifest, media)

    media = _media(tmp_path / 'third', manifest)
    (media / 'link').symlink_to(media / 'payload-0.tar.zst')
    with pytest.raises(PreflightError, match='symlinks'):
        verify_media(manifest, media)

    media = _media(tmp_path / 'fourth', manifest)
    media_link = tmp_path / 'media-link'
    media_link.symlink_to(media, target_is_directory=True)
    with pytest.raises(PreflightError, match='root must not be a symlink'):
        verify_media(manifest, media_link)


def test_unpinned_source_lock_and_manifest_unknown_field_are_rejected(
    tmp_path: Path,
) -> None:
    manifest = load_install_manifest(MANIFEST_PATH)
    source = tmp_path / 'source'
    source.mkdir()
    lock = source / 'requirements.txt'
    lock.write_text('fastapi\n')
    reduced = copy.deepcopy(manifest)
    reduced['source_locks'] = [
        {'component': 'agent', 'path': lock.name, 'format': 'pip-freeze'}
    ]
    with pytest.raises(PreflightError, match='unpinned'):
        inspect_source_locks(reduced, source)

    raw = json.loads(MANIFEST_PATH.read_text())
    raw['unknown'] = True
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(raw))
    with pytest.raises(PreflightError, match='fields'):
        load_install_manifest(path)

    npm_lock = source / 'package-lock.json'
    npm_lock.write_text('[]')
    reduced['source_locks'] = [
        {'component': 'frontend', 'path': npm_lock.name, 'format': 'npm-lock-v3'}
    ]
    with pytest.raises(PreflightError, match='lockfileVersion 3'):
        inspect_source_locks(reduced, source)


def test_cli_reports_current_missing_media_and_model_blocker() -> None:
    result = subprocess.run(
        ['python3', str(ROOT / 'deployment_preflight.py'), 'check'],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3
    value = json.loads(result.stdout)
    assert value['deterministic_install_ready'] is False
    assert value['full_offline_ready'] is False
    assert len([item for item in value['blockers'] if item.startswith('MISSING_MEDIA:')]) == 7
    assert 'MODEL_NOT_OFFLINE_CAPABLE' in value['blockers']
