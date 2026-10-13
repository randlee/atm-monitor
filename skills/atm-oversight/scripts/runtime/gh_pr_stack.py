"""Conditional REST lookup for remote stack membership."""
import json
from command_query import execute, now_iso
from query_types import Error, Ok
from pr_types import Stack

from query_guard import guarded


@guarded('gh_pr_stack','gh')
def query(repo_slug, pr_number, *, stack_number=None, scope='stack-membership', timeout=30):
    if stack_number is None:
        path = f'repos/{repo_slug}/stacks?pull_request={int(pr_number)}'
    else:
        path = f'repos/{repo_slug}/stacks/{int(stack_number)}'
    cmd = ('gh','api','--method','GET',path)
    result = execute('gh_pr_stack','github',scope,cmd,timeout=timeout)
    if isinstance(result, Error): return result
    try: raw = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        from command_query import failure
        return failure('gh_pr_stack','github',scope,'invalid-response',str(exc),cmd)
    items = raw if isinstance(raw,list) else [raw]
    data = tuple(Stack(str(x.get('id','')),x.get('number'),x.get('baseRefName')) for x in items if isinstance(x,dict))
    return Ok('gh_pr_stack','github',scope,data,now_iso())
