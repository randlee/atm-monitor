"""Fresh runnable-plus-idle evidence triggers investigation before intervention."""
from answer_types import Condition, Timer
from time_rules import elapsed, fresh, iso


def answer(tasks, agents, policy, now, timers=(), stale=False, activities=()):
    valid = {'idle:' + t.task_id + ':' + (t.assigned_at or t.assignment_evidence or t.assignee or 'unknown') for t in tasks}
    clocks = {x.key: x.since for x in timers if not x.key.startswith('idle:') or x.key in valid}
    by_agent = {}
    for agent in agents:
        by_agent.setdefault(agent.agent_id, []).append(agent)
    conditions = []
    for task in tasks:
        revision = task.assigned_at or task.assignment_evidence or task.assignee or 'unknown'
        key = 'idle:' + task.task_id + ':' + revision
        matches = by_agent.get(task.assignee, [])
        agent = matches[0] if len(matches) == 1 else None
        activity = next((a for a in activities if a.agent == task.assignee
                         and fresh(a.observed_at, now, policy.freshness_seconds)), None)
        recent = activity and elapsed(now, activity.message_at)
        progressing = recent is not None and recent <= policy.idle_grace_seconds
        available = agent and fresh(agent.observed_at, now, policy.freshness_seconds)
        state, kind = 'unknown', 'assigned-idle'
        detail = 'Assignment or harness context unavailable; preserve the prior incident.'
        simultaneous = False
        if not stale and task.status in {'completed', 'complete', 'closed', 'cancelled', 'refused'}:
            state, detail = 'clear', 'Task is closed.'
        elif progressing:
            state, detail = 'clear', 'Recent owner outbound message establishes activity: ' + activity.message_id
        elif available and agent.state.lower() in {'working', 'busy', 'active'}:
            state, detail = 'clear', 'Agent is working.'
        elif not stale and ((task.queue_position is not None and task.queue_position > 1) or task.dependency == 'waiting'):
            state, detail = 'clear', 'Legitimate queue/dependency wait.'
        elif available and agent.background in {'working', 'active'}:
            state, detail = 'clear', 'Background work explains foreground idle.'
        elif not stale and available and activity and agent.state.lower() == 'idle':
            simultaneous = task.status == 'active' or task.queue_position == 1
            if simultaneous:
                clocks.setdefault(key, iso(now))
                age = elapsed(now, clocks[key])
                state = 'active' if age is not None and age >= policy.idle_grace_seconds else 'clear'
                kind = 'idle-investigation'
                detail = f'{task.assignee} has runnable task {task.task_id} and idle observations. Observer {activity.host} has no recent outbound witness. Ask the owner for progress with a response deadline; verify owner-host/background/git activity before escalating. This is not stall or restart evidence.'
        if not simultaneous:
            clocks.pop(key, None)
        conditions.append(Condition(key, kind, task.task_id, revision, state,
                                    task.assignee or 'team-lead', detail, (task.task_id,)))
    return tuple(sorted(conditions, key=lambda c: c.key)), tuple(Timer(k, v) for k, v in sorted(clocks.items()))
