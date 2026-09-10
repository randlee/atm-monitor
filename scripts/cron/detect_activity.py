#!/usr/bin/env python3
"""Detect activity among configured candidate teams and retain a watch list."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import socket
import sys

from collectors import collect
from state_store import BusyError, locked, read_latest, save
from tick import load_config
from scheduled_output import emit


def path_within(value, root):
    if not isinstance(value, str) or not value or not root:
        return False
    candidate, parent = Path(value), Path(root)
    if not candidate.is_absolute() or not parent.is_absolute():
        return False
    return candidate.resolve().is_relative_to(parent.resolve())


def detect(config, state_dir, collector=collect):
    with locked(state_dir):
        previous, recovery = read_latest(state_dir)
        if previous and previous.get('role') != 'activity':
            raise ValueError('activity directory contains a different kind of state')
        timeout = config.get('timeout_seconds', 15)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {'herdr': pool.submit(collector, 'herdr', timeout=timeout)}
            for team in config['teams']:
                futures[team['name'] + '/roster'] = pool.submit(
                    collector, 'roster', team=team['name'], repo=team['repo'], timeout=timeout)
            sources = {key: future.result() for key, future in futures.items()}
        now = datetime.now(timezone.utc).isoformat()
        watched = dict(previous.get('watched_teams', {})) if previous else {}
        evidence = {team['name']: [] for team in config['teams']}
        members = []
        for team in config['teams']:
            source = sources[team['name'] + '/roster']
            if source['status'] != 'ok':
                continue
            for member in source['data']:
                members.append((team, member))
                if member.get('state') in {'active', 'working', 'blocked'}:
                    evidence[team['name']].append({'source': 'roster', 'agent_id': member['agent_id'],
                                                    'state': member['state']})
        unresolved = []
        herdr = sources['herdr']
        if herdr['status'] == 'ok':
            for agent in herdr['data']:
                if agent.get('agent_status') != 'working':
                    continue
                matches = []
                for team, member in members:
                    if agent['name'] not in {member['name'], member['agent_id']}:
                        continue
                    roots = [team['repo'], member.get('home_dir'), *team.get('worktrees', [])]
                    if any(path_within(agent.get(field), root)
                           for field in ('cwd', 'foreground_cwd') for root in roots):
                        matches.append((team, member))
                identities = {member['agent_id'] for _, member in matches}
                if len(identities) == 1:
                    team, member = matches[0]
                    evidence[team['name']].append({'source': 'herdr', 'agent_id': member['agent_id'],
                        'workspace_id': agent['workspace_id'], 'pane_id': agent['pane_id'],
                        'state_change_seq': agent.get('state_change_seq'), 'state': agent['agent_status']})
                else:
                    unresolved.append({'name': agent['name'], 'workspace_id': agent['workspace_id'],
                        'pane_id': agent['pane_id'], 'candidate_ids': sorted(identities),
                        'reason': 'ambiguous identity' if identities else 'no configured roster/path match'})
        added = []
        for team in config['teams']:
            name = team['name']
            if evidence[name]:
                old = watched.get(name, {})
                if not old:
                    added.append(name)
                watched[name] = {'first_seen_at': old.get('first_seen_at', now),
                                 'last_activity_at': now, 'repo': team['repo'], 'evidence': evidence[name]}
        failed = [key for key, source in sources.items() if source['status'] != 'ok']
        snapshot = {'schema_version': 1, 'role': 'activity', 'machine': socket.gethostname(),
                    'observed_at': now, 'sources': sources, 'teams': config['teams'],
                    'watched_teams': watched, 'unresolved_agents': unresolved,
                    'recovery_errors': recovery, 'fresh_start': previous is None}
        path = save(state_dir, snapshot, config.get('retain_snapshots', 1000))
        return {'schema_version': 1, 'status': 'degraded' if failed or recovery or unresolved else 'ok',
                'snapshot': str(path), 'added_teams': added, 'watched_teams': sorted(watched),
                'failed_sources': failed, 'unresolved_agents': unresolved, 'recovery_errors': recovery}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--json', action='store_true', help='print diagnostics even on healthy/busy runs')
    args = parser.parse_args()
    try:
        result = detect(load_config(args.config.resolve()), args.state_dir)
    except BusyError as exc:
        result = {'status': 'busy', 'error': str(exc)}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'status': 'error', 'error': str(exc)}
    return emit(result, args.json)


if __name__ == '__main__':
    sys.exit(main())
