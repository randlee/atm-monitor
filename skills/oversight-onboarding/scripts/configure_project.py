#!/usr/bin/env python3
"""Create/update deployment project settings, preserving other teams and options."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime


@contextmanager
def locked(path):
    with path.open('a+b') as stream:
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            if path.stat().st_size == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def configure(path, team, repo, phase, start_time, evidence, worktrees=None):
    path = Path(path).resolve()
    if datetime.fromisoformat(start_time.replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('start_time must include a timezone')
    if not team.strip() or not evidence.strip() or not phase.strip():
        raise ValueError('team, phase and start-time evidence are required')
    repo = Path(repo).resolve()
    if not repo.is_dir():
        raise ValueError('repo does not exist: ' + str(repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path.parent / ('.' + path.name + '.lock')):
        data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version': 1, 'teams': []}
        if data.get('schema_version') != 1 or not isinstance(data.get('teams'), list):
            raise ValueError('config requires schema_version 1 and a teams array')
        matches = [row for row in data['teams'] if row['name'] == team]
        if len(matches) > 1:
            raise ValueError('duplicate team settings')
        entry = matches[0] if matches else {'name': team, 'worktrees': []}
        if matches and (path.parent / entry['repo']).resolve() != repo:
            raise ValueError('team already monitors another repository; reconcile catalog first')
        projects = entry.setdefault('projects', [])
        if not isinstance(projects, list):
            raise ValueError('projects must be an array')
        existing = [p for p in projects if p['phase'] == phase]
        if len(existing) > 1:
            raise ValueError('duplicate phase settings')
        project = existing[0] if existing else {'phase': phase}
        if existing and project['start_time'] != start_time:
            raise ValueError('existing phase start differs; reconcile evidence before changing its boundary')
        project.update(start_time=start_time, start_time_evidence=evidence)
        if worktrees is not None:
            project['worktrees'] = [str(Path(w).resolve()) for w in worktrees]
        if not existing:
            projects.append(project)
        entry['repo'] = str(repo)
        if not matches:
            data['teams'].append(entry)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix='.project-settings-', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return dict(team=team, repo=str(repo), **project)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--team', required=True)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--phase', required=True)
    parser.add_argument('--worktree', action='append', type=Path, help='repeat for locally accessible phase worktrees')
    parser.add_argument('--start-time', required=True)
    parser.add_argument('--evidence', required=True, help='plan path, task/message ID, or user-provided start')
    args = parser.parse_args()
    try:
        entry = configure(args.config, args.team, args.repo, args.phase, args.start_time, args.evidence, args.worktree)
        print(json.dumps({'status': 'configured', 'project': entry}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
