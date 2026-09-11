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
from github_inventory import parse_start_time


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
        projects = team.get('projects', [])
        if not isinstance(projects, list):
            raise ValueError('projects must be an array of phase settings')
        phases = set()
        for project in projects:
            if not isinstance(project, dict) or not isinstance(project.get('phase'), str) or not project['phase']:
                raise ValueError('each project needs a phase')
            if project['phase'] in phases:
                raise ValueError('duplicate phase settings: ' + project['phase'])
            phases.add(project['phase'])
            parse_start_time(project.get('start_time'))
            local_trees = project.get('worktrees', [])
            if not isinstance(local_trees, list) or any(not isinstance(w, str) for w in local_trees):
                raise ValueError('project worktrees must be an array of paths')
            project['worktrees'] = [str((path.parent / w).resolve()) for w in local_trees]
        worktrees = team.get('worktrees', [])
        if not isinstance(worktrees, list) or any(not isinstance(w, str) for w in worktrees):
            raise ValueError('worktrees must be an array of paths')
        team['worktrees'] = [str((path.parent / w).resolve()) for w in worktrees]
    if not isinstance(data.get('timeout_seconds', 15), (int, float)) or not 0 < data.get('timeout_seconds', 15) <= 120:
        raise ValueError('timeout_seconds must be in (0, 120]')
    # Older deployments contain event_tasks_per_tick. Accept it for upgrades,
    # but never let that obsolete budget suppress event collection.
    if not isinstance(data.get('retain_snapshots', 1000), int) or data.get('retain_snapshots', 1000) < 2:
        raise ValueError('retain_snapshots must be at least 2')
    return data


def project_start(team):
    projects = team.get('projects', [])
    return min((p['start_time'] for p in projects), key=parse_start_time) if projects else None


def project_worktrees(team):
    return sorted(set(team.get('worktrees', []) + [w for p in team.get('projects', []) for w in p.get('worktrees', [])]))


def jobs(config):
    timeout = config.get('timeout_seconds', 15)
    result = [('herdr', 'herdr', {'timeout': timeout})]
    for team in config['teams']:
        for kind in ('roster', 'tasks', 'ci', 'git', 'worktrees'):
            options = {'repo': team['repo'], 'team': team['name'], 'timeout': timeout}
            if kind in {'ci', 'git'}:
                options['start_time'] = project_start(team)
            result.append((team['name'] + '/' + kind, kind, options))
        for worktree in project_worktrees(team):
            for kind in ('git', 'stack'):
                key = team['name'] + '/' + kind + '/' + worktree
                result.append((key, kind, {'repo': worktree, 'team': team['name'], 'timeout': timeout,
                                          'start_time': project_start(team)}))
    return result


def run_tick(config, state_dir, collector=collect):
    with locked(state_dir):
        previous, recovery_errors = read_latest(state_dir)
        if previous and previous.get('role') == 'activity':
            raise ValueError('phase state directory contains activity state; use separate directories')
        old_teams = {team['name']: team for team in (previous or {}).get('teams', [])}
        changed = {team['name'] for team in config['teams']
                   if any(team.get(field) != old_teams.get(team['name'], {}).get(field)
                          for field in ('repo', 'projects'))}
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
                                start_time=project_start(team),
                                timeout=config.get('timeout_seconds', 15))))
            sources.update({key: future.result() for key, future in additional})
            pending = []
            for team in config['teams']:
                task_source = sources[team['name'] + '/tasks']
                if task_source['status'] != 'ok':
                    continue
                grouped = {}
                for row in task_source['data']:
                    grouped.setdefault(row['task_id'], []).append(row)
                for task_id in grouped:
                    key = team['name'] + '/task-events/' + task_id
                    pending.append((key, team, task_id))
            # Task state can stay unchanged while new events arrive. Fetch every
            # task history each tick until ATM supplies a reliable event cursor.
            event_futures = [(key, pool.submit(collector, 'task-events',
                              repo=team['repo'], team=team['name'], task_id=task_id,
                              timeout=config.get('timeout_seconds', 15)))
                             for key, team, task_id in pending]
            for key, future in event_futures:
                sources[key] = future.result()
        # A failed observation never overwrites a prior successful observation.
        last_good = dict(previous.get('last_good', {})) if previous else {}
        last_good = {key: value for key, value in last_good.items() if key.split('/')[0] not in changed}
        for key, value in sources.items():
            if value['status'] == 'ok':
                last_good[key] = value
        tracked = dict(previous.get('tracked_sprints', {})) if previous else {}
        for name in changed:
            tracked.pop(name, None)
        discovery_errors = []
        for team in config['teams']:
            ci = sources[team['name'] + '/ci']
            if ci['status'] in {'ok', 'partial'}:
                tracked[team['name']], errors = discover(team['repo'], ci['data'], tracked.get(team['name']),
                                                        [p['phase'] for p in team.get('projects', [])])
                discovery_errors.extend(dict(error, team=team['name']) for error in errors)
        onboarding = []
        for team in config['teams']:
            candidates = {}
            configured_phases = {p['phase'] for p in team.get('projects', [])}
            current_sprints = tracked.get(team['name'], {}) if sources[team['name'] + '/ci']['status'] == 'ok' else {}
            for sprint in current_sprints.values():
                pr = sprint.get('pr') or {}
                if pr.get('state') == 'OPEN':
                    candidates.setdefault(sprint['phase'], []).append({'plan': sprint.get('plan_path'),
                                                                       'pr': pr.get('number')})
            for phase, evidence in sorted(candidates.items()):
                if phase not in configured_phases:
                    onboarding.append({'skill': 'oversight-onboarding', 'team': team['name'],
                                       'repo': team['repo'], 'phase': phase, 'evidence': evidence,
                                       'reason': 'discovered phase needs verified monitoring settings'})
            if not candidates and not configured_phases:
                onboarding.append({'skill': 'oversight-onboarding', 'team': team['name'],
                                   'repo': team['repo'], 'phase': None,
                                   'reason': 'project lacks a verified start time; identify active phase'})
        snapshot = {'schema_version': 1, 'machine': socket.gethostname(),
                    'observed_at': datetime.now(timezone.utc).isoformat(),
                    'fresh_start': previous is None, 'recovery_errors': recovery_errors,
                    'sources': sources, 'last_good': last_good,
                    'tracked_sprints': tracked, 'discovery_errors': discovery_errors,
                    'interventions': previous.get('interventions', {}) if previous else {},
                    'intervention_history': previous.get('intervention_history', []) if previous else [],
                    'deferred_event_tasks': 0,
                    'unscoped_projects': [team['name'] for team in config['teams'] if not team.get('projects')],
                    'onboarding_requests': onboarding,
                    'teams': config['teams']}
        path = save(state_dir, snapshot, config.get('retain_snapshots', 1000))
        failed = [key for key, source in sources.items() if source['status'] == 'unavailable']
        partial = [key for key, source in sources.items() if source['status'] == 'partial']
        return {'schema_version': 1, 'status': 'degraded' if failed or partial or recovery_errors else 'ok',
                'snapshot': str(path), 'source_count': len(sources),
                'failed_sources': failed, 'partial_sources': partial, 'fresh_start': snapshot['fresh_start'],
                'deferred_event_tasks': snapshot['deferred_event_tasks'],
                'unscoped_projects': snapshot['unscoped_projects'],
                'onboarding_requests': onboarding,
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
