#!/usr/bin/env python3
"""Monitor phases for watched teams and emit routed findings, without sending."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from check_health import evaluate
from collectors import collect
from state_store import BusyError, read_latest
from tick import load_config, run_tick
from scheduled_output import emit


def select_teams(config, activity_dir, max_age_seconds=600):
    if max_age_seconds <= 0:
        raise ValueError('max activity age must be positive')
    activity, recovery = read_latest(activity_dir)
    warnings = []
    try:
        if not activity or recovery or activity.get('role') != 'activity':
            raise ValueError('activity state missing, corrupt, or wrong kind')
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(activity['observed_at'])).total_seconds()
        if not 0 <= age <= max_age_seconds or activity.get('recovery_errors'):
            raise ValueError('activity state stale, recovered, or from a future clock')
        if activity['teams'] != config['teams']:
            raise ValueError('activity configuration differs; rerun detection')
        watched = activity['watched_teams']
        if not isinstance(watched, dict):
            raise ValueError('invalid watch list')
        # Source failures cannot establish that a candidate team is quiet.
        uncertain = {team['name'] for team in config['teams']
                     if activity['sources'].get(team['name'] + '/roster', {}).get('status') != 'ok'}
        for unresolved in activity.get('unresolved_agents', []):
            for identity in unresolved.get('candidate_ids', []):
                uncertain.add(identity.rsplit('@', 1)[-1])
        if activity['sources'].get('herdr', {}).get('status') != 'ok':
            uncertain.update(team['name'] for team in config['teams'])
        if uncertain:
            warnings.append('activity sources unavailable; include uncertain teams')
        return [team for team in config['teams'] if team['name'] in watched or team['name'] in uncertain], warnings
    except (ValueError, KeyError, TypeError) as exc:
        # A broken detector must not silently stop monitoring.
        return config['teams'], [str(exc) + '; monitoring all configured teams']


def monitor(config, activity_dir, state_dir, max_age_seconds=600, collector=collect):
    if Path(activity_dir).resolve() == Path(state_dir).resolve():
        raise ValueError('activity and phase state directories must be different')
    teams, warnings = select_teams(config, activity_dir, max_age_seconds)
    previous, _ = read_latest(state_dir)
    retained = {name for name, sprints in (previous or {}).get('tracked_sprints', {}).items() if sprints}
    selected = {team['name'] for team in teams}
    teams = [team for team in config['teams'] if team['name'] in selected or team['name'] in retained]
    result = run_tick(dict(config, teams=teams), state_dir, collector)
    # Read this tick's committed snapshot, not a later writer's observation.
    snapshot = json.loads(Path(result['snapshot']).read_text(encoding='utf-8'))
    findings = evaluate(snapshot)
    result.update(monitored_teams=[team['name'] for team in teams], activity_warnings=warnings,
                  findings=findings, notify=[item for item in findings if item['pending_routes']])
    if warnings:
        result['status'] = 'degraded'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--activity-dir', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--max-activity-age-seconds', type=int, default=600)
    parser.add_argument('--json', action='store_true', help='print diagnostics even on healthy/busy runs')
    args = parser.parse_args()
    try:
        result = monitor(load_config(args.config.resolve()), args.activity_dir,
                         args.state_dir, args.max_activity_age_seconds)
    except BusyError as exc:
        result = {'status': 'busy', 'error': str(exc)}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'status': 'error', 'error': str(exc)}
    return emit(result, args.json)


if __name__ == '__main__':
    sys.exit(main())
