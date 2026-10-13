"""Exception-safe bounded query invocation."""
from datetime import datetime, timezone, timedelta
from query_types import Ok, Partial, Error, Problem

def _now(): return datetime.now(timezone.utc).isoformat()

def run(query, source, scope, call, retries=0, retry_delay=1.0):
    attempts=0; last=None
    while attempts <= max(0,retries):
        attempts += 1
        try: result=call()
        except Exception as exc: result=None; last=str(exc)
        if isinstance(result,(Ok,Partial,Error)): return result
        last=last or 'query returned an invalid result union'
        if attempts <= retries: continue
    p=Problem('invalid-response','Query failed or returned an invalid union',(),None,last[-2000:],True,
              (datetime.now(timezone.utc)+timedelta(seconds=retry_delay)).timestamp(),
              'Repair the query boundary or its source adapter.')
    return Error(query,source,scope,_now(),p)
