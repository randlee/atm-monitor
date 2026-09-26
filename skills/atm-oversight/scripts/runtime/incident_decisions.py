"""Pure incident transitions; unknown observations never establish recovery."""
from dataclasses import replace
from answer_types import Incident
from time_rules import iso


def decide(conditions, prior, now):
    incidents = {i.key: i for i in prior}
    for condition in conditions:
        old = incidents.get(condition.key)
        if condition.status == 'active':
            if not old or not old.active:
                incidents[condition.key] = Incident(condition.key, condition, True, 'pending', iso(now))
            else:
                incidents[condition.key] = replace(old, condition=condition)
        elif condition.status == 'clear' and old:
            incidents[condition.key] = replace(old, active=False, condition=condition)
    return tuple(incidents[k] for k in sorted(incidents))


def reserve(incidents, now):
    events = []
    updated = []
    for incident in incidents:
        if incident.active and incident.delivery == 'pending':
            events.append(incident.condition)
            incident = replace(incident, delivery='attempting', last_attempt=iso(now))
        updated.append(incident)
    return tuple(updated), tuple(events)
