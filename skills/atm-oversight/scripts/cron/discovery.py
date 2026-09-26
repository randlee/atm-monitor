"""Join explicit plan identities to observed PR branches; retain discovered work."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_metadata import read_metadata
from github_inventory import latest_by_branch


def discover(repo, prs, previous=None, phases=()):
    plans, errors = {}, []
    for path in sorted((Path(repo) / 'docs' / 'plans').rglob('sprint-*.md')):
        try:
            meta = read_metadata(path.read_text(encoding='utf-8'))
            if not all(meta.get(key) for key in ('phase', 'sprint', 'branch')):
                continue
            record = dict(meta, plan_path=str(path), plan_source='working-tree')
            plans.setdefault(meta['branch'], []).append(record)
        except (ValueError, OSError):
            # Historical documents are not automatically active phases.
            continue
    tracked = dict(previous or {})
    active_phases = set(record['phase'] for record in tracked.values()) | set(phases)
    pr_by_branch = latest_by_branch(prs)
    for branch in pr_by_branch:
        matches = plans.get(branch, [])
        if len(matches) == 1:
            active_phases.add(matches[0]['phase'])
        elif len(matches) > 1:
            errors.append({'branch': branch, 'error': 'ambiguous sprint plan'})
        else:
            errors.append({'branch': branch, 'error': 'no parsed sprint plan; phase unresolved'})
    for matches in plans.values():
        if len(matches) != 1 or matches[0]['phase'] not in active_phases:
            continue
        record = matches[0]
        identity = record['phase'] + '/' + record['sprint']
        if identity in tracked and tracked[identity].get('branch') != record['branch']:
            errors.append({'sprint': identity, 'error': 'conflicting branch identity'})
            continue
        record = dict(record)
        record['pr'] = pr_by_branch.get(record['branch'])
        if not record['pr'] and identity in tracked:
            record['previous_pr'] = tracked[identity].get('pr') or tracked[identity].get('previous_pr')
        tracked[identity] = record
    return tracked, errors
