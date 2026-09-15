"""Explicit bounded windows survive pagination; no source parsing here."""
import atm_tasks
import atm_workflow
import gh_prs
import git_sprints
from time_rules import iso, timestamp


def calls(repo, policy, slots, now):
    previous = {s.key: s for s in slots}
    timeout = policy.command_timeout
    work = [('atm_tasks', lambda: atm_tasks.query(repo['team'], repo['actor'], policy.page_size, timeout))]
    checkpoints = []
    for phase in repo['phases']:
        key = 'git_sprints:' + phase['phase']
        slot = previous.get(key)
        scope = f"{repo['path']}@{phase['revision']}:{phase['plan']}"
        if not slot or slot.latest.status != 'ok' or slot.latest.scope != scope:
            work.append((key, lambda p=phase: git_sprints.query(repo['path'], p['revision'], p['plan'], timeout)))
    for name in ('atm_workflow', 'gh_prs'):
        slot = previous.get(name)
        since = slot.checkpoint if slot and slot.checkpoint else repo['since']
        start = (timestamp(since) or now) - policy.overlap_seconds
        end = min(start + policy.window_seconds, now)
        cursor = getattr(slot.latest, 'cursor', None) if slot else None
        if slot and slot.latest.status == 'error':
            cursor = getattr(slot.last_good, 'cursor', None)
        # Pending request inputs are persisted separately as a checkpoint in its own slot.
        pending = next((s for s in slots if s.key == name + ':window'), None)
        if slot and slot.latest.status != 'ok' and pending:
            start, end = pending.last_good.data[0]
        checkpoints.append((name, iso(end)))
        if name == 'atm_workflow':
            call = lambda a=iso(start), b=iso(end), c=cursor: atm_workflow.query(
                repo['team'], a, b, limit=policy.page_size, cursor=c, timeout=timeout)
        else:
            call = lambda a=iso(start), b=iso(end), c=cursor: gh_prs.query(
                repo['slug'], a, b, after=c, timeout=timeout)
        work.append((name, call))
        from query_types import Ok
        work.append((name + ':window', lambda n=name, a=start, b=end:
                     Ok(n + ':window', 'monitor', repo['slug'], ((a, b),), iso(now))))
    return work, tuple(checkpoints)
