import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'cron'))
from collectors import collect
from state_store import read_latest
from tick import load_config, run_tick


class AtmContractTests(unittest.TestCase):
    def runner(self, version='1.6.0', rows=None):
        calls = []
        def run(command, **options):
            calls.append((command, options))
            if command[1] == 'doctor':
                data = {'daemon_context': {'version': '1.5.14', 'http_api_version': version}}
            elif command[1] == 'members':
                data = {'team': 'a', 'members': []}
            else:
                data = rows or []
            return subprocess.CompletedProcess(command, 0, json.dumps(data), '')
        return calls, run

    def test_pre_ba_transitional_unknown_and_future_major_never_query_tasks(self):
        for version in ('1.3.0', '1.5.0', '2.0.0', None, 'unknown', 16):
            for kind in ('tasks', 'task-events'):
                with self.subTest(version=version, kind=kind):
                    calls, run = self.runner(version)
                    result = collect(kind, team='a', actor='monitor', task_id='t', run=run)
                    self.assertEqual(result['status'], 'unavailable')
                    self.assertIsNone(result['data'])
                    self.assertEqual([cmd[1] for cmd, _ in calls], ['doctor'])

    def test_supported_daemon_uses_new_verbs_with_explicit_identity(self):
        for kind in ('tasks', 'task-events'):
            calls, run = self.runner()
            result = collect(kind, team='a', actor='monitor', task_id='t', run=run)
            self.assertEqual(result['status'], 'ok', result)
            command = calls[-1][0]
            self.assertEqual(command[:3], ['atm', 'task', 'list' if kind == 'tasks' else 'events'])
            self.assertIn('--all' if kind == 'tasks' else 't', command)
            for command, options in calls:
                self.assertEqual(command[command.index('--team') + 1], 'a')
                self.assertEqual(options['env']['ATM_IDENTITY'], 'monitor')
                self.assertEqual(options['env']['ATM_TEAM'], 'a')
            self.assertEqual(command[command.index('--as') + 1], 'monitor')

    def test_missing_identity_never_falls_back_to_environment(self):
        for kind in ('doctor', 'roster', 'tasks', 'task-events'):
            calls, run = self.runner()
            result = collect(kind, team='a', run=run)
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(calls, [])

    def test_doctor_outage_does_not_issue_ledger_request(self):
        calls = []
        def run(command, **options):
            calls.append(command)
            return subprocess.CompletedProcess(command, 4, '', 'daemon down')
        result = collect('tasks', team='a', actor='monitor', run=run)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], 'doctor')

    def test_future_event_state_and_outcome_strings_are_retained(self):
        for kind, row in (
            ('tasks', {'team': 'a', 'task_id': 't', 'assignee': 'worker',
                       'state': 'future-state', 'close_outcome': 'future-outcome', 'position': None}),
            ('task-events', {'team': 'a', 'task_id': 't', 'assignee': 'worker',
                            'seq': 1, 'at': 'now', 'event': 'future-event', 'new_field': 42})):
            calls, run = self.runner('1.7.0', [row])
            result = collect(kind, team='a', actor='monitor', task_id='t', run=run)
            self.assertEqual(result['status'], 'ok', result)
            self.assertEqual(result['data'], [row])

    def test_tick_reuses_one_live_doctor_observation_for_all_histories(self):
        for version in ('1.3.0', '1.6.0'):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                calls, run = self.runner(version, [{'team': 'a', 'task_id': 't',
                    'assignee': 'worker', 'state': 'active', 'event': 'started', 'seq': 1, 'at': 'now'}])
                def collector(kind, **options):
                    if kind in {'doctor', 'roster', 'tasks', 'task-events'}:
                        return collect(kind, run=run, **options)
                    return {'status': 'ok', 'data': []}
                config = {'teams': [{'name': 'a', 'actor': 'monitor', 'repo': directory}]}
                run_tick(config, directory, collector=collector)
                commands = [cmd for cmd, _ in calls]
                self.assertEqual(sum(cmd[1] == 'doctor' for cmd in commands), 1)
                state, _ = read_latest(directory)
                if version == '1.3.0':
                    self.assertFalse(any(cmd[1] == 'task' for cmd in commands))
                    self.assertEqual(state['sources']['a/tasks']['error']['code'], 'pre-ba-task-api')
                else:
                    self.assertEqual(state['sources']['a/task-events/t']['status'], 'ok')
                    self.assertEqual(sum(cmd[1] == 'task' for cmd in commands), 2)

    def test_config_requires_explicit_actor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'monitor.json'
            path.write_text(json.dumps({'schema_version': 1, 'teams': [{'name': 'a', 'repo': directory}]}))
            with self.assertRaisesRegex(ValueError, 'explicit ATM actor'):
                load_config(path)


if __name__ == '__main__':
    unittest.main()
