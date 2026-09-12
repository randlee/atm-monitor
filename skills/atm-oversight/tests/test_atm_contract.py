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

    def test_pre_ba_unknown_and_future_major_never_query_tasks(self):
        for version in ('1.3.0', '2.0.0', None, 'unknown', 16):
            for kind in ('tasks', 'task-events'):
                with self.subTest(version=version, kind=kind):
                    calls, run = self.runner(version)
                    result = collect(kind, team='a', actor='monitor', task_id='t', run=run)
                    self.assertEqual(result['status'], 'unavailable')
                    self.assertIsNone(result['data'])
                    self.assertEqual([cmd[1] for cmd, _ in calls], ['doctor'])

    def test_ba2_queries_use_list_flags_without_mailbox_all_selector(self):
        for version in ('1.5.0', '1.5.4'):
            for kind in ('tasks', 'task-events'):
                with self.subTest(version=version, kind=kind):
                    calls, run = self.runner(version)
                    result = collect(kind, team='a', actor='monitor', task_id='t', run=run)
                    self.assertEqual(result['status'], 'ok', result)
                    self.assertEqual(result['task_query_surface'], 'list')
                    command = calls[-1][0]
                    self.assertEqual(command[:2], ['atm', 'list'])
                    self.assertIn('--tasks' if kind == 'tasks' else '--task-events', command)
                    self.assertNotIn('--all', command)
                    self.assertEqual(command[command.index('--team') + 1], 'a')
                    self.assertEqual(command[command.index('--as') + 1], 'monitor')

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
            self.assertIn(result['status'], {'ok', 'partial'}, result)
            self.assertEqual(result['data'], [row])

    def test_ba4_task_list_and_bounded_event_history_preserve_coverage_gaps(self):
        calls, run = self.runner('1.6.0', [{'team': 'a', 'task_id': 't', 'assignee': 'worker', 'state': 'active'}])
        result = collect('tasks', team='a', actor='monitor', run=run)
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(result['error'])
        self.assertEqual(result['coverage']['task_states'], 'open-only')
        self.assertEqual(len(result['data']), 1)
        calls, run = self.runner('1.6.0', result['data'] * 200)
        bounded = collect('tasks', team='a', actor='monitor', run=run)
        self.assertEqual(bounded['status'], 'partial')
        self.assertEqual(bounded['error']['code'], 'limit-reached')
        events = [{'team': 'a', 'task_id': 't', 'assignee': 'worker', 'seq': i,
                   'at': 'now', 'event': 'moved'} for i in range(1, 201)]
        calls, run = self.runner('1.6.0', events)
        result = collect('task-events', team='a', actor='monitor', task_id='t', run=run)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['error']['code'], 'limit-reached')
        self.assertEqual(result['data'], events)

    def test_current_api_reads_all_events_beyond_old_bound(self):
        events = [{'team': 'a', 'task_id': 't', 'assignee': 'worker',
                   'seq': i, 'at': 'now', 'event': 'moved'} for i in range(1, 656)]
        for version in ('1.7.0', '1.8.1'):
            calls, run = self.runner(version, events)
            result = collect('task-events', team='a', actor='monitor', task_id='t', run=run)
            self.assertIn('--all', calls[-1][0])
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['data'], events)
            self.assertIsNone(result['coverage']['row_limit'])
            self.assertFalse(result['coverage']['limit_reached'])
        for version in ('1.5.0', '1.6.0'):
            calls, run = self.runner(version, events[:2])
            collect('task-events', team='a', actor='monitor', task_id='t', run=run)
            self.assertNotIn('--all', calls[-1][0])

    def test_tick_reuses_one_live_doctor_observation_for_all_histories(self):
        for version in ('1.3.0', '1.5.0', '1.6.0'):
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
                    surface = 'list' if version == '1.5.0' else 'task'
                    self.assertEqual(sum(cmd[1] == surface for cmd in commands), 2)

    def test_config_requires_explicit_actor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'monitor.json'
            path.write_text(json.dumps({'schema_version': 1, 'teams': [{'name': 'a', 'repo': directory}]}))
            with self.assertRaisesRegex(ValueError, 'explicit ATM actor'):
                load_config(path)

    def test_ba4_transition_keeps_querying_previously_known_completed_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            version = '1.5.0'
            queried = []
            def run(command, **options):
                if command[1] == 'doctor':
                    data = {'daemon_context': {'version': '1.5.15', 'http_api_version': version}}
                elif command[1] == 'members':
                    data = {'team': 'a', 'members': []}
                elif '--task-events' in command or command[1:3] == ['task', 'events']:
                    task_id = command[command.index('--task-events') + 1] if '--task-events' in command else command[3]
                    queried.append(task_id)
                    data = [{'team': 'a', 'task_id': task_id, 'assignee': 'worker',
                             'seq': 1, 'at': 'now', 'event': 'completed' if task_id == 'closed' else 'assigned'}]
                else:
                    data = [{'team': 'a', 'task_id': 'open', 'assignee': 'worker', 'state': 'assigned'}]
                    if version == '1.5.0':
                        data.append({'team': 'a', 'task_id': 'closed', 'assignee': 'worker', 'state': 'complete'})
                return subprocess.CompletedProcess(command, 0, json.dumps(data), '')
            def collector(kind, **options):
                return collect(kind, run=run, **options) if kind in {'doctor', 'roster', 'tasks', 'task-events'} else {'status': 'ok', 'data': []}
            config = {'teams': [{'name': 'a', 'actor': 'monitor', 'repo': directory}]}
            run_tick(config, directory, collector=collector)
            version = '1.6.0'
            def unavailable(kind, **options):
                if kind == 'doctor':
                    return {'status': 'unavailable', 'data': None}
                return collector(kind, **options)
            # A source outage between the full-ledger and queue-only passes
            # must not erase historical IDs or prevent the final event read.
            run_tick(config, directory, collector=unavailable)
            queried.clear()
            run_tick(config, directory, collector=collector)
            self.assertEqual(set(queried), {'open', 'closed'})
            state, _ = read_latest(directory)
            self.assertEqual(state['sources']['a/tasks']['status'], 'ok')
            self.assertEqual(state['sources']['a/task-events/closed']['status'], 'ok')
            self.assertEqual(state['known_task_ids']['a'], ['closed', 'open'])


if __name__ == '__main__':
    unittest.main()
