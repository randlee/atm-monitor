"""Join explicit task/workflow/PR references without inventing completion."""
from dataclasses import replace
import re
from work_types import Sprint


def aliases(repo, prs):
    output = {k: set(v) for k, v in repo.get('aliases', {}).items()}
    for sprint, patterns in repo.get('branch_patterns', {}).items():
        output.setdefault(sprint, set()).update(p.head for p in prs if any(re.fullmatch(pattern, p.head) for pattern in patterns))
    return tuple((k, tuple(sorted(v))) for k, v in sorted(output.items()))


def scope(repo, value):
    if value in repo.get('scope_aliases', {}):
        return repo['scope_aliases'][value]
    matches = [s for s, patterns in repo.get('scope_patterns', {}).items()
               if value and any(re.fullmatch(p, value) for p in patterns)]
    return matches[0] if len(matches) == 1 else value


def bind_tasks(repo, sprints, tasks, workflow, prs):
    scopes = repo.get('scope_aliases', {})
    known = {s.sprint for s in sprints}
    by_task = {}
    for event in workflow:
        identity = scope(repo, event.sprint)
        if event.task_id and identity in known:
            by_task.setdefault(event.task_id, set()).add(identity)
    by_branch = {s.branch: s.sprint for s in sprints}
    for sprint, branches in aliases(repo, prs):
        by_branch.update({b: sprint for b in branches})
    by_pr = {p.number: by_branch[p.head] for p in prs if p.head in by_branch}
    bound = []
    provisional = []
    for task in tasks:
        candidates = by_task.get(task.task_id, set())
        if task.sprint in known:
            candidates = {task.sprint}
        if not candidates:
            candidates = {by_pr[int(n)] for n in re.findall(r'(?:PR\s*)?#(\d+)', task.description or '') if int(n) in by_pr}
        sprint = next(iter(candidates)) if len(candidates) == 1 else 'unscoped:' + task.task_id
        bound.append(replace(task, sprint=sprint))
        if sprint.startswith('unscoped:'):
            provisional.append(Sprint('Unscoped assignments', sprint, None, None, None, 'association unknown'))
    for pr in prs:
        if pr.state == 'OPEN' and pr.head not in by_branch:
            provisional.append(Sprint('Other active work', f'PR #{pr.number}', pr.head,
                                      pr.number, pr.base, 'phase association unknown'))
    return tuple(bound), tuple(provisional)
