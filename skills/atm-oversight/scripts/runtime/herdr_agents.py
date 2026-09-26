"""Live Herdr machine snapshot; command has no invented selector flags."""
import json
from query_types import Ok, Error
from command_query import execute, now_iso, failure
from work_types import Agent

def parse_agents(text, observed_at=None):
    raw=json.loads(text)
    if isinstance(raw,dict) and isinstance(raw.get('result'),dict):
        raw=raw['result']
    rows=raw.get('agents',raw) if isinstance(raw,dict) else raw
    if not isinstance(rows,list): raise ValueError('expected agents array')
    out=[]
    for r in rows:
        if not isinstance(r,dict) or not r.get('id',r.get('agent_id',r.get('name'))): raise ValueError('agent identity missing')
        aid=str(r.get('agent_id',r.get('name')))
        if aid == 'None':
            aid = str(r.get('agent', 'unknown'))
        state=str(r.get('agent_status',r.get('state',r.get('status','unknown'))))
        out.append(Agent(aid,state,r.get('observed_at',observed_at),r.get('task_id'),
                         r.get('background'),r.get('team'),r.get('cwd'),r.get('background_evidence'),
                         r.get('state_since',r.get('state_changed_at'))))
    return tuple(out)

from query_guard import guarded


@guarded('herdr_agents','herdr')
def query(timeout=30):
    scope='machine-snapshot'; args=('herdr','agent','list'); result=execute('herdr_agents','herdr',scope,args,timeout=timeout)
    if isinstance(result,Error): return result
    observed_at=now_iso()
    try: data=parse_agents(result.stdout,observed_at)
    except (ValueError,json.JSONDecodeError) as exc: return failure('herdr_agents','herdr',scope,'invalid-response',str(exc),args,repair='Verify installed Herdr agent list output format; no --json selector is supported.')
    return Ok('herdr_agents','herdr',scope,data,observed_at)
run=query
