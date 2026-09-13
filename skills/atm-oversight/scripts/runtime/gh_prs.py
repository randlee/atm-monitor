"""Bounded GraphQL search for relevant pull requests."""
from pr_types import PR
from query_types import Error, Problem
from gh_common import gql, envelope, api_error
from command_query import failure

QUERY = '''query($search:String!,$after:String){search(query:$search,type:ISSUE,first:50,after:$after){pageInfo{hasNextPage endCursor}nodes{... on PullRequest{id number updatedAt state headRefName headRefOid baseRefName baseRefOid isDraft mergeable mergeStateStatus isInMergeQueue stack{id number} stackEntry{position} statusCheckRollup{state commit{oid}}}}}rateLimit{cost remaining resetAt}}'''

def _pr(n):
    required = ('id','number','headRefName','headRefOid','baseRefName','baseRefOid','state')
    if not isinstance(n, dict) or any(not n.get(k) for k in required) or not isinstance(n.get('number'), int): return None
    r, s, e = n, n.get('stack') or {}, n.get('statusCheckRollup') or {}
    c = e.get('commit') or {}
    return PR(str(r.get('id','')), r['number'], str(r.get('updatedAt','')), str(r.get('state','')),
              str(r.get('headRefName','')), str(r.get('headRefOid','')), str(r.get('baseRefName','')),
              str(r.get('baseRefOid','')), r.get('isDraft'), r.get('mergeable'), r.get('mergeStateStatus'),
              r.get('isInMergeQueue'), s.get('id'), s.get('number'), (r.get('stackEntry') or {}).get('position'),
              e.get('state'), c.get('oid'))

from query_guard import guarded


@guarded('gh_prs','gh')
def query(repo_slug, since, until, *, budget=1, after=None, created=False, timeout=30):
    scope = f'{repo_slug}:{since}:{until}'
    key = 'created' if created else 'updated'
    search = f'repo:{repo_slug} is:pr {key}:{since}..{until}'
    rows = []; cursor = after; problems = []
    for _ in range(max(1, budget)):
        fields = {'search': search}
        if cursor: fields['after'] = cursor
        payload = gql('gh_prs', 'github', scope, QUERY, fields, timeout=timeout)
        if isinstance(payload, Error): return payload
        problems.extend(api_error(payload, 'gh_prs', 'github', scope))
        page = (payload.get('data') or {}).get('search') or {}
        nodes, info = page.get('nodes'), page.get('pageInfo')
        if not isinstance(nodes, list) or not isinstance(info, dict) or type(info.get('hasNextPage')) is not bool:
            return failure('gh_prs', 'github', scope, 'invalid-response', 'Missing search nodes/pageInfo')
        parsed = [_pr(n) for n in nodes]
        if any(p is None for p in parsed):
            problems.append(Problem('invalid-response', 'Malformed PR identity; coverage incomplete', repair='Inspect returned nodes and repair the adapter before advancing coverage.'))
        rows.extend(p for p in parsed if p is not None)
        cursor = info.get('endCursor')
        if info['hasNextPage'] and not cursor:
            return failure('gh_prs', 'github', scope, 'invalid-response', 'Next search page has no cursor')
        if not info['hasNextPage']: break
    else:
        problems.append(Problem('pagination', 'Search page budget exhausted',
                                repair='Resume this exact window with the returned cursor.'))
    return envelope(rows, 'gh_prs', 'github', scope, problems, cursor if problems else None)
