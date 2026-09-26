"""Exercise durable handoff ordering and restart behavior at the cron boundary."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
import repo_tick
from answer_types import Condition, DomainState, Envelope
from query_types import Ok
from runtime_policy import Policy
from runtime_registry import REGISTRY
from state_disk import load

POLICY = Policy(30, 300, 60, 60, 60, 60, 5, 2, 10, 100, 50, 2, 30, 30, 60, 5, 120)
REPO = {'slug': 'o/r'}
STATE = DomainState('o/r', (), (Condition('k', 'ci-failure', '1', 'h', 'active', 'lead', 'fail'),), 'complete')


class TickTests(unittest.TestCase):
    def setUp(self):
        for name in ('details', 'stacks', 'fallbacks'):
            mocked = patch.object(repo_tick, name, return_value=[])
            mocked.start()
            self.addCleanup(mocked.stop)
        patches = [patch.object(repo_tick, 'calls', return_value=([], ())),
                   patch.object(repo_tick, 'execute_calls', side_effect=lambda calls, slots, *args: slots),
                   patch.object(repo_tick, 'compose', return_value=(STATE, ())),
                   patch.object(repo_tick, 'retire', side_effect=lambda state, prior: state)]
        for mocked in patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def tick(self, directory):
        return repo_tick.tick(REPO, directory, POLICY, 100, Ok('herdr', 'herdr', '', (), ''))

    def test_restart_has_no_duplicate_wake_and_equal_domain(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.tick(directory)
            stored, _ = load(directory, Envelope, REGISTRY)
            self.assertTrue(first['wakeAgent'])
            self.assertEqual(stored.incidents[0].delivery, 'attempting')
            second = self.tick(directory)
            self.assertFalse(second['wakeAgent'])
            self.assertFalse(second['changed'])
            self.assertEqual(load(directory, Envelope, REGISTRY)[0].state, stored.state)

    def test_failed_persistence_cannot_return_wake(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(repo_tick, 'save', side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    self.tick(directory)
            self.assertFalse(Path(directory, 'report.md').exists())
            self.assertIsNone(load(directory, Envelope, REGISTRY)[0])

    def test_corrupt_primary_uses_backup_and_preserves_pending_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            self.tick(directory)
            self.tick(directory)
            Path(directory, 'state.json').write_text('{broken')
            recovered = self.tick(directory)
            self.assertFalse(recovered['wakeAgent'])
            self.assertEqual(load(directory, Envelope, REGISTRY)[0].state, STATE)
