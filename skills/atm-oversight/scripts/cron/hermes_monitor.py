#!/usr/bin/env python3
"""Collect configured work and emit a durable notable-event wake decision."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from agent_gate import evaluate_gate, _load, _save
from detect_activity import detect
from monitor_phase import monitor
from state_store import BusyError, locked
from tick import load_config


def run(config_path, state_dir):
    state_dir = Path(state_dir)
    with locked(state_dir / 'scheduler'):
        try:
            config = load_config(Path(config_path).resolve())
            activity = detect(config, state_dir / 'activity')
            result = monitor(config, state_dir / 'activity', state_dir / 'phases')
            if activity.get('failed_sources'):
                result['failed_sources'] = sorted(set(result.get('failed_sources', [])) |
                                                   set(activity['failed_sources']))
        except BusyError:
            return {'wakeAgent': False, 'events': [], 'status': 'busy'}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result = {'status': 'error', 'failed_sources': ['scheduler-collection'],
                      'error': str(exc)}
        decision, state = evaluate_gate(result, _load(state_dir / 'scheduler' / 'agent_gate.json'))
        receipt = {'observed_at': datetime.now(timezone.utc).isoformat(),
                   'result': result, 'decision': decision}
        _save(state_dir / 'scheduler' / 'last_run.json', receipt)
        _save(state_dir / 'scheduler' / 'agent_gate.json', state)
        return decision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--state-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        decision = run(args.config, args.state_dir)
    except BusyError:
        decision = {'wakeAgent': False, 'events': [], 'status': 'busy'}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Separate durable latch preserves corrupt gate history for investigation.
        # A broken incident ledger must not trigger an LLM on every cron tick.
        decision = {'wakeAgent': False, 'events': [], 'error': str(exc)}
        latch = args.state_dir / 'scheduler' / 'gate_failure.json'
        try:
            latch.parent.mkdir(parents=True, exist_ok=True)
            with latch.open('x', encoding='utf-8') as out:
                json.dump({'error': str(exc)}, out)
                out.flush()
                os.fsync(out.fileno())
            decision.update(wakeAgent=True, events=[{
                'incident_key': 'scheduler-gate-failure', 'kind': 'monitor-health',
                'routes': ['amon@atm-monitor'], 'evidence': {'error': str(exc)}}])
        except OSError:
            # Existing latch or unwritable state: preserve history, remain quiet.
            pass
    print(json.dumps(decision, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
