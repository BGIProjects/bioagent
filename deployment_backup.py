#!/usr/bin/env python3
"""Create, verify, and stage-restore bounded BioAgent recovery snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from deployment_profile import ProfileError, load_profile

BACKUP_SCHEMA_VERSION = 1
SAFE_NAME = re.compile(r'^[a-z0-9][a-z0-9._-]{0,63}$')
SAFE_RUN_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$')
REQUIRED_TABLES = {
    'analysis_project',
    'analysis_project_member',
    'chat',
    'analysis_dataset',
    'analysis_plan',
    'analysis_plan_execution',
    'analysis_assessment_revision',
    'analysis_review_event',
    'analysis_review_computation_proposal',
}
RELATIONSHIP_CHECKS = {
    'member_project': '''
        SELECT count(*) FROM analysis_project_member child
        LEFT JOIN analysis_project parent ON parent.id = child.project_id
        WHERE parent.id IS NULL
    ''',
    'chat_project': '''
        SELECT count(*) FROM chat child
        LEFT JOIN analysis_project parent ON parent.id = child.project_id
        WHERE child.project_id IS NOT NULL AND parent.id IS NULL
    ''',
    'dataset_project': '''
        SELECT count(*) FROM analysis_dataset child
        LEFT JOIN analysis_project parent ON parent.id = child.project_id
        WHERE child.project_id IS NOT NULL AND parent.id IS NULL
    ''',
    'plan_chat': '''
        SELECT count(*) FROM analysis_plan child
        LEFT JOIN chat parent ON parent.id = child.chat_id
        WHERE parent.id IS NULL
    ''',
    'execution_plan': '''
        SELECT count(*) FROM analysis_plan_execution child
        LEFT JOIN analysis_plan parent ON parent.id = child.plan_id
        WHERE parent.id IS NULL
    ''',
    'assessment_project': '''
        SELECT count(*) FROM analysis_assessment_revision child
        LEFT JOIN analysis_project parent ON parent.id = child.project_id
        WHERE parent.id IS NULL
    ''',
    'assessment_chat': '''
        SELECT count(*) FROM analysis_assessment_revision child
        LEFT JOIN chat parent ON parent.id = child.chat_id
        WHERE parent.id IS NULL
    ''',
    'assessment_run': '''
        SELECT count(*) FROM analysis_assessment_revision child
        LEFT JOIN analysis_plan_execution execution ON execution.run_id = child.run_id
        LEFT JOIN analysis_plan plan ON plan.id = execution.plan_id
        WHERE execution.run_id IS NULL OR plan.chat_id != child.chat_id
    ''',
    'review_assessment': '''
        SELECT count(*) FROM analysis_review_event child
        LEFT JOIN analysis_assessment_revision parent
          ON parent.id = child.assessment_revision_id
        WHERE parent.id IS NULL
           OR parent.project_id != child.project_id
           OR parent.chat_id != child.chat_id
    ''',
    'proposal_assessment': '''
        SELECT count(*) FROM analysis_review_computation_proposal child
        LEFT JOIN analysis_assessment_revision parent
          ON parent.id = child.assessment_revision_id
        WHERE parent.id IS NULL
           OR parent.project_id != child.project_id
           OR parent.chat_id != child.chat_id
    ''',
}


class BackupError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BackupError(f'invalid JSON: {path.name}') from error


def _bounded_text(value: Any, maximum: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum


def _validate_citation_block(value: dict[str, Any]) -> None:
    if (
        value.get('schema_version') != 1
        or value.get('status') != 'completed'
        or value.get('scope') != 'engineering_contract'
        or not _bounded_text(value.get('id'), 200)
        or not _bounded_text(value.get('release_id'), 200)
        or not _bounded_text(value.get('snapshot_id'), 300)
        or not _bounded_text(value.get('query'), 500)
    ):
        raise BackupError('stored engineering citation block is invalid')
    citations = value.get('citations')
    if not isinstance(citations, list) or not 1 <= len(citations) <= 4:
        raise BackupError('stored engineering citation count is invalid')
    identifiers = []
    for citation in citations:
        if not isinstance(citation, dict):
            raise BackupError('stored engineering citation is invalid')
        identifier = citation.get('citation_id')
        if (
            not _bounded_text(identifier, 200)
            or not _bounded_text(citation.get('corpus'), 100)
            or not _bounded_text(citation.get('source'), 300)
            or not citation['source'].startswith('bioagent://')
            or not _bounded_text(citation.get('source_version'), 300)
            or not _bounded_text(citation.get('locator'), 500)
            or not citation['locator'].startswith('$')
            or not _bounded_text(citation.get('excerpt'), 512)
            or citation.get('quality') != 'verified'
            or citation.get('review_status') != 'approved'
        ):
            raise BackupError('stored engineering citation fields are invalid')
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise BackupError('stored engineering citation identifiers are duplicated')


def _citation_count(value: Any) -> int:
    if isinstance(value, dict):
        count = 0
        if value.get('type') == 'analysis_knowledge_citations':
            _validate_citation_block(value)
            count += 1
        return count + sum(_citation_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_citation_count(item) for item in value)
    return 0


def _connect_readonly(path: Path, *, immutable: bool = False) -> sqlite3.Connection:
    if not path.is_file() or path.is_symlink():
        raise BackupError('business database must be a regular file')
    immutable_query = '&immutable=1' if immutable else ''
    uri = f'file:{quote(str(path), safe="/")}?mode=ro{immutable_query}'
    connection = sqlite3.connect(uri, uri=True)
    connection.execute('PRAGMA query_only = ON')
    return connection


def inspect_database(path: Path, *, immutable: bool = False) -> dict[str, Any]:
    with closing(_connect_readonly(path, immutable=immutable)) as connection:
        quick_check = connection.execute('PRAGMA quick_check').fetchone()
        if quick_check != ('ok',):
            raise BackupError('business database quick_check failed')
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise BackupError(f'business database is missing tables: {", ".join(missing)}')
        counts = {
            table: int(connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0])
            for table in sorted(REQUIRED_TABLES)
        }
        orphans = {
            name: int(connection.execute(query).fetchone()[0])
            for name, query in RELATIONSHIP_CHECKS.items()
        }
        broken = [name for name, count in orphans.items() if count]
        if broken:
            raise BackupError(f'business relationship check failed: {", ".join(broken)}')
        run_ids = sorted(
            {
                str(row[0])
                for row in connection.execute(
                    '''
                    SELECT run_id FROM analysis_plan_execution
                    UNION SELECT run_id FROM analysis_assessment_revision
                    '''
                )
                if row[0]
            }
        )
        if any(not SAFE_RUN_ID.fullmatch(run_id) for run_id in run_ids):
            raise BackupError('business database contains an unsafe run identifier')
        citation_blocks = 0
        for (raw_chat,) in connection.execute(
            'SELECT chat FROM chat WHERE chat IS NOT NULL'
        ):
            try:
                citation_blocks += _citation_count(json.loads(raw_chat))
            except (TypeError, json.JSONDecodeError) as error:
                raise BackupError('stored chat JSON is invalid') from error
    return {
        'table_counts': counts,
        'relationship_orphans': orphans,
        'run_ids': run_ids,
        'citation_blocks': citation_blocks,
    }


def snapshot_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=False)
    with (
        closing(_connect_readonly(source)) as source_connection,
        closing(sqlite3.connect(destination)) as destination_connection,
    ):
        source_connection.backup(destination_connection)
        destination_connection.commit()
    inspect_database(destination, immutable=True)


def _copy_regular_tree(source: Path, destination: Path) -> None:
    if not source.is_dir() or source.is_symlink():
        raise BackupError(f'source directory is unavailable: {source}')
    destination.mkdir(parents=True, exist_ok=False)
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise BackupError(f'symlinks are not allowed in backup sources: {path}')
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        else:
            raise BackupError(f'non-regular backup source is not allowed: {path}')


def _rsync_command(profile: dict[str, Any], run_id: str, destination: Path) -> list[str]:
    compute = profile['compute']
    run_root = profile['storage']['run_root'].rstrip('/')
    return [
        'rsync',
        '--archive',
        '--no-owner',
        '--no-group',
        '--safe-links',
        '--protect-args',
        '--prune-empty-dirs',
        '--include=/.bioagent/',
        '--include=/.bioagent/state.json',
        '--include=/reports/',
        '--include=/reports/***',
        '--exclude=*',
        '--timeout=60',
        '-e',
        'ssh -o ClearAllForwardings=yes',
        f'{compute["ssh_host"]}:{run_root}/{run_id}/',
        f'{destination}/',
    ]


def snapshot_remote_run(
    profile: dict[str, Any],
    run_id: str,
    destination: Path,
    remaining_bytes: int,
) -> int:
    command = _rsync_command(profile, run_id, destination)
    dry_run = [*command[:-2], '--dry-run', '--out-format=%l\t%n', *command[-2:]]
    result = subprocess.run(dry_run, check=False, capture_output=True, text=True)
    if result.returncode:
        raise BackupError(f'remote run preflight failed for {run_id}')
    estimated_bytes = 0
    for line in result.stdout.splitlines():
        size, separator, _ = line.partition('\t')
        if separator and size.isdigit():
            estimated_bytes += int(size)
    if estimated_bytes > remaining_bytes:
        raise BackupError('backup would exceed the configured size limit')
    destination.mkdir(parents=True, exist_ok=False)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise BackupError(f'remote run snapshot failed for {run_id}')
    state = destination / '.bioagent' / 'state.json'
    if not state.is_file() or state.is_symlink():
        raise BackupError(f'remote run state is unavailable for {run_id}')
    return estimated_bytes


def _file_manifest(root: Path, maximum_bytes: int) -> tuple[list[dict[str, Any]], int]:
    files = []
    total = 0
    for path in sorted(root.rglob('*')):
        if path.name in {'manifest.json', 'manifest.sha256'} and path.parent == root:
            continue
        if path.is_symlink():
            raise BackupError(f'backup contains a symlink: {path.relative_to(root)}')
        if path.is_dir():
            continue
        if not path.is_file():
            raise BackupError(f'backup contains a non-regular file: {path.relative_to(root)}')
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        total += size
        if total > maximum_bytes:
            raise BackupError('backup exceeds the configured size limit')
        files.append({'path': relative, 'size': size, 'sha256': _sha256(path)})
    return files, total


def _safe_remove_partial(path: Path, parent: Path) -> None:
    if path.parent == parent and path.name.startswith('.partial-') and path.exists():
        shutil.rmtree(path)


def create_backup(
    profile_path: Path,
    name: str,
    *,
    output_root: Path | None = None,
) -> Path:
    if not SAFE_NAME.fullmatch(name):
        raise BackupError('backup name must use lowercase letters, digits, dot, dash, or underscore')
    profile = load_profile(profile_path)
    operations = profile['operations']
    configured_root = output_root or Path(operations['backup_root'])
    if not configured_root.is_absolute():
        raise BackupError('backup root must be absolute')
    root = configured_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / name
    if destination.exists():
        raise BackupError('backup destination already exists')
    partial = root / f'.partial-{uuid.uuid4().hex}'
    partial.mkdir(mode=0o700)
    maximum_bytes = profile['resources']['backup_max_gib'] * 1024**3
    try:
        database_path = Path(operations['business_db'])
        inspect_database(database_path)
        snapshot_database(database_path, partial / 'business' / 'webui.db')
        snapshot_inventory = inspect_database(
            partial / 'business' / 'webui.db', immutable=True
        )
        _copy_regular_tree(Path(profile['storage']['asset_root']), partial / 'assets')
        files, used_bytes = _file_manifest(partial, maximum_bytes)
        del files
        for run_id in snapshot_inventory['run_ids']:
            estimated = snapshot_remote_run(
                profile,
                run_id,
                partial / 'runs' / run_id,
                maximum_bytes - used_bytes,
            )
            used_bytes += estimated
        files, total_bytes = _file_manifest(partial, maximum_bytes)
        manifest = {
            'schema_version': BACKUP_SCHEMA_VERSION,
            'profile_id': profile['profile_id'],
            'profile_sha256': profile['profile_sha256'],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'business-assets-registered-runs',
            'retention_count': operations['backup_retention_count'],
            'maximum_bytes': maximum_bytes,
            'total_bytes': total_bytes,
            'database': snapshot_inventory,
            'files': files,
        }
        manifest_bytes = _json_bytes(manifest)
        (partial / 'manifest.json').write_bytes(manifest_bytes)
        (partial / 'manifest.sha256').write_text(
            f'{hashlib.sha256(manifest_bytes).hexdigest()}\n', encoding='ascii'
        )
        verify_backup(partial)
        partial.rename(destination)
        return destination
    except Exception:
        _safe_remove_partial(partial, root)
        raise


def _safe_manifest_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str):
        raise BackupError('manifest file path is invalid')
    relative = PurePosixPath(value)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise BackupError('manifest file path escapes the backup')
    path = root.joinpath(*relative.parts)
    if path.resolve().parent != root.resolve() and root.resolve() not in path.resolve().parents:
        raise BackupError('manifest file path escapes the backup')
    return path


def verify_backup(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise BackupError('backup directory is unavailable')
    manifest_path = root / 'manifest.json'
    digest_path = root / 'manifest.sha256'
    manifest_bytes = manifest_path.read_bytes()
    expected_digest = digest_path.read_text(encoding='ascii').strip()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_digest):
        raise BackupError('manifest digest file is invalid')
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_digest:
        raise BackupError('manifest digest mismatch')
    manifest = _load_json(manifest_path)
    required = {
        'schema_version',
        'profile_id',
        'profile_sha256',
        'created_at',
        'scope',
        'retention_count',
        'maximum_bytes',
        'total_bytes',
        'database',
        'files',
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise BackupError('manifest fields are invalid')
    if manifest['schema_version'] != BACKUP_SCHEMA_VERSION:
        raise BackupError('unsupported backup schema')
    if manifest['scope'] != 'business-assets-registered-runs':
        raise BackupError('backup scope is invalid')
    if not isinstance(manifest['files'], list):
        raise BackupError('backup file list is invalid')
    expected_paths = set()
    total_bytes = 0
    for entry in manifest['files']:
        if not isinstance(entry, dict) or set(entry) != {'path', 'size', 'sha256'}:
            raise BackupError('backup file entry is invalid')
        path = _safe_manifest_path(root, entry['path'])
        if entry['path'] in expected_paths:
            raise BackupError('backup file paths are duplicated')
        expected_paths.add(entry['path'])
        if not path.is_file() or path.is_symlink():
            raise BackupError(f'backup file is unavailable: {entry["path"]}')
        size = path.stat().st_size
        if size != entry['size'] or _sha256(path) != entry['sha256']:
            raise BackupError(f'backup file identity mismatch: {entry["path"]}')
        total_bytes += size
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob('*')
        if path.is_file() and path.name not in {'manifest.json', 'manifest.sha256'}
    }
    if actual_paths != expected_paths:
        raise BackupError('backup contains missing or unexpected files')
    if total_bytes != manifest['total_bytes'] or total_bytes > manifest['maximum_bytes']:
        raise BackupError('backup total size is invalid')
    database = inspect_database(root / 'business' / 'webui.db', immutable=True)
    if database != manifest['database']:
        raise BackupError('restored database inventory does not match the manifest')
    for run_id in database['run_ids']:
        state = root / 'runs' / run_id / '.bioagent' / 'state.json'
        if not state.is_file() or state.is_symlink():
            raise BackupError(f'backup is missing registered run state: {run_id}')
        _load_json(state)
    return {
        'profile_id': manifest['profile_id'],
        'files': len(expected_paths),
        'bytes': total_bytes,
        'runs': len(database['run_ids']),
        'projects': database['table_counts']['analysis_project'],
        'members': database['table_counts']['analysis_project_member'],
        'assessments': database['table_counts']['analysis_assessment_revision'],
        'citations': database['citation_blocks'],
        'relationship_checks': len(database['relationship_orphans']),
    }


def stage_restore(backup: Path, destination: Path) -> Path:
    verify_backup(backup)
    destination = destination.resolve()
    if destination.exists():
        raise BackupError('restore destination already exists')
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    partial = parent / f'.partial-{uuid.uuid4().hex}'
    try:
        shutil.copytree(backup, partial, symlinks=False)
        verify_backup(partial)
        partial.rename(destination)
        return destination
    except Exception:
        _safe_remove_partial(partial, parent)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    create = subparsers.add_parser('create')
    create.add_argument('profile', type=Path)
    create.add_argument('name')
    create.add_argument('--output-root', type=Path)
    verify = subparsers.add_parser('verify')
    verify.add_argument('backup', type=Path)
    restore = subparsers.add_parser('stage-restore')
    restore.add_argument('backup', type=Path)
    restore.add_argument('destination', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'create':
            path = create_backup(args.profile, args.name, output_root=args.output_root)
            summary = verify_backup(path)
            print(json.dumps({'path': str(path), **summary}, sort_keys=True))
        elif args.command == 'verify':
            print(json.dumps(verify_backup(args.backup), sort_keys=True))
        else:
            path = stage_restore(args.backup, args.destination)
            print(json.dumps({'path': str(path), **verify_backup(path)}, sort_keys=True))
    except (BackupError, ProfileError, OSError, sqlite3.Error) as error:
        print(f'BioAgent backup error: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
