from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from deployment_backup import (
    BackupError,
    _rsync_command,
    apply_retention,
    create_backup,
    inspect_database,
    retention_plan,
    stage_restore,
    verify_backup,
)
from deployment_profile import load_profile

ROOT = Path(__file__).parents[1]


def _citation() -> dict:
    return {
        'type': 'analysis_knowledge_citations',
        'id': 'citation-block',
        'schema_version': 1,
        'status': 'completed',
        'release_id': 'engineering-knowledge-v4',
        'snapshot_id': 'engineering-knowledge-v4@sha256:test',
        'scope': 'engineering_contract',
        'query': 'fastp 参数',
        'citations': [
            {
                'citation_id': 'ENG-K08',
                'corpus': 'tools_databases',
                'source': 'bioagent://capability-catalog',
                'source_version': 'schema-v2@sha256:test',
                'locator': '$.capabilities[0]',
                'excerpt': '受控参数。',
                'quality': 'verified',
                'review_status': 'approved',
            }
        ],
    }


def _database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            '''
            CREATE TABLE analysis_project (id TEXT PRIMARY KEY);
            CREATE TABLE analysis_project_member (project_id TEXT, user_id TEXT);
            CREATE TABLE chat (id TEXT PRIMARY KEY, project_id TEXT, chat TEXT);
            CREATE TABLE analysis_dataset (id TEXT PRIMARY KEY, project_id TEXT);
            CREATE TABLE analysis_plan (id TEXT PRIMARY KEY, chat_id TEXT);
            CREATE TABLE analysis_plan_execution (
                id TEXT PRIMARY KEY, plan_id TEXT, run_id TEXT
            );
            CREATE TABLE analysis_assessment_revision (
                id TEXT PRIMARY KEY, project_id TEXT, chat_id TEXT, run_id TEXT
            );
            CREATE TABLE analysis_review_event (
                id TEXT PRIMARY KEY, project_id TEXT, chat_id TEXT,
                assessment_revision_id TEXT
            );
            CREATE TABLE analysis_review_computation_proposal (
                id TEXT PRIMARY KEY, project_id TEXT, chat_id TEXT,
                assessment_revision_id TEXT
            );
            INSERT INTO analysis_project VALUES ('project-1');
            INSERT INTO analysis_project_member VALUES ('project-1', 'user-1');
            INSERT INTO analysis_dataset VALUES ('dataset-1', 'project-1');
            INSERT INTO analysis_plan VALUES ('plan-1', 'chat-1');
            '''
        )
        connection.execute(
            'INSERT INTO chat VALUES (?, ?, ?)',
            ('chat-1', 'project-1', json.dumps({'output': [_citation()]})),
        )


def _profile(tmp_path: Path) -> Path:
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'release.json').write_text('{"release":"test"}\n')
    database = tmp_path / 'webui.db'
    _database(database)
    profile = json.loads(
        (ROOT / 'deployment/profiles/cyclone-development.json').read_text()
    )
    profile['storage']['application_root'] = str(tmp_path / 'application')
    profile['storage']['asset_root'] = str(assets)
    profile['operations']['business_db'] = str(database)
    profile['operations']['backup_root'] = str(tmp_path / 'backups')
    profile['resources']['backup_max_gib'] = 1
    profile_path = tmp_path / 'profile.json'
    profile_path.write_text(json.dumps(profile))
    return profile_path


def test_create_verify_and_stage_restore_are_content_checked(tmp_path: Path) -> None:
    profile_path = _profile(tmp_path)
    backup = create_backup(profile_path, 'backup-test')

    summary = verify_backup(backup)
    assert summary['projects'] == 1
    assert summary['members'] == 1
    assert summary['citations'] == 1
    assert summary['runs'] == 0
    assert summary['relationship_checks'] == 10

    restored = stage_restore(backup, tmp_path / 'restored')
    assert verify_backup(restored) == summary
    assert inspect_database(restored / 'business/webui.db')['citation_blocks'] == 1


def test_verify_rejects_content_change_and_existing_restore_target(tmp_path: Path) -> None:
    backup = create_backup(_profile(tmp_path), 'backup-test')
    with pytest.raises(BackupError, match='destination already exists'):
        stage_restore(backup, backup)

    (backup / 'assets/release.json').write_text('{"release":"changed"}\n')

    with pytest.raises(BackupError, match='identity mismatch'):
        verify_backup(backup)


