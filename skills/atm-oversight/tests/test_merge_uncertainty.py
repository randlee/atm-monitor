import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'cron'))
from agent_gate import evaluate_gate
from check_health import evaluate
from merge_uncertainty import unresolved_incidents


def result(status, head='same-head', number=1452):
    snapshot = {'teams': [{'name': 'atm-dev'}], 'sources': {'atm-dev/ci': {
        'status': 'ok', 'data': [{'number': number, 'state': 'OPEN',
        'headRefOid': head, 'headRefName': 'feature/bb-collapsed',
        'mergeStateStatus': status, 'mergeable': 'UNKNOWN' if status == 'UNKNOWN' else 'MERGEABLE'}]}}}
    return {'status': 'ok', 'findings': evaluate(snapshot),
            'unresolved_incidents': unresolved_incidents(snapshot)}


class MergeUncertaintyTests(unittest.TestCase):
    def test_unknown_does_not_rearm_same_revision(self):
        first, state = evaluate_gate(result('BLOCKED'))
        self.assertTrue(first['wakeAgent'])
        for status in ('UNKNOWN', 'UNKNOWN', 'BLOCKED', 'BLOCKED'):
            decision, state = evaluate_gate(result(status), state)
            self.assertFalse(decision['wakeAgent'])

    def test_clean_recovery_rearms(self):
        _, state = evaluate_gate(result('BLOCKED'))
        _, state = evaluate_gate(result('CLEAN'), state)
        decision, _ = evaluate_gate(result('BLOCKED'), state)
        self.assertTrue(decision['wakeAgent'])

    def test_new_revision_still_wakes(self):
        _, state = evaluate_gate(result('BLOCKED'))
        _, state = evaluate_gate(result('UNKNOWN'), state)
        decision, _ = evaluate_gate(result('BLOCKED', head='new-head'), state)
        self.assertTrue(decision['wakeAgent'])

    def test_unknown_does_not_prevent_independent_recovery(self):
        _, state = evaluate_gate(result('BLOCKED', number=1470))
        combined = result('UNKNOWN')
        combined['findings'] += result('CLEAN', number=1470)['findings']
        _, state = evaluate_gate(combined, state)
        decision, _ = evaluate_gate(result('BLOCKED', number=1470), state)
        self.assertTrue(decision['wakeAgent'])
