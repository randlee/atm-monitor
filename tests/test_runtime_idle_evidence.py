import sys
import unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
from activity_types import OwnerActivity
from answer_types import Timer
from idle_answers import answer
from runtime_policy import Policy
from time_rules import iso
from work_types import Agent, Task

P = Policy(30,300,60,60,60,60,5,2,10,100,50,2,30,30,60,5,120)
TASK = Task('task', assignee='fenix', status='active', assigned_at=iso(1))
AGENT = Agent('fenix', 'idle', iso(100), background=None)
KEY = 'idle:task:' + iso(1)


class IdleEvidenceTests(unittest.TestCase):
    def test_orchestration_send_clears_candidate_and_resets_timer(self):
        activity = OwnerActivity('fenix', 'observer', iso(100), iso(90), 'send-1')
        result, timers = answer((TASK,), (AGENT,), P, 100, (Timer(KEY, iso(1)),), activities=(activity,))
        self.assertEqual(result[0].status, 'clear')
        self.assertIn('send-1', result[0].detail)
        self.assertEqual(timers, ())

    def test_missing_query_evidence_is_unknown_not_a_stall(self):
        result, timers = answer((TASK,), (AGENT,), P, 100, (Timer(KEY, iso(1)),))
        self.assertEqual(result[0].status, 'unknown')
        self.assertEqual(timers, ())

    def test_empty_observer_store_only_asks_owner_after_grace(self):
        activity = OwnerActivity('fenix', 'observer', iso(100))
        result, timers = answer((TASK,), (AGENT,), P, 100, (Timer(KEY, iso(1)),), activities=(activity,))
        self.assertEqual(result[0].status, 'active')
        self.assertEqual(result[0].kind, 'idle-investigation')
        self.assertIn('Ask the owner', result[0].detail)
        self.assertIn('not stall or restart evidence', result[0].detail)

    def test_stale_send_does_not_mask_future_investigation(self):
        activity = OwnerActivity('fenix', 'observer', iso(100), iso(1), 'old')
        result, _ = answer((TASK,), (AGENT,), P, 100, (Timer(KEY, iso(1)),), activities=(activity,))
        self.assertEqual(result[0].status, 'active')
