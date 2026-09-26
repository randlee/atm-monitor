import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'cron'))
import hermes_monitor


class HermesMonitorTests(unittest.TestCase):
    def test_corrupt_gate_requests_maintenance_once_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(hermes_monitor, 'run', side_effect=ValueError('corrupt gate')), \
                patch.object(sys, 'argv', ['monitor', '--config', 'config.json', '--state-dir', tmp]):
            decisions = []
            for _ in range(2):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(hermes_monitor.main(), 0)
                decisions.append(json.loads(out.getvalue()))
            self.assertTrue(decisions[0]['wakeAgent'])
            self.assertFalse(decisions[1]['wakeAgent'])
            self.assertTrue((Path(tmp) / 'scheduler/gate_failure.json').exists())

    def test_scheduled_collection_records_receipt_and_deduplicates(self):
        result = {'status': 'ok', 'findings': [{'incident_key': 'ci-1',
                  'pending_routes': ['team-lead@atm-dev']}]}
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(hermes_monitor, 'load_config', return_value={}), \
                patch.object(hermes_monitor, 'detect', return_value={}), \
                patch.object(hermes_monitor, 'monitor', return_value=result):
            self.assertTrue(hermes_monitor.run('config.json', tmp)['wakeAgent'])
            self.assertFalse(hermes_monitor.run('config.json', tmp)['wakeAgent'])
            receipt = json.loads((Path(tmp) / 'scheduler/last_run.json').read_text())
            self.assertIn('observed_at', receipt)
            self.assertEqual(receipt['result'], result)

    def test_collection_exception_escalates_once(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(hermes_monitor, 'load_config', side_effect=OSError('access denied')):
            first = hermes_monitor.run('config.json', tmp)
            self.assertEqual(first['events'][0]['routes'], ['amon@atm-monitor'])
            self.assertFalse(hermes_monitor.run('config.json', tmp)['wakeAgent'])


if __name__ == '__main__':
    unittest.main()
