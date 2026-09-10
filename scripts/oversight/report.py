#!/usr/bin/env python3
"""Render the five-column sprint report from persisted evidence."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cron'))
from state_store import read_latest


def ci_marker(checks):
    if not checks:
        return '—'
    values = []
    for check in checks:
        values.append(check.get('conclusion') or check.get('state') or check.get('status', 'UNKNOWN'))
    if any(value in {'FAILURE', 'ERROR', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE'} for value in values):
        return '❌'
    if any(value in {'PENDING', 'QUEUED', 'IN_PROGRESS', 'WAITING', 'REQUESTED'} for value in values):
        return '🌀'
    if all(value in {'SUCCESS', 'NEUTRAL', 'SKIPPED'} for value in values):
        return '✅'
    return '—'


def qa_evidence(messages, pr):
    matches = []
    for message in messages:
        for block in re.findall(r'```json\s*\n(.*?)\n```', message.get('body', ''), re.S):
            try:
                record = json.loads(block)
                if not isinstance(record, dict) or not isinstance(record.get('commit'), str):
                    continue
                # Reports are valid only for the exact PR head; short/old SHAs stay unverified.
                if str(record.get('pr')) != str(pr['number']) or record['commit'] != pr['headRefOid']:
                    continue
                findings = record.get('findings', {})
                if any(type(findings.get(key)) is not int or findings[key] < 0
                       for key in ('blocking', 'important', 'minor')):
                    continue
                matches.append((message['message_at'], record, message['message_id']))
            except (ValueError, KeyError, TypeError):
                continue
    if not matches:
        return None
    return sorted(matches, key=lambda item: (item[0], item[2]))[-1]


def render(snapshot, team, evidence=None, max_age_seconds=600, now=None):
    now = now or datetime.now(timezone.utc)
    observed = datetime.fromisoformat(snapshot['observed_at'].replace('Z', '+00:00'))
    age = max(0, int((now - observed).total_seconds()))
    notes = [f'{team} · observed {snapshot["observed_at"]} · age {age}s']
    if age > max_age_seconds:
        notes.append('STALE SNAPSHOT — run a fresh tick before using this report to intervene.')
    source = snapshot['sources'].get(team + '/ci', {})
    if source.get('status') == 'partial':
        notes.append('PR coverage is bounded; this report covers the returned PRs and retained sprint identities.')
    elif source.get('status') != 'ok':
        notes.append('CI collection is unavailable; current CI conclusions are omitted.')
    supplied = evidence or {}
    if supplied and supplied.get('team') != team:
        raise ValueError('QA evidence belongs to another team')
    if supplied.get('status') in {'partial', 'unavailable'}:
        notes.append('QA evidence is incomplete; additional or newer reports may exist.')
    prs = {p['headRefName']: p for p in (source.get('data') or [])} if source.get('status') in {'ok', 'partial'} else {}
    rows = []
    tracked = snapshot.get('tracked_sprints', {}).get(team, {})
    for identity, sprint in sorted(tracked.items(), key=lambda item: natural_key(item[0])):
        pr = prs.get(sprint['branch'])
        label = sprint['sprint']
        dev, qa, ci, findings = '—', '—', '—', '—'
        if pr:
            url = pr.get('url', '')
            if url.startswith('https://github.com/'):
                label = f'[{label}]({url})'
            ci = ci_marker(pr.get('statusCheckRollup'))
            if pr.get('state') == 'MERGED':
                dev, ci = '✅', '🏁'
            evidence_row = qa_evidence(supplied.get('messages', []), pr)
            if evidence_row:
                _, record, _ = evidence_row
                qa = {'PASS': '✅', 'FAIL': '❌'}.get(record.get('verdict'), '—')
                findings = ':'.join(str(record['findings'][key]) for key in ('blocking', 'important', 'minor'))
                deliverables = record.get('deliverables', {})
                if (type(deliverables.get('total')) is int and deliverables['total'] > 0
                        and deliverables.get('complete') == deliverables['total']):
                    dev = '✅'
        rows.append('| ' + ' | '.join((label, dev, qa, ci, findings)) + ' |')
    if not rows:
        notes.append('No sprint associations have been established in this snapshot.')
    unresolved = [error for error in snapshot.get('discovery_errors', []) if error.get('team') == team]
    if unresolved:
        notes.append(f'{len(unresolved)} PR branch associations remain unresolved; see snapshot discovery_errors.')
    notes.append('— = not established by available evidence; absent open PRs are not assumed merged.')
    for key, result in snapshot['sources'].items():
        if key.startswith(team + '/stack/') and result.get('status') == 'ok' and result.get('data'):
            for branch in result['data']['branches']:
                if branch.get('needsRebase') and not branch.get('isMerged'):
                    notes.append('Stack maintenance: ' + branch['name'] + ' reports needsRebase.')
    return '\n'.join(notes[:2] + ['','| Sprint | DEV | QA | CI | FND |',
                                  '|---|---|---|---|---|'] + rows + ['', *dict.fromkeys(notes[2:])])


def natural_key(value):
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', value)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir', type=Path, required=True)
    p.add_argument('--team', required=True)
    p.add_argument('--qa-evidence', type=Path, help='JSON output of mine_messages --kind qa-report --with-bodies')
    p.add_argument('--max-age-seconds', type=int, default=600)
    args = p.parse_args()
    try:
        snapshot, errors = read_latest(args.state_dir)
        if snapshot is None:
            raise ValueError('no valid snapshot; run a collection tick')
        if args.team not in {team['name'] for team in snapshot['teams']}:
            raise ValueError('team is not configured in this snapshot')
        evidence = json.loads(args.qa_evidence.read_text(encoding='utf-8')) if args.qa_evidence else None
        if errors:
            print('State recovery warning: newest snapshot could not be read.')
        print(render(snapshot, args.team, evidence, args.max_age_seconds))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('Report unavailable: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
