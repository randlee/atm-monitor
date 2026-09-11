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
from tick import load_config, run_tick, jobs


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

    def test_all_events_refresh_even_with_legacy_budget_and_unchanged_tasks(self):
        calls = []
        def recorded(kind, **kwargs):
            if kind == 'task-events':
                calls.append(kwargs['task_id'])
            return self.collector(kind, **kwargs)
        first = run_tick(self.config, self.root / 'state', recorded)
        second = run_tick(self.config, self.root / 'state', recorded)
        third = run_tick(self.config, self.root / 'state', recorded)
        self.assertEqual(sorted(calls), ['t1', 't1', 't1', 't2', 't2', 't2'])
        self.assertEqual(first['deferred_event_tasks'], 0)
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
        self.assertEqual(sorted(attempts), ['t1', 't1', 't2', 't2'])

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

    def test_more_than_100_tasks_are_all_collected_in_one_tick(self):
        def collector(kind, **kwargs):
            if kind == 'tasks':
                return {'status': 'ok', 'data': [
                    {'task_id': str(i), 'assignee': 'worker', 'state': 'active'} for i in range(111)]}
            return self.collector(kind, **kwargs)
        result = run_tick(self.config, self.root / 'state', collector)
        snapshot, _ = read_latest(self.root / 'state')
        self.assertEqual(sum('/task-events/' in key for key in snapshot['sources']), 111)
        self.assertEqual(result['deferred_event_tasks'], 0)
        self.assertEqual(result['status'], 'ok')

    def test_overlapping_phase_collection_uses_earliest_start_and_all_worktrees(self):
        self.config['teams'][0]['projects'] = [
            {'phase': 'BA', 'start_time': '2026-09-11T00:00:00Z', 'worktrees': ['ba-tree']},
            {'phase': 'AZ', 'start_time': '2026-09-09T17:00:00-07:00', 'worktrees': ['az-tree']}]
        specifications = jobs(self.config)
        ci = next(options for _, kind, options in specifications if kind == 'ci')
        self.assertEqual(ci['start_time'], '2026-09-09T17:00:00-07:00')
        self.assertEqual({options['repo'] for _, kind, options in specifications if kind == 'stack'},
                         {'ba-tree', 'az-tree'})

    def test_duplicate_phase_or_timezone_missing_is_invalid(self):
        project = {'phase': 'AZ', 'start_time': '2026-09-10T00:00:00Z'}
        for projects in ([project, project], [dict(project, start_time='2026-09-10')]):
            self.config['teams'][0]['projects'] = projects
            path = self.root / 'config.json'
            path.write_text(json.dumps(self.config))
            with self.assertRaises(ValueError):
                load_config(path)

    def test_onboarding_multiple_phases_and_configuring_one_keeps_other_pending(self):
        plans = self.root / 'docs/plans'
        plans.mkdir(parents=True)
        for phase in ('AZ', 'BA'):
            (plans / ('sprint-' + phase + '.1.md')).write_text(
                f'---\nphase: {phase}\nsprint: {phase}.1\nbranch: feature/{phase.lower()}1\n---\n')
        def collector(kind, **kwargs):
            if kind == 'ci':
                return {'status': 'ok', 'data': [
                    {'number': i, 'headRefName': 'feature/' + phase.lower() + '1', 'state': 'OPEN'}
                    for i, phase in enumerate(('AZ', 'BA'), 1)]}
            return self.collector(kind, **kwargs)
        result = run_tick(self.config, self.root / 'state', collector)
        self.assertEqual({r['phase'] for r in result['onboarding_requests']}, {'AZ', 'BA'})
        self.config['teams'][0]['projects'] = [{'phase': 'AZ', 'start_time': '2026-09-10T00:00:00Z'}]
        result = run_tick(self.config, self.root / 'state', collector)
        self.assertEqual([r['phase'] for r in result['onboarding_requests']], ['BA'])
        self.config['teams'][0]['projects'].append({'phase': 'BA', 'start_time': '2026-09-11T00:00:00Z'})
        result = run_tick(self.config, self.root / 'state', collector)
        self.assertEqual(result['onboarding_requests'], [])

    def test_changed_scope_does_not_relabel_old_ci_as_current(self):
        run_tick(self.config, self.root / 'state', self.collector)
        self.config['teams'][0]['projects'] = [{'phase': 'BA', 'start_time': '2026-09-11T00:00:00Z'}]
        def collector(kind, **kwargs):
            if kind == 'ci':
                return {'status': 'unavailable', 'data': None}
            return self.collector(kind, **kwargs)
        run_tick(self.config, self.root / 'state', collector)
        state, _ = read_latest(self.root / 'state')
        self.assertNotIn('a/ci', state['last_good'])


if __name__ == '__main__':
    unittest.main()
