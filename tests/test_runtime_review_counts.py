import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
from review_answers import reviews
from work_types import Report


class ReviewCountsTests(unittest.TestCase):
    def test_closed_heads_show_historical_findings_as_stale(self):
        reports = (Report('a', '1234567a', '5', 'fail', (), (('blocking', 4),)),
                   Report('b', '1234567b', '1', 'pass', (), (('blocking', 0),)))
        qa, rounds, counts = reviews(reports, set())
        self.assertEqual(qa.value, 'pass')
        self.assertEqual(qa.freshness, 'stale')
        self.assertIn('B:0', counts.value)
        self.assertEqual(counts.freshness, 'stale')

    def test_aggregate_counts_do_not_assume_distinct_findings(self):
        reports = (Report('a', '1234567a', '1', 'fail', (), (('blocking', 2),)),
                   Report('b', '1234567b', '1', 'fail', (), (('blocking', 2),)))
        qa, rounds, counts = reviews(reports, {'1234567a', '1234567b'})
        self.assertIn('B:2 / 2', counts.value)
        self.assertIn('overlap unknown', counts.value)
        self.assertEqual(counts.support, 'partial')
