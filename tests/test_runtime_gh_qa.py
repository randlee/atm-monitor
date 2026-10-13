import json
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, 'skills/atm-oversight/scripts/runtime')
from gh_qa import query

class GithubQATests(unittest.TestCase):
    def run_body(self, body, sha='abcdef1234567', previous=False):
        payload = {'data': {'repository': {'pullRequest': {'id':'pr1','headRefOid':sha,'body':body,
                    'comments': {'pageInfo': {'hasPreviousPage': previous}, 'nodes': []}}}}}
        with patch('gh_qa.gql', return_value=payload):
            return query('o/r', 3, sha)

    def test_accepts_exact_revision_addressed_prose(self):
        result = self.run_body('Final Quality Report\ncommit: `abcdef1234567`\nFinal verdict: PASS')
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.data[0].revision, 'abcdef1234567')

    def test_old_revision_is_empty(self):
        result = self.run_body('Final Quality Report\ncommit: `deadbeef1234567`\nFinal verdict: FAIL')
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.data, ())

    def test_generic_approval_is_not_qa(self):
        result = self.run_body('Approved by reviewer; looks good.')
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.data, ())

    def test_malformed_explicit_report_is_partial(self):
        result = self.run_body('Final Quality Report\nFinal verdict: FAIL')
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.problems[0].kind, 'invalid-response')

    def test_explicit_comment_report_and_truncated_history(self):
        body = 'Approved.'
        comment = {'id':'c1','body':'Final Quality Report\ncommit: `abcdef1234567`\nFinal verdict: PASS'}
        payload = {'data': {'repository': {'pullRequest': {'id':'pr1','headRefOid':'abcdef1234567','body':body,
                    'comments': {'pageInfo': {'hasPreviousPage': True}, 'nodes': [comment]}}}}}
        with patch('gh_qa.gql', return_value=payload):
            result = query('o/r', 3, 'abcdef1234567')
        self.assertEqual(result.status, 'partial')
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.problems[0].kind, 'pagination')

if __name__ == '__main__':
    unittest.main()
