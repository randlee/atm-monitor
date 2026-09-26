"""Read branch protection and explicitly reported required checks."""
import json
from urllib.parse import quote
from command_query import execute, now_iso, failure
from query_types import Error, Ok, Partial, Problem
from pr_types import Requirement

from query_guard import guarded


@guarded('gh_requirements','gh')
def query(repo_slug, branch, *, pr_number=None, scope='requirements', timeout=30):
    path = f'repos/{repo_slug}/branches/{quote(branch, safe="")}/protection'
    cmd = ('gh','api','--method','GET',path)
    result = execute('gh_requirements','github',scope,cmd,timeout=timeout)
    if isinstance(result, Error):
        primary = result.problem
        rules = f'repos/{repo_slug}/rules/branches/{quote(branch, safe="")}'
        rules_result = execute('gh_requirements','github',scope,('gh','api','--method','GET',rules),timeout=timeout)
        if not isinstance(rules_result, Error):
            try:
                raw_rules = json.loads(rules_result.stdout)
                rules_list = raw_rules if isinstance(raw_rules, list) else (raw_rules.get('rules') or [])
                names = []
                for rule in rules_list:
                    if not isinstance(rule, dict): continue
                    if rule.get('type') == 'required_status_checks':
                        names.extend(Requirement(str(x.get('context','')), 'expected') for x in rule.get('parameters', {}).get('required_status_checks', ()) if x.get('context'))
                    elif rule.get('name'):
                        names.append(Requirement(str(rule['name']), 'expected'))
                names = tuple(names)
                absent_protection = primary.exit_code == 1 and 'not protected' in primary.diagnostics.lower()
                if absent_protection:
                    return Ok('gh_requirements','github',scope,names,now_iso())
                return Partial('gh_requirements','github',scope,names,now_iso(),(primary,),None)
            except (TypeError, ValueError):
                pass
        if pr_number is None: return result
        cmd = ('gh','pr','checks',str(int(pr_number)),'--repo',repo_slug,'--required','--json','name,state,bucket,startedAt,completedAt,event,workflow,link')
        result = execute('gh_requirements','github',scope,cmd,timeout=timeout,accepted=(0,8))
        if isinstance(result, Error): return result
    try: raw = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        return failure('gh_requirements','github',scope,'invalid-response',str(exc),cmd)
    if isinstance(raw, list):
        rows = tuple(Requirement(str(x.get('name','')),str(x.get('state',x.get('bucket','unknown'))),x.get('event'),x.get('workflow'),x.get('startedAt'),x.get('completedAt'),x.get('link')) for x in raw if isinstance(x,dict))
    else:
        checks = (((raw.get('required_status_checks') or {}).get('contexts')) or [])
        rows = tuple(Requirement(str(x),'expected') for x in checks)
    return Ok('gh_requirements','github',scope,rows,now_iso())
