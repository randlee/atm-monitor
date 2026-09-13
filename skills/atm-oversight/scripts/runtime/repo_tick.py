"""One isolated repository tick: ask, compose, commit, then reserve handoff."""
from dataclasses import asdict
from pathlib import Path
import time
from answer_types import Envelope, DomainState
from command_query import failure, now_iso
from query_types import Ok
from compose_state import compose
from detail_queries import calls as details
from incident_decisions import decide, reserve
from query_catalog import calls
from render_report import write_report
from runtime_registry import REGISTRY
from source_queries import execute_calls
from state_disk import load, save, locked
from time_rules import iso
from stack_queries import calls as stacks
from retire_conditions import retire
from fallback_queries import calls as fallbacks


def tick(repo, directory, policy, now, agents, shadow=False):
    directory = Path(directory)
    with locked(directory / 'runner'):
        previous, loaded_from = load(directory, Envelope, REGISTRY)
        slots = previous.slots if previous else ()
        planned, checkpoints = calls(repo, policy, slots, now)
        planned.append(('herdr_agents', lambda: agents))
        if loaded_from and loaded_from.name != 'state.json':
            planned.append(('state_recovery', lambda: failure('state_recovery', 'monitor', repo['slug'],
                'corrupt-state', 'Recovered the last valid generation.', repair='Inspect archived corrupt primary and verify subsequent persistence.')))
        elif any(s.key == 'state_recovery' for s in slots):
            planned.append(('state_recovery', lambda: Ok('state_recovery', 'monitor', repo['slug'], (), now_iso())))
        slots = execute_calls(planned, slots, policy, now, checkpoints, ('atm_workflow', 'gh_prs'))
        slots = execute_calls(details(repo, slots, policy, now), slots, policy, now)
        slots = execute_calls(stacks(repo, slots, policy, now), slots, policy, now)
        slots = execute_calls(fallbacks(repo, slots, policy, now), slots, policy, now)
        now = time.time()
        state, timers = compose(repo, slots, policy, now, previous.timers if previous else ())
        state = retire(state, previous.incidents if previous else ())
        incidents = decide(state.conditions, previous.incidents if previous else (), now)
        intents, events = reserve(incidents, now) if not shadow else (incidents, ())
        generation = previous.generation + 1 if previous else 1
        envelope = Envelope(1, generation, state, slots, intents, timers, iso(now))
        # No wake can leave this function until its state and action intent are durable.
        save(directory, envelope, Envelope, REGISTRY)
        write_report(directory / 'report.md', envelope)
        changed = not previous or previous.state != state
        if changed:
            save(directory / 'events' / f'{generation:012}', state, DomainState, REGISTRY)
        output = []
        for event in events:
            payload = {'incident_key': event.key, 'kind': event.kind, 'subject': event.subject,
                'repo': repo['slug'], 'routes': [event.owner], 'evidence': asdict(event),
                'state_dir': str(directory), 'report': str(directory / 'report.md')}
            if event.kind == 'query-repair':
                slot = next(s for s in slots if s.key == event.subject)
                payload['query_result'] = asdict(slot.latest)
            output.append(payload)
        return {'repo': repo['slug'], 'wakeAgent': bool(output), 'events': output,
                'changed': changed, 'report': str(directory / 'report.md'),
                'generation': generation, 'rows': len(state.rows)}
