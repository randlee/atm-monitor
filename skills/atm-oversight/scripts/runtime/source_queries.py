"""Execute independent questions and preserve each question's own checkpoint."""
from concurrent.futures import ThreadPoolExecutor
from query_runner import run
from query_memory import remember, due
from query_types import Error
from command_query import failure
from runtime_registry import REGISTRY
from state_codec import encode, decode


def execute_calls(calls, slots, policy, now, checkpoints=(), accumulated=()):
    previous = {s.key: s for s in slots}
    accepted = dict(checkpoints)
    scheduled = [(key, call) for key, call in calls if due(previous.get(key), now)]
    with ThreadPoolExecutor(max_workers=policy.query_workers) as pool:
        futures = [(key, pool.submit(run, key, key.split('_')[0], key, call)) for key, call in scheduled]
        for key, future in futures:
            result = future.result()
            try:
                decode(encode(result, REGISTRY), type(result), REGISTRY)
            except (TypeError, ValueError) as exc:
                result = failure(key, key.split('_')[0], key, 'invalid-response', str(exc),
                                 repair='Repair the adapter: results must be immutable typed records with valid fields.')
            previous[key] = remember(key, result, previous.get(key), now, policy,
                                     accepted.get(key), key in accumulated)
    return tuple(previous[key] for key in sorted(previous))


def data(slots, key, record_type=None):
    slot = next((s for s in slots if s.key == key), None)
    if not slot or not slot.last_good:
        return ()
    return tuple(x for x in slot.last_good.data if record_type is None or isinstance(x, record_type))
