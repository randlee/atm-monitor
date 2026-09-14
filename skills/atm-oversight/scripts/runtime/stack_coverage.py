"""Accept remote stack coverage without claiming local tracking was repaired."""
from dataclasses import replace
from pr_types import PR, Stack, Ancestry
from time_rules import fresh


def covered(identity, slots, prs, policy, now):
    remote = next((s for s in slots if s.key == 'gh_checks:stack:' + identity), None)
    if not remote or remote.latest.status != 'ok' or not remote.last_good:
        return False
    if not fresh(remote.latest.observed_at, now, policy.freshness_seconds):
        return False
    stack = next((s for s in remote.last_good.data if isinstance(s, Stack) and s.node_id == identity), None)
    if not stack or not stack.members or not stack.base:
        return False
    members = sorted(stack.members, key=lambda p: p.stack_position or 0)
    if [p.stack_position for p in members] != list(range(1, len(members) + 1)):
        return False
    current = {p.node_id: p for p in prs}
    parent = stack.base
    for member in members:
        pr = current.get(member.node_id)
        if not pr or pr.head_sha != member.head_sha or pr.base_sha != member.base_sha:
            return False
        if (pr.head, pr.base, pr.state, pr.stack_id) != (member.head, member.base, member.state, identity):
            return False
        if member.stack_id != identity or member.base != parent:
            return False
        parent = member.head
        if member.state != 'OPEN':
            continue
        ancestry = next((s for s in slots if s.key == f'gh_ancestry:{member.number}'), None)
        if not ancestry or ancestry.latest.status != 'ok' or not ancestry.last_good:
            return False
        if not any(isinstance(a, Ancestry) and a.base_sha == member.base_sha and
                   a.head_sha == member.head_sha for a in ancestry.last_good.data):
            return False
    return True


def reconcile(conditions, slots, prs, policy, now):
    queries = {s.key: s for s in slots}
    output = []
    for condition in conditions:
        slot = queries.get(condition.subject)
        if condition.subject.startswith('gh_stack:') and slot and slot.latest.status == 'error':
            if slot.latest.problem.kind == 'local-stack-context':
                identity = condition.subject.split(':', 1)[1]
                if covered(identity, slots, prs, policy, now):
                    condition = replace(condition, status='clear', kind='coverage-note', detail=
                        'Remote stack order, current readiness and exact ancestry cover monitored PRs. '
                        'Local tracking remains unavailable; unpublished local branches are unknown.',
                        evidence=(identity, 'gh_checks:stack:' + identity))
        output.append(condition)
    return tuple(output)
