"""Combine source portions into O1–O4 without hiding a failed refresh."""
from dataclasses import replace
from answer_types import DomainState
from activity_types import OwnerActivity
from assignment_types import AssignmentState, AgentState
from pr_types import PR, Check, Requirement
from work_types import Sprint, Task, Agent, Member, Report, WorkflowEvent
from source_binding import bind_tasks, aliases
from source_queries import data
from time_rules import fresh
from query_memory import recovery
import ci_answers
import readiness_answers
import idle_answers
from idle_dispositions import conditions as resolved_conditions
import row_answers
import stack_answers
from stack_coverage import reconcile as reconcile_coverage
import branch_answers


def compose(repo, slots, policy, now, timers=()):
    stale = {s.key for s in slots if s.latest.status == 'error' or
             not fresh(s.latest.observed_at, now, policy.freshness_seconds)}
    sprints = tuple(x for s in slots if s.key.startswith('git_sprints:')
                    for x in data(slots, s.key, Sprint))
    tasks = data(slots, 'atm_tasks', Task)
    agents = tuple(a for a in data(slots, 'herdr_agents', Agent)
                   if a.team == repo['team'] or a.cwd and
                   (a.cwd == repo['path'] or a.cwd.startswith(repo['path'] + '-worktrees/')))
    if 'herdr_agents' in stale:
        agents = tuple(Agent(m.agent_id, m.state, m.observed_at, team=repo['team'])
                       for m in data(slots, 'atm_members', Member)) if 'atm_members' not in stale else ()
    candidates = {p.node_id: p for p in data(slots, 'gh_prs', PR)}
    candidates.update({p.node_id: p for p in data(slots, 'gh_checks', PR)})
    for slot in slots:
        if slot.key.startswith('gh_checks:stack:') and slot.latest.status != 'error':
            candidates.update({p.node_id: p for p in slot.latest.data if isinstance(p, PR)})
    prs = tuple(sorted((p for p in candidates.values() if any(p.head.startswith(x)
                       for x in repo['branch_prefixes'])), key=lambda p: p.number))
    checks = data(slots, 'gh_checks', Check)
    tasks, provisional = bind_tasks(repo, sprints, tasks, data(slots, 'atm_workflow', WorkflowEvent), prs)
    current = next((s.latest for s in slots if s.key == 'gh_checks'), None)
    expected = tuple((s.key.split(':', 1)[1], tuple(r.name for r in s.last_good.data
                     if isinstance(r, Requirement) and r.state == 'expected')) for s in slots
                     if s.key.startswith('gh_requirements:') and s.last_good and s.latest.status == 'ok')
    ci, clock = readiness_answers.answer(prs, slots, policy, now, timers, expected)
    activity = tuple(a for s in slots if s.key.startswith('atm_owner_activity:')
                     and s.latest.status == 'ok' for a in s.latest.data if isinstance(a, OwnerActivity))
    idle, clock = idle_answers.answer(tasks, agents, policy, now, clock, 'atm_tasks' in stale, activity)
    idle = resolved_conditions(idle, slots)
    repairs = reconcile_coverage(recovery(slots, policy), slots, prs, policy, now)
    conditions = tuple(sorted((*ci, *idle, *stack_answers.answer(slots, prs), *repairs), key=lambda c: c.key))
    reports = {}
    events = {e.report_id: e for e in data(slots, 'atm_workflow', WorkflowEvent)}
    for slot in slots:
        if slot.key.startswith(('atm_report:', 'gh_qa:')) and slot.last_good:
            sprint = slot.key.split(':')[1]
            for report in slot.last_good.data:
                if isinstance(report, Report):
                    event = events.get(report.report_id)
                    if event:
                        report = replace(report, review_id=event.task_id or report.review_id or event.event_id,
                                         round=str(event.iteration) if event.iteration is not None else None)
                    reports.setdefault(sprint, []).append(report)
    rows = row_answers.answer(sprints + provisional, tasks, prs, tuple((k, tuple(v)) for k, v in reports.items()),
                              conditions, stale, aliases(repo, prs))
    count = sum(p['expected_sprints'] for p in repo['phases'])
    inventory = 'complete' if len(sprints) == count and all(s.latest.status == 'ok' for s in slots
                  if s.key.startswith('git_sprints:')) else 'incomplete'
    routed = tuple(replace(c, owner=c.owner + '@' + repo['team']) if '@' not in c.owner else c for c in conditions)
    assignments = tuple(AssignmentState(t.task_id, t.sprint, t.assignee, t.status, t.assigned_at,
        t.started_at, t.queue_position, t.dependency, 'stale' if 'atm_tasks' in stale else 'fresh')
        for t in sorted(tasks, key=lambda t: t.task_id))
    agent_state = tuple(AgentState(a.agent_id, a.state, a.background,
        'fresh' if fresh(a.observed_at, now, policy.freshness_seconds) else 'stale')
        for a in sorted(agents, key=lambda a: a.agent_id))
    return DomainState(repo['slug'], rows, routed, inventory, branch_answers.answer(slots, prs), assignments, agent_state), clock
