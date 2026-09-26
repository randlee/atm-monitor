"""Keep successful portions and checkpoints separate from failed refreshes."""
from dataclasses import replace
from answer_types import QuerySlot, Condition
from query_types import Error, Ok, Partial
from time_rules import iso, timestamp


def item_key(item):
    for name in ('node_id', 'task_id', 'event_id', 'report_id', 'sprint', 'agent_id'):
        if getattr(item, name, None):
            return (type(item).__name__, getattr(item, name))
    if hasattr(item, 'pr_number'):
        return (type(item).__name__, item.pr_number, item.head_sha, item.name, item.attempt)
    return (type(item).__name__, repr(item))


def remember(key, result, old, now, policy, checkpoint=None, accumulate=False):
    latest = result
    good = old.last_good if old else None
    failed = isinstance(result, Error) or isinstance(result, Partial) and any(p.kind != 'pagination' for p in result.problems)
    failures = (old.failures if old else 0) + 1 if failed else 0
    retry_at = None
    if isinstance(result, Error):
        delay = min(policy.retry_seconds * 2 ** min(failures - 1, 6), policy.followup_seconds)
        retry_at = iso(max(now + delay, result.problem.retry_after or 0))
    else:
        if (accumulate or isinstance(result, Partial) or isinstance(good, Partial)) and good:
            merged = {item_key(x): x for x in good.data}
            merged.update({item_key(x): x for x in result.data})
            result = replace(result, data=tuple(merged[k] for k in sorted(merged)))
        good = result
    accepted = checkpoint if isinstance(result, Ok) else (old.checkpoint if old else None)
    return QuerySlot(key, good, latest, failures, retry_at, accepted)


def due(slot, now):
    return not slot or not slot.retry_at or (timestamp(slot.retry_at) or 0) <= now


def recovery(slots, policy):
    output = []
    for slot in slots:
        result = slot.latest
        problem = result.problem if isinstance(result, Error) else None
        if isinstance(result, Partial) and result.problems:
            problem = next((p for p in result.problems if p.kind != 'pagination'), None)
        state = 'clear'
        if problem:
            state = 'active' if not problem.retryable or slot.failures > policy.retries else 'unknown'
        detail = f'{slot.key}: {problem.kind}: {problem.message}. {problem.repair}' if problem else f'{slot.key} query succeeded.'
        output.append(Condition('query:' + slot.key, 'query-repair', slot.key, '', state,
                                'amon@atm-monitor', detail, (result.scope,)))
    return tuple(output)
