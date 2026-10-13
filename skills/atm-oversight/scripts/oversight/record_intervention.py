#!/usr/bin/env python3
"""Checkpoint a confirmed delivery, acknowledgment, or resolution."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cron'))
from state_store import BusyError, locked, read_latest, save


def record(directory, incident, recipient, status, evidence_id):
    if status not in {'sent', 'acknowledged', 'resolved'} or not all((incident, recipient, evidence_id)):
        raise ValueError('incident, recipient, status, and evidence ID are required')
    with locked(directory):
        state, errors = read_latest(directory)
        if state is None or errors:
            raise ValueError('refresh missing or recovered state before recording delivery')
        item = {'status': status, 'evidence_id': evidence_id,
                'at': datetime.now(timezone.utc).isoformat()}
        state.setdefault('interventions', {}).setdefault(incident, {})[recipient] = item
        state.setdefault('intervention_history', []).append(dict(item, incident=incident, recipient=recipient))
        return str(save(directory, state))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir', type=Path, required=True)
    p.add_argument('--incident', required=True)
    p.add_argument('--recipient', required=True)
    p.add_argument('--status', choices=['sent', 'acknowledged', 'resolved'], required=True)
    p.add_argument('--evidence-id', required=True, help='actual message ID or resolution evidence reference')
    args = p.parse_args()
    try:
        path = record(args.state_dir, args.incident, args.recipient, args.status, args.evidence_id)
        print(json.dumps({'status': 'ok', 'snapshot': path}))
        return 0
    except (ValueError, OSError, BusyError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
