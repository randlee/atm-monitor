"""Read-only collectors. Source status is separate from observed state."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from github_inventory import collect_prs, parse_start_time

MAX_OUTPUT_BYTES = 16 * 1024 * 1024
KINDS = ('herdr', 'roster', 'tasks', 'task-events', 'git', 'ci', 'stack', 'worktrees')


def command_for(kind, team=None, task_id=None, limit=None, branch='HEAD', since=None):
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
    if kind == 'git':
        if branch.startswith('-'):
            raise ValueError('branch may not begin with a dash')
        options = (['--since=' + since] if since else []) + (['--max-count=' + str(limit)] if limit else [])
        return ['git', 'log', branch, *options, '--format=%H%x00%cI%x00%s', '--']
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
        branches = require(list_of_objects(data.get('branches'), 'branches'), ('name', 'needsRebase'))
        # gh-stack retains merged entries after their local refs disappear.
        # Their head may be omitted; an active branch still needs commit identity.
        require([row for row in branches if row.get('isMerged') is not True], ('head',))
        return data
    raise ValueError('unsupported decoder')


class SourceError(Exception):
    def __init__(self, error):
        self.error = error


def collect(kind, *, repo=None, team=None, task_id=None, limit=None, branch='HEAD',
            since=None, start_time=None, timeout=15, run=subprocess.run):
    started = time.monotonic()
    result = {'schema_version': 1, 'source': kind, 'machine': socket.gethostname(),
              'team': team, 'repo': str(Path(repo).resolve()) if repo else None,
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'status': 'unavailable', 'data': None, 'error': None}
    try:
        if start_time is not None:
            parse_start_time(start_time)
            result['start_time'] = start_time
            if kind == 'git':
                since = start_time
        if timeout <= 0 or (limit is not None and not 1 <= limit <= (100 if kind == 'ci' else 10000)):
            raise ValueError('timeout must be positive; limit must be 1..100 for CI pages or 1..10000 for Git')
        env = os.environ.copy()
        env.update({'GIT_TERMINAL_PROMPT': '0', 'GH_PROMPT_DISABLED': '1', 'NO_COLOR': '1'})
        def execute(command):
            page = run(command, cwd=repo, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=timeout, env=env)
            if page.returncode:
                raise SourceError({'code': 'command-failed', 'exit_code': page.returncode,
                                   'detail': page.stderr.strip()[:2000]})
            if len(page.stdout.encode('utf-8')) > MAX_OUTPUT_BYTES:
                raise SourceError({'code': 'result-too-large', 'detail': 'source page exceeded output budget'})
            return page.stdout
        if kind == 'ci':
            result.update(data=collect_prs(execute, limit or 100, start_time), status='ok')
            return result
        cmd = command_for(kind, team, task_id, limit, branch, since)
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
            if kind == 'git' and limit is not None and len(result['data']) >= limit:
                result['status'] = 'partial'
                result['error'] = {'code': 'limit-reached', 'detail': 'additional results may exist'}
    except SourceError as exc:
        result['error'] = exc.error
    except subprocess.TimeoutExpired:
        result['error'] = {'code': 'timeout', 'detail': f'source exceeded {timeout}s'}
    except FileNotFoundError as exc:
        result['error'] = {'code': 'not-found', 'detail': str(exc)}
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
        result['data'] = None
        result['error'] = {'code': 'invalid-result', 'detail': str(exc)}
    finally:
        result['duration_ms'] = round((time.monotonic() - started) * 1000)
    return result


def cli(kind):
    p = argparse.ArgumentParser(description=f'Collect {kind} once, read-only, as JSON.')
    p.add_argument('--repo', type=Path)
    p.add_argument('--team', required=kind in {'roster', 'tasks', 'task-events'})
    p.add_argument('--task-id', required=kind == 'task-events')
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--limit', type=int, help='CI page size (all pages fetched), or an explicit Git record limit')
    p.add_argument('--branch', default='HEAD')
    p.add_argument('--since', help='optional Git history filter; scheduled collection reads full branch history')
    p.add_argument('--start-time', help='project start timestamp with timezone; scopes CI and Git collection')
    args = p.parse_args()
    result = collect(kind, **vars(args))
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'ok' else 2
