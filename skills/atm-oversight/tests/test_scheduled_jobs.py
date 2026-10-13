import copy
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import json
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/cron'))
from detect_activity import detect, path_within
from monitor_phase import monitor, select_teams
from state_store import BusyError, locked, read_latest, save
from tick import run_tick
from scheduled_output import emit


class ScheduledJobTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.activity, self.phases = self.root / 'activity', self.root / 'phases'
        self.config = {'schema_version': 1, 'teams': [
            {'name': name, 'repo': str(self.root / name), 'worktrees': []} for name in ('a', 'b')]}
        self.rows = {name: [{'name': 'worker', 'agent_id': 'worker@' + name,
                            'state': 'idle', 'home_dir': str(self.root / name)}] for name in ('a', 'b')}
        self.agents = []
        self.calls = []
        self.failures = set()

    def collect(self, kind, **kwargs):
        team = kwargs.get('team')
        self.calls.append((kind, team))
        if (kind, team) in self.failures:
            return {'status': 'unavailable', 'data': None}
        rows = self.agents if kind == 'herdr' else self.rows[team] if kind == 'roster' else []
        if kind == 'ci' and team == 'a':
            rows = [{'number': 1, 'headRefOid': 'abc', 'headRefName': 'feature/a', 'state': 'OPEN',
                     'statusCheckRollup': [{'name': 'tests', 'conclusion': 'FAILURE'}]}]
        return {'status': 'ok', 'data': copy.deepcopy(rows),
                'observed_at': datetime.now(timezone.utc).isoformat()}

    def agent(self, repo='a'):
        return {'name': 'worker', 'agent_status': 'working', 'pane_id': 'p1',
                'workspace_id': 'w1', 'cwd': str(self.root / repo), 'state_change_seq': 1}

    def write_activity(self, mutate):
        state, _ = read_latest(self.activity)
        mutate(state)
        with locked(self.activity):
            save(self.activity, state)

    def test_detector_uses_only_herdr_and_rosters_and_quiet_start_does_not_enroll(self):
        result = detect(self.config, self.activity, self.collect)
        self.assertEqual(result['watched_teams'], [])
        self.assertEqual(set(self.calls), {('herdr', None), ('roster', 'a'), ('roster', 'b')})

    def test_same_named_agents_require_matching_path_and_roster(self):
        self.agents = [self.agent()]
        result = detect(self.config, self.activity, self.collect)
        self.assertEqual(result['added_teams'], ['a'])
        self.assertEqual(result['unresolved_agents'], [])

    def test_ambiguous_agent_does_not_guess_and_monitor_includes_candidates(self):
        self.rows['b'][0]['home_dir'] = str(self.root / 'a')
        self.agents = [self.agent()]
        result = detect(self.config, self.activity, self.collect)
        self.assertEqual(result['added_teams'], [])
        self.assertEqual(result['unresolved_agents'][0]['reason'], 'ambiguous identity')
        teams, warnings = select_teams(self.config, self.activity)
        self.assertEqual(len(teams), 2)
        self.assertTrue(warnings)

    def test_unconfigured_agent_is_reported_without_enrollment(self):
        self.agents = [self.agent('other-repo')]
        result = detect(self.config, self.activity, self.collect)
        self.assertEqual(result['added_teams'], [])
        self.assertEqual(len(result['unresolved_agents']), 1)

    def test_roster_activity_and_blocking_enroll_even_without_herdr_match(self):
        self.rows['a'][0]['state'] = 'active'
        self.rows['b'][0]['state'] = 'blocked'
        result = detect(self.config, self.activity, self.collect)
        self.assertEqual(result['added_teams'], ['a', 'b'])

    def test_documented_roster_status_enrolls_activity(self):
        self.rows['a'][0].pop('state')
        self.rows['a'][0]['status'] = 'active'
        result = detect(self.config, self.activity, self.collect)
        self.assertEqual(result['added_teams'], ['a'])

    def test_idle_and_source_failure_preserve_watch_list_and_first_seen(self):
        self.rows['a'][0]['state'] = 'active'
        detect(self.config, self.activity, self.collect)
        first, _ = read_latest(self.activity)
        self.rows['a'][0]['state'] = 'idle'
        self.failures.add(('herdr', None))
        result = detect(self.config, self.activity, self.collect)
        state, _ = read_latest(self.activity)
        self.assertEqual(result['watched_teams'], ['a'])
        self.assertEqual(first['watched_teams'], state['watched_teams'])

    def test_activity_overlap_is_busy(self):
        with locked(self.activity):
            with self.assertRaises(BusyError):
                detect(self.config, self.activity, self.collect)

    def test_path_match_has_directory_boundary_and_rejects_relative_paths(self):
        self.assertTrue(path_within(str(self.root / 'a/sub'), str(self.root / 'a')))
        self.assertFalse(path_within(str(self.root / 'abc'), str(self.root / 'a')))
        self.assertFalse(path_within('a/sub', str(self.root / 'a')))

    def test_missing_stale_future_and_corrupt_detection_fall_back_to_all_teams(self):
        teams, warnings = select_teams(self.config, self.activity)
        self.assertEqual(len(teams), 2)
        self.assertTrue(warnings)
        for offset in (-1000, 1000):
            detect(self.config, self.activity, self.collect)
            self.write_activity(lambda state: state.update(observed_at=(
                datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat()))
            teams, warnings = select_teams(self.config, self.activity)
            self.assertEqual(len(teams), 2)
            self.assertTrue(warnings)
        detect(self.config, self.activity, self.collect)
        newest = sorted((self.activity / 'snapshots').glob('*.json'))[-1]
        newest.write_text('{', encoding='utf-8')
        teams, warnings = select_teams(self.config, self.activity)
        self.assertEqual(len(teams), 2)
        self.assertTrue(warnings)

    def test_changed_config_forces_detection_refresh(self):
        detect(self.config, self.activity, self.collect)
        changed = copy.deepcopy(self.config)
        changed['teams'][0]['repo'] = str(self.root / 'changed')
        teams, warnings = select_teams(changed, self.activity)
        self.assertEqual(len(teams), 2)
        self.assertIn('configuration differs', warnings[0])

    def test_roster_failure_adds_only_uncertain_team(self):
        self.failures.add(('roster', 'b'))
        detect(self.config, self.activity, self.collect)
        teams, warnings = select_teams(self.config, self.activity)
        self.assertEqual([team['name'] for team in teams], ['b'])
        self.assertTrue(warnings)

    def test_phase_job_collects_watched_teams_and_emits_routed_findings(self):
        self.rows['a'][0]['state'] = 'active'
        detect(self.config, self.activity, self.collect)
        self.calls.clear()
        result = monitor(self.config, self.activity, self.phases, collector=self.collect)
        self.assertEqual(result['monitored_teams'], ['a'])
        self.assertFalse(any(team == 'b' for _, team in self.calls))
        self.assertEqual(result['notify'][0]['routes'], ['team-lead@a'])
        state, _ = read_latest(self.phases)
        self.assertEqual(state['interventions'], {})

    def test_quiet_catalog_does_not_run_expensive_queries(self):
        detect(self.config, self.activity, self.collect)
        self.calls.clear()
        result = monitor(self.config, self.activity, self.phases, collector=self.collect)
        self.assertEqual(result['monitored_teams'], [])
        self.assertEqual(self.calls, [('herdr', None)])

    def test_retained_phase_survives_activity_state_reset(self):
        with locked(self.phases):
            save(self.phases, {'schema_version': 1, 'sources': {},
                              'tracked_sprints': {'a': {'AZ/AZ.1': {'phase': 'AZ', 'branch': 'feature/a'}}}})
        detect(self.config, self.activity, self.collect)
        result = monitor(self.config, self.activity, self.phases, collector=self.collect)
        self.assertEqual(result['monitored_teams'], ['a'])

    def test_empty_prior_phase_inventory_does_not_keep_quiet_teams_selected(self):
        with locked(self.phases):
            save(self.phases, {'schema_version': 1, 'sources': {}, 'tracked_sprints': {'a': {}}})
        detect(self.config, self.activity, self.collect)
        result = monitor(self.config, self.activity, self.phases, collector=self.collect)
        self.assertEqual(result['monitored_teams'], [])

    def test_activity_and_phase_state_cannot_overwrite_each_other(self):
        detect(self.config, self.activity, self.collect)
        with self.assertRaises(ValueError):
            monitor(self.config, self.activity, self.activity, collector=self.collect)
        with self.assertRaises(ValueError):
            run_tick(self.config, self.activity, self.collect)
        with locked(self.phases):
            save(self.phases, {'schema_version': 1, 'sources': {}})
        with self.assertRaises(ValueError):
            detect(self.config, self.phases, self.collect)

    def test_cron_output_distinguishes_findings_failure_and_overlap(self):
        for payload, code, silent in [
            ({'status': 'ok'}, 0, True),
            ({'status': 'ok', 'added_teams': ['a']}, 0, True),
            ({'status': 'degraded', 'partial_sources': ['a/ci']}, 0, True),
            ({'status': 'ok', 'notify': [{'incident_key': 'x'}]}, 1, False),
            ({'status': 'ok', 'onboarding_requests': [{'phase': 'BA'}]}, 1, False),
            ({'status': 'degraded', 'failed_sources': ['a/ci']}, 2, False),
            ({'status': 'degraded', 'activity_warnings': ['stale']}, 2, False),
            ({'status': 'error', 'error': 'bad config'}, 2, False),
            ({'status': 'busy'}, 3, True),
        ]:
            with self.subTest(payload=payload):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(emit(payload), code)
                self.assertEqual(out.getvalue() == '', silent)
                if not silent:
                    self.assertEqual(json.loads(out.getvalue())['exit_code'], code)

    def test_diagnostic_mode_prints_success_without_changing_exit_code(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(emit({'status': 'ok'}, diagnostic=True), 0)
        self.assertEqual(json.loads(out.getvalue())['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
