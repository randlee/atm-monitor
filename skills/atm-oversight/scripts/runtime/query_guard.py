"""Make direct query calls as safe as cron invocations."""
from functools import wraps
from command_query import failure
from query_types import Ok, Partial, Error
from state_codec import encode, decode
from runtime_registry import REGISTRY


def guarded(query, source):
    def decorate(function):
        @wraps(function)
        def invoke(*args, **kwargs):
            scope = str(kwargs.get('scope', args[0] if args else 'current-state'))[:500]
            try:
                result = function(*args, **kwargs)
                if not isinstance(result, (Ok, Partial, Error)):
                    raise ValueError('Query returned no valid result union')
                decode(encode(result, REGISTRY), type(result), REGISTRY)
                return result
            except Exception as exc:
                return failure(query, source, scope, 'invalid-response',
                    type(exc).__name__ + ': ' + str(exc),
                    repair=f'Repair {query}.py response/input parsing; preserve other questions and retry this scope.')
        return invoke
    return decorate
