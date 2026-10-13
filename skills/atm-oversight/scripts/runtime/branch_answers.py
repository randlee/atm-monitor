"""Report remote stack order and preserve local branches without PRs."""
from branch_types import BranchRow
from pr_types import Stack, StackView, Ancestry
from source_queries import data


def answer(slots, prs):
    remote = {s.node_id: s for slot in slots if slot.key.startswith('gh_checks')
              for s in data(slots, slot.key, Stack)}
    current = {p.number: p for p in prs}
    ancestry = {(a.base_sha, a.head_sha): a.included for slot in slots
                if slot.key.startswith('gh_ancestry:') and slot.latest.status == 'ok'
                for a in data(slots, slot.key, Ancestry)}
    rows = []
    for identity, stack in sorted(remote.items()):
        seen = set()
        parent = stack.base or 'unknown'
        for item in stack.members:
            pr = current.get(item.number, item)
            included = ancestry.get((pr.base_sha, pr.head_sha))
            maintenance = 'unknown' if included is None else ('base included' if included else 'base not included')
            rows.append(BranchRow(identity, pr.head, pr.base or parent, '#' + str(pr.number),
                                  pr.head_sha, pr.state, maintenance))
            seen.add(pr.head)
            parent = pr.head
        for view in data(slots, 'gh_stack:' + identity, StackView):
            parent = view.trunk or 'unknown'
            for branch in view.branches:
                if branch not in seen:
                    rows.append(BranchRow(identity, branch, parent, 'unknown',
                        dict(view.heads).get(branch, 'unknown'), 'local-only observation', 'unknown'))
                parent = branch
    return tuple(rows)
