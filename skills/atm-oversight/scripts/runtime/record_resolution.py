"""Persist owner/host investigation evidence separately from delivery receipts."""
import argparse
from dataclasses import replace
from pathlib import Path
import time
from activity_types import IdleResolution
from answer_types import Envelope, QuerySlot, DomainState
from idle_dispositions import apply
from incident_decisions import decide
from query_types import Ok
from runtime_registry import REGISTRY
from state_disk import load, save, locked
from time_rules import iso


def record(env, key, outcome, reason, evidence, now):
    incident = next((i for i in env.incidents if i.key == key), None)
    if not incident or incident.condition.kind not in {'assigned-idle', 'idle-investigation'}:
        raise ValueError('An existing idle investigation is required')
    if outcome not in {'false-positive', 'resolved', 'reopen'} or not reason.strip() or not evidence:
        raise ValueError('Supply an outcome, reason and actual owner/host evidence')
    slot_key = 'idle_resolution:' + key
    prior = next((s for s in env.slots if s.key == slot_key), None)
    if outcome == 'reopen' and (not prior or set(evidence) <= set(prior.last_good.data[0].evidence)):
        raise ValueError('Reopening requires a previous disposition and new evidence')
    disposition = IdleResolution(key, outcome, reason, tuple(evidence), iso(now))
    result = Ok('idle_resolution', 'operator', key, (disposition,), iso(now))
    slot = QuerySlot(slot_key, result, result, 0, None)
    slots = tuple(sorted((*[s for s in env.slots if s.key != slot_key], slot), key=lambda s: s.key))
    state = env.state
    if key not in {c.key for c in state.conditions}:
        state = replace(state, conditions=(*state.conditions, incident.condition))
    state = apply(state, slots)
    incidents = decide(state.conditions, env.incidents, now)
    return replace(env, generation=env.generation + 1, state=state, slots=slots, incidents=incidents)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--incident', required=True)
    parser.add_argument('--outcome', choices=('false-positive', 'resolved', 'reopen'), required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--evidence', action='append', required=True)
    args = parser.parse_args()
    with locked(args.state_dir / 'runner'):
        env, _ = load(args.state_dir, Envelope, REGISTRY)
        if env is None:
            raise ValueError('State does not exist')
        updated = record(env, args.incident, args.outcome, args.reason, args.evidence, time.time())
        save(args.state_dir, updated, Envelope, REGISTRY)
        save(args.state_dir / 'events' / f'{updated.generation:012}', updated.state, DomainState, REGISTRY)


if __name__ == '__main__':
    main()
