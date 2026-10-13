#!/usr/bin/env python3
"""Deduplicate notable monitor events before handing them to Hermes."""

import argparse
import hashlib
import json
from pathlib import Path

from state_store import BusyError, locked
from gate_store import _load, _save


STATE_VERSION = 1


def _key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:24]


def _health_event(result):
    failed = sorted(str(x) for x in result.get('failed_sources', []) or [])
    partial = sorted(str(x) for x in result.get('partial_sources', []) or [])
    recovery = sorted(str(x) for x in result.get('recovery_errors', []) or [])
    warnings = bool(result.get('activity_warnings'))
    if not (failed or partial or recovery or warnings or result.get('status') == 'error'):
        return None
    # Deliberately use source/category identity only: timestamps and prose can churn.
    identity = ['monitor-health', failed, partial, recovery]
    return {'incident_key': _key(identity), 'kind': 'monitor-health',
            'subject': 'monitoring coverage failure', 'severity': 'serious',
            'routes': ['amon@atm-monitor'],
            'evidence': {'failed_sources': failed, 'partial_sources': partial,
                         'recovery_errors': recovery, 'activity_warnings': warnings}}


def _incidents(result):
    all_incidents = {}
    pending = {}
    for finding in result.get('findings', result.get('notify', [])) or []:
        if not isinstance(finding, dict) or not finding.get('incident_key'):
            continue
        all_incidents[finding['incident_key']] = dict(finding)
        routes = finding.get('pending_routes', finding.get('routes', []))
        if routes:
            pending[finding['incident_key']] = dict(finding, routes=sorted(set(routes)))
    health = _health_event(result)
    if health:
        all_incidents[health['incident_key']] = health
        pending[health['incident_key']] = health
    return all_incidents, pending


def _validate_state(previous):
    if previous is None:
        return {'schema_version': STATE_VERSION, 'incidents': {}}
    if not isinstance(previous, dict) or previous.get('schema_version') != STATE_VERSION:
        raise ValueError('corrupt agent gate state')
    incidents = previous.get('incidents')
    if not isinstance(incidents, dict):
        raise ValueError('corrupt agent gate state')
    for key, value in incidents.items():
        if not isinstance(key, str) or not isinstance(value, dict) or not isinstance(value.get('active'), bool) \
                or not isinstance(value.get('wake_sent'), bool):
            raise ValueError('corrupt agent gate state')
    return {'schema_version': STATE_VERSION, 'incidents': dict(incidents)}


def evaluate_gate(result, previous=None):
    """Return ``(decision, state)`` without performing IO or delivery."""
    if not isinstance(result, dict):
        raise ValueError('monitor result must be an object')
    state = _validate_state(previous)
    decision = {'wakeAgent': False, 'events': []}
    if result.get('status') in {'busy'} or result.get('exit_code') == 3:
        return decision, state
    current, pending = _incidents(result)
    coverage_good = (result.get('status', 'ok') == 'ok' and not result.get('failed_sources')
                     and not result.get('partial_sources') and not result.get('recovery_errors')
                     and not result.get('activity_warnings'))
    for key in current:
        prior = state['incidents'].get(key, {'active': False, 'wake_sent': False})
        wake = key in pending and not prior['wake_sent']
        state['incidents'][key] = {'active': True, 'wake_sent': prior['wake_sent'] or wake}
        if wake:
            decision['events'].append(pending[key])
            decision['wakeAgent'] = True
    if coverage_good:
        for key, prior in list(state['incidents'].items()):
            if key not in current and key not in result.get('unresolved_incidents', []) and prior['active']:
                state['incidents'][key] = {'active': False, 'wake_sent': False}
    return decision, state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-file', required=True, type=Path)
    parser.add_argument('--state-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = json.loads(args.result_file.read_text(encoding='utf-8'))
        with locked(args.state_dir):
            path = args.state_dir / 'agent_gate.json'
            decision, state = evaluate_gate(result, _load(path))
            _save(path, state)
        print(json.dumps(decision, sort_keys=True, separators=(',', ':')))
        return 0
    except BusyError:
        print('{"wakeAgent":false,"events":[]}')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'wakeAgent': False, 'events': [], 'error': str(exc)}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
