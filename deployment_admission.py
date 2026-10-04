#!/usr/bin/env python3
"""Inspect or atomically change BioAgent analysis admission state."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deployment_profile import ProfileError, load_profile

STATE_SCHEMA_VERSION = 1
MAX_STATE_BYTES = 8192
SHA256 = re.compile(r'^[0-9a-f]{64}$')


class AdmissionError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')


def _text(value: Any, name: str, maximum: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise AdmissionError(f'{name} must be a string')
    text = value.strip()
    if len(text) > maximum or any(character in text for character in ('\0', '\n', '\r')):
        raise AdmissionError(f'{name} is invalid')
    return text


def validate_state(value: Any) -> dict[str, Any]:
    fields = {
        'schema_version',
        'admission',
        'reason',
        'updated_at',
        'updated_by',
        'state_sha256',
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise AdmissionError('admission state fields are invalid')
    if value['schema_version'] != STATE_SCHEMA_VERSION:
        raise AdmissionError('admission state schema is unsupported')
    if value['admission'] not in {'accepting', 'draining'}:
        raise AdmissionError('admission state must be accepting or draining')
    reason = _text(
        value['reason'],
        'reason',
        500,
        allow_empty=value['admission'] == 'accepting',
    )
    updated_by = _text(value['updated_by'], 'updated_by', 100)
    updated_at = _text(value['updated_at'], 'updated_at', 64)
    try:
        parsed = datetime.fromisoformat(updated_at)
    except ValueError as error:
        raise AdmissionError('updated_at is invalid') from error
    if parsed.tzinfo is None:
        raise AdmissionError('updated_at must include a timezone')
    state_sha256 = value['state_sha256']
    if not isinstance(state_sha256, str) or not SHA256.fullmatch(state_sha256):
        raise AdmissionError('state_sha256 is invalid')
    unsigned = {
        'schema_version': STATE_SCHEMA_VERSION,
        'admission': value['admission'],
        'reason': reason,
        'updated_at': updated_at,
        'updated_by': updated_by,
    }
    if hashlib.sha256(_canonical(unsigned)).hexdigest() != state_sha256:
        raise AdmissionError('admission state digest mismatch')
    return {**unsigned, 'state_sha256': state_sha256}


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            'schema_version': STATE_SCHEMA_VERSION,
            'admission': 'accepting',
            'reason': '',
            'updated_at': None,
            'updated_by': None,
            'state_sha256': None,
            'source': 'default',
        }
    if not path.is_file() or path.is_symlink():
        raise AdmissionError('admission state must be a regular file')
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise AdmissionError('admission state is unreadable') from error
    if not raw or len(raw) > MAX_STATE_BYTES:
        raise AdmissionError('admission state size is invalid')
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AdmissionError('admission state JSON is invalid') from error
    return {**validate_state(value), 'source': 'file'}


def write_state(
    path: Path,
    admission: str,
    reason: str,
    *,
    updated_by: str | None = None,
) -> dict[str, Any]:
    if admission not in {'accepting', 'draining'}:
        raise AdmissionError('admission state must be accepting or draining')
    normalized_reason = _text(
        reason,
        'reason',
        500,
        allow_empty=admission == 'accepting',
    )
    operator = _text(updated_by or getpass.getuser(), 'updated_by', 100)
    unsigned = {
        'schema_version': STATE_SCHEMA_VERSION,
        'admission': admission,
        'reason': normalized_reason,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'updated_by': operator,
    }
    value = {
        **unsigned,
        'state_sha256': hashlib.sha256(_canonical(unsigned)).hexdigest(),
    }
    encoded = _canonical(value) + b'\n'
    if len(encoded) > MAX_STATE_BYTES:
        raise AdmissionError('admission state size is invalid')
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f'.admission-{uuid.uuid4().hex}.tmp'
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()
    return read_state(path)


def _state_path(args: argparse.Namespace) -> Path:
    if args.state_file is not None:
        if not args.state_file.is_absolute():
            raise AdmissionError('--state-file must be absolute')
        return args.state_file
    if args.profile is None:
        raise AdmissionError('provide --profile or --state-file')
    return Path(load_profile(args.profile)['operations']['admission_state_file'])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--profile', type=Path)
    source.add_argument('--state-file', type=Path)
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('status')
    drain = subparsers.add_parser('drain')
    drain.add_argument('--reason', required=True)
    resume = subparsers.add_parser('resume')
    resume.add_argument('--reason', default='维护完成')
    args = parser.parse_args(argv)
    try:
        path = _state_path(args)
        if args.command == 'status':
            value = read_state(path)
        else:
            value = write_state(path, 'draining' if args.command == 'drain' else 'accepting', args.reason)
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (AdmissionError, ProfileError, OSError) as error:
        print(f'BioAgent admission error: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
