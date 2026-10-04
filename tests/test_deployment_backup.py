from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from deployment_backup import (
    BackupError,
    _rsync_command,
    create_backup,
    inspect_database,
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
