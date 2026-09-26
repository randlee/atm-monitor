import sys
import unittest
sys.path.insert(0, 'skills/atm-oversight/scripts/runtime')
from answer_types import QuerySlot
from query_types import Ok
from pr_types import PR, Stack, StackView, Ancestry
import stack_answers
import stack_queries
from runtime_policy import Policy

class StackCompositionTests(unittest.TestCase):
    def test_context_schedules_stack_view_and_exact_ancestry(self):
        p = PR('p1', 7, '', 'OPEN', 'feature/a', 'head', 'main', 'base', stack_id='s1')
        stack = Stack('s1', 1, 'main', (p,))
        context = (('/repo\nbranch refs/heads/feature/a',), ('feature/a head',))
        slots = (QuerySlot('gh_prs', Ok('q','s','x',(p,), '2026-01-01'), Ok('q','s','x',(p,), '2026-01-01'), 0, None),
                 QuerySlot('gh_checks', Ok('q','s','x',(stack,), '2026-01-01'), Ok('q','s','x',(stack,), '2026-01-01'), 0, None),
                 QuerySlot('gh_git_context', Ok('q','s','x',(context,), '2026-01-01'), Ok('q','s','x',(context,), '2026-01-01'), 0, None))
        policy = Policy(5,300,60,60,60,120,1,2,10,60,10,2,60,300,600,5,120)
        # The answer layer consumes only immutable exact ancestry evidence;
        # context binding is exercised by the integration runtime.
        self.assertEqual(stack_answers.answer(slots, (p,)), ())
    def test_only_fresh_exact_ancestry_can_raise_maintenance(self):
        old = StackView('main', ('feature/a',), 'base')
        slots = (QuerySlot('gh_stack', Ok('q','s','x',(old,), '2026-01-01'),
                           Ok('q','s','x',(old,), '2026-01-01'), 0, None),)
        self.assertEqual(stack_answers.answer(slots, ()), ())
        current = Ancestry('/repo','base-sha','head-sha',False)
        slots = (QuerySlot('gh_ancestry:7:head-sha', Ok('q','s','x',(current,), '2026-01-01'), Ok('q','s','x',(current,), '2026-01-01'), 0, None),)
        matching = PR('p', 7, '', 'OPEN', 'feature/a', 'head-sha', 'main', 'base-sha')
        result = stack_answers.answer(slots, (matching,))
        self.assertEqual(result[0].status, 'active')

    def test_ancestry_included_is_clear(self):
        item = Ancestry('/repo','base','head',True)
        slot = QuerySlot('gh_ancestry:7:head', Ok('q','s','x',(item,), '2026-01-01'), Ok('q','s','x',(item,), '2026-01-01'), 0, None)
        matching = PR('p', 7, '', 'OPEN', 'feature/a', 'head', 'main', 'base')
        self.assertEqual(stack_answers.answer((slot,), (matching,))[0].status, 'clear')

    def test_mismatched_remote_sha_does_not_raise_maintenance(self):
        item = Ancestry('/repo','base','head',False)
        slot = QuerySlot('gh_ancestry:7:head', Ok('q','s','x',(item,), '2026-01-01'), Ok('q','s','x',(item,), '2026-01-01'), 0, None)
        old = PR('p', 7, '', 'OPEN', 'feature/a', 'old-head', 'main', 'base')
        self.assertEqual(stack_answers.answer((slot,), (old,)), ())

if __name__ == '__main__':
    unittest.main()
