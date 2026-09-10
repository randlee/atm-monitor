import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

CRON = Path(__file__).resolve().parents[1] / 'scripts' / 'cron'
sys.path.insert(0, str(CRON))
from state_store import BusyError, locked, read_latest, save, snapshots
from tick import load_config, run_tick


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'state with spaces'

    def snapshot(self, value):
        return {'schema_version': 1, 'sources': {'test': value}}

    def test_atomic_snapshots_keep_history(self):
        with locked(self.directory):
            save(self.directory, self.snapshot('one'))
            save(self.directory, self.snapshot('two'))
        latest, errors = read_latest(self.directory)
        self.assertEqual(latest['sources']['test'], 'two')
        self.assertEqual(latest['sequence'], 2)
        self.assertEqual(errors, [])
        self.assertEqual(len(snapshots(self.directory)), 2)

    def test_failed_replace_preserves_previous_and_removes_temp(self):
        with locked(self.directory):
            save(self.directory, self.snapshot('one'))
            with patch('state_store.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    save(self.directory, self.snapshot('two'))
        self.assertEqual(read_latest(self.directory)[0]['sources']['test'], 'one')
        self.assertFalse(list((self.directory / 'snapshots').glob('.writing-*')))

    def test_corrupt_latest_recovers_with_visible_error(self):
        with locked(self.directory):
            save(self.directory, self.snapshot('one'))
            last = save(self.directory, self.snapshot('two'))
            last.write_text('broken')
        data, errors = read_latest(self.directory)
        self.assertEqual(data['sources']['test'], 'one')
        self.assertEqual(len(errors), 1)
        with locked(self.directory):
            path = save(self.directory, self.snapshot('three'))
        self.assertEqual(path.stem, '000000000003')

    def test_incomplete_write_is_not_a_snapshot(self):
        folder = self.directory / 'snapshots'
        folder.mkdir(parents=True)
        (folder / '.writing-interrupted').write_text('{')
        self.assertEqual(read_latest(self.directory), (None, []))

    def test_exception_releases_lock(self):
        with self.assertRaises(ValueError):
            with locked(self.directory):
                raise ValueError('crash')
        with locked(self.directory):
            pass

    def test_competing_process_and_process_death(self):
        code = ('import sys,time; sys.path.insert(0,sys.argv[1]); from state_store import locked; '
                '\nwith locked(sys.argv[2]):\n print("locked",flush=True)\n time.sleep(30)\n')
        process = subprocess.Popen([sys.executable, '-u', '-c', code, str(CRON), str(self.directory)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'locked')
            with self.assertRaises(BusyError):
                with locked(self.directory):
                    self.fail('second process acquired lock')
        finally:
            process.terminate()
            process.communicate(timeout=10)
        with locked(self.directory):
            pass


class TickTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {'schema_version': 1, 'event_tasks_per_tick': 1,
                       'teams': [{'name': 'a', 'repo': str(self.root), 'worktrees': []}]}

    def collector(self, kind, **kwargs):
        rows = []
        if kind == 'tasks':
            rows = [{'team': 'a', 'task_id': x, 'assignee': 'worker', 'state': 'active'} for x in ['t1', 't2']]
        return {'status': 'ok', 'data': rows, 'observed_at': '2026-01-01T00:00:00Z'}

    def test_failed_source_retains_last_good_but_latest_is_unavailable(self):
        run_tick(self.config, self.root / 'state', self.collector)
        def failed(kind, **kwargs):
            if kind == 'tasks':
                return {'status': 'unavailable', 'data': None, 'error': 'timeout'}
            return self.collector(kind, **kwargs)
        result = run_tick(self.config, self.root / 'state', failed)
        state, _ = read_latest(self.root / 'state')
        self.assertEqual(result['status'], 'degraded')
        self.assertEqual(state['sources']['a/tasks']['status'], 'unavailable')
        self.assertEqual(len(state['last_good']['a/tasks']['data']), 2)

    def test_event_budget_and_restart_resume(self):
        calls = []
        def recorded(kind, **kwargs):
            if kind == 'task-events':
                calls.append(kwargs['task_id'])
            return self.collector(kind, **kwargs)
        first = run_tick(self.config, self.root / 'state', recorded)
        second = run_tick(self.config, self.root / 'state', recorded)
        third = run_tick(self.config, self.root / 'state', recorded)
        self.assertEqual(calls, ['t1', 't2'])
        self.assertEqual(first['deferred_event_tasks'], 1)
        self.assertEqual(second['deferred_event_tasks'], 0)
        self.assertTrue(first['fresh_start'])
        self.assertFalse(third['fresh_start'])

    def test_failed_event_fetch_is_retried(self):
        attempts = []
        def failed(kind, **kwargs):
            if kind == 'task-events':
                attempts.append(kwargs['task_id'])
                return {'status': 'unavailable', 'data': None}
            return self.collector(kind, **kwargs)
        run_tick(self.config, self.root / 'state', failed)
        run_tick(self.config, self.root / 'state', failed)
        self.assertEqual(attempts, ['t1', 't1'])

    def test_teams_are_separate_even_when_agent_names_match(self):
        self.config['teams'].append({'name': 'b', 'repo': str(self.root), 'worktrees': []})
        run_tick(self.config, self.root / 'state', self.collector)
        state, _ = read_latest(self.root / 'state')
        self.assertIn('a/tasks', state['sources'])
        self.assertIn('b/tasks', state['sources'])

    def test_config_relative_to_config_not_current_directory(self):
        folder = self.root / 'configuration'
        folder.mkdir()
        path = folder / 'monitor.json'
        path.write_text(json.dumps({'schema_version': 1, 'teams': [{'name': 'a', 'repo': '..'}]}))
        self.assertEqual(load_config(path)['teams'][0]['repo'], str(self.root.resolve()))

    def test_duplicate_team_and_missing_repository_are_rejected(self):
        for rows in [[{'name': 'a', 'repo': '.'}, {'name': 'a', 'repo': '.'}],
                     [{'name': 'a', 'repo': 'does-not-exist'}]]:
            path = self.root / 'config.json'
            path.write_text(json.dumps({'schema_version': 1, 'teams': rows}))
            with self.assertRaises(ValueError):
                load_config(path)


if __name__ == '__main__':
    unittest.main()
