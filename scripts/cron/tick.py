#!/usr/bin/env python3
"""Run one local collection tick; persist successful and failed observations."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sys

from collectors import collect
from discovery import discover
from state_store import BusyError, locked, read_latest, save


def load_config(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('teams'), list) or not data['teams']:
        raise ValueError('config requires schema_version: 1 and a nonempty teams array')
    seen = set()
    for team in data['teams']:
        if not isinstance(team, dict) or not isinstance(team.get('name'), str) or not team['name']:
            raise ValueError('each team needs a nonempty name')
        if team['name'] in seen:
            raise ValueError('duplicate team: ' + team['name'])
        seen.add(team['name'])
        if not isinstance(team.get('repo'), str):
            raise ValueError('each team needs a repo path')
        repo = (path.parent / team['repo']).resolve()
        if not repo.is_dir():
            raise ValueError('repo does not exist: ' + str(repo))
        team['repo'] = str(repo)
        worktrees = team.get('worktrees', [])
        if not isinstance(worktrees, list) or any(not isinstance(w, str) for w in worktrees):
            raise ValueError('worktrees must be an array of paths')
        team['worktrees'] = [str((path.parent / w).resolve()) for w in worktrees]
    if not isinstance(data.get('timeout_seconds', 15), (int, float)) or not 0 < data.get('timeout_seconds', 15) <= 120:
        raise ValueError('timeout_seconds must be in (0, 120]')
    if not isinstance(data.get('event_tasks_per_tick', 10), int) or not 1 <= data.get('event_tasks_per_tick', 10) <= 100:
        raise ValueError('event_tasks_per_tick must be between 1 and 100')
    if not isinstance(data.get('retain_snapshots', 1000), int) or data.get('retain_snapshots', 1000) < 2:
        raise ValueError('retain_snapshots must be at least 2')
    return data


def jobs(config):
    timeout = config.get('timeout_seconds', 15)
    result = [('herdr', 'herdr', {'timeout': timeout})]
    for team in config['teams']:
        for kind in ('roster', 'tasks', 'ci', 'git', 'worktrees'):
            options = {'repo': team['repo'], 'team': team['name'], 'timeout': timeout}
            result.append((team['name'] + '/' + kind, kind, options))
        for worktree in team['worktrees']:
            for kind in ('git', 'stack'):
                key = team['name'] + '/' + kind + '/' + worktree
                result.append((key, kind, {'repo': worktree, 'team': team['name'], 'timeout': timeout}))
    return result


def run_tick(config, state_dir, collector=collect):
    with locked(state_dir):
        previous, recovery_errors = read_latest(state_dir)
        specifications = jobs(config)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [(key, pool.submit(collector, kind, **options))
                       for key, kind, options in specifications]
            sources = {key: future.result() for key, future in futures}
            additional = []
            for team in config['teams']:
                ci = sources[team['name'] + '/ci']
                worktrees = sources[team['name'] + '/worktrees']
                if ci['status'] not in {'ok', 'partial'} or worktrees['status'] != 'ok':
                    continue
                branches = {'refs/heads/' + pr['headRefName'] for pr in ci['data'] if pr.get('state', 'OPEN') == 'OPEN'}
                for tree in worktrees['data']:
                    if tree.get('branch') not in branches:
                        continue
                    for kind in ('git', 'stack'):
                        key = team['name'] + '/' + kind + '/' + tree['worktree']
                        if key not in sources:
                            additional.append((key, pool.submit(collector, kind,
                                repo=tree['worktree'], team=team['name'],
                                timeout=config.get('timeout_seconds', 15))))
            sources.update({key: future.result() for key, future in additional})
            fingerprints = dict(previous.get('event_fingerprints', {})) if previous else {}
            pending = []
            for team in config['teams']:
                task_source = sources[team['name'] + '/tasks']
                if task_source['status'] != 'ok':
                    continue
                grouped = {}
                for row in task_source['data']:
                    grouped.setdefault(row['task_id'], []).append(row)
                for task_id, rows in grouped.items():
                    key = team['name'] + '/task-events/' + task_id
                    fingerprint = json.dumps(sorted(rows, key=lambda row: row['assignee']), sort_keys=True)
                    if fingerprints.get(key) != fingerprint:
                        pending.append((key, fingerprint, team, task_id))
            selected = pending[:config.get('event_tasks_per_tick', 10)]
            event_futures = [(key, fingerprint, pool.submit(collector, 'task-events',
                              repo=team['repo'], team=team['name'], task_id=task_id,
                              timeout=config.get('timeout_seconds', 15)))
                             for key, fingerprint, team, task_id in selected]
            for key, fingerprint, future in event_futures:
                sources[key] = future.result()
                if sources[key]['status'] == 'ok':
                    fingerprints[key] = fingerprint
        # A failed observation never overwrites a prior successful observation.
        last_good = dict(previous.get('last_good', {})) if previous else {}
        for key, value in sources.items():
            if value['status'] == 'ok':
                last_good[key] = value
        tracked = dict(previous.get('tracked_sprints', {})) if previous else {}
        discovery_errors = []
        for team in config['teams']:
            ci = sources[team['name'] + '/ci']
            if ci['status'] in {'ok', 'partial'}:
                tracked[team['name']], errors = discover(team['repo'], ci['data'], tracked.get(team['name']))
                discovery_errors.extend(dict(error, team=team['name']) for error in errors)
        snapshot = {'schema_version': 1, 'machine': socket.gethostname(),
                    'observed_at': datetime.now(timezone.utc).isoformat(),
                    'fresh_start': previous is None, 'recovery_errors': recovery_errors,
                    'sources': sources, 'last_good': last_good,
                    'event_fingerprints': fingerprints,
                    'tracked_sprints': tracked, 'discovery_errors': discovery_errors,
                    'interventions': previous.get('interventions', {}) if previous else {},
                    'intervention_history': previous.get('intervention_history', []) if previous else [],
                    'deferred_event_tasks': len(pending) - len(selected),
                    'teams': config['teams']}
        path = save(state_dir, snapshot, config.get('retain_snapshots', 1000))
        failed = [key for key, source in sources.items() if source['status'] == 'unavailable']
        partial = [key for key, source in sources.items() if source['status'] == 'partial']
        return {'schema_version': 1, 'status': 'degraded' if failed or partial or recovery_errors else 'ok',
                'snapshot': str(path), 'source_count': len(sources),
                'failed_sources': failed, 'partial_sources': partial, 'fresh_start': snapshot['fresh_start'],
                'deferred_event_tasks': snapshot['deferred_event_tasks'],
                'discovery_issue_count': len(discovery_errors),
                'recovery_errors': recovery_errors}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--state-dir', required=True, type=Path)
    args = p.parse_args()
    try:
        result = run_tick(load_config(args.config.resolve()), args.state_dir)
        code = 0 if result['status'] == 'ok' else 2
    except BusyError as exc:
        result, code = {'status': 'busy', 'error': str(exc)}, 3
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result, code = {'status': 'error', 'error': str(exc)}, 2
    print(json.dumps(result, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
