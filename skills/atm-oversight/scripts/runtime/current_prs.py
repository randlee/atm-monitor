"""Select each PR's newest provider revision across independent observations."""
from pr_types import PR
from time_rules import timestamp


def select(slots):
    chosen = {}
    for slot in slots:
        if not slot.key.startswith(('gh_prs', 'gh_checks')) or not slot.last_good:
            continue
        for pr in slot.last_good.data:
            if not isinstance(pr, PR):
                continue
            rank = (timestamp(pr.updated_at) or 0, timestamp(slot.last_good.observed_at) or 0)
            if pr.node_id not in chosen or rank > chosen[pr.node_id][0]:
                chosen[pr.node_id] = (rank, pr)
    return tuple(value[1] for key, value in sorted(chosen.items()))
