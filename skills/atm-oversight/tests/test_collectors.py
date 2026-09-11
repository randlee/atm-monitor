import json
from pathlib import Path
import subprocess
import sys
import unittest

CRON = Path(__file__).resolve().parents[1] / 'scripts' / 'cron'
sys.path.insert(0, str(CRON))
from collectors import collect, KINDS, MAX_OUTPUT_BYTES
from github_inventory import collect_prs, latest_by_branch


def connection(rows, cursor=None):
    return {'nodes': rows, 'pageInfo': {'hasNextPage': cursor is not None, 'endCursor': cursor}}


def pr(number, created='2026-09-11T00:00:01Z', checks=None):
    return {'number': number, 'headRefName': 'feature/' + str(number), 'headRefOid': 'abc',
            'createdAt': created, 'commits': {'nodes': [{'commit': {'oid': 'abc',
            'statusCheckRollup': {'contexts': checks or connection([])}}}]}}


def page(rows, cursor=None):
    return {'data': {'repository': {'pullRequests': connection(rows, cursor)}}}


class CollectorTests(unittest.TestCase):
    def response(self, data, exit_code=0, stderr=''):
        return lambda *a, **k: subprocess.CompletedProcess(a[0], exit_code, json.dumps(data), stderr)

    def test_empty_success_is_not_failure(self):
        for kind, value in [('herdr', {'result': {'agents': []}}),
                            ('roster', {'team': 'alpha', 'members': []}),
                            ('tasks', []), ('task-events', []), ('ci', page([]))]:
            with self.subTest(kind=kind):
                result = collect(kind, team='alpha', task_id='t1', run=self.response(value))
                self.assertEqual(result['status'], 'ok', result)
                self.assertEqual(result['data'], [])

    def test_every_collector_preserves_command_failure(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                result = collect(kind, team='alpha', task_id='t1', run=self.response([], 1, 'daemon down'))
                self.assertEqual(result['status'], 'unavailable')
                self.assertIsNone(result['data'])
                self.assertEqual(result['error']['code'], 'command-failed')

    def test_every_collector_preserves_timeout(self):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs['timeout'])
        for kind in KINDS:
            with self.subTest(kind=kind):
                result = collect(kind, team='alpha', task_id='t1', run=timeout)
                self.assertEqual(result['error']['code'], 'timeout')
                self.assertEqual(result['status'], 'unavailable')

    def test_missing_binary_is_explicit(self):
        def missing(*a, **k):
            raise FileNotFoundError('atm not found')
        self.assertEqual(collect('tasks', team='a', run=missing)['error']['code'], 'not-found')

    def test_wrong_envelopes_do_not_become_empty_state(self):
        for kind, data in [('herdr', {'result': {}}), ('roster', {}),
                           ('tasks', {}), ('ci', None), ('stack', {})]:
            with self.subTest(kind=kind):
                self.assertEqual(collect(kind, team='a', run=self.response(data))['status'], 'unavailable')

    def test_herdr_error_envelope_cannot_pass(self):
        data = {'error': {'message': 'bad'}, 'result': {'agents': []}}
        self.assertEqual(collect('herdr', run=self.response(data))['status'], 'unavailable')

    def test_unnamed_herdr_terminal_does_not_invalidate_named_agents(self):
        rows = [{'name': None, 'agent_status': 'idle', 'pane_id': 'p', 'workspace_id': 'w'},
                {'name': 'worker', 'agent_status': 'working', 'pane_id': 'p2', 'workspace_id': 'w'}]
        result = collect('herdr', run=self.response({'result': {'agents': rows}}))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['data'], rows)

    def test_herdr_may_omit_name_for_an_unassigned_terminal(self):
        result = collect('herdr', run=self.response({'result': {'agents': [
            {'agent_status': 'idle', 'pane_id': 'p', 'workspace_id': 'w'}]}}))
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(result['data'][0]['name'])

    def test_incomplete_rows_do_not_pass(self):
        for kind, data in [('tasks', [{}]), ('ci', [{}]),
                          ('roster', {'team': 'a', 'members': [{'name': 'worker'}]})]:
            with self.subTest(kind=kind):
                self.assertEqual(collect(kind, team='a', run=self.response(data))['status'], 'unavailable')

    def test_team_and_task_isolation(self):
        cases = [('tasks', [{'team': 'wrong', 'task_id': 't', 'assignee': 'w', 'state': 'active'}]),
                 ('roster', {'team': 'a', 'members': [{'name': 'w', 'agent_id': 'w@b'}]}),
                 ('task-events', [{'team': 'a', 'task_id': 'wrong', 'assignee': 'w', 'seq': 1, 'at': 'now', 'event': 'assigned'}])]
        for kind, data in cases:
            with self.subTest(kind=kind):
                result = collect(kind, team='a', task_id='t', run=self.response(data))
                self.assertEqual(result['status'], 'unavailable')
                self.assertIsNone(result['data'])

    def test_additive_fields_and_unknown_status_survive(self):
        row = {'team': 'a', 'task_id': 't', 'assignee': 'w', 'state': 'new-state', 'future': 42}
        result = collect('tasks', team='a', run=self.response([row]))
        self.assertEqual(result['data'], [row])

    def test_full_page_without_next_cursor_is_complete(self):
        result = collect('ci', limit=1, run=self.response(page([pr(1)])))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['data']), 1)

    def test_ci_follows_all_pages_and_preserves_closed_prs(self):
        pages = [page([dict(pr(3), state='CLOSED')], 'next'), page([pr(2)]),]
        commands = []
        def run(cmd, **kwargs):
            commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(pages.pop(0)), '')
        result = collect('ci', limit=1, run=run)
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual([row['number'] for row in result['data']], [3, 2])
        self.assertEqual(result['data'][0]['state'], 'CLOSED')
        self.assertIn('cursor=next', commands[1])

    def test_more_than_100_prs_have_no_inventory_cap(self):
        pages = [page([pr(i) for i in range(201, 101, -1)], 'p2'),
                 page([pr(i) for i in range(101, 1, -1)], 'p3'), page([pr(1)])]
        rows = collect_prs(lambda cmd: json.dumps(pages.pop(0)))
        self.assertEqual(len(rows), 201)
        self.assertEqual(rows[-1]['number'], 1)

    def test_start_time_stops_at_boundary_and_handles_offsets(self):
        calls = []
        def query(cmd):
            calls.append(cmd)
            return json.dumps(page([pr(3), pr(2, '2026-09-10T17:00:00-07:00'), pr(1)], 'unused'))
        rows = collect_prs(query, start_time='2026-09-11T00:00:00Z')
        self.assertEqual([row['number'] for row in rows], [3])
        self.assertEqual(len(calls), 1)

    def test_check_overflow_is_collected_at_same_commit(self):
        payloads = [page([pr(1, checks=connection([{'name': 'one'}], 'checks2'))]),
                    {'data': {'repository': {'object': {'statusCheckRollup': {
                        'contexts': connection([{'name': 'hidden-failure', 'conclusion': 'FAILURE'}])}}}}}]
        commands = []
        def query(cmd):
            commands.append(cmd)
            return json.dumps(payloads.pop(0))
        rows = collect_prs(query)
        self.assertEqual(len(rows[0]['statusCheckRollup']), 2)
        self.assertIn('oid=abc', commands[1])

    def test_later_page_failure_does_not_publish_partial_inventory(self):
        for failure in ('exit', 'timeout', 'graphql', 'malformed'):
            calls = []
            def run(cmd, **kwargs):
                calls.append(cmd)
                if len(calls) == 1:
                    return subprocess.CompletedProcess(cmd, 0, json.dumps(page([pr(2)], 'next')), '')
                if failure == 'timeout':
                    raise subprocess.TimeoutExpired(cmd, 1)
                return subprocess.CompletedProcess(cmd, 1 if failure == 'exit' else 0,
                    json.dumps({'errors': [{'message': 'denied'}]}) if failure == 'graphql' else '{}', 'denied')
            result = collect('ci', run=run)
            self.assertEqual(result['status'], 'unavailable', failure)
            self.assertIsNone(result['data'])

    def test_repeated_cursor_and_duplicate_pr_fail(self):
        for values in ([page([pr(2)], 'repeat'), page([pr(1)], 'repeat')],
                       [page([pr(2)], 'next'), page([pr(2)])]):
            with self.assertRaises(ValueError):
                collect_prs(lambda cmd: json.dumps(values.pop(0)))

    def test_missing_pagination_or_head_identity_is_not_success(self):
        bad = pr(1)
        bad['commits']['nodes'][0]['commit']['oid'] = 'changed'
        for data in (page([bad]), {'data': {'repository': {'pullRequests': {'nodes': []}}}}):
            self.assertEqual(collect('ci', run=self.response(data))['status'], 'unavailable')

    def test_empty_commit_connection_preserves_pr_with_unknown_checks(self):
        historical = dict(pr(1), state='CLOSED', commits={'nodes': []})
        result = collect('ci', run=self.response(page([pr(2), historical])))
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(len(result['data']), 2)
        self.assertIsNone(result['data'][1]['statusCheckRollup'])
        self.assertEqual(result['data'][1]['check_evidence'], 'head-commit-unavailable')

    def test_branch_reuse_chooses_newest_pr_in_any_order(self):
        old, new = dict(pr(1), headRefName='feature/reused'), dict(pr(2), headRefName='feature/reused')
        for rows in ([old, new], [new, old]):
            self.assertEqual(latest_by_branch(rows)['feature/reused']['number'], 2)

    def test_git_default_is_complete_and_project_start_is_explicit(self):
        commands = []
        def run(cmd, **kwargs):
            commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, '', '')
        collect('git', run=run)
        self.assertFalse(any(arg.startswith(('--max-count', '--since')) for arg in commands[0]))
        collect('git', start_time='2026-09-11T00:00:00Z', run=run)
        self.assertIn('--since=2026-09-11T00:00:00Z', commands[1])

    def test_no_stack_is_absence_only_for_expected_diagnostic(self):
        result = collect('stack', run=self.response(None, 2, 'current branch develop is not part of a stack'))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['absence'], 'not-in-stack')
        result = collect('stack', run=self.response(None, 2, 'API authorization failure'))
        self.assertEqual(result['status'], 'unavailable')

    def test_merged_stack_entry_can_outlive_its_local_ref(self):
        data = {'trunk': 'develop', 'branches': [
            {'name': 'feature/merged', 'isMerged': True, 'needsRebase': False},
            {'name': 'feature/active', 'head': 'abc', 'isMerged': False, 'needsRebase': True}]}
        result = collect('stack', run=self.response(data))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['data'], data)

    def test_unmerged_stack_entry_still_requires_head(self):
        data = {'trunk': 'develop', 'branches': [
            {'name': 'feature/active', 'isMerged': False, 'needsRebase': True}]}
        self.assertEqual(collect('stack', run=self.response(data))['status'], 'unavailable')

    def test_subprocess_is_noninteractive_and_uses_argv(self):
        def inspect(cmd, **kwargs):
            self.assertIsInstance(cmd, list)
            self.assertNotIn('shell', kwargs)
            self.assertEqual(kwargs['env']['GIT_TERMINAL_PROMPT'], '0')
            self.assertEqual(kwargs['env']['GH_PROMPT_DISABLED'], '1')
            self.assertEqual(kwargs['cwd'], 'repo with spaces')
            self.assertEqual(kwargs['timeout'], 7)
            return subprocess.CompletedProcess(cmd, 0, '[]', '')
        self.assertEqual(collect('tasks', team='a', repo='repo with spaces', timeout=7, run=inspect)['status'], 'ok')

    def test_invalid_json_and_oversize_output_fail(self):
        for raw in ('not json', ' ' * (MAX_OUTPUT_BYTES + 1)):
            run = lambda *a, **k: subprocess.CompletedProcess(a[0], 0, raw, '')
            self.assertEqual(collect('ci', run=run)['status'], 'unavailable')

    def test_git_subject_keeps_delimiters_and_empty_log_is_valid(self):
        run = lambda *a, **k: subprocess.CompletedProcess(a[0], 0, 'abc\0date\0subject | special\n', '')
        self.assertEqual(collect('git', run=run)['data'][0]['subject'], 'subject | special')
        run = lambda *a, **k: subprocess.CompletedProcess(a[0], 0, '', '')
        self.assertEqual(collect('git', run=run)['data'], [])

    def test_invalid_budgets_do_not_run_command(self):
        def unexpected(*a, **k):
            self.fail('command should not execute')
        for params in ({'timeout': 0}, {'limit': 0}, {'limit': 10001}):
            self.assertEqual(collect('ci', run=unexpected, **params)['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
