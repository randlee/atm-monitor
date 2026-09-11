from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'oversight'))
sys.path.insert(0, str(ROOT / 'scripts' / 'cron'))
from mine_messages import mine
from report import ci_marker, render, qa_evidence
from discovery import discover
from collectors import decode


def hit(mid='m1', when='2026-09-10T01:00:00Z', team='a'):
    return {'key': {'team': team, 'agent': 'lead'}, 'message_id': mid, 'message_at': when}


class MiningTests(unittest.TestCase):
    def test_kind_uses_all_catalog_revisions_and_preserves_cursors(self):
        calls = []
        def query(cmd):
            calls.append(cmd)
            if cmd[1] == 'templates':
                return [{'template_type': 'qa-task', 'template_sha': sha} for sha in ['a1', 'a2']]
            sha = cmd[cmd.index('--template-sha') + 1]
            return {'hits': [hit(sha)], 'next_cursor': 'next' if sha == 'a1' else None}
        result = mine('a', kind='qa-task', query=query)
        self.assertEqual(len(result['messages']), 2)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['pages'][0], {'template_sha': 'a1', 'next_cursor': 'next'})
        self.assertTrue(all('--team' in cmd for cmd in calls[1:]))

    def test_missing_catalog_is_coverage_failure_not_no_work(self):
        result = mine('a', kind='dev-task', query=lambda cmd: [])
        self.assertEqual(result['status'], 'unavailable')

    def test_cross_team_evidence_is_rejected(self):
        result = mine('a', query=lambda cmd: {'hits': [hit(team='b')]})
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['messages'], [])

    def test_duplicates_and_reverse_arrival_produce_ordered_evidence(self):
        result = mine('a', query=lambda cmd: {'hits': [hit('m2', '2026-09-10T02:00:00Z'), hit(), hit()]})
        self.assertEqual([h['message_id'] for h in result['messages']], ['m1', 'm2'])

    def test_body_budget_and_nonmutating_command(self):
        calls = []
        def query(cmd):
            calls.append(cmd)
            if cmd[1] == 'search':
                return {'hits': [hit('m1'), hit('m2')]}
            return {'mutation_applied': False, 'message': {'message_id': 'm2', 'text': 'evidence'}}
        result = mine('a', with_bodies=True, max_bodies=1, query=query)
        self.assertEqual(result['bodies_omitted'], 1)
        self.assertEqual(result['messages'][1]['body'], 'evidence')
        self.assertTrue(all(cmd[1] in {'search', 'peek'} for cmd in calls))

    def test_failed_body_keeps_hit_and_explicit_error(self):
        def query(cmd):
            if cmd[1] == 'search':
                return {'hits': [hit()]}
            raise ValueError('source unavailable')
        result = mine('a', with_bodies=True, query=query)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['messages']), 1)
        self.assertEqual(len(result['errors']), 1)

    def test_mutation_flag_or_wrong_message_is_not_accepted(self):
        for payload in [{'mutation_applied': True, 'message': {'message_id': 'm1', 'text': 'bad'}},
                        {'mutation_applied': False, 'message': {'message_id': 'm2', 'text': 'bad'}}]:
            result = mine('a', with_bodies=True,
                          query=lambda cmd: {'hits': [hit()]} if cmd[1] == 'search' else payload)
            self.assertNotIn('body', result['messages'][0])
            self.assertEqual(result['status'], 'partial')

    def test_template_budget_exposes_remaining_work(self):
        def query(cmd):
            if cmd[1] == 'templates':
                return [{'template_type': 'qa-task', 'template_sha': sha} for sha in ['a', 'b']]
            return {'hits': []}
        result = mine('a', kind='qa-task', max_templates=1, query=query)
        self.assertEqual(result['remaining_template_shas'], ['b'])
        self.assertEqual(result['status'], 'partial')

    def test_cursor_requires_its_revision(self):
        with self.assertRaises(ValueError):
            mine('a', kind='qa-task', cursor='opaque')


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.pr = {'number': 12, 'headRefOid': 'a' * 40, 'headRefName': 'feature/az3-work',
                   'url': 'https://github.com/example/repo/pull/12',
                   'statusCheckRollup': [{'conclusion': 'SUCCESS'}]}
        self.snapshot = {'observed_at': '2026-09-10T01:00:00Z',
                         'sources': {'a/ci': {'status': 'ok', 'data': [self.pr]}},
                         'tracked_sprints': {'a': {'AZ/AZ.3': {'phase': 'AZ', 'sprint': 'AZ.3', 'branch': 'feature/az3-work'}}}}

    def evidence(self, commit=None):
        record = {'pr': 12, 'commit': commit or 'a' * 40, 'verdict': 'FAIL',
                  'findings': {'blocking': 1, 'important': 2, 'minor': 3}}
        return dict(hit(), body='```json\n' + json.dumps(record) + '\n```')

    def test_ci_never_calls_missing_or_unknown_checks_green(self):
        for value in [[], [{'state': 'UNKNOWN'}], [{'conclusion': 'CANCELLED'}]]:
            self.assertEqual(ci_marker(value), '—')
        self.assertEqual(ci_marker([{'conclusion': 'SUCCESS'}, {'status': 'IN_PROGRESS'}]), '🌀')
        self.assertEqual(ci_marker([{'conclusion': 'SUCCESS'}, {'conclusion': 'FAILURE'}]), '❌')

    def test_stale_qa_cannot_apply_to_new_head(self):
        self.assertIsNone(qa_evidence([self.evidence('b' * 40)], self.pr))
        self.assertIsNotNone(qa_evidence([self.evidence()], self.pr))

    def test_report_preserves_five_columns_and_exact_findings(self):
        text = render(self.snapshot, 'a', {'team': 'a', 'messages': [self.evidence()]},
                      now=datetime(2026, 9, 10, 1, 1, tzinfo=timezone.utc))
        self.assertIn('| Sprint | DEV | QA | CI | FND |', text)
        self.assertIn('| — | ❌ | ✅ | 1:2:3 |', text)

    def test_report_marks_old_snapshot_and_does_not_reuse_failed_ci(self):
        self.snapshot['sources']['a/ci']['status'] = 'unavailable'
        text = render(self.snapshot, 'a', now=datetime(2026, 9, 10, 2, tzinfo=timezone.utc))
        self.assertIn('STALE SNAPSHOT', text)
        self.assertIn('| AZ.3 | — | — | — | — |', text)

    def test_wrong_team_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            render(self.snapshot, 'a', {'team': 'other', 'messages': []})

    def test_overlapping_phases_use_their_own_start_boundary(self):
        self.pr['createdAt'] = '2026-09-10T12:00:00Z'
        newer = dict(self.pr, number=13, headRefName='feature/ba1-work')
        self.snapshot['sources']['a/ci']['data'].append(newer)
        self.snapshot['tracked_sprints']['a']['BA/BA.1'] = {
            'phase': 'BA', 'sprint': 'BA.1', 'branch': 'feature/ba1-work'}
        self.snapshot['teams'] = [{'name': 'a', 'projects': [
            {'phase': 'AZ', 'start_time': '2026-09-10T00:00:00Z'},
            {'phase': 'BA', 'start_time': '2026-09-11T00:00:00Z'}]}]
        text = render(self.snapshot, 'a')
        self.assertIn('[AZ.3]', text)
        self.assertIn('| BA.1 | — | — | — | — |', text)


