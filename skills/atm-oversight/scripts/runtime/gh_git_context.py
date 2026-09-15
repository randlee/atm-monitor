"""One read-only snapshot of existing worktrees and local branch heads."""
from command_query import execute, now_iso
from query_types import Error, Ok

from query_guard import guarded


@guarded('gh_git_context','gh')
def query(repo_path, *, scope='git-context', timeout=30):
    wt = ('git','-C',repo_path,'worktree','list','--porcelain','-z')
    refs = ('git','-C',repo_path,'for-each-ref','--format=%(refname:short) %(objectname)','refs/heads/')
    a = execute('gh_git_context','git',scope,wt,cwd=repo_path,timeout=timeout)
    if isinstance(a, Error): return a
    b = execute('gh_git_context','git',scope,refs,cwd=repo_path,timeout=timeout)
    if isinstance(b, Error): return b
    fields = [x for x in a.stdout.split('\0') if x]
    worktrees = []
    current = []
    for field in fields:
        if field.startswith('worktree ') and current:
            worktrees.append('\n'.join(current)); current = []
        current.append(field)
    if current: worktrees.append('\n'.join(current))
    heads = tuple(x for x in b.stdout.splitlines() if x.strip())
    return Ok('gh_git_context','git',scope,(tuple(worktrees), tuple(heads)),now_iso())
