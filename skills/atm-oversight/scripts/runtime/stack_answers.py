"""Only fresh ancestry on current remote SHA pairs supports maintenance alerts."""
from answer_types import Condition
from pr_types import Ancestry
from source_queries import data


def answer(slots, prs):
    current = {(p.base_sha, p.head_sha): p for p in prs if p.state == 'OPEN'}
    output = []
    for slot in slots:
        if not slot.key.startswith('gh_ancestry:'):
            continue
        for item in data(slots, slot.key, Ancestry):
            pr = current.get((item.base_sha, item.head_sha))
            if pr is None:
                continue
            status = 'unknown' if slot.latest.status != 'ok' else ('clear' if item.included else 'active')
            output.append(Condition(f'ancestry:{pr.number}:{item.base_sha}:{item.head_sha}',
                'stack-maintenance', str(pr.number), item.head_sha, status, 'team-lead',
                'Current base ancestry: ' + ('included.' if item.included else 'not included; inspect merge-forward or team-approved maintenance. No automatic rebase.'),
                (item.base_sha, item.head_sha)))
    return tuple(sorted(output, key=lambda c: c.key))
