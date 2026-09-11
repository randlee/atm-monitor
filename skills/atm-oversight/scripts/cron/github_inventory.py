"""Read every PR and head-check page; never publish an incomplete inventory."""

import json
from datetime import datetime

PR_FIELDS = ('number url headRefName headRefOid baseRefName state mergedAt '
             'closedAt createdAt updatedAt mergeable mergeStateStatus isDraft')
CHECK_FIELDS = '''__typename
 ... on CheckRun { name status conclusion startedAt completedAt detailsUrl
                  checkSuite { workflowRun { workflow { name } } } }
 ... on StatusContext { context state targetUrl createdAt description }'''
PAGE = 'pageInfo { hasNextPage endCursor }'
CONTEXTS = 'contexts(first:100, after:$checkCursor) { nodes { ' + CHECK_FIELDS + ' } ' + PAGE + ' }'
QUERY = '''query($owner:String!, $repo:String!, $cursor:String, $size:Int!, $checkCursor:String) {
 repository(owner:$owner, name:$repo) {
  pullRequests(first:$size, after:$cursor, orderBy:{field:CREATED_AT,direction:DESC}) {
   nodes { ''' + PR_FIELDS + ''' commits(last:1) { nodes { commit {
    oid statusCheckRollup { ''' + CONTEXTS + ''' }
   } } } } ''' + PAGE + '''
  }
 }
}'''
CHECK_QUERY = '''query($owner:String!, $repo:String!, $oid:GitObjectID!, $checkCursor:String) {
 repository(owner:$owner, name:$repo) {
  object(oid:$oid) { ... on Commit { statusCheckRollup { ''' + CONTEXTS + ''' } } }
 }
}'''


def connection(value):
    if not isinstance(value, dict) or not isinstance(value.get('nodes'), list):
        raise ValueError('invalid GitHub connection')
    if any(not isinstance(row, dict) for row in value['nodes']):
        raise ValueError('invalid GitHub connection row')
    info = value.get('pageInfo', {})
    if type(info.get('hasNextPage')) is not bool:
        raise ValueError('GitHub connection missing pagination evidence')
    cursor = info.get('endCursor') if info['hasNextPage'] else None
    if info['hasNextPage'] and (not isinstance(cursor, str) or not cursor):
        raise ValueError('GitHub next page missing cursor')
    return value['nodes'], cursor


def request(query, execute, **variables):
    command = ['gh', 'api', 'graphql', '-F', 'owner={owner}', '-F', 'repo={repo}', '-f', 'query=' + query]
    for key, value in variables.items():
        if value is not None:
            command += ['-F', key + '=' + str(value)]
    data = json.loads(execute(command))
    if not isinstance(data, dict) or data.get('errors'):
        raise ValueError('GitHub returned GraphQL errors')
    repo = data.get('data', {}).get('repository')
    if not isinstance(repo, dict):
        raise ValueError('GitHub response missing repository')
    return repo


def parse_start_time(value):
    if not isinstance(value, str):
        raise ValueError('start_time must be an ISO 8601 timestamp with timezone')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('start_time must include a timezone')
    return parsed


def collect_prs(execute, page_size=100, start_time=None):
    rows, seen, cursors = [], set(), set()
    start = parse_start_time(start_time) if start_time is not None else None
    cursor = None
    while True:
        repo = request(QUERY, execute, cursor=cursor, size=page_size)
        page, next_cursor = connection(repo.get('pullRequests'))
        for raw in page:
            if any(raw.get(field) is None for field in ('number', 'headRefName', 'headRefOid')):
                raise ValueError('PR missing identity')
            # CREATED_AT descending permits stopping at the project boundary.
            if start is not None and parse_start_time(raw.get('createdAt')) <= start:
                return rows
            if raw['number'] in seen:
                raise ValueError('PR inventory changed during pagination; retry collection')
            seen.add(raw['number'])
            row = {key: value for key, value in raw.items() if key != 'commits'}
            commits = raw.get('commits', {}).get('nodes')
            if not isinstance(commits, list) or len(commits) != 1:
                raise ValueError('PR missing head commit evidence')
            commit = commits[0]['commit']
            if commit['oid'] != row['headRefOid']:
                raise ValueError('PR head changed during collection')
            rollup = commit.get('statusCheckRollup')
            checks, check_cursor = connection(rollup.get('contexts')) if rollup is not None else ([], None)
            checks = list(checks)
            check_cursors = set()
            while check_cursor is not None:
                if check_cursor in check_cursors:
                    raise ValueError('GitHub check pagination did not advance')
                check_cursors.add(check_cursor)
                repo_checks = request(CHECK_QUERY, execute, oid=commit['oid'], checkCursor=check_cursor)
                more, check_cursor = connection(repo_checks['object']['statusCheckRollup']['contexts'])
                checks.extend(more)
            row['statusCheckRollup'] = checks
            rows.append(row)
        if next_cursor is None:
            return rows
        if next_cursor in cursors:
            raise ValueError('GitHub PR pagination did not advance')
        cursors.add(next_cursor)
        cursor = next_cursor


def latest_by_branch(prs):
    """A reused branch belongs to its newest PR, independent of source order."""
    result = {}
    for pr in prs:
        branch = pr['headRefName']
        if branch not in result or pr['number'] > result[branch]['number']:
            result[branch] = pr
    return result
