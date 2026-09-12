#!/usr/bin/env python3
"""Produce routed findings from a snapshot. Never sends messages or repairs work."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from state_store import read_latest
from github_inventory import latest_by_branch


def finding(team, kind, subject, routes, evidence, severity='warning'):
    key = hashlib.sha256(json.dumps([team, kind, subject], sort_keys=True).encode()).hexdigest()[:24]
    return {'incident_key': key, 'team': team, 'kind': kind, 'subject': subject,
            'severity': severity, 'routes': routes, 'evidence': evidence}


def evaluate(snapshot):
    findings = []
    for team in snapshot['teams']:
        name = team['name']
        lead = 'team-lead@' + name
        ci = snapshot['sources'].get(name + '/ci', {})
        prs = ci.get('data') or [] if ci.get('status') in {'ok', 'partial'} else []
        by_branch = latest_by_branch(prs)
        for pr in prs:
            if pr.get('state') != 'OPEN':
                continue
            failed = sorted({check.get('name', 'unnamed check') for check in pr.get('statusCheckRollup') or []
                             if check.get('conclusion') in {'FAILURE', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE'}
                             or check.get('state') in {'FAILURE', 'ERROR'}})
            if failed:
                findings.append(finding(name, 'ci-failure', [pr['number'], pr['headRefOid'], failed],
                                        [lead], {'pr': pr['number'], 'url': pr.get('url'), 'failed_checks': failed,
                                                 'head': pr['headRefOid'], 'observed_at': ci.get('observed_at')}))
            if pr.get('mergeable') == 'CONFLICTING' or pr.get('mergeStateStatus') == 'DIRTY':
                findings.append(finding(name, 'merge-conflict', [pr['number'], pr['headRefOid']], [lead],
                                        {'pr': pr['number'], 'head': pr['headRefOid'],
                                         'mergeable': pr.get('mergeable'), 'mergeStateStatus': pr.get('mergeStateStatus')}))
            elif pr.get('mergeStateStatus') in {'BLOCKED', 'BEHIND', 'UNSTABLE'}:
                findings.append(finding(name, 'merge-blocked',
                                        [pr['number'], pr['headRefOid'], pr['mergeStateStatus']], [lead],
                                        {'pr': pr['number'], 'url': pr.get('url'),
                                         'branch': pr['headRefName'], 'head': pr['headRefOid'],
                                         'mergeable': pr.get('mergeable'),
                                         'mergeStateStatus': pr['mergeStateStatus'],
                                         'observed_at': ci.get('observed_at'),
                                         'classification': 'merge requirements need attention; inspect PR for cause'}))
        for key, source in snapshot['sources'].items():
            if not key.startswith(name + '/stack/') or source.get('status') != 'ok' or not source.get('data'):
                continue
            for branch in source['data']['branches']:
                if branch.get('needsRebase') and not branch.get('isMerged'):
                    head = branch.get('head') or None
                    findings.append(finding(name, 'stack-maintenance', [branch['name'], head], [lead],
                                            {'branch': branch['name'], 'head': head, 'needsRebase': True,
                                             'head_evidence': 'available' if head else 'unavailable',
                                             'pr': branch.get('pr'), 'observed_at': source.get('observed_at'),
                                             'classification': 'maintenance-needed; rule violation not yet established'}))
        sprints = snapshot.get('tracked_sprints', {}).get(name, {})
        sprint_branches = {sprint['branch'] for sprint in sprints.values()}
        for sprint in sprints.values():
            # A final integrate/phase-* PR contains the sprints and lands last.
            # Only a base identified as another sprint establishes this order rule.
            parent_branch = sprint.get('integration_branch')
            if parent_branch not in sprint_branches or parent_branch == sprint['branch']:
                continue
            child = by_branch.get(sprint['branch'])
            parent = by_branch.get(parent_branch)
            if not child or not parent or child.get('state') != 'MERGED' or not child.get('mergedAt'):
                continue
            reason = None
            if parent.get('state') != 'MERGED':
                reason = 'child merged while its declared parent PR is not merged'
            elif parent.get('mergedAt'):
                parent_at = datetime.fromisoformat(parent['mergedAt'].replace('Z', '+00:00'))
                child_at = datetime.fromisoformat(child['mergedAt'].replace('Z', '+00:00'))
                if parent_at > child_at:
                    reason = 'child merged before its declared parent PR'
            if reason:
                findings.append(finding(name, 'merge-order-violation', [parent['number'], child['number']],
                                        [lead, 'operator:telegram'], {'rule': 'STACK-ORDER-001', 'reason': reason,
                                         'parent': parent['number'], 'child': child['number'],
                                         'parent_merged_at': parent.get('mergedAt'), 'child_merged_at': child['mergedAt'],
                                         'plan': sprint.get('plan_path')}, 'serious'))
        critical = [snapshot['sources'].get(key, {}).get('status')
                    for key in ('herdr', name + '/roster', name + '/tasks')]
        if all(status == 'unavailable' for status in critical):
            findings.append(finding(name, 'monitor-blind', name, ['operator:telegram'],
                                    {'reason': 'Herdr, roster, and task collection all unavailable'}, 'serious'))
    # A stack may have been inspected from more than one worktree.
    unique = {item['incident_key']: item for item in findings}
    interventions = snapshot.get('interventions', {})
    for key, item in unique.items():
        records = interventions.get(key, {})
        item['pending_routes'] = [route for route in item['routes']
                                  if records.get(route, {}).get('status') not in {'sent', 'acknowledged'}]
    return list(unique.values())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir', required=True, type=Path)
    p.add_argument('--max-age-seconds', type=int, default=600)
    args = p.parse_args()
    try:
        snapshot, errors = read_latest(args.state_dir)
        if snapshot is None:
            raise ValueError('no valid monitoring snapshot')
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(snapshot['observed_at'].replace('Z', '+00:00'))).total_seconds()
        if errors or age < 0 or age > args.max_age_seconds:
            raise ValueError('snapshot is stale or recovered; refresh before notifying')
        findings = evaluate(snapshot)
        print(json.dumps({'schema_version': 1, 'observed_at': snapshot['observed_at'],
                          'findings': findings, 'notify': [f for f in findings if f['pending_routes']]}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'unavailable', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
