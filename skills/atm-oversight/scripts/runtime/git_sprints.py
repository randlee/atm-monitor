"""Read configured sprint plan files at one pinned git revision."""
import re, json
from query_types import Ok, Partial, Error, Problem
from command_query import execute, now_iso, failure
from work_types import Sprint

def parse_plan(text):
    try:
        document=json.loads(text)
        rows=document.get('sprints',document) if isinstance(document,dict) else document
        if isinstance(rows,list):
            return tuple(Sprint(str(r['phase']),str(r['sprint']),r.get('branch'),r.get('order'),r.get('integration_branch'),r.get('status')) for r in rows if isinstance(r,dict) and r.get('phase') and r.get('sprint'))
    except (ValueError, KeyError, TypeError):
        pass
    blocks=re.findall(r'(?ms)^---\s*\n(.*?)^---\s*$',text)
    if not blocks: blocks=[text]
    out=[]
    for block in blocks:
        vals={}
        for line in block.splitlines():
            m=re.match(r'^\s*(phase|sprint|branch|integration_branch|status|order):\s*["\']?([^"\'#]+)',line)
            if m: vals[m.group(1)]=m.group(2).strip()
        if vals.get('phase') and vals.get('sprint'):
            order=int(vals['order']) if vals.get('order','').isdigit() else None
            out.append(Sprint(vals['phase'],vals['sprint'],vals.get('branch'),order,vals.get('integration_branch'),vals.get('status')))
    return tuple(out)

from query_guard import guarded


@guarded('git_sprints','git')
def query(repo_path, plan_revision, plan_file, timeout=30):
    scope=f'{repo_path}@{plan_revision}:{plan_file}'; args=('git','-C',repo_path,'show',f'{plan_revision}:{plan_file}')
    result=execute('git_sprints','git',scope,args,timeout=timeout)
    if isinstance(result,Error): return result
    try:
        data=parse_plan(result.stdout)
        # Phase-BB's authority file declares seven docs; each sprint doc owns
        # its branch frontmatter, so inventory is assembled from the pinned tree.
        problems=[]
        if '/phase-' in plan_file and re.search(r'/phase-[^/]+/phase-[^/]+-plan\.md$', plan_file):
            directory=plan_file.rsplit('/',1)[0]
            listed=execute('git_sprints','git',scope,('git','-C',repo_path,'ls-tree','-r','--name-only',plan_revision,'--',directory),timeout=timeout)
            if isinstance(listed,Error):
                problems.append(Problem('plan-tree-unavailable','Could not enumerate pinned plan directory',listed.problem.command,listed.problem.exit_code,listed.problem.diagnostics,listed.problem.retryable,listed.problem.retry_after,listed.problem.repair))
            else:
                records=[]
                for path in listed.stdout.splitlines():
                    match=re.search(r'/sprint-([A-Za-z]+\.\d+)-[^/]+\.md$',path)
                    if not match: continue
                    shown=execute('git_sprints','git',scope,('git','-C',repo_path,'show',f'{plan_revision}:{path}'),timeout=timeout)
                    if isinstance(shown,Error):
                        problems.append(Problem('plan-file-unavailable',f'Could not read {path}',shown.problem.command,shown.problem.exit_code,shown.problem.diagnostics,shown.problem.retryable,shown.problem.retry_after,shown.problem.repair))
                        continue
                    parsed=parse_plan(shown.stdout)
                    phase=directory.rsplit('/',1)[-1].replace('phase-','').upper()
                    branch=re.search(r'^branch:\s*["\']?([^"\'#\s]+)',shown.stdout,re.M)
                    status=re.search(r'^status:\s*["\']?([^"\'#\s]+)',shown.stdout,re.M)
                    records.append(Sprint(phase,match.group(1).upper(),branch.group(1) if branch else None,len(records)+1,'integrate/phase-'+phase.lower(),status.group(1) if status else None))
                if records: data=tuple(records)
                if len(records) != 7:
                    problems.append(Problem('incomplete-plan-inventory',f'Expected 7 sprints from phase authority, found {len(records)}',(),None,'',False,None,'Repair the pinned phase plan tree and sprint documents.'))
        if not data and not problems:
            raise ValueError('empty plan inventory')
    except (ValueError,TypeError) as exc: return failure('git_sprints','git',scope,'invalid-response',str(exc),args,repair='Repair explicit plan metadata at the pinned revision.')
    if problems:
        return Partial('git_sprints','git',scope,data,now_iso(),tuple(problems))
    return Ok('git_sprints','git',scope,data,now_iso())
run=query
