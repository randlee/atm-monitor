import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
from answer_types import Condition, DomainState, Envelope, Incident
from idle_dispositions import apply
from incident_decisions import decide, reserve
from record_resolution import record
from runtime_registry import REGISTRY
from state_disk import load, save

C = Condition('idle:t:assignment', 'idle-investigation', 't', 'assignment', 'active', 'fenix', 'idle')
E = Envelope(1, 1, DomainState('repo', (), (C,), 'complete'), (),
             (Incident(C.key, C, True, 'delivered', 'then', receipt='real-delivery'),), (), 'then')


class ResolutionTests(unittest.TestCase):
    def test_false_positive_survives_disk_restart_and_repeated_idle(self):
        resolved = record(E, C.key, 'false-positive', 'Owner orchestrating', ('owner-reply',), 100)
        with tempfile.TemporaryDirectory() as directory:
            save(directory, resolved, Envelope, REGISTRY)
            stored, _ = load(directory, Envelope, REGISTRY)
        state = apply(replace(stored.state, conditions=(C,)), stored.slots)
        incidents = decide(state.conditions, stored.incidents, 5000)
        self.assertFalse(incidents[0].active)
        self.assertEqual(incidents[0].receipt, 'real-delivery')
        self.assertEqual(reserve(incidents, 5000)[1], ())

    def test_new_assignment_is_not_suppressed(self):
        resolved = record(E, C.key, 'false-positive', 'Working', ('owner-reply',), 100)
        new = replace(C, key='idle:t:new-assignment', revision='new-assignment')
        state = apply(replace(resolved.state, conditions=(new,)), resolved.slots)
        self.assertEqual(state.conditions[0].status, 'active')

    def test_reopen_requires_new_evidence(self):
        resolved = record(E, C.key, 'false-positive', 'Working', ('owner-reply',), 100)
        with self.assertRaises(ValueError):
            record(resolved, C.key, 'reopen', 'Time passed', ('owner-reply',), 5000)
        reopened = record(resolved, C.key, 'reopen', 'Owner confirms blocked', ('new-owner-reply',), 5000)
        self.assertEqual(apply(E.state, reopened.slots).conditions[0].status, 'active')
