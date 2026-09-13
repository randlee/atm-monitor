"""Spawn-isolated bounded repository workers."""
import multiprocessing as mp
import time
from pathlib import Path

def _run(repo, root, policy, now, agents, shadow):
    from repo_tick import tick
    repo_dir = Path(root) / repo['slug'].replace('/', '--')
    return tick(repo, repo_dir, policy, now, agents, shadow)

WORKER_TARGET = _run

def _entry(conn, repo, root, policy, now, agents, shadow, target=None):
    try:
        fn = target or WORKER_TARGET
        conn.send({'ok': True, 'result': fn(repo, root, policy, now, agents, shadow)})
    except Exception as exc:
        conn.send({'ok': False, 'error': f'{type(exc).__name__}: {exc}'})
    finally:
        conn.close()

def _stop(proc):
    if proc.is_alive():
        proc.terminate(); proc.join(1)
    if proc.is_alive() and hasattr(proc, 'kill'):
        proc.kill(); proc.join(1)

def results(configrepos, root, policy, now, agents, shadow=False, worker_limit=4, timeout=None, target=None):
    """Yield `(repo, payload)` as workers complete; one timeout cannot starve others."""
    repos=tuple(configrepos); limit=max(1,min(int(worker_limit),4)); timeout=float(timeout or getattr(policy,'repo_timeout_seconds',300))
    ctx=mp.get_context('spawn'); pending=list(repos); active={}; started={}; fn=target or WORKER_TARGET
    try:
      while pending or active:
        while pending and len(active)<limit:
            repo=pending.pop(0); parent,child=ctx.Pipe(False)
            # Pass the fixture target explicitly; globals are not inherited by spawn.
            proc=ctx.Process(target=_entry,args=(child,repo,root,policy,now,agents,shadow,fn)); proc.start(); child.close(); active[repo['slug']]=(proc,parent); started[repo['slug']]=time.monotonic()
        progressed=False
        for slug,(proc,conn) in list(active.items()):
            if conn.poll():
                try: payload=conn.recv()
                except (EOFError,OSError) as exc: payload={'ok':False,'error':f'transport: {exc}'}
                proc.join(1)
                if proc.is_alive(): _stop(proc)
                conn.close(); del active[slug]; yield next(r for r in repos if r['slug']==slug), payload; progressed=True; continue
            if not proc.is_alive():
                proc.join(); conn.close(); del active[slug]; yield next(r for r in repos if r['slug']==slug), {'ok':False,'error':'worker exited without result'}; progressed=True; continue
            if time.monotonic()-started[slug] >= timeout:
                _stop(proc); conn.close(); del active[slug]
                yield next(r for r in repos if r['slug']==slug), {'ok':False,'error':f'timeout after {timeout:g}s','retryable':True}; progressed=True
        if not progressed: time.sleep(0.01)
    finally:
      for proc,conn in active.values():
        _stop(proc); conn.close()
