import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'))
import gh_stack
from command_query import CommandSuccess, failure


class StackContextTests(unittest.TestCase):
    def missing(self):
        return failure('gh_stack', 'github', 's1', 'command-failed', 'unavailable',
                       exit_code=2, diagnostics='branch is not part of a stack')

    def test_alternate_member_recovers_without_mutating_stack(self):
        valid = CommandSuccess(json.dumps({'trunk': 'main', 'branches': [{'name': 'feature/a'}]}), '', 0)
        with patch.object(gh_stack, 'execute', side_effect=[self.missing(), valid]) as run:
            result = gh_stack.query('/first', scope='s1', alternatives=('/second', '/third'))
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.data[0].branches, ('feature/a',))
        self.assertEqual([c.kwargs['cwd'] for c in run.call_args_list], ['/first', '/second'])
        self.assertTrue(all(c.args[3] == ('gh', 'stack', 'view', '--json') for c in run.call_args_list))

    def test_two_missing_contexts_return_bounded_actionable_error(self):
        with patch.object(gh_stack, 'execute', side_effect=[self.missing(), self.missing()]) as run:
            result = gh_stack.query('/first', scope='s1', alternatives=('/second', '/third'))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(result.scope, 's1')
        self.assertEqual(result.problem.kind, 'local-stack-context')
        self.assertTrue(result.problem.retryable)
        self.assertIn('cwd=/first', result.problem.diagnostics)
        self.assertIn('cwd=/second', result.problem.diagnostics)

    def test_auth_failure_does_not_fan_out_to_other_worktrees(self):
        error = failure('gh_stack', 'github', 's1', 'access', 'denied', exit_code=4)
        with patch.object(gh_stack, 'execute', return_value=error) as run:
            result = gh_stack.query('/first', alternatives=('/second',))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(result.problem.kind, 'access')
