import sys
import unittest
sys.path.insert(0, 'skills/atm-oversight/scripts/runtime')
from answer_types import QuerySlot
from query_types import Ok, Error, Problem, Partial
from pr_types import PR, Check
from runtime_policy import Policy
from readiness_answers import answer

P = Policy(5,300,60,60,60,120,1,2,10,60,10,2,60,300,600,5,120)
class ReadinessTests(unittest.TestCase):
    def test_stack_positive_facts_survive_standalone_failure(self):
        p = PR('p',7,'','OPEN','feature/a','head','main','base',False,'MERGEABLE','CLEAN',False,rollup_sha='head')
        check = Check(7,'head','CI','COMPLETED','FAILURE',attempt='run-2')
        failed = Error('gh_checks','github','x','1970-01-01T00:00:00+00:00',Problem('timeout','down'))
        standalone = QuerySlot('gh_checks', None, failed, 1, None)
        stack = QuerySlot('gh_checks:stack:s1', Ok('q','github','x',(p,check),'1970-01-01T00:00:00+00:00'), Ok('q','github','x',(p,check),'1970-01-01T00:00:00+00:00'), 0, None)
        conditions, _ = answer((p,), (standalone,stack), P, 0)
        self.assertTrue(any(c.kind == 'ci-failure' and c.status == 'active' for c in conditions))

    def test_partial_does_not_claim_missing_check(self):
        p = PR('p',7,'','OPEN','feature/a','head','main','base',False,'MERGEABLE','CLEAN',False,rollup_sha='head')
        partial = Partial('q','github','x',(p,), '1970-01-01T00:00:00+00:00', (Problem('pagination','more'),), 'cursor')
        slot = QuerySlot('gh_checks', partial, partial, 0, None)
        conditions, _ = answer((p,), (slot,), P, 0, expected=(('main',('CI',)),))
        self.assertEqual(next(c for c in conditions if c.kind == 'ci-not-started').status, 'unknown')

if __name__ == '__main__': unittest.main()
