"""Answer O3 from exact-head observations, without querying or sending."""
from answer_types import Condition, Timer
from time_rules import elapsed, iso


def answer(prs, checks, policy, now, timers=(), expected=(), complete=True, stale=False):
    clock = {x.key: x.since for x in timers}
    conditions = []
    requirements = dict(expected)
    for pr in prs:
        prefix = f'pr:{pr.number}:{pr.head_sha}'
        evidence = (pr.node_id, pr.head_sha)
        closed = pr.state != 'OPEN'
        conflict = pr.mergeable == 'CONFLICTING' or pr.merge_state == 'DIRTY'
        status = 'clear' if closed and not stale else ('unknown' if stale or pr.merge_state in {None, 'UNKNOWN'} else 'clear')
        if not stale and not closed and conflict:
            status = 'active'
        conditions.append(Condition(prefix + ':conflict', 'merge-conflict', str(pr.number),
                                    pr.head_sha, status, 'team-lead',
                                    'Merge conflict prevents merge; inspect base/head and repair CI prerequisites.', evidence))
        exact = pr.rollup_sha == pr.head_sha
        current = [c for c in checks if c.pr_number == pr.number and c.head_sha == pr.head_sha]
        for check in current:
            identity = check.attempt or check.started_at or check.name
            key = prefix + ':' + check.name + ':' + identity
            failed = check.conclusion in {'FAILURE', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE'}
            failed |= check.status in {'FAILURE', 'ERROR'}
            state = 'clear' if closed and not stale else ('unknown' if stale or not exact else ('active' if failed else 'clear'))
            if not closed and check.status == 'COMPLETED' and check.conclusion is None:
                state = 'unknown'
            conditions.append(Condition(key + ':failed', 'ci-failure', str(pr.number), pr.head_sha,
                state, 'team-lead', f'{check.name}: {check.conclusion or check.status}; inspect {check.url or "check log"}.', evidence))
            running = check.status == 'IN_PROGRESS'
            pending = check.status in {'QUEUED', 'PENDING', 'WAITING', 'REQUESTED'}
            anchor = check.started_at if running else check.queued_at
            observed_key = key + ':observed-pending'
            if not stale and exact and not closed and (running or pending) and anchor is None:
                clock.setdefault(observed_key, iso(now))
                anchor = clock[observed_key]
            elif not (running or pending) or stale:
                clock.pop(observed_key, None)
            age = elapsed(now, anchor)
            limit = policy.ci_run_seconds if running else policy.ci_queue_seconds
            state = 'clear' if closed and not stale else ('unknown' if stale or not exact or ((running or pending) and age is None) else 'clear')
            if not closed and not stale and exact and (running or pending) and age is not None and age >= limit:
                state = 'active'
            conditions.append(Condition(key + ':stuck', 'ci-stuck', str(pr.number), pr.head_sha,
                state, 'team-lead', f'{check.name}: {check.status}; inspect runner/job queue. Missing provider timing uses a conservative first-confirmed observation.', evidence))
        eligible = (not stale and complete and pr.draft is False and pr.queued is False
                    and pr.state == 'OPEN' and pr.mergeable == 'MERGEABLE' and not conflict)
        for name in requirements.get(pr.base, ()):
            key = prefix + ':missing:' + name
            absent = name not in {c.name for c in current}
            if eligible and complete and (exact or pr.rollup_sha is None) and absent:
                clock.setdefault(key, iso(now))
                state = 'active' if elapsed(now, clock[key]) >= policy.ci_start_seconds else 'clear'
            else:
                clock.pop(key, None)
                state = 'clear' if not stale and complete and (not absent or conflict) else 'unknown'
            conditions.append(Condition(key, 'ci-not-started', str(pr.number), pr.head_sha,
                state, 'team-lead', f'Required check {name} has not appeared after the configured eligible-head grace; inspect workflow triggers.', evidence))
    return tuple(sorted(conditions, key=lambda c: c.key)), tuple(Timer(k, v) for k, v in sorted(clock.items()))
