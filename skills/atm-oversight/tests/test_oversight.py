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
from mine_messages import mine, parse_escalation_summary
from report import ci_marker, render, qa_evidence
from branch_tree import build_tree, render_tree
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
        result = mine('a', actor='team-lead', kind='qa-task', query=query)
        self.assertEqual(len(result['messages']), 2)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['pages'][0], {'template_sha': 'a1', 'next_cursor': 'next'})
        self.assertTrue(all('--team' in cmd and '--as' in cmd for cmd in calls[1:]))
        self.assertTrue(all(cmd[cmd.index('--as') + 1] == 'team-lead' for cmd in calls[1:]))

    def test_missing_catalog_is_coverage_failure_not_no_work(self):
        result = mine('a', actor='team-lead', kind='dev-task', query=lambda cmd: [])
        self.assertEqual(result['status'], 'unavailable')

    def test_cross_team_evidence_is_rejected(self):
        result = mine('a', actor='team-lead', query=lambda cmd: {'hits': [hit(team='b')]})
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['messages'], [])

    def test_duplicates_and_reverse_arrival_produce_ordered_evidence(self):
        result = mine('a', actor='team-lead', query=lambda cmd: {'hits': [hit('m2', '2026-09-10T02:00:00Z'), hit(), hit()]})
        self.assertEqual([h['message_id'] for h in result['messages']], ['m1', 'm2'])

    def test_body_budget_and_nonmutating_command(self):
        calls = []
        def query(cmd):
            calls.append(cmd)
            if cmd[1] == 'search':
                return {'hits': [hit('m1'), hit('m2')]}
            return {'mutation_applied': False, 'message': {'message_id': 'm2', 'text': 'evidence'}}
        result = mine('a', actor='team-lead', with_bodies=True, max_bodies=1, query=query)
        self.assertEqual(result['bodies_omitted'], 1)
        self.assertEqual(result['messages'][1]['body'], 'evidence')
        self.assertTrue(all(cmd[1] in {'search', 'peek'} for cmd in calls))

    def test_failed_body_keeps_hit_and_explicit_error(self):
        def query(cmd):
            if cmd[1] == 'search':
                return {'hits': [hit()]}
            raise ValueError('source unavailable')
        result = mine('a', actor='team-lead', with_bodies=True, query=query)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['messages']), 1)
        self.assertEqual(len(result['errors']), 1)

    def test_mutation_flag_or_wrong_message_is_not_accepted(self):
        for payload in [{'mutation_applied': True, 'message': {'message_id': 'm1', 'text': 'bad'}},
                        {'mutation_applied': False, 'message': {'message_id': 'm2', 'text': 'bad'}}]:
            result = mine('a', actor='team-lead', with_bodies=True,
                          query=lambda cmd: {'hits': [hit()]} if cmd[1] == 'search' else payload)
            self.assertNotIn('body', result['messages'][0])
            self.assertEqual(result['status'], 'partial')

    def test_template_budget_exposes_remaining_work(self):
        def query(cmd):
            if cmd[1] == 'templates':
                return [{'template_type': 'qa-task', 'template_sha': sha} for sha in ['a', 'b']]
            return {'hits': []}
        result = mine('a', actor='team-lead', kind='qa-task', max_templates=1, query=query)
        self.assertEqual(result['remaining_template_shas'], ['b'])
        self.assertEqual(result['status'], 'partial')

    def test_cursor_requires_its_revision(self):
        with self.assertRaises(ValueError):
            mine('a', actor='team-lead', kind='qa-task', cursor='opaque')

    def test_identity_is_required_before_query_invocation(self):
        calls = []
        with self.assertRaises(ValueError):
            mine('a', actor='', query=lambda cmd: calls.append(cmd))
        self.assertEqual(calls, [])

    def test_escalation_summary_preserves_unknown_kind(self):
        self.assertEqual(parse_escalation_summary('escalation:future-kind:agent@team'),
                         {'kind': 'future-kind', 'agent': 'agent', 'team': 'team'})
        self.assertIsNone(parse_escalation_summary('escalation:future-kind agent@team'))

    def test_escalation_metadata_is_attached_to_retrieved_body(self):
        def query(cmd):
            if cmd[1] == 'search':
                return {'hits': [hit()]}
            return {'mutation_applied': False,
                    'message': {'message_id': 'm1', 'text': 'escalation:future-kind:agent@team'}}
        result = mine('a', actor='team-lead', with_bodies=True, query=query)
        self.assertEqual(result['messages'][0]['escalation']['kind'], 'future-kind')

    def test_escalation_metadata_uses_summary_when_body_is_prose(self):
        def query(cmd):
            if cmd[1] == 'search':
                return {'hits': [hit()]}
            return {'mutation_applied': False, 'message': {'message_id': 'm1',
                    'summary': 'escalation:new-kind:worker@a', 'text': 'Please investigate this episode.'}}
        result = mine('a', actor='monitor', with_bodies=True, query=query)
        self.assertEqual(result['messages'][0]['escalation'],
                         {'kind': 'new-kind', 'agent': 'worker', 'team': 'a'})


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

    def test_branch_tree_renders_base_siblings_and_nested_pr_bases(self):
        prs = [
            {'number': 10, 'headRefName': 'feature/ba2', 'baseRefName': 'integrate/phase-ba',
             'state': 'OPEN'},
            {'number': 11, 'headRefName': 'feature/ba3', 'baseRefName': 'feature/ba2',
             'state': 'OPEN', 'mergeStateStatus': 'BLOCKED'},
            {'number': 12, 'headRefName': 'feature/ba4', 'baseRefName': 'integrate/phase-ba',
             'state': 'MERGED'},
        ]
        text = render_tree(prs)
        self.assertLess(text.index('feature/ba2'), text.index('feature/ba3'))
        self.assertLess(text.index('feature/ba3'), text.index('feature/ba4'))
        self.assertIn('merge state: BLOCKED', text)
        self.assertIn('| Branch hierarchy | PR | Status | Action |', text)
        self.assertIn('　└─', text)
        self.assertIn('| `　├─ feature/ba2` |', text)
        self.assertIn('| `　│　　└─ feature/ba3` |', text)

    def test_branch_tree_uses_ordered_stack_and_deduplicates_worktrees(self):
        prs = [
            {'number': 20, 'headRefName': 'feature/ba2', 'baseRefName': 'integrate/phase-ba',
             'state': 'OPEN'},
            {'number': 21, 'headRefName': 'feature/ba3', 'baseRefName': 'feature/ba2',
             'state': 'OPEN'},
        ]
        payload = {'trunk': 'integrate/phase-ba', 'branches': [
            {'name': 'feature/ba2', 'needsRebase': False},
            {'name': 'feature/ba3', 'needsRebase': True},
        ]}
        source = {'status': 'ok', 'data': payload}
        text = render_tree(prs, [source, dict(source)])
        self.assertEqual(text.count('feature/ba2'), 1)
        self.assertEqual(text.count('feature/ba3'), 1)
        self.assertIn('needs-rebase', text)

    def test_branch_tree_preserves_unknown_conflicts_and_cycles(self):
        prs = [
            {'number': 30, 'headRefName': 'feature/unknown', 'baseRefName': None, 'state': 'OPEN'},
            {'number': 31, 'headRefName': 'feature/conflict', 'baseRefName': 'develop', 'state': 'OPEN'},
            {'number': 32, 'headRefName': 'feature/cycle-a', 'baseRefName': 'feature/cycle-b', 'state': 'OPEN'},
            {'number': 33, 'headRefName': 'feature/cycle-b', 'baseRefName': 'feature/cycle-a', 'state': 'OPEN'},
        ]
        stack = {'trunk': 'develop', 'branches': [
            {'name': 'feature/other', 'needsRebase': False},
            {'name': 'feature/conflict', 'needsRebase': False},
        ]}
        text = render_tree(prs, [stack])
        self.assertIn('parent unknown', text)
        self.assertIn('parent conflict:', text)
        self.assertIn('cycle detected:', text)
        self.assertEqual(text.count('`feature/cycle-a`'), 1)
        self.assertEqual(text.count('`feature/cycle-b`'), 1)
        tree = build_tree(prs, [stack])
        self.assertIsNone(tree['feature/cycle-a']['parent'])

    def test_stack_only_pr_identity_and_merged_history(self):
        stack = {'trunk': 'main', 'branches': [
            {'name': 'old', 'needsRebase': True, 'isMerged': True},
            {'name': 'active', 'needsRebase': True, 'pr': {'number': 7, 'state': 'OPEN'}}]}
        text = render_tree([], [stack])
        old = next(line for line in text.splitlines() if ' old`' in line)
        self.assertIn('| MERGED | — |', old)
        active = next(line for line in text.splitlines() if ' active`' in line)
        self.assertIn('| #7 |', active)
        self.assertIn('rebase required', active)
        self.assertIn('stack head unknown', active)

    def test_closed_pr_has_no_stale_repair_action(self):
        prs = [{'number': 1, 'headRefName': 'old', 'baseRefName': 'main',
                'state': 'CLOSED', 'mergeStateStatus': 'BLOCKED'}]
        text = render_tree(prs, [{'trunk': 'main', 'branches': [
            {'name': 'old', 'needsRebase': True}]}])
        self.assertIn('| CLOSED | — |', text)
        self.assertNotIn('rebase required', text)

    def test_branch_table_escapes_cells_without_changing_branch_identity(self):
        prs = [{'number': 1, 'headRefName': 'topic|with`tick', 'baseRefName': 'main', 'state': 'OPEN'}]
        text = render_tree(prs)
        self.assertIn('topic\\|with`tick', text)
        self.assertIn('`` ', text)
        self.assertEqual(len(text.splitlines()), 4)

    def test_deep_parent_chain_does_not_overflow_python_recursion(self):
        prs = [{'number': i, 'headRefName': f'b{i}', 'baseRefName': f'b{i-1}', 'state': 'OPEN'}
               for i in range(1, 1050)]
        tree = build_tree(prs)
        self.assertEqual(tree['b1049']['parent'], 'b1048')
        self.assertEqual(len(tree), 1050)


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
