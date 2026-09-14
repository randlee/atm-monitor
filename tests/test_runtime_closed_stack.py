import sys
import unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
from answer_types import QuerySlot, Condition
from current_prs import select
from command_query import failure
from pr_types import PR, Stack
from query_types import Ok
from stack_coverage import retired, reconcile
from runtime_policy import Policy
from time_rules import iso

P = Policy(30,300,60,60,60,60,5,2,10,100,50,2,30,30,60,5,120)
OPEN = PR('p',1,iso(10),'OPEN','feature/a','h','main','b',stack_id='s',stack_position=1)
CLOSED = replace(OPEN,state='MERGED',updated_at=iso(20))


def slot(key, items, observed):
    value = Ok('q','gh','r',items,iso(observed))
    return QuerySlot(key,value,value,0,None)


class ClosedStackTests(unittest.TestCase):
    def fixtures(self):
        return (slot('gh_checks:stack:s',(OPEN,Stack('s',1,'main',(OPEN,))),10),
                slot('gh_prs',(CLOSED,),20))

    def test_new_closed_pr_is_not_overwritten_by_old_stack_snapshot(self):
        self.assertEqual(select(self.fixtures()),(CLOSED,))
        self.assertTrue(retired('s',self.fixtures()))

    def test_closed_stack_does_not_realert_when_old_snapshot_expires(self):
        error = failure('gh_stack','gh','s','local-stack-context','missing')
        slots = (*self.fixtures(),QuerySlot('gh_stack:s',None,error,50,None))
        condition = Condition('query:gh_stack:s','query-repair','gh_stack:s','','active','amon','missing')
        result = reconcile((condition,),slots,(CLOSED,),P,5000)
        self.assertEqual(result[0].status,'clear')
        self.assertIn('retired',result[0].detail)

    def test_missing_closure_evidence_does_not_retire(self):
        self.assertFalse(retired('s',self.fixtures()[:1]))

    def test_reopened_member_and_new_open_member_restore_monitoring(self):
        reopened = replace(OPEN,updated_at=iso(30))
        self.assertFalse(retired('s',(*self.fixtures(),slot('gh_checks',(reopened,),30))))
        added = replace(OPEN,node_id='new',number=2,updated_at=iso(30))
        self.assertFalse(retired('s',(*self.fixtures(),slot('gh_checks',(added,),30))))

    def test_provider_revision_beats_later_receipt_of_old_data(self):
        slots = (slot('gh_prs',(CLOSED,),20),slot('gh_checks',(OPEN,),100))
        self.assertEqual(select(slots),(CLOSED,))

    def test_closed_pr_retires_prior_ci_even_after_check_cache_expiry(self):
        from readiness_answers import answer
        from retire_conditions import retire
        from answer_types import DomainState, Incident
        conditions, _ = answer((CLOSED,),self.fixtures(),P,5000)
        prior = Condition('old-ci','ci-failure','1','h','active','lead','failed')
        state = retire(DomainState('r',(),conditions,'complete'),
                       (Incident('old-ci',prior,True,'delivered',iso(1)),))
        self.assertEqual(next(c.status for c in state.conditions if c.key=='old-ci'),'clear')
        self.assertFalse(any(c.status=='active' for c in state.conditions))

    def test_closed_scope_stops_detail_and_stack_queries(self):
        import detail_queries
        import stack_queries
        import fallback_queries
        repo = {'slug': 'o/r', 'team': 't', 'actor': 'a', 'path': '/repo',
                'branch_prefixes': ['feature/'], 'phases': []}
        slots = (*self.fixtures(), slot('gh_checks', (OPEN,), 100))
        for module in (detail_queries, stack_queries, fallback_queries):
            self.assertEqual(module.calls(repo, slots, P, 5000), [])
