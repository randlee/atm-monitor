import json
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, 'skills/atm-oversight/scripts/runtime')
from gh_checks import query

def pr(node_id, number, head='h', contexts=None, more=False):
    return {'id':node_id,'number':number,'state':'OPEN','headRefName':'x','headRefOid':head,
            'baseRefName':'main','baseRefOid':'b','statusCheckRollup':{'commit':{'oid':head},
            'contexts':{'nodes':contexts or [],'pageInfo':{'hasNextPage':more,'endCursor':'c1' if more else None}}}}

class GithubPagingTests(unittest.TestCase):
    def test_budget_processes_all_ids_without_truncating_batch(self):
        payload = {'data': {'nodes': [pr(f'p{i}', i) for i in range(1, 5)]}}
        with patch('gh_checks.gql', return_value=payload) as call:
            result = query([f'p{i}' for i in range(1, 5)], budget=1)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(len(result.data), 4)
        self.assertEqual(call.call_args.args[4]['ids'], ['p1','p2','p3','p4'])

    def test_nested_cursor_resume_merges_pages(self):
        first = {'data': {'nodes': [pr('p1', 1, contexts=[{'id':'a','name':'CI','status':'QUEUED'}], more=True)]}}
        second = {'data': {'nodes': [pr('p1', 1, contexts=[{'id':'b','name':'CI','status':'COMPLETED','conclusion':'SUCCESS'}])]}}
        with patch('gh_checks.gql', side_effect=[first, second]) as call:
            partial = query(['p1'], budget=1)
            done = query(['p1'], budget=1, continuation=partial.cursor)
        self.assertEqual(partial.status, 'partial')
        self.assertEqual(len(json.loads(partial.cursor)), 1)
        self.assertEqual(done.status, 'ok')
        self.assertEqual(len(done.data), 2)
        self.assertEqual(call.call_count, 2)

    def test_changed_head_drops_page_records_and_restarts(self):
        first = {'data': {'nodes': [pr('p1', 1, head='new', contexts=[], more=False)]}}
        continuation = json.dumps([{'ids':['p1'],'connection':'contexts','after':'c1','head':'old'}])
        with patch('gh_checks.gql', return_value=first):
            result = query(['p1'], budget=1, continuation=continuation)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.data, ())
        self.assertEqual(json.loads(result.cursor)[0]['connection'], None)

if __name__ == '__main__':
    unittest.main()
