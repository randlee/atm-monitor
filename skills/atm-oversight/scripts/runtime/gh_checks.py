"""Bounded current readiness, with independently resumable nested connections."""
import json
from pathlib import Path
from command_query import failure, now_iso
from gh_common import gql, api_error, envelope
from gh_check_parse import parse_nodes
from query_types import Error, Partial, Problem
from pr_types import PR

QUERY = (Path(__file__).parent / 'graphql/readiness.graphql').read_text()


from query_guard import guarded


@guarded('gh_checks','gh')
def query(ids, *, scope='active-prs', budget=3, timeout=30, continuation=None):
    ids = tuple(dict.fromkeys(ids))
    try:
        pending = json.loads(continuation) if continuation else [
            {'ids': list(ids[n:n + 50]), 'connection': None, 'after': None, 'head': None}
            for n in range(0, len(ids), 50)]
        if type(budget) is not int or not 1 <= budget <= 10 or not isinstance(pending, list):
            raise ValueError('Invalid readiness budget/continuation')
        for request in pending:
            if set(request) != {'ids', 'connection', 'after', 'head'} or not request['ids']:
                raise ValueError('Invalid continuation request')
            if request['connection'] not in {None, 'entries', 'contexts'}:
                raise ValueError('Invalid continuation connection')
            if request['connection'] and len(request['ids']) != 1:
                raise ValueError('A cursor must belong to exactly one parent')
    except (ValueError, TypeError, KeyError) as exc:
        return failure('gh_checks', 'github', scope, 'invalid-input', str(exc))
    rows, problems = [], []
    for _ in range(budget):
        if not pending:
            break
        request = pending.pop(0)
        document = QUERY.replace('__ENTRY_AFTER__', ',after:$after' if request['connection'] == 'entries' else '')
        document = document.replace('__CHECK_AFTER__', ',after:$after' if request['connection'] == 'contexts' else '')
        fields = {'ids': request['ids']}
        if request['after']:
            fields['after'] = request['after']
        else:
            document = document.replace(', $after: String', '')
        payload = gql('gh_checks', 'github', scope, document, fields, timeout=timeout)
        if isinstance(payload, Error):
            if not rows:
                return payload
            pending.insert(0, request)
            problems.append(payload.problem)
            break
        errors = api_error(payload, 'gh_checks', 'github', scope)
        nodes = (payload.get('data') or {}).get('nodes')
        if not isinstance(nodes, list):
            return failure('gh_checks', 'github', scope, 'invalid-response', str(errors or 'Missing nodes'))
        received, more, issues = parse_nodes(nodes)
        if len(nodes) != len(request['ids']):
            issues.append(Problem('coverage', 'Requested IDs missing', repair='Retry the missing PR/stack identities.'))
        if request['head'] and any(p.head_sha != request['head'] for p in received if isinstance(p, PR)):
            received = []
            more = [dict(request, connection=None, after=None, head=None)]
            issues.append(Problem('revision-mismatch', 'Head changed during pagination', retryable=True,
                                  repair='Restart current readiness for this PR.'))
        rows.extend(received)
        pending.extend(more)
        problems.extend((*errors, *issues))
    if pending:
        problems.append(Problem('pagination', 'Readiness page budget exhausted', repair='Resume the returned parent-specific continuation.'))
    return envelope(rows, 'gh_checks', 'github', scope, problems, json.dumps(pending) if pending else None)
