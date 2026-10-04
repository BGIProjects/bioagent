#!/usr/bin/env python3
"""Import, validate, activate, and roll back immutable BioAgent asset packages."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from deployment_admission import AdmissionError
from deployment_admission import read_state as read_admission_state

SCHEMA_VERSION = 1
MANIFEST_NAME = 'package-manifest.json'
STATE_NAME = 'active-release-set.json'
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_FILES = 10_000
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')
ASSET_TYPES = {'knowledge', 'rules', 'reference', 'capability', 'model'}


class AssetReleaseError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()


def _read_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink():
        raise AssetReleaseError(f'{path.name} must be a regular file')
    try:
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_JSON_BYTES:
            raise AssetReleaseError(f'{path.name} size is invalid')
        return json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AssetReleaseError(f'{path.name} is invalid JSON') from error


def _mapping(value: Any, name: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AssetReleaseError(f'{name} fields are invalid')
    return value


def _text(value: Any, name: str, maximum: int = 1000) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(character in value for character in ('\0', '\n', '\r'))
    ):
        raise AssetReleaseError(f'{name} is invalid')
    return value


def _identifier(value: Any, name: str) -> str:
    text = _text(value, name, 128)
    if not SAFE_ID.fullmatch(text):
        raise AssetReleaseError(f'{name} is invalid')
    return text


def _relative(value: Any, name: str) -> PurePosixPath:
    text = _text(value, name, 500)
    path = PurePosixPath(text)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise AssetReleaseError(f'{name} must be a safe relative path')
    return path


def _timestamp(value: Any, name: str) -> str:
    text = _text(value, name, 64)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise AssetReleaseError(f'{name} is invalid') from error
    if parsed.tzinfo is None:
        raise AssetReleaseError(f'{name} must include a timezone')
    return text


def _identity(value: Any, name: str) -> dict[str, str]:
    item = _mapping(value, name, {'asset_type', 'asset_id', 'version'})
    if item['asset_type'] not in ASSET_TYPES:
        raise AssetReleaseError(f'{name}.asset_type is invalid')
    return {
        'asset_type': item['asset_type'],
        'asset_id': _identifier(item['asset_id'], f'{name}.asset_id'),
        'version': _identifier(item['version'], f'{name}.version'),
    }


def load_package_manifest(root: Path) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise AssetReleaseError('package root must be a regular directory')
    value = _mapping(
        _read_json(root / MANIFEST_NAME),
        'package manifest',
        {'schema_version', 'asset', 'requires', 'files', 'validation'},
    )
    if value['schema_version'] != SCHEMA_VERSION:
        raise AssetReleaseError('package manifest schema is unsupported')
    asset = _mapping(
        value['asset'],
        'asset',
        {'asset_type', 'asset_id', 'version', 'source', 'license'},
    )
    identity = _identity(
        {key: asset[key] for key in ('asset_type', 'asset_id', 'version')},
        'asset',
    )
    source = _text(asset['source'], 'asset.source')
    license_name = _text(asset['license'], 'asset.license', 500)
    requires = value['requires']
    if not isinstance(requires, list):
        raise AssetReleaseError('requires must be a list')
    normalized_requires = [
        _identity(item, f'requires[{index}]') for index, item in enumerate(requires)
    ]
    requirement_keys = [tuple(item.values()) for item in normalized_requires]
    if requirement_keys != sorted(requirement_keys) or len(requirement_keys) != len(
        set(requirement_keys)
    ):
        raise AssetReleaseError('requires must be sorted and unique')
    validation = _mapping(value['validation'], 'validation', {'status', 'record'})
    if validation['status'] not in {'pending', 'passed', 'failed'}:
        raise AssetReleaseError('validation.status is invalid')
    record = _text(validation['record'], 'validation.record')
    files = value['files']
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        raise AssetReleaseError('files must be a bounded non-empty list')
    normalized_files = []
    paths = []
    for index, file in enumerate(files):
        entry = _mapping(file, f'files[{index}]', {'path', 'size', 'sha256'})
        relative = _relative(entry['path'], f'files[{index}].path')
        path_text = relative.as_posix()
        if path_text == MANIFEST_NAME:
            raise AssetReleaseError('package manifest cannot list itself as payload')
        size = entry['size']
        sha256 = entry['sha256']
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(sha256, str)
            or not SHA256.fullmatch(sha256)
        ):
            raise AssetReleaseError(f'files[{index}] identity is invalid')
        paths.append(path_text)
        normalized_files.append({'path': path_text, 'size': size, 'sha256': sha256})
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise AssetReleaseError('files must be sorted and unique')
    return {
        'schema_version': SCHEMA_VERSION,
        'asset': {
            **identity,
            'source': source,
            'license': license_name,
        },
        'requires': normalized_requires,
        'files': normalized_files,
        'validation': {'status': validation['status'], 'record': record},
    }


def verify_package(root: Path, *, max_bytes: int) -> dict[str, Any]:
    if max_bytes <= 0:
        raise AssetReleaseError('max_bytes must be positive')
    manifest = load_package_manifest(root)
    expected = {item['path'] for item in manifest['files']}
    paths = list(root.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise AssetReleaseError('asset packages must not contain symlinks')
    if any(not path.is_file() and not path.is_dir() for path in paths):
        raise AssetReleaseError('asset packages contain an unsupported file type')
    actual = {
        path.relative_to(root).as_posix()
        for path in paths
        if path.is_file() and path != root / MANIFEST_NAME
    }
    if actual != expected:
        raise AssetReleaseError('asset package contains missing or unexpected files')
    total_bytes = 0
    for entry in manifest['files']:
        path = root.joinpath(*PurePosixPath(entry['path']).parts)
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != entry['size']
            or _sha256(path) != entry['sha256']
        ):
            raise AssetReleaseError(f'asset file identity mismatch: {entry["path"]}')
        total_bytes += entry['size']
        if total_bytes > max_bytes:
            raise AssetReleaseError('asset package exceeds the configured size limit')
    manifest_path = root / MANIFEST_NAME
    return {
        'manifest': manifest,
        'manifest_sha256': _sha256(manifest_path),
        'file_count': len(expected),
        'total_bytes': total_bytes,
    }


def _ensure_store(store: Path) -> Path:
    if not store.is_absolute() or store == Path('/'):
        raise AssetReleaseError('asset store must be a non-root absolute path')
    if store.exists() and (not store.is_dir() or store.is_symlink()):
        raise AssetReleaseError('asset store must be a regular directory')
    store.mkdir(parents=True, exist_ok=True)
    for name in ('packages', 'release-sets'):
        path = store / name
        if path.exists() and (not path.is_dir() or path.is_symlink()):
            raise AssetReleaseError(f'asset store {name} must be a regular directory')
        path.mkdir(exist_ok=True)
    return store.resolve()


@contextmanager
def _locked_store(store: Path) -> Iterator[Path]:
    root = _ensure_store(store)
    lock_path = root / '.lock'
    if lock_path.is_symlink():
        raise AssetReleaseError('asset store lock must not be a symlink')
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, 'a+b') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield root
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _package_path(
    store: Path, identity: dict[str, str], *, create_parents: bool = False
) -> Path:
    current = store / 'packages'
    for component in (identity['asset_type'], identity['asset_id']):
        current /= component
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise AssetReleaseError('asset package path contains an unsafe component')
        if create_parents:
            current.mkdir(exist_ok=True)
    target = current / identity['version']
    if target.is_symlink():
        raise AssetReleaseError('asset package target must not be a symlink')
    return target


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def import_package(
    source: Path,
    store: Path,
    *,
    max_bytes: int,
    min_free_bytes: int,
) -> dict[str, Any]:
    if min_free_bytes < 0:
        raise AssetReleaseError('min_free_bytes must not be negative')
    verified = verify_package(source, max_bytes=max_bytes)
    identity = {
        key: verified['manifest']['asset'][key]
        for key in ('asset_type', 'asset_id', 'version')
    }
    with _locked_store(store) as root:
        target = _package_path(root, identity, create_parents=True)
        if target.exists():
            existing = verify_package(target, max_bytes=max_bytes)
            if existing['manifest_sha256'] != verified['manifest_sha256']:
                raise AssetReleaseError('immutable asset version already exists')
            return {**identity, **existing, 'installed': False, 'path': str(target)}
        free_bytes = shutil.disk_usage(root).free
        required = verified['total_bytes'] + min_free_bytes
        if free_bytes < required:
            raise AssetReleaseError('insufficient free space for asset import')
        staging = Path(
            tempfile.mkdtemp(prefix=f'.partial-{identity["asset_id"]}-', dir=target.parent)
        )
        try:
            for entry in verified['manifest']['files']:
                relative = PurePosixPath(entry['path'])
                destination = staging.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source.joinpath(*relative.parts), destination)
            shutil.copy2(source / MANIFEST_NAME, staging / MANIFEST_NAME)
            staged = verify_package(staging, max_bytes=max_bytes)
            if staged['manifest_sha256'] != verified['manifest_sha256']:
                raise AssetReleaseError('staged asset manifest changed during import')
            os.replace(staging, target)
            _fsync_directory(target.parent)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return {**identity, **verified, 'installed': True, 'path': str(target)}


def load_release_set(path: Path) -> dict[str, Any]:
    value = _mapping(
        _read_json(path),
        'release set',
        {'schema_version', 'release_set_id', 'created_at', 'packages', 'validation'},
    )
    if value['schema_version'] != SCHEMA_VERSION:
        raise AssetReleaseError('release set schema is unsupported')
    release_set_id = _identifier(value['release_set_id'], 'release_set_id')
    created_at = _timestamp(value['created_at'], 'created_at')
    packages = value['packages']
    if not isinstance(packages, list) or not packages:
        raise AssetReleaseError('release set packages must be a non-empty list')
    normalized = []
    keys = []
    logical = []
    for index, package in enumerate(packages):
        entry = _mapping(
            package,
            f'packages[{index}]',
            {'asset_type', 'asset_id', 'version', 'manifest_sha256'},
        )
        identity = _identity(
            {key: entry[key] for key in ('asset_type', 'asset_id', 'version')},
            f'packages[{index}]',
        )
        digest = entry['manifest_sha256']
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise AssetReleaseError(f'packages[{index}].manifest_sha256 is invalid')
        normalized.append({**identity, 'manifest_sha256': digest})
        keys.append(tuple(identity.values()))
        logical.append((identity['asset_type'], identity['asset_id']))
    if keys != sorted(keys) or len(keys) != len(set(keys)) or len(logical) != len(set(logical)):
        raise AssetReleaseError('release set packages must be sorted and logically unique')
    validation = _mapping(value['validation'], 'validation', {'status', 'record'})
    if validation['status'] not in {'pending', 'passed', 'failed'}:
        raise AssetReleaseError('release set validation.status is invalid')
    record = _text(validation['record'], 'release set validation.record')
    return {
        'schema_version': SCHEMA_VERSION,
        'release_set_id': release_set_id,
        'created_at': created_at,
        'packages': normalized,
        'validation': {'status': validation['status'], 'record': record},
    }


def _verify_release_set(value: dict[str, Any], store: Path) -> dict[str, Any]:
    selected = {
        (item['asset_type'], item['asset_id'], item['version']): item
        for item in value['packages']
    }
    package_details = []
    for item in value['packages']:
        identity = {key: item[key] for key in ('asset_type', 'asset_id', 'version')}
        package_root = _package_path(store, identity)
        verified = verify_package(package_root, max_bytes=2**63 - 1)
        if verified['manifest_sha256'] != item['manifest_sha256']:
            raise AssetReleaseError('release set package manifest identity mismatch')
        manifest = verified['manifest']
        for requirement in manifest['requires']:
            if tuple(requirement.values()) not in selected:
                raise AssetReleaseError(
                    f'incompatible release set: {identity["asset_id"]} requirement is missing'
                )
        package_details.append(
            {
                **identity,
                'manifest_sha256': verified['manifest_sha256'],
                'validation_status': manifest['validation']['status'],
                'license': manifest['asset']['license'],
                'total_bytes': verified['total_bytes'],
            }
        )
    return {
        'release_set_id': value['release_set_id'],
        'release_set_sha256': _json_digest(value),
        'packages': package_details,
        'total_bytes': sum(item['total_bytes'] for item in package_details),
    }


def import_release_set(source: Path, store: Path) -> dict[str, Any]:
    value = load_release_set(source)
    with _locked_store(store) as root:
        verified = _verify_release_set(value, root)
        target = root / 'release-sets' / f'{value["release_set_id"]}.json'
        serialized = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        if target.is_symlink():
            raise AssetReleaseError('release set target must not be a symlink')
        if target.exists():
            if target.is_symlink() or target.read_text(encoding='utf-8') != serialized:
                raise AssetReleaseError('immutable release set already exists')
            return {**verified, 'installed': False, 'path': str(target)}
        temporary = target.with_name(f'.partial-{target.name}-{os.getpid()}')
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644
        )
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            _fsync_directory(target.parent)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return {**verified, 'installed': True, 'path': str(target)}


def _load_installed_release_set(store: Path, release_set_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    value = load_release_set(store / 'release-sets' / f'{release_set_id}.json')
    return value, _verify_release_set(value, store)


def _state_body(
    active: str,
    previous: str | None,
    *,
    actor: str,
    activated_at: str,
) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'active_release_set': active,
        'previous_release_set': previous,
        'activated_at': activated_at,
        'activated_by': actor,
    }


def _read_state(store: Path) -> dict[str, Any] | None:
    path = store / STATE_NAME
    if path.is_symlink():
        raise AssetReleaseError('active release state must not be a symlink')
    if not path.exists():
        return None
    value = _mapping(
        _read_json(path),
        'active release state',
        {
            'schema_version',
            'active_release_set',
            'previous_release_set',
            'activated_at',
            'activated_by',
            'sha256',
        },
    )
    if value['schema_version'] != SCHEMA_VERSION:
        raise AssetReleaseError('active release state schema is unsupported')
    _identifier(value['active_release_set'], 'active_release_set')
    previous = value['previous_release_set']
    if previous is not None:
        _identifier(previous, 'previous_release_set')
    _timestamp(value['activated_at'], 'activated_at')
    _text(value['activated_by'], 'activated_by', 128)
    digest = value['sha256']
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise AssetReleaseError('active release state sha256 is invalid')
    body = {key: value[key] for key in value if key != 'sha256'}
    if _json_digest(body) != digest:
        raise AssetReleaseError('active release state identity mismatch')
    return value


def _write_state(store: Path, body: dict[str, Any]) -> dict[str, Any]:
    value = {**body, 'sha256': _json_digest(body)}
    target = store / STATE_NAME
    temporary = target.with_name(f'.partial-{target.name}-{os.getpid()}')
    descriptor = os.open(
        temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        _fsync_directory(store)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return value


def _activation_ready(value: dict[str, Any], verified: dict[str, Any]) -> None:
    if value['validation']['status'] != 'passed':
        raise AssetReleaseError('release set validation has not passed')
    invalid = [
        item['asset_id']
        for item in verified['packages']
        if item['validation_status'] != 'passed'
        or item['license'].strip().casefold().startswith('unknown')
    ]
    if invalid:
        raise AssetReleaseError(
            'release set contains unapproved or unlicensed packages: ' + ', '.join(invalid)
        )


def activate_release_set(
    store: Path,
    release_set_id: str,
    *,
    actor: str,
    activated_at: str | None = None,
) -> dict[str, Any]:
    release_set_id = _identifier(release_set_id, 'release_set_id')
    actor = _text(actor, 'actor', 128)
    now = activated_at or datetime.now().astimezone().isoformat(timespec='seconds')
    _timestamp(now, 'activated_at')
    with _locked_store(store) as root:
        value, verified = _load_installed_release_set(root, release_set_id)
        _activation_ready(value, verified)
        current = _read_state(root)
        if current and current['active_release_set'] == release_set_id:
            return {**current, 'changed': False, 'release_set': verified}
        body = _state_body(
            release_set_id,
            current['active_release_set'] if current else None,
            actor=actor,
            activated_at=now,
        )
        return {**_write_state(root, body), 'changed': True, 'release_set': verified}


def rollback_release_set(
    store: Path,
    *,
    actor: str,
    activated_at: str | None = None,
) -> dict[str, Any]:
    actor = _text(actor, 'actor', 128)
    now = activated_at or datetime.now().astimezone().isoformat(timespec='seconds')
    _timestamp(now, 'activated_at')
    with _locked_store(store) as root:
        current = _read_state(root)
        if not current or not current['previous_release_set']:
            raise AssetReleaseError('no previous release set is available for rollback')
        target_id = current['previous_release_set']
        value, verified = _load_installed_release_set(root, target_id)
        _activation_ready(value, verified)
        body = _state_body(
            target_id,
            current['active_release_set'],
            actor=actor,
            activated_at=now,
        )
        return {**_write_state(root, body), 'changed': True, 'release_set': verified}


def status(store: Path) -> dict[str, Any]:
    with _locked_store(store) as root:
        state = _read_state(root)
        active = None
        if state:
            _, active = _load_installed_release_set(root, state['active_release_set'])
        package_count = 0
        partials = []
        packages_root = root / 'packages'
        for type_path in packages_root.iterdir():
            if type_path.name.startswith('.partial-'):
                partials.append(type_path.relative_to(root).as_posix())
                continue
            if type_path.is_symlink() or not type_path.is_dir():
                raise AssetReleaseError('asset store package inventory is invalid')
            for asset_path in type_path.iterdir():
                if asset_path.name.startswith('.partial-'):
                    partials.append(asset_path.relative_to(root).as_posix())
                    continue
                if asset_path.is_symlink() or not asset_path.is_dir():
                    raise AssetReleaseError('asset store package inventory is invalid')
                for version_path in asset_path.iterdir():
                    if version_path.name.startswith('.partial-'):
                        partials.append(version_path.relative_to(root).as_posix())
                        continue
                    if version_path.is_symlink() or not version_path.is_dir():
                        raise AssetReleaseError('asset store package inventory is invalid')
                    manifest_path = version_path / MANIFEST_NAME
                    if not manifest_path.is_file() or manifest_path.is_symlink():
                        raise AssetReleaseError('installed asset package manifest is unavailable')
                    package_count += 1
        release_sets_root = root / 'release-sets'
        release_set_count = 0
        for path in release_sets_root.iterdir():
            if path.name.startswith('.partial-'):
                partials.append(path.relative_to(root).as_posix())
            elif path.suffix == '.json' and path.is_file() and not path.is_symlink():
                release_set_count += 1
            else:
                raise AssetReleaseError('asset store release set inventory is invalid')
        return {
            'state': state,
            'active': active,
            'installed_packages': package_count,
            'installed_release_sets': release_set_count,
            'incomplete_imports': sorted(partials),
        }


def require_draining(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        raise AssetReleaseError('--admission-state must be an absolute path')
    try:
        value = read_admission_state(path)
    except AdmissionError as error:
        raise AssetReleaseError(f'admission state is invalid: {error}') from error
    if value['admission'] != 'draining':
        raise AssetReleaseError('asset activation and rollback require admission draining')
    return value


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError('value must be positive')
    return parsed


def _non_negative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError('value must not be negative')
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', required=True, type=Path)
    parser.add_argument('--admission-state', type=Path)
    subparsers = parser.add_subparsers(dest='command', required=True)
    verify = subparsers.add_parser('verify-package')
    verify.add_argument('source', type=Path)
    verify.add_argument('--max-bytes', type=_positive, required=True)
    import_asset = subparsers.add_parser('import-package')
    import_asset.add_argument('source', type=Path)
    import_asset.add_argument('--max-bytes', type=_positive, required=True)
    import_asset.add_argument('--min-free-bytes', type=_non_negative, required=True)
    import_set = subparsers.add_parser('import-set')
    import_set.add_argument('source', type=Path)
    activate = subparsers.add_parser('activate')
    activate.add_argument('release_set_id')
    activate.add_argument('--actor', required=True)
    rollback = subparsers.add_parser('rollback')
    rollback.add_argument('--actor', required=True)
    subparsers.add_parser('status')
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify-package':
            result = verify_package(args.source, max_bytes=args.max_bytes)
        elif args.command == 'import-package':
            result = import_package(
                args.source,
                args.store,
                max_bytes=args.max_bytes,
                min_free_bytes=args.min_free_bytes,
            )
        elif args.command == 'import-set':
            result = import_release_set(args.source, args.store)
        elif args.command == 'activate':
            if args.admission_state is None:
                raise AssetReleaseError('activate requires --admission-state')
            require_draining(args.admission_state)
            result = activate_release_set(args.store, args.release_set_id, actor=args.actor)
        elif args.command == 'rollback':
            if args.admission_state is None:
                raise AssetReleaseError('rollback requires --admission-state')
            require_draining(args.admission_state)
            result = rollback_release_set(args.store, actor=args.actor)
        else:
            result = status(args.store)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, AssetReleaseError) as error:
        print(f'BioAgent asset release error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
