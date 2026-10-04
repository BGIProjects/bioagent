from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from asset_release_manager import (
    AssetReleaseError,
    activate_release_set,
    import_package,
    import_release_set,
    require_draining,
    rollback_release_set,
    status,
    verify_package,
)
from deployment_admission import write_state


def _package(
    root: Path,
    asset_type: str,
    asset_id: str,
    version: str,
    *,
    requires: list[dict] | None = None,
    validation: str = 'passed',
    license_name: str = 'BioAgent test license',
) -> tuple[Path, str]:
    package = root / f'{asset_type}-{asset_id}-{version}'
    package.mkdir(parents=True)
    payload = package / 'payload.json'
    content = json.dumps({'asset_id': asset_id, 'version': version}).encode()
    payload.write_bytes(content)
    manifest = {
        'schema_version': 1,
        'asset': {
            'asset_type': asset_type,
            'asset_id': asset_id,
            'version': version,
            'source': 'BioAgent test fixture',
            'license': license_name,
        },
        'requires': sorted(
            requires or [],
            key=lambda item: (item['asset_type'], item['asset_id'], item['version']),
        ),
        'files': [
            {
                'path': payload.name,
                'size': len(content),
                'sha256': hashlib.sha256(content).hexdigest(),
            }
        ],
        'validation': {'status': validation, 'record': 'fixture regression'},
    }
    manifest_path = package / 'package-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return package, hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _release_set(
    path: Path,
    release_set_id: str,
    packages: list[tuple[str, str, str, str]],
    *,
    validation: str = 'passed',
) -> Path:
    value = {
        'schema_version': 1,
        'release_set_id': release_set_id,
        'created_at': '2026-10-04T19:00:00+08:00',
        'packages': [
            {
                'asset_type': asset_type,
                'asset_id': asset_id,
                'version': version,
                'manifest_sha256': digest,
            }
            for asset_type, asset_id, version, digest in sorted(packages)
        ],
        'validation': {'status': validation, 'record': 'fixture compatibility regression'},
    }
    path.write_text(json.dumps(value, indent=2) + '\n')
    return path


def _import(
    package: Path,
    store: Path,
) -> dict:
    return import_package(package, store, max_bytes=1_000_000, min_free_bytes=0)


def test_import_activate_and_rollback_are_immutable_and_atomic(tmp_path: Path) -> None:
    store = tmp_path / 'store'
    knowledge_v1, knowledge_v1_digest = _package(
        tmp_path, 'knowledge', 'knowledge', '1'
    )
    rules, rules_digest = _package(
        tmp_path,
        'rules',
        'rules',
        '1',
        requires=[{'asset_type': 'knowledge', 'asset_id': 'knowledge', 'version': '1'}],
    )
    knowledge_v2, knowledge_v2_digest = _package(
        tmp_path, 'knowledge', 'knowledge', '2'
    )
    for package in (knowledge_v1, rules, knowledge_v2):
        assert _import(package, store)['installed'] is True
        assert _import(package, store)['installed'] is False

    first = _release_set(
        tmp_path / 'first.json',
        'set-1',
        [
            ('knowledge', 'knowledge', '1', knowledge_v1_digest),
            ('rules', 'rules', '1', rules_digest),
        ],
    )
    second = _release_set(
        tmp_path / 'second.json',
        'set-2',
        [('knowledge', 'knowledge', '2', knowledge_v2_digest)],
    )
    assert import_release_set(first, store)['installed'] is True
    assert import_release_set(second, store)['installed'] is True

    active = activate_release_set(
        store, 'set-1', actor='test', activated_at='2026-10-04T19:01:00+08:00'
    )
    assert active['active_release_set'] == 'set-1'
    assert oct((store / 'active-release-set.json').stat().st_mode & 0o777) == '0o600'
    assert activate_release_set(store, 'set-1', actor='test')['changed'] is False
    active = activate_release_set(
        store, 'set-2', actor='test', activated_at='2026-10-04T19:02:00+08:00'
    )
    assert active['previous_release_set'] == 'set-1'
    rolled_back = rollback_release_set(
        store, actor='test', activated_at='2026-10-04T19:03:00+08:00'
    )
    assert rolled_back['active_release_set'] == 'set-1'
    assert rolled_back['previous_release_set'] == 'set-2'
    assert status(store)['active']['release_set_id'] == 'set-1'


def test_tamper_extra_file_and_symlink_fail_closed(tmp_path: Path) -> None:
    package, _ = _package(tmp_path, 'knowledge', 'knowledge', '1')
    (package / 'payload.json').write_text('changed')
    with pytest.raises(AssetReleaseError, match='identity mismatch'):
        verify_package(package, max_bytes=1_000_000)

    package, _ = _package(tmp_path / 'extra', 'knowledge', 'knowledge', '1')
    (package / 'extra.txt').write_text('unexpected')
    with pytest.raises(AssetReleaseError, match='unexpected'):
        verify_package(package, max_bytes=1_000_000)

    package, _ = _package(tmp_path / 'nested', 'knowledge', 'knowledge', '1')
    nested_manifest = package / 'nested' / 'package-manifest.json'
    nested_manifest.parent.mkdir()
    nested_manifest.write_text('{}')
    with pytest.raises(AssetReleaseError, match='unexpected'):
        verify_package(package, max_bytes=1_000_000)

    package, _ = _package(tmp_path / 'link', 'knowledge', 'knowledge', '1')
    (package / 'link').symlink_to(package / 'payload.json')
    with pytest.raises(AssetReleaseError, match='symlinks'):
        verify_package(package, max_bytes=1_000_000)


