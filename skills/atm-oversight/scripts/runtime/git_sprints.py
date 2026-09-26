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

SPRINT_DOC=re.compile(r'/sprint-(?:(?P<bare>[A-Za-z]+\.\d+)|(?P<pl>[A-Za-z][A-Za-z0-9]*)-(?P<num>\d+))-(?!sanity)[^/]*\.md$')

def _field(text,name):
    m=re.search(rf'^[ \t]*(?:[-*][ \t]+)?{name}[^:]*?[:=][ \t]*[`"\']?([^\n`"\'#]+?)[`"\']?[ \t]*$',text,re.M|re.I)
    return m.group(1).strip() if m else None

from query_guard import guarded


@guarded('git_sprints','git')
def query(repo_path, plan_revision, plan_file, timeout=30, expected_sprints=None):
    scope=f'{repo_path}@{plan_revision}:{plan_file}'; args=('git','-C',repo_path,'show',f'{plan_revision}:{plan_file}')
    result=execute('git_sprints','git',scope,args,timeout=timeout)
    if isinstance(result,Error): return result
    try:
        data=parse_plan(result.stdout)
        # Authority trees assemble inventory from every sprint document in the
        # pinned plan directory. Both naming conventions are accepted:
        # sprint-BB.3-*.md and sprint-d-10-*.md; sanity companions are excluded.
        # Metadata may be key:value frontmatter or markdown bullets
        # ("- Branch: `sprint/d-1...`", "- PR target ...: `integrate/...`").
        problems=[]
        if '/phase-' in plan_file and re.search(r'/phase-[^/]+/(phase-[^/]+-plan|plan-[^/]+)\.md$', plan_file):
            directory=plan_file.rsplit('/',1)[0]
            listed=execute('git_sprints','git',scope,('git','-C',repo_path,'ls-tree','-r','--name-only',plan_revision,'--',directory),timeout=timeout)
            if isinstance(listed,Error):
                problems.append(Problem('plan-tree-unavailable','Could not enumerate pinned plan directory',listed.problem.command,listed.problem.exit_code,listed.problem.diagnostics,listed.problem.retryable,listed.problem.retry_after,listed.problem.repair))
            else:
                records=[]
                phase=directory.rsplit('/',1)[-1].replace('phase-','').upper()
                for path in listed.stdout.splitlines():
                    match=SPRINT_DOC.search(path)
                    if not match: continue
                    identity=match.group('bare').upper() if match.group('bare') else phase+'.'+match.group('num')
                    shown=execute('git_sprints','git',scope,('git','-C',repo_path,'show',f'{plan_revision}:{path}'),timeout=timeout)
                    if isinstance(shown,Error):
                        problems.append(Problem('plan-file-unavailable',f'Could not read {path}',shown.problem.command,shown.problem.exit_code,shown.problem.diagnostics,shown.problem.retryable,shown.problem.retry_after,shown.problem.repair))
                        continue
                    parsed=parse_plan(shown.stdout)
                    row=next((r for r in parsed if str(r.sprint).upper().split('.')[-1]==identity.split('.')[-1]),parsed[0] if parsed else None)
                    branch=_field(shown.stdout,'branch') or (row.branch if row else None)
                    status=_field(shown.stdout,'status') or (row.status if row else None)
                    integration=_field(shown.stdout,'PR target') or (row.integration_branch if row else None) or 'integrate/phase-'+phase.lower()
                    records.append(Sprint(phase,identity,branch,len(records)+1,integration,status))
                if records: data=tuple(records)
                expected=expected_sprints if expected_sprints is not None else 7
                if len(records) != expected:
                    problems.append(Problem('incomplete-plan-inventory',f'Expected {expected} sprints from phase authority, found {len(records)}',(),None,'',False,None,'Repair the pinned phase plan tree and sprint documents.'))
        if not data and not problems:
            raise ValueError('empty plan inventory')
    except (ValueError,TypeError) as exc: return failure('git_sprints','git',scope,'invalid-response',str(exc),args,repair='Repair explicit plan metadata at the pinned revision.')
    if problems:
        return Partial('git_sprints','git',scope,data,now_iso(),tuple(problems))
    return Ok('git_sprints','git',scope,data,now_iso())
run=query