def test_database_inspection_rejects_orphan_and_invalid_citation(tmp_path: Path) -> None:
    profile_path = _profile(tmp_path)
    database = Path(json.loads(profile_path.read_text())['operations']['business_db'])
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO analysis_project_member VALUES ('missing', 'user-2')"
        )
    with pytest.raises(BackupError, match='member_project'):
        inspect_database(database)

    database.unlink()
    _database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            'UPDATE chat SET chat = ?',
            (json.dumps({'type': 'analysis_knowledge_citations'}),),
        )
    with pytest.raises(BackupError, match='citation block'):
        inspect_database(database)


def test_remote_snapshot_command_has_fixed_ssh_and_bounded_includes(tmp_path: Path) -> None:
    profile = load_profile(_profile(tmp_path))
    command = _rsync_command(profile, 'analysis-safe-run', tmp_path / 'run')

    assert '--protect-args' in command
    assert '--safe-links' in command
    assert 'ssh -o ClearAllForwardings=yes' in command
    assert '--include=/.bioagent/state.json' in command
    assert '--include=/reports/***' in command
    assert command[-2].startswith('Cyclone:/data/user/liufangzhou/runs/')


def test_retention_requires_exact_plan_before_pruning_verified_snapshots(
    tmp_path: Path,
) -> None:
    profile_path = _profile(tmp_path)
    profile = json.loads(profile_path.read_text())
    profile['operations']['backup_retention_count'] = 2
    profile_path.write_text(json.dumps(profile))
    backups = tmp_path / 'retention'
    for name in ('backup-1', 'backup-2', 'backup-3'):
        create_backup(profile_path, name, output_root=backups)

    plan = retention_plan(profile_path, output_root=backups)
    assert [item['name'] for item in plan['keep']] == ['backup-3', 'backup-2']
    assert [item['name'] for item in plan['delete']] == ['backup-1']
    assert plan['reclaimable_bytes'] > 0
    with pytest.raises(BackupError, match='inventory changed'):
        apply_retention(profile_path, '0' * 64, output_root=backups)
    assert (backups / 'backup-1').is_dir()

    result = apply_retention(profile_path, plan['sha256'], output_root=backups)
    assert [item['name'] for item in result['deleted']] == ['backup-1']
    assert result['deleted_bytes'] == plan['reclaimable_bytes']
    assert result['remaining'] == 2
    assert not (backups / 'backup-1').exists()
    assert [item['name'] for item in retention_plan(profile_path, output_root=backups)['keep']] == [
        'backup-3',
        'backup-2',
    ]


def test_retention_fails_closed_on_unknown_or_incomplete_inventory(
    tmp_path: Path,
) -> None:
    profile_path = _profile(tmp_path)
    backups = tmp_path / 'retention'
    create_backup(profile_path, 'backup-1', output_root=backups)
    (backups / 'unexpected.txt').write_text('not managed')
    with pytest.raises(BackupError, match='unexpected entry'):
        retention_plan(profile_path, output_root=backups)
    (backups / 'unexpected.txt').unlink()
    (backups / '.partial-interrupted').mkdir()
    with pytest.raises(BackupError, match='incomplete operation'):
        retention_plan(profile_path, output_root=backups)


def test_retention_fails_closed_on_invalid_or_foreign_snapshot(
    tmp_path: Path,
) -> None:
    profile_path = _profile(tmp_path)
    backups = tmp_path / 'retention'
    backup = create_backup(profile_path, 'backup-1', output_root=backups)
    (backup / 'assets/release.json').write_text('{"release":"changed"}\n')
    with pytest.raises(BackupError, match='identity mismatch'):
        retention_plan(profile_path, output_root=backups)

    backup = tmp_path / 'foreign'
    create_backup(profile_path, 'backup-1', output_root=backup)
    profile = json.loads(profile_path.read_text())
    profile['profile_id'] = 'another-profile'
    profile_path.write_text(json.dumps(profile))
    with pytest.raises(BackupError, match='belongs to another profile'):
        retention_plan(profile_path, output_root=backup)
