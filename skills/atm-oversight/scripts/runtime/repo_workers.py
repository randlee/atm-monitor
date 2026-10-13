"""Spawn-isolated bounded repository workers."""
import multiprocessing as mp
import time
from pathlib import Path


def _run(repo, root, policy, now, agents, shadow):
    from repo_tick import tick
    return tick(repo, Path(root) / repo['slug'].replace('/', '--'), policy, now, agents, shadow)


WORKER_TARGET = _run


def _entry(conn, repo, root, policy, now, agents, shadow, target=None):
    try:
        result = (target or WORKER_TARGET)(repo, root, policy, now, agents, shadow)
        conn.send({'ok': True, 'result': result})
    except Exception as exc:
        conn.send({'ok': False, 'error': f'{type(exc).__name__}: {exc}'})
    finally:
        conn.close()


def _stop(proc):
    if proc.is_alive():
        proc.terminate()
        proc.join(1)
    if proc.is_alive():
        proc.kill()
    proc.join(1)


def results(configrepos, root, policy, now, agents, shadow=False, worker_limit=4, timeout=None, target=None):
    """Yield each result independently, including bounded transport/timeout failures."""
    pending = list(configrepos)
    limit = max(1, min(int(worker_limit), 4))
    timeout = float(timeout or policy.repo_timeout_seconds)
    ctx, active = mp.get_context('spawn'), {}
    try:
        while pending or active:
            while pending and len(active) < limit:
                repo = pending.pop(0)
                parent, child = ctx.Pipe(False)
                proc = ctx.Process(target=_entry, args=(child, repo, root, policy, now,
                                   agents, shadow, target or WORKER_TARGET))
                proc.start()
                child.close()
                active[repo['slug']] = (repo, proc, parent, time.monotonic())
            progressed = False
            for slug, (repo, proc, conn, started) in list(active.items()):
                payload = None
                if conn.poll():
                    try:
                        payload = conn.recv()
                    except (EOFError, OSError) as exc:
                        payload = {'ok': False, 'error': f'transport: {exc}'}
                    proc.join(1)
                elif not proc.is_alive():
                    payload = {'ok': False, 'error': 'worker exited without result'}
                elif time.monotonic() - started >= timeout:
                    payload = {'ok': False, 'error': f'timeout after {timeout:g}s', 'retryable': True}
                if payload is None:
                    continue
                _stop(proc)
                conn.close()
                del active[slug]
                progressed = True
                yield repo, payload
            if not progressed:
                time.sleep(0.01)
    finally:
        for repo, proc, conn, started in active.values():
            _stop(proc)
            conn.close()
