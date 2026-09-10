import json
from pathlib import Path
import subprocess
import sys
import unittest

CRON = Path(__file__).resolve().parents[1] / 'scripts' / 'cron'
sys.path.insert(0, str(CRON))
from collectors import collect, KINDS, MAX_OUTPUT_BYTES


class CollectorTests(unittest.TestCase):
    def response(self, data, exit_code=0, stderr=''):
        return lambda *a, **k: subprocess.CompletedProcess(a[0], exit_code, json.dumps(data), stderr)

    def test_empty_success_is_not_failure(self):
        for kind, value in [('herdr', {'result': {'agents': []}}),
                            ('roster', {'team': 'alpha', 'members': []}),
                            ('tasks', []), ('task-events', []), ('ci', [])]:
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

    def test_limit_boundary_is_explicitly_partial(self):
        rows = [{'number': 1, 'headRefOid': 'abc', 'headRefName': 'feature/a'}]
        result = collect('ci', limit=1, run=self.response(rows))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['data'], rows)

    def test_no_stack_is_absence_only_for_expected_diagnostic(self):
        result = collect('stack', run=self.response(None, 2, 'current branch develop is not part of a stack'))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['absence'], 'not-in-stack')
        result = collect('stack', run=self.response(None, 2, 'API authorization failure'))
        self.assertEqual(result['status'], 'unavailable')

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
