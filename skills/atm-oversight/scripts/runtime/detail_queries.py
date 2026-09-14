"""Select identified current PRs and reports; never scan task histories."""
import atm_report
import atm_owner_activity
import atm_members
import gh_checks
import gh_requirements
import gh_git_context
from pr_types import PR
from current_prs import select
from work_types import WorkflowEvent, Task, Agent
from source_queries import data
from time_rules import elapsed, iso
from source_binding import scope
from query_memory import due


def calls(repo, slots, policy, now):
    previous = {s.key: s for s in slots}
    candidates = {p.node_id: p for p in select(slots)}
    known = [p for p in candidates.values() if any(p.head.startswith(x) for x in repo['branch_prefixes'])]
    ids = sorted({p.node_id for p in known if p.state == 'OPEN'} | set(repo.get('seed_pr_ids', ())))
    work = []
    idle = {a.agent_id for a in data(slots, 'herdr_agents', Agent) if a.state.lower() == 'idle'}
    owners = sorted({t.assignee for t in data(slots, 'atm_tasks', Task) if t.assignee in idle
                     and (t.status == 'active' or t.queue_position == 1)})
    owners.sort(key=lambda a: previous['atm_owner_activity:' + a].latest.observed_at
                if 'atm_owner_activity:' + a in previous else '')
    for owner in owners[:policy.detail_budget]:
        work.append(('atm_owner_activity:' + owner, lambda a=owner: atm_owner_activity.query(
            repo['team'], a, iso(now - policy.idle_grace_seconds), iso(now), policy.command_timeout)))
    harness = previous.get('herdr_agents')
    if harness and harness.latest.status == 'error':
        work.append(('atm_members', lambda: atm_members.query(repo['team'], timeout=policy.command_timeout)))
    if ids:
        slot = previous.get('gh_checks')
        cursor = getattr(slot.last_good, 'cursor', None) if slot and slot.latest.status != 'ok' else None
        work.append(('gh_checks', lambda: gh_checks.query(ids, scope=repo['slug'],
                     timeout=policy.command_timeout, continuation=cursor, budget=policy.github_page_budget)))
    for branch in sorted({p.base for p in known if p.state == 'OPEN'}):
        key = 'gh_requirements:' + branch
        slot = previous.get(key)
        age = elapsed(now, slot.latest.observed_at) if slot else None
        if not slot or slot.latest.status != 'ok' or age is None or age >= policy.policy_refresh_seconds:
            work.append((key, lambda b=branch: gh_requirements.query(repo['slug'], b, timeout=policy.command_timeout)))
    if any(p.stack_id for p in known if p.state == 'OPEN'):
        work.append(('gh_git_context', lambda: gh_git_context.query(repo['path'], timeout=policy.command_timeout)))
    for event in sorted(data(slots, 'atm_workflow', WorkflowEvent), key=lambda e: e.event_id, reverse=True):
        if not event.sprint or not event.report_id or event.template_type not in {'qa-quality-report', 'qa-findings-report'}:
            continue
        sprint = scope(repo, event.sprint)
        key = 'atm_report:' + sprint + ':' + event.report_id
        prior = previous.get(key)
        if (not prior or prior.latest.status != 'ok') and due(prior, now):
            mailbox = event.mailbox or event.recipient or repo['actor']
            work.append((key, lambda e=event, m=mailbox: atm_report.query(
                repo['team'], m, e.report_id, timeout=policy.command_timeout)))
        if sum(k.startswith('atm_report:') for k, _ in work) >= policy.detail_budget:
            break
    return work
