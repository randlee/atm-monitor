"""Identify merge incidents whose absence cannot prove recovery this tick."""
from check_health import finding


def unresolved_incidents(snapshot):
    keys = set()
    for team in snapshot['teams']:
        name = team['name']
        source = snapshot['sources'].get(name + '/ci', {})
        if source.get('status') not in {'ok', 'partial'}:
            continue  # The gate already preserves incidents on failed coverage.
        for pr in source.get('data') or []:
            if pr.get('state') != 'OPEN':
                continue
            if pr.get('mergeStateStatus') not in {None, 'UNKNOWN'}:
                continue
            subject = [pr['number'], pr['headRefOid']]
            for status in ('BLOCKED', 'BEHIND', 'UNSTABLE'):
                keys.add(finding(name, 'merge-blocked', subject + [status], [], {})['incident_key'])
            keys.add(finding(name, 'merge-conflict', subject, [], {})['incident_key'])
    return sorted(keys)
