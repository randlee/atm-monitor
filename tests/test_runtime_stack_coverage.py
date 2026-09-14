import sys
import unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
from answer_types import QuerySlot, Condition
from command_query import failure
from pr_types import PR, Stack, Ancestry
from query_types import Ok, Partial, Problem
from runtime_policy import Policy
from stack_coverage import reconcile
from time_rules import iso

P = Policy(30,300,60,60,60,60,5,2,10,100,50,2,30,30,60,5,120)
PR1 = PR('p',1,iso(100),'OPEN','feature/a','h','main','b',stack_id='s',stack_position=1)
COND = Condition('query:gh_stack:s','query-repair','gh_stack:s','','active','amon','missing')


def slot(key, value):
    return QuerySlot(key, value if value.status != 'error' else None, value, 4, None)


def fixtures():
    remote = Ok('q','gh','s',(Stack('s',1,'main',(PR1,)),),iso(100))
    ancestry = Ok('q','git','s',(Ancestry('/r','b','h',False),),iso(1))
    error = failure('gh_stack','gh','s','local-stack-context','no local tracking')
    return (slot('gh_stack:s',error),slot('gh_checks:stack:s',remote),slot('gh_ancestry:1',ancestry))


class CoverageTests(unittest.TestCase):
    def test_complete_fallback_clears_repair_without_rewriting_query_error(self):
        slots = fixtures()
        result = reconcile((COND,),slots,(PR1,),P,100)
        self.assertEqual(result[0].status,'clear')
        self.assertIn('Local tracking remains unavailable',result[0].detail)
        self.assertEqual(slots[0].latest.status,'error')
        # Ancestry false is valid evidence of maintenance, not a failed query.
        self.assertFalse(slots[2].latest.data[0].included)

    def test_stale_partial_or_failed_remote_keeps_repair(self):
        for replacement in (replace(fixtures()[1].latest,observed_at=iso(-1000)),
                Partial('q','gh','s',(),iso(100),(Problem('pagination','more'),),'cursor'),
                failure('q','gh','s','unavailable','down')):
            slots = (fixtures()[0],slot('gh_checks:stack:s',replacement),fixtures()[2])
            self.assertEqual(reconcile((COND,),slots,(PR1,),P,100)[0].status,'active')

    def test_missing_or_wrong_revision_ancestry_keeps_repair(self):
        self.assertEqual(reconcile((COND,),fixtures()[:2],(PR1,),P,100)[0].status,'active')
        self.assertEqual(reconcile((COND,),fixtures(),(replace(PR1,head_sha='new'),),P,100)[0].status,'active')

    def test_other_query_failures_are_not_suppressed(self):
        original = fixtures()[0].latest
        error = replace(original,problem=replace(original.problem,kind='access'))
        slots = (slot('gh_stack:s',error),*fixtures()[1:])
        self.assertEqual(reconcile((COND,),slots,(PR1,),P,100)[0].status,'active')

    def test_partial_topology_is_not_complete_coverage(self):
        bad = replace(PR1,stack_position=2)
        remote = replace(fixtures()[1].latest,data=(Stack('s',1,'main',(bad,)),))
        slots = (fixtures()[0],slot('gh_checks:stack:s',remote),fixtures()[2])
        self.assertEqual(reconcile((COND,),slots,(bad,),P,100)[0].status,'active')
