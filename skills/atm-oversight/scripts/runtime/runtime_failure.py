"""Durable recovery incidents use the same verified receipt path as query alerts."""
from dataclasses import asdict
from pathlib import Path
import time
from answer_types import Envelope, DomainState, Condition
from incident_decisions import decide, reserve
from command_query import failure
from runtime_registry import REGISTRY
from state_disk import load, save, locked
from time_rules import iso


def record(directory, subject, error=None, shadow=False):
    directory = Path(directory) / 'runtime-failure'
    with locked(directory / 'runner'):
        return _record(directory, subject, error, shadow)


def _record(directory, subject, error, shadow):
    previous, _ = load(directory, Envelope, REGISTRY)
    if error is None and previous is None:
        return ()
    now = time.time()
    result = failure('runtime', 'monitor', subject, 'runtime-failure', str(error)[:2000],
        repair='Inspect the named runtime failure, preserve last valid state, and retry this repository.')
    condition = Condition('runtime:' + subject, 'runtime-repair', subject, '',
        'active' if error else 'clear', 'amon@atm-monitor',
        str(error)[:2000] if error else 'Runtime recovered.', (str(directory),))
    incidents = decide((condition,), previous.incidents if previous else (), now)
    intents, events = reserve(incidents, now) if not shadow else (incidents, ())
    envelope = Envelope(1, previous.generation + 1 if previous else 1,
        DomainState(subject, (), (condition,), 'unavailable'), (), intents, (), iso(now))
    save(directory, envelope, Envelope, REGISTRY)
    return tuple({'incident_key': e.key, 'kind': e.kind, 'repo': subject,
        'routes': [e.owner], 'state_dir': str(directory), 'evidence': asdict(e),
        'query_result': asdict(result)} for e in events)
