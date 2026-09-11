"""Scheduler contract: silent success, structured attention, distinct errors."""

import json


def emit(result, diagnostic=False):
    if result.get('status') == 'busy':
        code = 3
    elif (result.get('status') == 'error' or result.get('failed_sources')
          or result.get('recovery_errors') or result.get('activity_warnings')):
        code = 2
    elif (result.get('notify') or result.get('onboarding_requests')
          or any(item.get('candidate_ids') for item in result.get('unresolved_agents', []))):
        code = 1
    else:
        code = 0
    if diagnostic or code in {1, 2}:
        print(json.dumps(dict(result, exit_code=code), indent=2))
    return code
