"""Read-only scheduler execution receipts."""
import sqlite3
from pathlib import Path
from recovery_types import SchedulerRun
from query_types import Error, Problem, Ok
from command_query import now_iso

def recent(db_path, job_id, limit=20):
    if not isinstance(job_id,str) or not job_id or not isinstance(limit,int) or limit<1: raise ValueError('invalid job or limit')
    p=Path(db_path); con=sqlite3.connect(f'file:{p}?mode=ro',uri=True)
    try:
        cols={r[1] for r in con.execute('pragma table_info(executions)')}
        required={'id','job_id','status','claimed_at','started_at','finished_at','error'}
        if not required <= cols: raise ValueError('unsupported executions schema')
        rows=con.execute('select id,job_id,status,claimed_at,started_at,finished_at,error from executions where job_id=? order by claimed_at desc limit ?', (job_id,limit)).fetchall()
        return tuple(SchedulerRun(r[1],r[0],r[2],r[3],r[4],r[5],r[6],True,r[2]=='completed') for r in rows)
    finally: con.close()

def registered(db_path, job_id, limit=20): return recent(db_path,job_id,limit)

def read(db_path, job_id, limit=20):
    try: return Ok('scheduler_runs', 'hermes', job_id, recent(db_path, job_id, min(limit, 20)), now_iso())
    except (OSError, sqlite3.Error, ValueError) as exc:
        return Error('scheduler-runs','hermes',job_id,'',Problem(
            'invalid-response' if isinstance(exc,ValueError) else 'unavailable',str(exc),
            retryable=not isinstance(exc,ValueError),repair='Verify the readonly executions database and scheduler schema.'))