class DiscoveryTests(unittest.TestCase):
    def test_existing_phase_is_retained_when_no_pr_is_open(self):
        with tempfile.TemporaryDirectory() as directory:
            old = {'AZ/AZ.3': {'phase': 'AZ', 'sprint': 'AZ.3', 'branch': 'feature/az3-work'}}
            tracked, errors = discover(directory, [], old)
            self.assertEqual(tracked, old)
            self.assertEqual(errors, [])

    def test_activity_discovers_phase_and_all_its_planned_sprints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'docs/plans/phase-az'
            folder.mkdir(parents=True)
            for number in [1, 2]:
                (folder / f'sprint-AZ.{number}-work.md').write_text(
                    f'---\nphase: AZ\nsprint: AZ.{number}\nbranch: feature/az{number}-work\n---\n')
            tracked, errors = discover(root, [{'headRefName': 'feature/az1-work'}])
            self.assertEqual(set(tracked), {'AZ/AZ.1', 'AZ/AZ.2'})
            self.assertEqual(errors, [])

    def test_unmapped_branch_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            tracked, errors = discover(directory, [{'headRefName': 'feature/new'}])
            self.assertFalse(tracked)
            self.assertEqual(errors[0]['error'], 'no parsed sprint plan; phase unresolved')

    def test_explicitly_onboarded_phase_can_report_before_first_pr(self):
        with tempfile.TemporaryDirectory() as directory:
            plans = Path(directory) / 'docs/plans'
            plans.mkdir(parents=True)
            (plans / 'sprint-BA.1.md').write_text(
                '---\nphase: BA\nsprint: BA.1\nbranch: feature/ba1\n---\n')
            tracked, errors = discover(directory, [], phases=['BA'])
            self.assertEqual(set(tracked), {'BA/BA.1'})
            self.assertIsNone(tracked['BA/BA.1']['pr'])

    def test_worktrees_support_spaces_and_detached_heads(self):
        data = decode('worktrees', 'worktree /tmp/repo space\0HEAD abc\0branch refs/heads/main\0\0worktree /tmp/other\0HEAD def\0detached\0\0', None)
        self.assertEqual(data[0]['worktree'], '/tmp/repo space')
        self.assertEqual(data[1]['HEAD'], 'def')


if __name__ == '__main__':
    unittest.main()
