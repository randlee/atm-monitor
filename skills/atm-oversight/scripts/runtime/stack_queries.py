"""Bind each identified stack to one existing context and exact remote SHAs."""
import gh_stack
import gh_checks
from command_query import failure
from pr_types import PR
from source_queries import data


def calls(repo, slots, policy, now):
    current = {p.node_id: p for p in data(slots, 'gh_prs', PR)}
    current.update({p.node_id: p for p in data(slots, 'gh_checks', PR)})
    groups = {}
    for pr in current.values():
        if pr.stack_id and pr.state == 'OPEN' and any(pr.head.startswith(p) for p in repo['branch_prefixes']):
            groups.setdefault(pr.stack_id, []).append(pr)
    context = data(slots, 'gh_git_context')
    worktrees = context[0] if context else ()
    output = []
    for identity, members in sorted(groups.items()):
        branches = [p.head for p in sorted(members, key=lambda p: p.stack_position or 0, reverse=True)]
        candidates = [w.split('\n')[0].removeprefix('worktree ') for b in branches for w in worktrees
                      if 'branch refs/heads/' + b in w.split('\n')]
        candidates.sort(key=lambda p: p not in repo.get('preferred_stack_contexts', ()))
        old = next((s for s in slots if s.key == 'gh_stack:' + identity), None)
        offset = old.failures if old and old.latest.status == 'error' else 0
        path = candidates[offset % len(candidates)] if candidates else None
        check_slot = next((s for s in slots if s.key == 'gh_checks:stack:' + identity), None)
        cursor = getattr(check_slot.last_good, 'cursor', None) if check_slot and check_slot.latest.status != 'ok' else None
        output.append(('gh_checks:stack:' + identity, lambda i=identity, c=cursor:
                       gh_checks.query((i,), scope=repo['slug'], timeout=policy.command_timeout, budget=policy.github_page_budget, continuation=c)))
        if path:
            output.append(('gh_stack:' + identity, lambda p=path:
                           gh_stack.query(p, timeout=policy.command_timeout)))
            for member in members:
                key = f'gh_ancestry:{member.number}'
                previous = next((s for s in slots if s.key == key), None)
                values = previous.last_good.data if previous and previous.last_good else ()
                if previous and previous.latest.status == 'ok' and any(
                        a.base_sha == member.base_sha and a.head_sha == member.head_sha for a in values):
                    continue
                output.append((key, lambda p=path, b=member.base_sha, h=member.head_sha:
                               gh_stack.ancestry(p, b, h, timeout=policy.command_timeout)))
        else:
            output.append(('gh_stack:' + identity, lambda i=identity: failure('gh_stack', 'git', i,
                'missing-context', 'No existing member worktree is available.',
                repair='Bind an existing stack member worktree; remote PR/check evidence remains available.')))
    return output
