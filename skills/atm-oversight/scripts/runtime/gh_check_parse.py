"""Strict current PR/check decoding and per-connection continuations."""
from pr_types import PR, Check, Stack
from query_types import Problem


def parse_pr(node):
    required = ('id', 'number', 'state', 'headRefName', 'headRefOid', 'baseRefName', 'baseRefOid')
    if not isinstance(node, dict) or any(not node.get(k) for k in required):
        raise ValueError('Missing required PR identity/state fields')
    if type(node['number']) is not int:
        raise ValueError('Invalid PR number')
    rollup = node.get('statusCheckRollup') or {}
    stack = node.get('stack') or {}
    pr = PR(node['id'], node['number'], node.get('updatedAt', ''), node['state'],
        node['headRefName'], node['headRefOid'], node['baseRefName'], node['baseRefOid'],
        node.get('isDraft'), node.get('mergeable'), node.get('mergeStateStatus'),
        node.get('isInMergeQueue'), stack.get('id'), stack.get('number'),
        (node.get('stackEntry') or {}).get('position'), rollup.get('state'),
        (rollup.get('commit') or {}).get('oid'))
    checks = []
    connection = rollup.get('contexts') or {}
    for item in connection.get('nodes', ()):
        if not isinstance(item, dict) or not (item.get('name') or item.get('context')):
            raise ValueError('Invalid check identity')
        checks.append(Check(pr.number, pr.head_sha, item.get('name') or item['context'],
            item.get('status') or item.get('state', 'UNKNOWN'), item.get('conclusion'),
            attempt=item.get('id'), queued_at=item.get('createdAt'),
            started_at=item.get('startedAt'), completed_at=item.get('completedAt'),
            url=item.get('detailsUrl') or item.get('targetUrl')))
    return pr, checks, continuation(connection, pr.node_id, 'contexts', pr.head_sha)


def continuation(connection, identity, kind, head=None):
    page = connection.get('pageInfo') or {}
    if page.get('hasNextPage'):
        if not page.get('endCursor'):
            raise ValueError('More pages advertised without a cursor')
        return [{'ids': [identity], 'connection': kind, 'after': page['endCursor'], 'head': head}]
    return []


def parse_nodes(nodes):
    rows, pending, problems = [], [], []
    for node in nodes:
        if not isinstance(node, dict):
            problems.append(Problem('coverage', 'Requested node was absent', repair='Refresh this retained PR/stack identity and retry.'))
            continue
        try:
            if 'entries' not in node:
                pr, checks, more = parse_pr(node)
                rows.extend((pr, *checks))
                pending.extend(more)
            else:
                members = []
                for entry in node['entries']['nodes']:
                    pr, checks, more = parse_pr(entry['pullRequest'])
                    members.append(pr)
                    rows.extend((pr, *checks))
                    pending.extend(more)
                rows.append(Stack(node['id'], node['number'], node['baseRefName'], tuple(members)))
                pending.extend(continuation(node['entries'], node['id'], 'entries'))
        except (KeyError, ValueError, TypeError) as exc:
            problems.append(Problem('invalid-response', str(exc), repair='Repair the GitHub readiness adapter; retain unaffected nodes.'))
    for pr in (r for r in rows if isinstance(r, PR)):
        if pr.rollup_sha and pr.rollup_sha != pr.head_sha:
            problems.append(Problem('revision-mismatch', f'PR {pr.number} check head differs',
                                    retryable=True, repair='Requery current readiness; do not use old-head checks.'))
    return rows, pending, problems
