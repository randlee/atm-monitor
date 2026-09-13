"""Conditional QA fallback for an identified head; cache until PR evidence changes."""
import gh_qa
from pr_types import PR
from work_types import Report
from source_queries import data
from source_binding import aliases
from time_rules import timestamp
from query_memory import due


def calls(repo, slots, policy, now):
    prior = {s.key: s for s in slots}
    prs = data(slots, 'gh_checks', PR)
    reports = tuple(r for s in slots if s.key.startswith('atm_report:')
                    for r in data(slots, s.key, Report))
    groups = dict(aliases(repo, prs))
    output = []
    for sprint, branches in sorted(groups.items()):
        candidates = sorted((p for p in prs if p.head in branches and p.state == 'OPEN'),
                            key=lambda p: p.number, reverse=True)
        for pr in candidates:
            if any(r.revision and len(r.revision) >= 7 and pr.head_sha.startswith(r.revision) for r in reports):
                continue
            key = f'gh_qa:{sprint}:{pr.number}:{pr.head_sha}'
            old = prior.get(key)
            changed = old and (timestamp(pr.updated_at) or 0) > (timestamp(old.latest.observed_at) or 0)
            if due(old, now) and (not old or old.latest.status == 'error' or changed):
                output.append((key, lambda p=pr: gh_qa.query(repo['slug'], p.number, p.head_sha,
                    scope=f'{repo["slug"]}:{p.number}@{p.head_sha}', timeout=policy.command_timeout)))
            if len(output) >= policy.detail_budget:
                return output
    return output
