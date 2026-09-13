"""External scheduler watchdog; emits deduplicable O4 conditions only."""
from answer_types import Condition
from time_rules import elapsed

def inspect(observed_at, now, policy, incidents=(), scheduler_runs=()):
    conditions=[]
    age=elapsed(now,observed_at)
    status = 'unknown' if age is None else ('active' if age >= policy.watchdog_seconds else 'clear')
    conditions.append(Condition('watchdog:missed-run','scheduler-missed','cron','',status,'amon@atm-monitor','No fresh envelope observed within the watchdog deadline.',(observed_at or '',)))
    for i in incidents:
        age = elapsed(now, i.last_attempt)
        status = 'unknown'
        if not i.active or i.delivery in {'delivered', 'acknowledged'}:
            status = 'clear'
        elif age is not None:
            status = 'active' if age >= policy.followup_seconds else 'clear'
        conditions.append(Condition(i.key + ':delivery', 'delivery-overdue', i.condition.subject,
            i.condition.revision, status, 'amon@atm-monitor',
            'Incident handoff lacks a verified delivery receipt; reconcile transport before resending.', i.condition.evidence))
    return tuple(sorted({c.key:c for c in conditions}.values(),key=lambda c:c.key))
