"""Separate scheduled execution watches missed ticks and undelivered intents."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from answer_types import Envelope, DomainState, Condition
from incident_decisions import decide, reserve
from runtime_registry import REGISTRY
from runtime_policy import read_policy
from state_disk import load, save, locked
from time_rules import iso
from watchdog import inspect
from scheduler_runs import read
from query_types import Error
from runtime_failure import record
from state_store import BusyError


def run(config, root, directory, now):
    policy = read_policy(config['policy'])
    previous, _ = load(directory, Envelope, REGISTRY)
    conditions = []
    for repo in config['repos']:
        slug = repo['slug']
        try:
            env, _ = load(Path(root) / slug.replace('/', '--'), Envelope, REGISTRY)
            if not env:
                raise ValueError('Monitoring state is missing; restore the primary scheduled job.')
            conditions.append(Condition(slug + ':state', 'runtime-repair', slug, '', 'clear',
                              'amon@atm-monitor', 'State readable.', (str(root),)))
            for condition in inspect(env.observed_at, now, policy, env.incidents):
                conditions.append(Condition(slug + ':' + condition.key, condition.kind, slug,
                    condition.revision, condition.status, 'amon@atm-monitor', condition.detail, condition.evidence))
        except (OSError, ValueError) as exc:
            conditions.append(Condition(slug + ':state', 'runtime-repair', slug, '', 'active',
                              'amon@atm-monitor', str(exc), (str(root),)))
    binding = config.get('scheduler')
    if binding:
        result = read(binding['executions_db'], binding['job_id'])
        if isinstance(result, Error):
            conditions.append(Condition('scheduler:receipts', 'query-repair', 'scheduler', '', 'active',
                              'amon@atm-monitor', result.problem.repair, (result.problem.message,)))
        else:
            conditions.append(Condition('scheduler:receipts', 'query-repair', 'scheduler', '', 'clear',
                              'amon@atm-monitor', 'Scheduler receipts readable.', (binding['job_id'],)))
    incidents = decide(conditions, previous.incidents if previous else (), now)
    intents, events = reserve(incidents, now)
    envelope = Envelope(1, previous.generation + 1 if previous else 1,
        DomainState('watchdog', (), tuple(conditions), 'not-applicable'), (), intents, (), iso(now))
    save(directory, envelope, Envelope, REGISTRY)
    return {'wakeAgent': bool(events), 'events': [{'incident_key': e.key, 'kind': e.kind,
            'routes': [e.owner], 'evidence': asdict(e), 'state_dir': str(directory)} for e in events]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--watchdog-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        with locked(args.watchdog_dir / 'runner'):
            result = run(json.loads(args.config.read_text()), args.state_dir, args.watchdog_dir, time.time())
            record(args.watchdog_dir / 'failure', 'watchdog')
    except BusyError:
        result = {'wakeAgent': False, 'events': [], 'status': 'busy'}
    except Exception as exc:
        events = record(args.watchdog_dir / 'failure', 'watchdog', str(exc))
        result = {'wakeAgent': bool(events), 'events': events, 'error': str(exc)[:2000]}
    print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    main()
