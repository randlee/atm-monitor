"""Fresh replacement identities retire obsolete revision-specific incidents."""
from dataclasses import replace


def retire(state, incidents):
    conditions = {c.key: c for c in state.conditions}
    heads = {c.subject: c.revision for c in state.conditions
             if c.kind == 'merge-conflict' and c.status != 'unknown'}
    fresh_tasks = {t.task_id for t in state.assignments if t.freshness == 'fresh'}
    assignments = {c.subject: c.key for c in state.conditions
                   if c.kind in {'assigned-idle', 'idle-investigation'} and c.subject in fresh_tasks}
    attempts = {c.key.rsplit(':', 2)[0]: c.key for c in state.conditions
                if c.kind in {'ci-failure', 'ci-stuck'} and c.status != 'unknown'}
    closed = {c.subject for c in state.conditions if c.kind == 'pr-closed' and c.status == 'clear'}
    for incident in incidents:
        c = incident.condition
        if not incident.active or c.key in conditions:
            continue
        changed_head = c.kind.startswith(('ci-', 'merge-', 'stack-')) and c.subject in heads and heads[c.subject] != c.revision
        changed_assignment = c.kind in {'assigned-idle', 'idle-investigation'} and c.subject in assignments and assignments[c.subject] != c.key
        changed_attempt = c.kind in {'ci-failure', 'ci-stuck'} and c.key.rsplit(':', 2)[0] in attempts
        completed = c.kind.startswith(('ci-', 'merge-', 'stack-')) and c.subject in closed
        if completed or changed_head or changed_assignment or changed_attempt:
            conditions[c.key] = replace(c, status='clear', detail='Fresh evidence supersedes this incident identity.')
    return replace(state, conditions=tuple(conditions[k] for k in sorted(conditions)))
