import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
import atm_owner_activity
from command_query import CommandSuccess, failure


class OwnerActivityTests(unittest.TestCase):
    def test_one_send_is_complete_existence_answer_despite_more_pages(self):
        payload = {'hits': [{'from_agent': {'agent': 'fenix', 'team': 'atm-dev'},
                   'message_at': '2026-09-13T20:12:18Z', 'message_id': 'actual-send'}], 'next_cursor': 'more'}
        with patch.object(atm_owner_activity, 'execute', return_value=CommandSuccess(json.dumps(payload), '', 0)) as run:
            result = atm_owner_activity.query('atm-dev', 'fenix', '2026-09-13T20:10:00Z', '2026-09-13T20:15:00Z')
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.data[0].message_id, 'actual-send')
        self.assertIn('--limit', run.call_args.args[3])
        self.assertEqual(run.call_count, 1)

    def test_empty_observer_result_preserves_host_and_no_witness(self):
        with patch.object(atm_owner_activity, 'execute', return_value=CommandSuccess('{"hits":[]}', '', 0)):
            result = atm_owner_activity.query('atm-dev', 'fenix', '2026-09-13T20:10:00Z', '2026-09-13T20:15:00Z')
        self.assertTrue(result.data[0].host)
        self.assertIsNone(result.data[0].message_id)

    def test_wrong_owner_and_provider_failure_do_not_become_inactivity(self):
        payload = {'hits': [{'from_agent': {'agent': 'daemon', 'team': 'atm-dev'},
                   'message_at': '2026-09-13T20:12:18Z', 'message_id': 'reminder'}]}
        with patch.object(atm_owner_activity, 'execute', return_value=CommandSuccess(json.dumps(payload), '', 0)):
            result = atm_owner_activity.query('atm-dev', 'fenix', '2026-09-13T20:10:00Z', '2026-09-13T20:15:00Z')
        self.assertEqual(result.status, 'error')
        with patch.object(atm_owner_activity, 'execute', return_value=failure('q','atm','scope','unavailable','down')):
            self.assertEqual(atm_owner_activity.query('atm-dev','fenix','start','end').status, 'error')
