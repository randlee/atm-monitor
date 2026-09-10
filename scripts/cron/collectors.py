"""Bounded, read-only collectors. Source status is separate from observed state."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

MAX_OUTPUT_BYTES = 16 * 1024 * 1024
KINDS = ('herdr', 'roster', 'tasks', 'task-events', 'git', 'ci', 'stack', 'worktrees')


def command_for(kind, team=None, task_id=None, limit=100, branch='HEAD', since='24 hours ago'):
    if kind == 'herdr':
        return ['herdr', 'agent', 'list']
    if kind in {'roster', 'tasks', 'task-events'} and not team:
        raise ValueError('team is required')
    if kind == 'roster':
        return ['atm', 'members', '--team', team, '--json']
    if kind == 'tasks':
        return ['atm', 'list', '--team', team, '--tasks', '--json']
    if kind == 'task-events':
        if not task_id:
            raise ValueError('task_id is required')
        return ['atm', 'list', '--team', team, '--task-events', task_id, '--json']
    if kind == 'stack':
        return ['gh', 'stack', 'view', '--json']
    if kind == 'worktrees':
        return ['git', 'worktree', 'list', '--porcelain', '-z']
    if kind == 'ci':
        return ['gh', 'pr', 'list', '--state', 'all', '--limit', str(limit), '--json',
                'number,url,headRefName,headRefOid,baseRefName,state,mergedAt,closedAt,updatedAt,mergeable,mergeStateStatus,isDraft,statusCheckRollup']
    if kind == 'git':
        if branch.startswith('-'):
            raise ValueError('branch may not begin with a dash')
        return ['git', 'log', branch, '--since=' + since, '--max-count=' + str(limit),
                '--format=%H%x00%cI%x00%s', '--']
    raise ValueError('unknown collector: ' + kind)


def list_of_objects(data, name):
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError(name + ' must be an array of objects')
    return data


def require(rows, fields):
    for row in rows:
        if any(key not in row or row[key] is None for key in fields):
            raise ValueError('row missing required fields: ' + ', '.join(fields))
    return rows


def decode(kind, raw, team):
    if kind == 'worktrees':
        rows, current = [], {}
        for field in raw.split('\0'):
            if not field:
                if current:
                    rows.append(current)
                    current = {}
                continue
            key, _, value = field.partition(' ')
            current[key] = value
        if current:
            rows.append(current)
        return require(rows, ('worktree', 'HEAD'))
    if kind == 'git':
        rows = []
        for line in raw.splitlines():
            parts = line.split('\0', 2)
            if len(parts) != 3:
                raise ValueError('malformed Git log record')
            rows.append(dict(zip(('commit', 'committed_at', 'subject'), parts)))
        return rows
    data = json.loads(raw)
    if kind == 'herdr':
        if not isinstance(data, dict) or 'error' in data:
            raise ValueError('Herdr returned an error or invalid envelope')
        result = data.get('result')
        if not isinstance(result, dict) or 'agents' not in result:
            raise ValueError('Herdr response missing result.agents')
        return require(list_of_objects(result['agents'], 'agents'),
                       ('name', 'agent_status', 'pane_id', 'workspace_id'))
    if kind == 'roster':
        if not isinstance(data, dict) or data.get('team') != team or 'members' not in data:
            raise ValueError('roster response missing members or mismatched team')
        rows = require(list_of_objects(data['members'], 'members'), ('name', 'agent_id'))
        if any(row['agent_id'] != row['name'] + '@' + team for row in rows):
            raise ValueError('roster member identity does not match requested team')
        return rows
    if kind in {'tasks', 'task-events'}:
        rows = require(list_of_objects(data, kind), ('team', 'task_id', 'assignee'))
        if any(row['team'] != team for row in rows):
            raise ValueError('task response includes a different team')
        return require(rows, ('state',) if kind == 'tasks' else ('seq', 'at', 'event'))
    if kind == 'ci':
        return require(list_of_objects(data, 'PRs'), ('number', 'headRefOid', 'headRefName'))
    if kind == 'stack':
        if not isinstance(data, dict) or not isinstance(data.get('trunk'), str):
            raise ValueError('stack response missing trunk')
        require(list_of_objects(data.get('branches'), 'branches'), ('name', 'head', 'needsRebase'))
        return data
    raise ValueError('unsupported decoder')


def collect(kind, *, repo=None, team=None, task_id=None, limit=100, branch='HEAD',
            since='24 hours ago', timeout=15, run=subprocess.run):
    started = time.monotonic()
    result = {'schema_version': 1, 'source': kind, 'machine': socket.gethostname(),
              'team': team, 'repo': str(Path(repo).resolve()) if repo else None,
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'status': 'unavailable', 'data': None, 'error': None}
    try:
        if timeout <= 0 or not 1 <= limit <= 10000:
            raise ValueError('timeout must be positive; limit must be between 1 and 10000')
        cmd = command_for(kind, team, task_id, limit, branch, since)
        env = os.environ.copy()
        env.update({'GIT_TERMINAL_PROMPT': '0', 'GH_PROMPT_DISABLED': '1', 'NO_COLOR': '1'})
        p = run(cmd, cwd=repo, capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=timeout, env=env)
        if p.returncode:
            # No-stack is a successful absence observation, not a transport failure.
            if kind == 'stack' and p.returncode == 2 and 'not part of a stack' in p.stderr:
                result.update(status='ok', data=None, absence='not-in-stack')
            else:
                result['error'] = {'code': 'command-failed', 'exit_code': p.returncode,
                                   'detail': p.stderr.strip()[:2000]}
        elif len(p.stdout.encode('utf-8')) > MAX_OUTPUT_BYTES:
            result['error'] = {'code': 'result-too-large', 'detail': 'source exceeded output budget'}
        else:
            result['data'] = decode(kind, p.stdout, team)
            if kind == 'task-events' and any(row['task_id'] != task_id for row in result['data']):
                raise ValueError('event response includes a different task')
            result['status'] = 'ok'
            if kind in {'ci', 'git'} and len(result['data']) >= limit:
                result['status'] = 'partial'
                result['error'] = {'code': 'limit-reached', 'detail': 'additional results may exist'}
    except subprocess.TimeoutExpired:
        result['error'] = {'code': 'timeout', 'detail': f'source exceeded {timeout}s'}
    except FileNotFoundError as exc:
        result['error'] = {'code': 'not-found', 'detail': str(exc)}
    except (ValueError, OSError, TypeError) as exc:
        result['data'] = None
        result['error'] = {'code': 'invalid-result', 'detail': str(exc)}
    result['duration_ms'] = round((time.monotonic() - started) * 1000)
    return result


def cli(kind):
    p = argparse.ArgumentParser(description=f'Collect {kind} once, read-only, as JSON.')
    p.add_argument('--repo', type=Path)
    p.add_argument('--team', required=kind in {'roster', 'tasks', 'task-events'})
    p.add_argument('--task-id', required=kind == 'task-events')
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--limit', type=int, default=100)
    p.add_argument('--branch', default='HEAD')
    p.add_argument('--since', default='24 hours ago')
    args = p.parse_args()
    result = collect(kind, **vars(args))
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'ok' else 2
