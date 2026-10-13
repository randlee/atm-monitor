import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, 'skills/atm-oversight/scripts/runtime')
from command_query import CommandSuccess
from query_types import Error, Problem
from gh_prs import query as prs
from gh_checks import query as checks
from gh_stack import ancestry
from gh_requirements import query as requirements

class GithubQueryTests(unittest.TestCase):
    def test_pr_search_returns_partial_cursor(self):
        payload = {'data': {'search': {'pageInfo': {'hasNextPage': True, 'endCursor': 'c1'}, 'nodes': [{
            'id': 'P1', 'number': 7, 'updatedAt': '2026-01-01', 'state': 'OPEN',
            'headRefName': 'topic', 'headRefOid': 'h', 'baseRefName': 'main', 'baseRefOid': 'b'}]}}}
        with patch('gh_prs.gql', return_value=payload) as call:
            result = prs('o/r', '2026-01-01', '2026-01-02')
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.cursor, 'c1')
        self.assertEqual(result.data[0].number, 7)
        self.assertEqual(call.call_args.args[4]['search'], 'repo:o/r is:pr updated:2026-01-01..2026-01-02')

    def test_checks_preserve_nested_pagination_and_attempt(self):
        node = {'id':'P1','number':7,'state':'OPEN','headRefName':'x','headRefOid':'h',
                'baseRefName':'main','baseRefOid':'b','statusCheckRollup':{'state':'SUCCESS','commit':{'oid':'h'},
                'contexts':{'pageInfo':{'hasNextPage':True,'endCursor':'c1'},'nodes':[{'id':'run-2','name':'CI','status':'COMPLETED','conclusion':'FAILURE'}]}}}
        with patch('gh_checks.gql', return_value={'data': {'nodes': [node]}}):
            result = checks(['P1'])
        self.assertEqual(result.status, 'partial')
        check = next(x for x in result.data if getattr(x, 'name', None) == 'CI')
        self.assertEqual(check.attempt, 'run-2')

    def test_ancestry_exit_one_is_domain_fact(self):
        with patch('gh_stack.execute', return_value=CommandSuccess('', '', 1)):
            result = ancestry('/repo', 'base', 'head')
        self.assertEqual(result.status, 'ok')
        self.assertFalse(result.data[0].included)

    def test_missing_node_and_provider_errors_are_not_success(self):
        with patch('gh_checks.gql', return_value={'errors': [{'message': 'bad schema'}], 'data': {}}):
            self.assertEqual(checks(['P1']).status, 'error')
        with patch('gh_checks.gql', return_value={'data': {'nodes': [None]}}):
            self.assertEqual(checks(['P1']).status, 'partial')

    def test_rollup_head_mismatch_is_partial(self):
        node = {'id':'P1','number':7,'state':'OPEN','headRefName':'x','headRefOid':'new',
                'baseRefName':'main','baseRefOid':'b','statusCheckRollup':{'commit':{'oid':'old'}}}
        with patch('gh_checks.gql', return_value={'data': {'nodes': [node]}}):
            result = checks(['P1'])
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.problems[0].kind, 'revision-mismatch')

    def test_rules_fallback_retains_primary_failure(self):
        primary = Error('gh_requirements', 'github', 'requirements', '', Problem('access', 'denied'))
        ok = CommandSuccess('{"rules":[{"name":"CI"}]}', '', 0)
        with patch('gh_requirements.execute', side_effect=[primary, ok]):
            result = requirements('o/r', 'feature/a')
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.data[0].name, 'CI')

    def test_unprotected_branch_with_effective_rules_is_ok(self):
        primary = Error('gh_requirements', 'github', 'requirements', '',
                        Problem('command-failed', 'Branch not protected', exit_code=1,
                                diagnostics='Branch not protected (HTTP 404)'))
        ok = CommandSuccess('[{"type":"required_status_checks","parameters":{"required_status_checks":[{"context":"CI"}]}}]', '', 0)
        with patch('gh_requirements.execute', side_effect=[primary, ok]):
            result = requirements('o/r', 'main')
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.data[0].name, 'CI')

if __name__ == '__main__':
    unittest.main()
