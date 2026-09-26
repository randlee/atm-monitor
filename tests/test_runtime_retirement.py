import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
from answer_types import Condition, DomainState, Incident
from retire_conditions import retire


class RetirementTests(unittest.TestCase):
    def test_new_attempt_retires_old_failure_without_requiring_new_commit(self):
        old = Condition('pr:1:h:build:run1:failed', 'ci-failure', '1', 'h', 'active', 'lead', 'failed')
        new = Condition('pr:1:h:build:run2:failed', 'ci-failure', '1', 'h', 'clear', 'lead', 'passed')
        prior = Incident(old.key, old, True, 'delivered', 'then')
        state = retire(DomainState('r', (), (new,), 'complete'), (prior,))
        self.assertEqual(next(c.status for c in state.conditions if c.key == old.key), 'clear')

    def test_unknown_new_attempt_does_not_claim_recovery(self):
        old = Condition('pr:1:h:build:run1:failed', 'ci-failure', '1', 'h', 'active', 'lead', 'failed')
        new = Condition('pr:1:h:build:run2:failed', 'ci-failure', '1', 'h', 'unknown', 'lead', 'missing')
        prior = Incident(old.key, old, True, 'delivered', 'then')
        state = retire(DomainState('r', (), (new,), 'complete'), (prior,))
        self.assertNotIn(old.key, {c.key for c in state.conditions})
