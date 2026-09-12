import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'cron'))
from agent_gate import evaluate_gate


def finding(key='incident-1'):
    return {'incident_key': key, 'kind': 'ci-failure', 'routes': ['team-lead@a'],
            'pending_routes': ['team-lead@a'], 'subject': 'bad check'}


class AgentGateTests(unittest.TestCase):
    def test_new_then_unchanged_deduplicates(self):
        first, state = evaluate_gate({'status': 'ok', 'findings': [finding()]})
        second, state = evaluate_gate({'status': 'ok', 'findings': [finding()]}, state)
        self.assertTrue(first['wakeAgent'])
        self.assertFalse(second['wakeAgent'])
        self.assertEqual(second['events'], [])

    def test_delivered_finding_stays_active_and_pending_wakes_once(self):
        delivered = dict(finding(), pending_routes=[])
        decision, state = evaluate_gate({'status': 'ok', 'findings': [delivered]})
        self.assertFalse(decision['wakeAgent'])
        decision, state = evaluate_gate({'status': 'ok', 'findings': [finding()]}, state)
        self.assertTrue(decision['wakeAgent'])
        decision, _ = evaluate_gate({'status': 'ok', 'findings': [finding()]}, state)
        self.assertFalse(decision['wakeAgent'])

    def test_recurrence_rearms_after_good_recovery(self):
        _, state = evaluate_gate({'status': 'ok', 'findings': [finding()]})
        _, state = evaluate_gate({'status': 'ok', 'findings': []}, state)
        decision, _ = evaluate_gate({'status': 'ok', 'findings': [finding()]}, state)
        self.assertTrue(decision['wakeAgent'])

    def test_outage_does_not_false_recover(self):
        _, state = evaluate_gate({'status': 'ok', 'findings': [finding()]})
        _, state = evaluate_gate({'status': 'degraded', 'failed_sources': ['a/ci'], 'findings': []}, state)
        decision, _ = evaluate_gate({'status': 'ok', 'findings': [finding()]}, state)
        self.assertFalse(decision['wakeAgent'])

    def test_busy_does_not_advance_state(self):
        before = {'schema_version': 1, 'incidents': {}}
        decision, after = evaluate_gate({'status': 'busy'}, before)
        self.assertEqual(decision, {'wakeAgent': False, 'events': []})
        self.assertEqual(after, before)

    def test_health_failure_is_single_stable_maintainer_event(self):
        a, state = evaluate_gate({'status': 'degraded', 'failed_sources': ['a/ci'],
                                  'findings': []})
        b, _ = evaluate_gate({'status': 'degraded', 'failed_sources': ['a/ci'],
                              'activity_warnings': ['timestamp changed'], 'findings': []}, state)
        self.assertTrue(a['wakeAgent'])
        self.assertFalse(b['wakeAgent'])
        self.assertEqual(a['events'][0]['routes'], ['amon@atm-monitor'])

    def test_corrupt_state_fails_closed(self):
        with self.assertRaises(ValueError):
            evaluate_gate({'status': 'ok'}, {'schema_version': 9, 'incidents': {}})

    def test_cli_emits_gate_and_rejects_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result = root / 'result.json'; result.write_text(json.dumps({'status': 'busy'}))
            proc = subprocess.run([sys.executable, str(ROOT / 'scripts/cron/agent_gate.py'),
                                   '--result-file', str(result), '--state-dir', str(root / 'state')],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads(proc.stdout), {'wakeAgent': False, 'events': []})


if __name__ == '__main__':
    unittest.main()
