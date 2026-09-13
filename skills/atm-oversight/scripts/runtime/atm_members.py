"""ATM roster fallback, retaining source observation timestamps."""
import json
from query_types import Ok, Error
from command_query import execute, now_iso, failure
from work_types import Member

def parse_members(text):
    raw=json.loads(text)
    rows=raw.get('members',raw) if isinstance(raw,dict) else raw
    if not isinstance(rows,list): raise ValueError('expected members array')
    out=[]
    for r in rows:
        if not isinstance(r,dict) or not r.get('agent_id',r.get('id')): raise ValueError('member identity missing')
        out.append(Member(str(r.get('agent_id',r.get('id'))),str(r.get('status',r.get('state','unknown'))),r.get('last_observed_at',r.get('observed_at',r.get('observedAt')))))
    return tuple(out)

from query_guard import guarded


@guarded('atm_members','atm')
def query(team, timeout=30):
    scope=f'{team}:roster'; args=('atm','members','--team',team,'--json'); result=execute('atm_members','atm',scope,args,timeout=timeout)
    if isinstance(result,Error): return result
    try: data=parse_members(result.stdout)
    except (ValueError,json.JSONDecodeError) as exc: return failure('atm_members','atm',scope,'invalid-response',str(exc),args,repair='Inspect ATM roster JSON schema.')
    return Ok('atm_members','atm',scope,data,now_iso())
run=query
