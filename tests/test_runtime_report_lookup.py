import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
import atm_report


class ReportLookupTests(unittest.TestCase):
    def test_history_report_is_retrieved_and_parsed(self):
        body = 'Commit: `5ceb9a48f997ad41274f4a30050ba85830e3a0c7`\nVerdict: **FAIL**\nMachine Status\n```json\n{"findings":{"blocking":6,"important":5,"minor":1}}\n```'
        def execute(query, provider, scope, args, **kwargs):
            payload = {'count': 1, 'message': {'bucket': 'history', 'text': body}} if '--all' in args else {'count': 0}
            return SimpleNamespace(stdout=json.dumps(payload))
        with patch.object(atm_report, 'execute', side_effect=execute):
            result = atm_report.query('team', 'owner', 'report')
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.data[0].verdict, 'fail')
        self.assertEqual(dict(result.data[0].aggregate), {'blocking':6,'important':5,'minor':1})

    def test_missing_message_reports_lookup_failure(self):
        with patch.object(atm_report, 'execute', return_value=SimpleNamespace(stdout='{"count":0}')):
            result = atm_report.query('team', 'owner', 'absent')
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.problem.kind, 'report-not-found')
        self.assertIn('mailbox', result.problem.repair)
