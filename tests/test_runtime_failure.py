import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
from runtime_failure import record
from record_action import record as attach
from answer_types import Envelope
from runtime_registry import REGISTRY
from state_disk import load, save


class RuntimeFailureTests(unittest.TestCase):
    def test_actual_receipt_survives_repeated_failure_until_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            events = record(root, 'repo', 'worker crashed')
            self.assertEqual(len(events), 1)
            event = events[0]
            directory = event['state_dir']
            env, _ = load(directory, Envelope, REGISTRY)
            saved = attach(env, event['incident_key'], 'actual-message', 'amon@atm-monitor')
            save(directory, saved, Envelope, REGISTRY)
            self.assertEqual(record(root, 'repo', 'worker crashed'), ())
            env, _ = load(directory, Envelope, REGISTRY)
            self.assertEqual(env.incidents[0].receipt, 'amon@atm-monitor:actual-message')
            self.assertEqual(record(root, 'repo'), ())
            self.assertFalse(load(directory, Envelope, REGISTRY)[0].incidents[0].active)
            self.assertEqual(len(record(root, 'repo', 'worker crashed again')), 1)
