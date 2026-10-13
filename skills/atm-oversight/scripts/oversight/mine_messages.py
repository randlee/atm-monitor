#!/usr/bin/env python3
"""Retrieve bounded ATM evidence; never marks messages read or sends mail."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import re

KINDS = ('dev-task', 'fix-task', 'qa-task', 'qa-report')
_ESCALATION_SUMMARY = re.compile(
    r'^escalation:(?P<kind>.+):(?P<agent>[^@\s]+)@(?P<team>[^\s]+)$')


def parse_escalation_summary(text):
    """Parse an escalation summary while preserving kinds unknown to this client."""
    if not isinstance(text, str):
        return None
    match = _ESCALATION_SUMMARY.fullmatch(text.strip())
    return match.groupdict() if match else None


def invoke(command, repo=None, timeout=15, *, actor=None, team=None):
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    if actor is not None:
        env['ATM_IDENTITY'] = actor
    if team is not None:
        env['ATM_TEAM'] = team
    p = subprocess.run(command, cwd=repo, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout, env=env)
    if p.returncode:
        raise ValueError(p.stderr.strip()[:2000] or f'command exited {p.returncode}')
    if len(p.stdout.encode('utf-8')) > 16 * 1024 * 1024:
        raise ValueError('result exceeds 16 MiB budget')
    return json.loads(p.stdout)


def mine(team, *, actor, kind=None, template_sha=None, cursor=None, text=None,
         task_id=None, sprint=None, sender=None, agent=None, tag=None,
         effective_tag=None, since=None, until=None, limit=20,
         with_bodies=False, max_bodies=10, max_templates=8, query=None):
    if (not isinstance(team, str) or not team.strip() or not isinstance(actor, str) or not actor.strip()
            or not 1 <= limit <= 1000 or not 1 <= max_templates <= 100 or not 0 <= max_bodies <= 100):
        raise ValueError('invalid team or query budget')
    if query is None:
        query = lambda command: invoke(command, actor=actor, team=team)
    if kind and kind not in KINDS:
        raise ValueError('unsupported work-record kind')
    if cursor and kind and not template_sha:
        raise ValueError('use the page template_sha with its cursor to continue a kind query')
    result = {'schema_version': 1, 'team': team, 'actor': actor, 'observed_at': datetime.now(timezone.utc).isoformat(),
              'status': 'ok', 'messages': [], 'pages': [], 'errors': [],
              'selector': 'template-sha' if kind or template_sha else 'search'}
    shas = [template_sha]
    if kind and not template_sha:
        catalog = query(['atm', 'templates', 'list', '--json'])
        if not isinstance(catalog, list) or any(not isinstance(row, dict) for row in catalog):
            raise ValueError('invalid template catalog')
        shas = sorted({row['template_sha'] for row in catalog
                       if row.get('template_type') == kind and isinstance(row.get('template_sha'), str)})
        if not shas:
            result.update(status='unavailable', errors=[{'error': 'no catalog revision matches requested kind'}])
            return result
    result['remaining_template_shas'] = shas[max_templates:]
    if result['remaining_template_shas']:
        result['status'] = 'partial'
    unique = {}
    for sha in shas[:max_templates]:
        command = ['atm', 'search']
        if text:
            command += [text]
        command += ['--team', team, '--limit', str(limit), '--json']
        filters = [('--template-sha', sha), ('--cursor', cursor), ('--from', sender),
                   ('--agent', agent), ('--tag', tag), ('--effective-tag', effective_tag),
                   ('--since', since), ('--until', until)]
        if task_id:
            filters.append(('--var', 'task_id=' + task_id))
        if sprint:
            filters.append(('--var', 'sprint=' + sprint))
        for flag, value in filters:
            if value is not None:
                command += [flag, value]
        try:
            data = query(command)
            if not isinstance(data, dict) or not isinstance(data.get('hits'), list):
                raise ValueError('search response missing hits')
            for hit in data['hits']:
                if not isinstance(hit, dict) or not isinstance(hit.get('key'), dict):
                    raise ValueError('invalid search hit')
                if hit['key'].get('team') != team or not hit.get('message_id') or not hit.get('message_at'):
                    raise ValueError('search hit missing identity or belongs to another team')
                escalation = parse_escalation_summary(hit.get('summary')) or parse_escalation_summary(hit.get('text'))
                if escalation:
                    hit['escalation'] = escalation
                unique[hit['message_id']] = hit
            result['pages'].append({'template_sha': sha, 'next_cursor': data.get('next_cursor')})
            if data.get('next_cursor'):
                result['status'] = 'partial'
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            result['errors'].append({'template_sha': sha, 'error': str(exc)})
            result['status'] = 'partial'
    result['messages'] = sorted(unique.values(), key=lambda hit: (hit['message_at'], hit['message_id']))
    if with_bodies:
        selected = result['messages'][-max_bodies:] if max_bodies else []
        result['bodies_omitted'] = len(result['messages']) - len(selected)
        if result['bodies_omitted']:
            result['status'] = 'partial'
        for hit in selected:
            try:
                data = query(['atm', 'peek', '--as', actor, '--team', team, hit['key']['agent'],
                              '--message-id', hit['message_id'], '--json'])
                if not isinstance(data, dict) or data.get('mutation_applied') is not False:
                    raise ValueError('peek did not confirm non-mutating read')
                message = data.get('message', {})
                if message.get('message_id') != hit['message_id'] or not isinstance(message.get('text'), str):
                    raise ValueError('peek returned wrong or missing message')
                hit['body'] = message['text']
                escalation = parse_escalation_summary(message.get('summary')) or parse_escalation_summary(message['text'])
                if escalation:
                    hit['escalation'] = escalation
            except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
                result['errors'].append({'message_id': hit['message_id'], 'error': str(exc)})
                result['status'] = 'partial'
    if result['errors'] and not result['messages']:
        result['status'] = 'unavailable'
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--team', required=True)
    p.add_argument('--as', dest='actor', required=True)
    p.add_argument('--repo', type=Path)
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--kind', choices=KINDS)
    for flag in ('template-sha', 'cursor', 'text', 'task-id', 'sprint', 'sender',
                 'agent', 'tag', 'effective-tag', 'since', 'until'):
        p.add_argument('--' + flag)
    p.add_argument('--limit', type=int, default=20, help='maximum hits per template revision')
    p.add_argument('--max-templates', type=int, default=8)
    p.add_argument('--max-bodies', type=int, default=10)
    p.add_argument('--with-bodies', action='store_true')
    args = vars(p.parse_args())
    repo, timeout = args.pop('repo'), args.pop('timeout')
    try:
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        result = mine(**args, query=lambda command: invoke(command, repo, timeout, actor=args['actor'], team=args['team']))
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        result = {'status': 'unavailable', 'errors': [{'error': str(exc)}]}
    print(json.dumps(result, indent=2))
    return 2 if result['status'] == 'unavailable' else 0


if __name__ == '__main__':
    sys.exit(main())
