"""Resolve freshness and coverage independently for each current PR head."""
from pr_types import PR, Check
from answer_types import Condition
from time_rules import fresh
import ci_answers


def answer(prs, slots, policy, now, timers=(), expected=()):
    conditions, clock = [], timers
    sources = [s for s in slots if s.key == 'gh_checks' or s.key.startswith('gh_checks:stack:')]
    for pr in prs:
        closed = pr.state in {'MERGED', 'CLOSED'}
        if closed:
            conditions.append(Condition(f'pr:{pr.number}:{pr.head_sha}:closed', 'pr-closed',
                str(pr.number), pr.head_sha, 'clear', 'team-lead',
                'Provider confirms PR ' + pr.state.lower() + '.', (pr.node_id, pr.updated_at)))
            continue
        candidates = []
        for slot in sources:
            if slot.latest.status == 'error' or not slot.last_good:
                continue
            if not fresh(slot.latest.observed_at, now, policy.freshness_seconds):
                continue
            observed = next((p for p in slot.last_good.data if isinstance(p, PR)
                             and p.node_id == pr.node_id and p.head_sha == pr.head_sha
                             and p.state == pr.state and p.base == pr.base), None)
            if observed:
                candidates.append((slot, observed))
        candidates.sort(key=lambda x: (x[0].latest.status == 'ok', x[0].latest.observed_at), reverse=True)
        selected = candidates[0] if candidates else None
        checks = {}
        for slot, observed in candidates:
            for check in slot.last_good.data:
                if isinstance(check, Check) and check.pr_number == pr.number and check.head_sha == pr.head_sha:
                    checks.setdefault((check.name, check.attempt), check)
        current, clock = ci_answers.answer((selected[1] if selected else pr,), tuple(checks.values()),
            policy, now, clock, expected, complete=bool(selected and selected[0].latest.status == 'ok'),
            stale=selected is None and not closed)
        conditions.extend(current)
    return tuple(sorted(conditions, key=lambda c: c.key)), clock
