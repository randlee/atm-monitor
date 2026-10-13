import sys
import unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'skills/atm-oversight/scripts/runtime'))
from test_runtime_closed_stack import OPEN, P, slot
from current_prs import scoped
import stack_queries
import detail_queries


class StackScopeTests(unittest.TestCase):
    def test_identified_stack_keeps_members_outside_discovery_prefix(self):
        docs = replace(OPEN,node_id='docs',number=2,head='docs/manual',stack_position=2)
        unrelated = replace(docs,node_id='other',number=3,stack_id=None)
        slots = (slot('gh_checks',(OPEN,docs,unrelated),10),
                 slot('gh_git_context',(('worktree /repo\nbranch refs/heads/feature/a',),),10))
        repo = {'branch_prefixes':['feature/'],'slug':'o/r','path':'/repo','team':'t','actor':'a'}
        self.assertEqual({p.number for p in scoped(repo,slots)},{1,2})
        keys = {key for key, _ in stack_queries.calls(repo,slots,P,100)}
        self.assertIn('gh_ancestry:2',keys)
        self.assertNotIn('gh_ancestry:3',keys)
        self.assertIn('gh_checks',{key for key,_ in detail_queries.calls(repo,slots,P,100)})
