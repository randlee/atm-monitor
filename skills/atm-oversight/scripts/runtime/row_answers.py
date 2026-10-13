"""Build every configured sprint row with field-level evidence and gaps."""
from answer_types import Fact, SprintRow


def fact(values, evidence=(), stale=False, support='authoritative'):
    text = ', '.join(sorted(set(str(x) for x in values if x is not None)))
    return Fact(text or 'unknown', support if text else 'unknown',
                'stale' if stale else 'fresh', tuple(sorted(set(evidence))))


from review_answers import reviews


def answer(sprints, tasks, prs, reports=(), conditions=(), stale_sources=(), aliases=()):
    rows = []
    branch_aliases = dict(aliases)
    report_map = dict(reports)
    for sprint in sorted(sprints, key=lambda s: (s.phase, s.order or 0, s.sprint)):
        assigned = [t for t in tasks if t.sprint == sprint.sprint]
        branches = {sprint.branch, *branch_aliases.get(sprint.sprint, ())}
        related = [p for p in prs if p.head in branches]
        active = [p for p in related if p.state == 'OPEN']
        current = active or [p for p in related if p.state == 'MERGED'] or related
        task_ids = tuple(t.task_id for t in assigned)
        owner = fact([t.assignee for t in assigned], task_ids, 'atm_tasks' in stale_sources)
        task_fact = fact([t.task_id + ':' + t.status for t in assigned], task_ids, 'atm_tasks' in stale_sources)
        dev = fact([t.status for t in assigned], task_ids, 'atm_tasks' in stale_sources)
        if not assigned and related:
            dev = fact([f'PR {p.number} {p.state.lower()} into {p.base}' for p in current],
                       tuple(p.node_id for p in current), support='PR evidence')
        if not assigned and not related:
            dev = Fact('planned; execution unknown', 'plan', evidence=(sprint.sprint,))
        qa, rounds, counts = reviews(report_map.get(sprint.sprint, ()), {p.head_sha for p in active})
        pr_evidence = tuple(p.node_id + '@' + p.head_sha for p in current)
        pr_fact = fact([f'#{p.number} {p.state}' for p in current], pr_evidence, 'gh_checks' in stale_sources)
        ci = fact([f'#{p.number}: {p.rollup_state or "unknown"}; merge {p.merge_state or "unknown"}'
                   for p in current], pr_evidence, 'gh_checks' in stale_sources)
        blockers = [c.detail for c in conditions if c.status == 'active' and
                    (c.subject in {str(p.number) for p in current} or c.subject in task_ids)]
        blocker = fact(blockers, pr_evidence)
        action = blockers[0] if blockers else ('Obtain revision-addressed QA evidence.' if qa.support == 'unknown' else 'Track current assignments and PR completion.')
        rows.append(SprintRow(sprint.phase, sprint.sprint, sprint.branch or 'unknown',
            sprint.integration_branch or 'unknown', owner, task_fact, dev, qa, rounds,
            counts, pr_fact, ci, blocker, action))
    return tuple(rows)
