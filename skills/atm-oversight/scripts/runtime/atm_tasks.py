"""Bounded current ATM task queue query."""
import json
import re
from query_types import Ok, Partial, Error, Problem
from command_query import execute, now_iso, failure
from work_types import Task

def parse_tasks(text):
    raw = json.loads(text)
    rows = raw.get('tasks', raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list): raise ValueError('expected tasks array')
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get('task_id', row.get('id')):
            raise ValueError('task identity missing')
        description = row.get('description')
        sprint = row.get('sprint')
        if not sprint and isinstance(description, str):
            match = re.search(r'\bsprint=["\']([^"\']+)' , description)
            sprint = match.group(1).upper() if match else None
        out.append(Task(str(row.get('task_id', row.get('id'))), sprint,
                        row.get('assignee', row.get('owner')), str(row.get('state', row.get('status', 'unknown'))),
                        row.get('assigned_at', row.get('assignedAt')), row.get('started_at', row.get('startedAt')),
                        row.get('queue_position', row.get('position')), row.get('dependency'),
                        description, row.get('assignment_message_id')))
    return tuple(out), bool(raw.get('next_cursor') if isinstance(raw, dict) else False)

from query_guard import guarded


@guarded('atm_tasks','atm')
def query(team, actor, limit=100, timeout=30):
    scope = f'{team}:current-queue'
    args = ('atm','task','list','--team',team,'--as',actor,'--all','--json')
    result = execute('atm_tasks','atm',scope,args,timeout=timeout)
    if isinstance(result, Error): return result
    try: data, more = parse_tasks(result.stdout)
    except (ValueError, json.JSONDecodeError) as exc: return failure('atm_tasks','atm',scope,'invalid-response',str(exc),args,repair='Inspect ATM task JSON schema and adapter.')
    if len(data) > limit:
        problem=Problem('scope-bound','Current queue exceeded configured adapter budget',args,None,'',False,None,'Use a supported narrower queue scope before advancing the checkpoint.')
        return Partial('atm_tasks','atm',scope,data[:limit],now_iso(),(problem,), 'queue-continuation-required')
    if more:
        problem=Problem('incomplete-page','ATM returned a continuation marker',args,None,'',False,None,'Continue the same bounded queue request and deduplicate task IDs.')
        return Partial('atm_tasks','atm',scope,data,now_iso(),(problem,), 'next_cursor')
    return Ok('atm_tasks','atm',scope,data,now_iso())

run = query
