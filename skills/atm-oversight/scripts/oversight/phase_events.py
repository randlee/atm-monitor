#!/usr/bin/env python3
"""Append and inspect immutable, idempotent phase event records."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cron'))
from state_store import BusyError, locked


_REQUIRED = ('event_id', 'team', 'repo', 'phase', 'kind', 'occurred_at', 'evidence', 'payload')
_IDENTITY = _REQUIRED


def _validate(event):
    if not isinstance(event, dict):
        raise ValueError('event must be an object')
    missing = [key for key in _REQUIRED if key not in event]
    if missing:
        raise ValueError('missing event fields: ' + ', '.join(missing))
    for key in ('event_id', 'team', 'repo', 'phase', 'kind'):
        if not isinstance(event[key], str) or not event[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    if not isinstance(event['evidence'], list) or not event['evidence']:
        raise ValueError('evidence must be a nonempty array')
    if any(not isinstance(item, str) or not item.strip() for item in event['evidence']):
        raise ValueError('evidence entries must be nonempty references')
    if not isinstance(event['payload'], dict):
        raise ValueError('payload must be an object')
    if not isinstance(event['occurred_at'], str) or not event['occurred_at'].strip():
        raise ValueError('occurred_at must be a timezone-aware ISO timestamp')
    try:
        timestamp = event['occurred_at'].replace('Z', '+00:00')
        if datetime.fromisoformat(timestamp).tzinfo is None:
            raise ValueError
    except ValueError as exc:
        raise ValueError('occurred_at must be a timezone-aware ISO timestamp') from exc


def _identity(event):
    return {key: event[key] for key in _IDENTITY}


def _event_files(state_dir):
    folder = Path(state_dir) / 'events'
    paths = sorted(folder.glob('*.json'))
    rows = []
    for path in paths:
        try:
            sequence = int(path.stem)
        except ValueError as exc:
            raise ValueError(f'invalid event filename: {path.name}') from exc
        if sequence < 1 or len(path.stem) != 12:
            raise ValueError(f'invalid event filename: {path.name}')
        rows.append((sequence, path))
    if len({sequence for sequence, _ in rows}) != len(rows):
        raise ValueError('duplicate event sequence')
    rows.sort()
    return rows


def _read_events(state_dir):
    events = []
    for expected, (sequence, path) in enumerate(_event_files(state_dir), 1):
        if sequence != expected:
            raise ValueError(f'event sequence gap before {path.name}')
        try:
            event = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f'corrupt event log: {path.name}') from exc
        _validate(event)
        if event.get('seq') != sequence or not isinstance(event.get('observed_at'), str):
            raise ValueError(f'invalid writer metadata: {path.name}')
        events.append(event)
    return events


def _fsync_directory(folder):
    if os.name != 'nt' and hasattr(os, 'O_DIRECTORY'):
        fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def append(state_dir, event):
    """Append *event*, returning the stored record; duplicate IDs are idempotent."""
    _validate(event)
    directory = Path(state_dir)
    with locked(directory):
        existing = _read_events(directory)
        for prior in existing:
            if prior['event_id'] == event['event_id']:
                if _identity(prior) != _identity(event):
                    raise ValueError('event_id already exists with conflicting content')
                return prior
        sequence = (existing[-1]['seq'] if existing else 0) + 1
        stored = dict(_identity(event), observed_at=datetime.now(timezone.utc).isoformat(), seq=sequence)
        folder = directory / 'events'
        folder.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.writing-', dir=folder)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as out:
                json.dump(stored, out, ensure_ascii=True, separators=(',', ':'))
                out.write('\n')
                out.flush()
                os.fsync(out.fileno())
            destination = folder / f'{sequence:012d}.json'
            os.replace(name, destination)
            _fsync_directory(folder)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return stored


def list_events(state_dir, team=None, repo=None, phase=None):
    """Return validated events in writer sequence order, optionally filtered."""
    events = _read_events(Path(state_dir))
    return [event for event in events
            if (team is None or event['team'] == team)
            and (repo is None or event['repo'] == repo)
            and (phase is None or event['phase'] == phase)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    append_parser = sub.add_parser('append')
    append_parser.add_argument('--state-dir', type=Path, required=True)
    append_parser.add_argument('--event-file', type=Path, required=True)
    list_parser = sub.add_parser('list')
    list_parser.add_argument('--state-dir', type=Path, required=True)
    list_parser.add_argument('--team')
    list_parser.add_argument('--repo')
    list_parser.add_argument('--phase')
    list_parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args()
    try:
        if args.command == 'append':
            event = json.loads(args.event_file.read_text(encoding='utf-8'))
            result = append(args.state_dir, event)
            print(json.dumps({'status': 'ok', 'event': result}, ensure_ascii=False))
        else:
            result = list_events(args.state_dir, args.team, args.repo, args.phase)
            if args.as_json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                for event in result:
                    print(json.dumps(event, ensure_ascii=False))
        return 0
    except (ValueError, OSError, BusyError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
