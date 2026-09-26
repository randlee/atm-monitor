"""Did this owner send any message in the bounded observation window?"""
import json
import socket
from activity_types import OwnerActivity
from command_query import execute, failure, now_iso
from query_guard import guarded
from query_types import Error, Ok
from time_rules import timestamp


@guarded('atm_owner_activity', 'atm')
def query(team, agent, since, until, timeout=30):
    host = socket.gethostname()
    scope = f'{team}:{agent}@{host}:{since}..{until}'
    args = ('atm', 'search', '--team', team, '--from', agent, '--since', since,
            '--until', until, '--limit', '1', '--json')
    result = execute('atm_owner_activity', 'atm', scope, args, timeout=timeout)
    if isinstance(result, Error):
        return result
    try:
        rows = json.loads(result.stdout)['hits']
        if not isinstance(rows, list) or len(rows) > 1:
            raise ValueError('Expected at most one owner-send witness')
        observed, sent, identity = now_iso(), None, None
        if rows:
            row = rows[0]
            sender = row['from_agent']
            sent, identity = row['message_at'], row['message_id']
            if sender.get('agent') != agent or sender.get('team') != team or not identity:
                raise ValueError('Owner identity mismatch')
            if timestamp(sent) is None or not timestamp(since) <= timestamp(sent) <= timestamp(until):
                raise ValueError('Message outside requested window')
        # This asks existence, not history completeness: one witness is sufficient.
        return Ok('atm_owner_activity', 'atm', scope,
                  (OwnerActivity(agent, host, observed, sent, identity),), observed)
    except (KeyError, TypeError, ValueError) as exc:
        return failure('atm_owner_activity', 'atm', scope, 'invalid-response', str(exc), args,
                       repair='Verify the explicit owner/team/window and observer store. Empty results do not prove owner-host inactivity.')
