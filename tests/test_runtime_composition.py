import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, 'skills/atm-oversight/scripts/runtime')
from answer_types import QuerySlot
from query_types import Error, Ok, Partial, Problem
from query_memory import remember
from query_catalog import calls
from runtime_policy import Policy

POLICY = Policy(5, 300, 60, 60, 60, 120, 1, 2, 10, 60, 10, 2, 60, 300, 600, 5, 120)
REPO = {'slug':'o/r','path':'/tmp/r','team':'t','actor':'a','since':'2026-01-01T00:00:00+00:00',
        'phases':(), 'branch_prefixes':('feature/',)}

class RuntimeCompositionTests(unittest.TestCase):
    def test_pr_window_is_fixed_and_cursor_is_carried(self):
        partial = Partial('gh_prs','github','o/r',(), '2026-01-01T00:01:00+00:00',
                          (Problem('pagination','more'),), 'cursor-7')
        slot = QuerySlot('gh_prs', partial, partial, 0, None, 'old-boundary')
        planned, checkpoints = calls(REPO, POLICY, (slot,), 1767225660)
        fn = dict(planned)['gh_prs']
        with patch('query_catalog.gh_prs.query', return_value=partial) as invoke:
            fn()
        args = invoke.call_args.kwargs
        self.assertEqual(args['after'], 'cursor-7')
        self.assertIn('T', invoke.call_args.args[1])
        self.assertEqual(len(checkpoints), 2)

    def test_error_does_not_advance_checkpoint(self):
        old = Ok('q','s','scope',(), '2026-01-01T00:00:00+00:00')
        slot = QuerySlot('q', old, old, 0, None, 'accepted')
        failed = Error('q','s','scope','2026-01-01T00:01:00+00:00', Problem('timeout','x'))
        kept = remember('q', failed, slot, 1767225660, POLICY, 'new')
        self.assertEqual(kept.checkpoint, 'accepted')
        self.assertIs(kept.last_good, old)

    def test_malformed_query_value_becomes_error(self):
        from source_queries import execute_calls
        result = execute_calls([('bad', lambda: {'healthy': True})], (), POLICY, 1767225660)
        self.assertEqual(result[0].latest.status, 'error')
        self.assertEqual(result[0].latest.problem.kind, 'invalid-response')

    def test_same_domain_data_remains_equal_across_observation_receipts(self):
        a = Ok('q','s','scope',('value',), '2026-01-01T00:00:00+00:00')
        b = Ok('q','s','scope',('value',), '2026-01-01T00:05:00+00:00')
        self.assertEqual(a.data, b.data)
        self.assertEqual(remember('q', a, None, 1, POLICY).last_good.data,
                         remember('q', b, None, 2, POLICY).last_good.data)

if __name__ == '__main__':
    unittest.main()
