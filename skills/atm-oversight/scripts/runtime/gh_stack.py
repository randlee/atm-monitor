"""Read-only local gh-stack view and exact-SHA ancestry evidence."""
import json
from dataclasses import replace
from command_query import execute, now_iso
from query_types import Error, Ok, Partial, Problem
from pr_types import StackView, Ancestry

def _problem(kind, message, command=(), code=None, repair='Bind a known existing member worktree and retry.'):
    return Problem(kind, message, tuple(command), code, '', False, None, repair, 'amon@atm-monitor')

from query_guard import guarded


@guarded('gh_stack','gh')
def query(repo_path, *, scope='stack', timeout=30, alternatives=()):
    failures = []
    for path in tuple(dict.fromkeys((repo_path, *alternatives)))[:2]:
        views = execute('gh_stack','github',scope,('gh','stack','view','--json'),cwd=path,timeout=timeout)
        if not isinstance(views, Error):
            break
        failures.append(f'cwd={path}: {views.problem.diagnostics or views.problem.message}')
        if views.problem.exit_code not in (2, 6):
            break
    if isinstance(views, Error):
        problem = replace(views.problem, diagnostics='\n'.join(failures)[-2000:])
        if problem.exit_code in (2, 6):
            problem = replace(problem, kind='local-stack-context', retryable=True,
                repair='Retry a discovered member worktree with local gh-stack tracking. Remote stack/check and exact ancestry queries remain independent; do not initialize or change the monitored stack.')
        return replace(views, problem=problem)
    try: raw = json.loads(views.stdout)
    except (TypeError, ValueError) as exc:
        return Error('gh_stack','github',scope,now_iso(),_problem('invalid-response',str(exc),('gh','stack','view','--json'),repair='Check gh-stack version and JSON schema.'))
    if not isinstance(raw, dict):
        return Error('gh_stack','github',scope,now_iso(),_problem('invalid-response','Stack view must be an object.'))
    branches = raw.get('branches') or raw.get('entries') or []
    names = tuple(x.get('branch',x.get('name','')) if isinstance(x,dict) else str(x) for x in branches)
    data = StackView(raw.get('trunk'), tuple(x for x in names if x), raw.get('base'),
        tuple((b['name'], b['head']) for b in branches if b.get('head')),
        tuple((b['name'], b['pr']['number']) for b in branches if isinstance(b.get('pr'), dict)),
        tuple(b['name'] for b in branches if b.get('isMerged')),
        tuple(b['name'] for b in branches if b.get('isQueued')),
        tuple(b['name'] for b in branches if b.get('needsRebase')))
    return Ok('gh_stack','github',scope,(data,),now_iso())

def ancestry(repo_path, base_sha, head_sha, *, scope='ancestry', timeout=30):
    cmd = ('git','-C',repo_path,'merge-base','--is-ancestor',base_sha,head_sha)
    result = execute('gh_stack','git',scope,cmd,cwd=repo_path,timeout=timeout,accepted=(0,1))
    if isinstance(result, Error): return result
    data = Ancestry(repo_path,base_sha,head_sha,result.exit_code == 0)
    return Ok('gh_stack','git',scope,(data,),now_iso())
