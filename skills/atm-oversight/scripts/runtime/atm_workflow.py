"""Bounded, explicitly tagged ATM workflow search."""
import json
from query_types import Ok, Partial, Error, Problem
from command_query import execute, now_iso, failure
from work_types import WorkflowEvent

def parse_events(text):
    raw=json.loads(text)
    rows=raw.get('events',raw.get('messages',raw.get('hits',raw))) if isinstance(raw,dict) else raw
    if not isinstance(rows,list): raise ValueError('expected workflow event array')
    out=[]
    for r in rows:
        if not isinstance(r,dict) or not r.get('message_id',r.get('id',r.get('event_id'))): raise ValueError('event identity missing')
        scope=r.get('workflow_scope') or {}
        workflow=r.get('workflow') if isinstance(r.get('workflow'),dict) else {}
        snapshot=workflow.get('snapshot',{}) if isinstance(workflow.get('snapshot',{}),dict) else {}
        scope=scope if isinstance(scope,dict) else {}
        event_id=str(r.get('message_id',r.get('id',r.get('event_id'))))
        out.append(WorkflowEvent(event_id,r.get('sprint',scope.get('id',snapshot.get('scope_id'))),r.get('stage',r.get('workflow_stage',snapshot.get('stage'))),r.get('task_id'),r.get('actor',r.get('sender',(r.get('from_agent') or {}).get('agent'))),r.get('revision',r.get('sha')),r.get('message_at',r.get('occurred_at',r.get('createdAt'))),bool(r.get('metadata_ok',True)),r.get('recipient',(r.get('to_agent') or {}).get('agent')),r.get('mailbox',(r.get('key') or {}).get('agent')),r.get('report_id',event_id),r.get('template_type'),snapshot.get('state'),str(snapshot.get('iteration')) if snapshot.get('iteration') is not None else None))
    cursor = raw.get('next_cursor', raw.get('cursor')) if isinstance(raw,dict) else None
    has_more = bool(raw.get('has_more', raw.get('more', False))) if isinstance(raw,dict) else False
    if has_more and not cursor:
        raise ValueError('workflow response indicates more results but has no cursor')
    return tuple(out), cursor

from query_guard import guarded


@guarded('atm_workflow','atm')
def query(team, since, until, sprint=None, stage=None, limit=100, cursor=None, timeout=30):
    scope=f'{team}:{sprint or "all"}:{since}/{until}'; args=['atm','search','--team',team,'--workflow-scope-kind','sprint']
    if sprint: args += ['--workflow-scope-id',sprint]
    if stage: args += ['--workflow-stage',stage]
    args += ['--since',since,'--until',until,'--limit',str(limit)]
    if cursor: args += ['--cursor',cursor]
    args += ['--json']; result=execute('atm_workflow','atm',scope,args,timeout=timeout)
    if isinstance(result,Error): return result
    try: data,next_cursor=parse_events(result.stdout)
    except (ValueError,json.JSONDecodeError) as exc: return failure('atm_workflow','atm',scope,'invalid-response',str(exc),args,repair='Inspect ATM workflow JSON and preserve tagged scope metadata.')
    if next_cursor:
        problem=Problem('incomplete-page','ATM returned a workflow continuation marker',args,None,'',False,None,'Continue the same tagged workflow window and deduplicate message IDs.')
        return Partial('atm_workflow','atm',scope,data,now_iso(),(problem,),next_cursor)
    return Ok('atm_workflow','atm',scope,data,now_iso())

run=query
