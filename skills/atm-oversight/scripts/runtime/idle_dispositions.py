"""Keep a resolved investigation quiet for the same assignment identity."""
from dataclasses import replace
from activity_types import IdleResolution


def conditions(items, slots):
    dispositions = {r.incident_key: r for s in slots if s.key.startswith('idle_resolution:')
                    and s.last_good for r in s.last_good.data if isinstance(r, IdleResolution)}
    output = []
    for condition in items:
        resolution = dispositions.get(condition.key)
        if resolution and resolution.outcome != 'reopen':
            condition = replace(condition, status='clear',
                detail=f'Investigation {resolution.outcome}: {resolution.reason}', evidence=resolution.evidence)
        output.append(condition)
    return tuple(output)


def apply(state, slots):
    return replace(state, conditions=conditions(state.conditions, slots))