def test_release_set_rejects_missing_requirement_and_manifest_mismatch(
    tmp_path: Path,
) -> None:
    store = tmp_path / 'store'
    rules, rules_digest = _package(
        tmp_path,
        'rules',
        'rules',
        '1',
        requires=[{'asset_type': 'knowledge', 'asset_id': 'knowledge', 'version': '1'}],
    )
    _import(rules, store)
    incompatible = _release_set(
        tmp_path / 'incompatible.json',
        'incompatible',
        [('rules', 'rules', '1', rules_digest)],
    )
    with pytest.raises(AssetReleaseError, match='requirement is missing'):
        import_release_set(incompatible, store)

    mismatched = _release_set(
        tmp_path / 'mismatched.json',
        'mismatched',
        [('rules', 'rules', '1', '0' * 64)],
    )
    with pytest.raises(AssetReleaseError, match='identity mismatch'):
        import_release_set(mismatched, store)


@pytest.mark.parametrize(
    ('validation', 'license_name'),
    [('pending', 'BioAgent test license'), ('passed', 'unknown; development only')],
)
def test_activation_rejects_unapproved_or_unlicensed_package(
    tmp_path: Path, validation: str, license_name: str
) -> None:
    store = tmp_path / 'store'
    package, digest = _package(
        tmp_path,
        'knowledge',
        'knowledge',
        '1',
        validation=validation,
        license_name=license_name,
    )
    _import(package, store)
    release_set = _release_set(
        tmp_path / 'set.json',
        'set-1',
        [('knowledge', 'knowledge', '1', digest)],
    )
    import_release_set(release_set, store)
    with pytest.raises(AssetReleaseError, match='unapproved or unlicensed'):
        activate_release_set(store, 'set-1', actor='test')


def test_release_set_validation_must_pass_before_activation(tmp_path: Path) -> None:
    store = tmp_path / 'store'
    package, digest = _package(tmp_path, 'knowledge', 'knowledge', '1')
    _import(package, store)
    release_set = _release_set(
        tmp_path / 'set.json',
        'set-1',
        [('knowledge', 'knowledge', '1', digest)],
        validation='pending',
    )
    import_release_set(release_set, store)
    with pytest.raises(AssetReleaseError, match='has not passed'):
        activate_release_set(store, 'set-1', actor='test')


def test_capacity_and_immutable_collision_fail_before_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / 'store'
    package, _ = _package(tmp_path, 'knowledge', 'knowledge', '1')
    monkeypatch.setattr(
        'asset_release_manager.shutil.disk_usage',
        lambda _path: SimpleNamespace(free=1),
    )
    with pytest.raises(AssetReleaseError, match='free space'):
        import_package(package, store, max_bytes=1_000_000, min_free_bytes=10)

    monkeypatch.undo()
    _import(package, store)
    manifest = json.loads((package / 'package-manifest.json').read_text())
    manifest['asset']['source'] = 'different immutable content'
    (package / 'package-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with pytest.raises(AssetReleaseError, match='immutable asset version'):
        _import(package, store)


def test_state_tamper_and_incomplete_import_are_observable(tmp_path: Path) -> None:
    store = tmp_path / 'store'
    package, digest = _package(tmp_path, 'knowledge', 'knowledge', '1')
    _import(package, store)
    release_set = _release_set(
        tmp_path / 'set.json',
        'set-1',
        [('knowledge', 'knowledge', '1', digest)],
    )
    import_release_set(release_set, store)
    activate_release_set(store, 'set-1', actor='test')
    partial = store / 'packages' / '.partial-interrupted'
    partial.mkdir()
    assert status(store)['incomplete_imports'] == ['packages/.partial-interrupted']

    state_path = store / 'active-release-set.json'
    state = json.loads(state_path.read_text())
    state['active_release_set'] = 'tampered'
    state_path.write_text(json.dumps(state))
    with pytest.raises(AssetReleaseError, match='identity mismatch'):
        status(store)

    state_path.unlink()
    state_path.symlink_to(tmp_path / 'missing-state')
    with pytest.raises(AssetReleaseError, match='must not be a symlink'):
        status(store)


def test_activation_gate_requires_valid_draining_state(tmp_path: Path) -> None:
    admission = tmp_path / 'admission.json'
    with pytest.raises(AssetReleaseError, match='require admission draining'):
        require_draining(admission)
    write_state(admission, 'draining', 'asset update', updated_by='test')
    assert require_draining(admission)['admission'] == 'draining'
    admission.write_text('{}')
    with pytest.raises(AssetReleaseError, match='state is invalid'):
        require_draining(admission)


def test_store_rejects_symlinked_package_inventory(tmp_path: Path) -> None:
    store = tmp_path / 'store'
    package, _ = _package(tmp_path, 'knowledge', 'knowledge', '1')
    store.mkdir()
    (store / 'packages').mkdir()
    (store / 'release-sets').mkdir()
    (store / 'packages' / 'knowledge').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AssetReleaseError, match='unsafe component'):
        _import(package, store)
    with pytest.raises(AssetReleaseError, match='inventory is invalid'):
        status(store)
    with pytest.raises(AssetReleaseError, match='non-root absolute path'):
        status(Path('relative-store'))
