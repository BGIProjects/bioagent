#!/usr/bin/env python3
"""Validate BioAgent source locks and target-specific offline installation media."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

INSTALL_SCHEMA_VERSION = 1
MEDIA_SCHEMA_VERSION = 1
SHA256 = re.compile(r'^[0-9a-f]{64}$')
PINNED_REQUIREMENT = re.compile(
    r'^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?==[^=\s]+$'
)
MAX_LOCK_BYTES = 64 * 1024 * 1024


class PreflightError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_LOCK_BYTES:
            raise PreflightError(f'JSON file size is invalid: {path.name}')
        return json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PreflightError(f'JSON file is invalid: {path.name}') from error


def _text(value: Any, name: str, maximum: int = 500) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(character in value for character in ('\0', '\n', '\r'))
    ):
        raise PreflightError(f'{name} is invalid')
    return value


def _relative(value: Any, name: str) -> PurePosixPath:
    text = _text(value, name)
    path = PurePosixPath(text)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise PreflightError(f'{name} must be a safe relative path')
    return path


def load_install_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise PreflightError('offline install manifest must be a regular file')
    value = _load_json(path)
    fields = {
        'schema_version',
        'python_version',
        'node_version',
        'source_locks',
        'required_media',
        'model',
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise PreflightError('offline install manifest fields are invalid')
    if value['schema_version'] != INSTALL_SCHEMA_VERSION:
        raise PreflightError('offline install manifest schema is unsupported')
    _text(value['python_version'], 'python_version', 20)
    _text(value['node_version'], 'node_version', 20)
    locks = value['source_locks']
    if not isinstance(locks, list) or not locks:
        raise PreflightError('source_locks must be a non-empty list')
    lock_components = []
    for item in locks:
        if not isinstance(item, dict) or set(item) != {'component', 'path', 'format'}:
            raise PreflightError('source lock entry is invalid')
        lock_components.append(_text(item['component'], 'source lock component', 100))
        _relative(item['path'], 'source lock path')
        if item['format'] not in {'pip-freeze', 'uv-lock', 'npm-lock-v3'}:
            raise PreflightError('source lock format is unsupported')
    if len(lock_components) != len(set(lock_components)):
        raise PreflightError('source lock components must be unique')
    media = value['required_media']
    if not isinstance(media, list) or not media:
        raise PreflightError('required_media must be a non-empty list')
    media_components = []
    for item in media:
        if not isinstance(item, dict) or set(item) != {'component', 'purpose'}:
            raise PreflightError('required media entry is invalid')
        media_components.append(_text(item['component'], 'media component', 100))
        _text(item['purpose'], 'media purpose')
    if len(media_components) != len(set(media_components)):
        raise PreflightError('required media components must be unique')
    model = value['model']
    if not isinstance(model, dict) or set(model) != {
        'provider',
        'mode',
        'offline_capable',
        'blocker',
    }:
        raise PreflightError('model declaration fields are invalid')
    _text(model['provider'], 'model provider', 100)
    if model['mode'] not in {'external', 'local'} or not isinstance(
        model['offline_capable'], bool
    ):
        raise PreflightError('model declaration is invalid')
    _text(model['blocker'], 'model blocker')
    if model['mode'] == 'external' and model['offline_capable']:
        raise PreflightError('external model service cannot be declared offline capable')
    return value


def _source_path(root: Path, relative: PurePosixPath) -> Path:
    path = root.joinpath(*relative.parts)
    root_resolved = root.resolve()
    try:
        path.resolve().relative_to(root_resolved)
    except ValueError as error:
        raise PreflightError('source lock escapes source root') from error
    if not path.is_file() or path.is_symlink():
        raise PreflightError(f'source lock is unavailable: {relative.as_posix()}')
    if path.stat().st_size > MAX_LOCK_BYTES:
        raise PreflightError(f'source lock is too large: {relative.as_posix()}')
    return path


def _inspect_pip_freeze(path: Path) -> dict[str, int]:
    requirements = []
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if not PINNED_REQUIREMENT.fullmatch(line):
            raise PreflightError(f'unpinned or unsupported requirement: {line}')
        requirements.append(line.casefold())
    if not requirements or len(requirements) != len(set(requirements)):
        raise PreflightError('pip freeze lock is empty or contains duplicates')
    return {'packages': len(requirements)}


def _inspect_uv_lock(path: Path) -> dict[str, int]:
    text = path.read_text(encoding='utf-8')
    packages = text.count('[[package]]')
    hashes = len(re.findall(r'hash = "sha256:[0-9a-f]{64}"', text))
    if not text.startswith('version = 1\n') or packages < 1 or hashes < packages:
        raise PreflightError('uv lock does not contain a complete hashed package graph')
    return {'packages': packages, 'artifact_hashes': hashes}


def _inspect_npm_lock(path: Path) -> dict[str, int]:
    value = _load_json(path)
    if not isinstance(value, dict):
        raise PreflightError('npm lock must use lockfileVersion 3')
    packages = value.get('packages')
    if value.get('lockfileVersion') != 3 or not isinstance(packages, dict):
        raise PreflightError('npm lock must use lockfileVersion 3')
    locked = 0
    integrity = 0
    for package_path, package in packages.items():
        if package_path == '':
            continue
        if not isinstance(package, dict):
            raise PreflightError('npm lock package entry is invalid')
        locked += 1
        package_integrity = package.get('integrity')
        if (
            package.get('link') is True
            or package.get('inBundle') is True
            or (isinstance(package_integrity, str) and bool(package_integrity))
        ):
            integrity += 1
    if not locked or integrity != locked:
        raise PreflightError('npm lock contains packages without integrity identity')
    return {'packages': locked, 'artifact_identities': integrity}


def inspect_source_locks(manifest: dict[str, Any], source_root: Path) -> dict[str, Any]:
    inspectors = {
        'pip-freeze': _inspect_pip_freeze,
        'uv-lock': _inspect_uv_lock,
        'npm-lock-v3': _inspect_npm_lock,
    }
    values = []
    total_bytes = 0
    for item in manifest['source_locks']:
        relative = _relative(item['path'], 'source lock path')
        path = _source_path(source_root, relative)
        size = path.stat().st_size
        total_bytes += size
        values.append(
            {
                'component': item['component'],
                'path': relative.as_posix(),
                'format': item['format'],
                'size': size,
                'sha256': _sha256(path),
                **inspectors[item['format']](path),
            }
        )
    return {
        'status': 'ready',
        'python_version': manifest['python_version'],
        'node_version': manifest['node_version'],
        'files': values,
        'total_bytes': total_bytes,
    }


def verify_media(
    manifest: dict[str, Any], media_root: Path
) -> dict[str, Any]:
    if media_root.is_symlink():
        raise PreflightError('offline media root must not be a symlink')
    root = media_root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise PreflightError('offline media root is unavailable')
    media_manifest_path = root / 'media-manifest.json'
    if not media_manifest_path.is_file() or media_manifest_path.is_symlink():
        raise PreflightError('media manifest must be a regular file')
    value = _load_json(media_manifest_path)
    fields = {'schema_version', 'platform', 'architecture', 'created_at', 'files'}
    if not isinstance(value, dict) or set(value) != fields:
        raise PreflightError('media manifest fields are invalid')
    if value['schema_version'] != MEDIA_SCHEMA_VERSION:
        raise PreflightError('media manifest schema is unsupported')
    _text(value['platform'], 'media platform', 100)
    _text(value['architecture'], 'media architecture', 100)
    created_at = _text(value['created_at'], 'media created_at', 64)
    try:
        parsed_created_at = datetime.fromisoformat(created_at)
    except ValueError as error:
        raise PreflightError('media created_at is invalid') from error
    if parsed_created_at.tzinfo is None:
        raise PreflightError('media created_at must include a timezone')
    files = value['files']
    if not isinstance(files, list):
        raise PreflightError('media file list is invalid')
    expected_components = {item['component'] for item in manifest['required_media']}
    seen_components = set()
    seen_paths = set()
    total_bytes = 0
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {
            'component',
            'path',
            'size',
            'sha256',
        }:
            raise PreflightError('media file entry is invalid')
        component = _text(entry['component'], 'media file component', 100)
        relative = _relative(entry['path'], 'media file path')
        if component in seen_components or relative.as_posix() in seen_paths:
            raise PreflightError('media components and paths must be unique')
        seen_components.add(component)
        seen_paths.add(relative.as_posix())
        path = _source_path(root, relative)
        if (
            not isinstance(entry['size'], int)
            or isinstance(entry['size'], bool)
            or entry['size'] < 0
            or not isinstance(entry['sha256'], str)
            or not SHA256.fullmatch(entry['sha256'])
            or path.stat().st_size != entry['size']
            or _sha256(path) != entry['sha256']
        ):
            raise PreflightError(f'media file identity mismatch: {relative.as_posix()}')
        total_bytes += entry['size']
    if seen_components != expected_components:
        missing = sorted(expected_components - seen_components)
        extra = sorted(seen_components - expected_components)
        raise PreflightError(f'media component mismatch; missing={missing}, extra={extra}')
    paths = list(root.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise PreflightError('offline media must not contain symlinks')
    actual_files = {
        path.relative_to(root).as_posix()
        for path in paths
        if path.is_file() and path != media_manifest_path
    }
    if actual_files != seen_paths:
        raise PreflightError('offline media contains missing or unexpected files')
    return {
        'status': 'ready',
        'platform': value['platform'],
        'architecture': value['architecture'],
        'components': len(seen_components),
        'total_bytes': total_bytes,
    }


def readiness(
    manifest: dict[str, Any],
    source_root: Path,
    media_root: Path | None,
) -> dict[str, Any]:
    source = inspect_source_locks(manifest, source_root)
    blockers = []
    media = None
    if media_root is None:
        blockers.extend(
            f'MISSING_MEDIA:{item["component"]}' for item in manifest['required_media']
        )
    else:
        try:
            media = verify_media(manifest, media_root)
        except PreflightError as error:
            blockers.append(f'MEDIA_INVALID:{error}')
    if not manifest['model']['offline_capable']:
        blockers.append('MODEL_NOT_OFFLINE_CAPABLE')
    return {
        'source_locks': source,
        'media': media,
        'deterministic_install_ready': media is not None,
        'full_offline_ready': media is not None and not blockers,
        'model': manifest['model'],
        'blockers': blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--manifest',
        type=Path,
        default=Path(__file__).parent / 'deployment/offline-install-manifest.json',
    )
    parser.add_argument('--source-root', type=Path, default=Path(__file__).parent)
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('source')
    verify = subparsers.add_parser('verify-media')
    verify.add_argument('media_root', type=Path)
    check = subparsers.add_parser('check')
    check.add_argument('--media-root', type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = load_install_manifest(args.manifest)
        if args.command == 'source':
            result = inspect_source_locks(manifest, args.source_root)
            exit_code = 0
        elif args.command == 'verify-media':
            result = verify_media(manifest, args.media_root)
            exit_code = 0
        else:
            result = readiness(manifest, args.source_root, args.media_root)
            exit_code = 0 if result['full_offline_ready'] else 3
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return exit_code
    except (OSError, PreflightError) as error:
        print(f'BioAgent deployment preflight error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
