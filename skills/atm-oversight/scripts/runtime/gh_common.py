import json
from command_query import execute, now_iso, failure, CommandSuccess
from query_types import Ok, Partial, Error, Problem

def _json(result, query, source, scope):
    if isinstance(result, Error): return result
    try: return json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        return failure(query, source, scope, 'invalid-response', str(exc),
                       repair='Inspect GitHub JSON output and CLI/schema compatibility.')

def gql(query, source, scope, document, fields, timeout=30):
    args = ['gh', 'api', 'graphql', '-f', 'query=' + document]
    for key, value in fields.items():
        if isinstance(value, (tuple, list)):
            for item in value: args += ['-f', f'{key}[]={item}']
        else: args += ['-F' if type(value) in (int, bool) else '-f', f'{key}={str(value).lower() if type(value) is bool else value}']
    return _json(execute(query, source, scope, args, timeout=timeout), query, source, scope)

def envelope(data, query, source, scope, problems=(), cursor=None):
    observed = now_iso()
    if problems: return Partial(query, source, scope, tuple(data), observed, tuple(problems), cursor)
    return Ok(query, source, scope, tuple(data), observed)

def api_error(payload, query, source, scope):
    errors = payload.get('errors') if isinstance(payload, dict) else None
    if not errors: return ()
    return tuple(Problem('provider-response', str(e.get('message', e)), (), None, '', False,
                         None, 'Inspect GraphQL errors and repair unsupported fields or access.',
                         'amon@atm-monitor') for e in errors if isinstance(e, dict))
