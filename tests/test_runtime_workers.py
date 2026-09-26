import unittest, time
from unittest.mock import patch
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'skills/atm-oversight/scripts/runtime'))
from repo_workers import results

class P: repo_timeout_seconds=5
def fixture(repo, root, policy, now, agents, shadow):
 if repo['slug']=='r28': time.sleep(60)
 if repo['slug']=='r29': raise RuntimeError('boom')
 return {'slug':repo['slug']}
class Workers(unittest.TestCase):
 def test_all_repos_return_and_hung_is_bounded(self):
  repos=tuple({'slug':f'r{i}'} for i in range(30)); start=time.monotonic()
  got=list(results(repos,'/tmp',P(),0,(),worker_limit=4,timeout=5,target=fixture))
  self.assertLess(time.monotonic()-start,30); self.assertEqual(len(got),30)
  good=[p for r,p in got if r['slug'] not in {'r28','r29'}]
  self.assertEqual(sum(p['ok'] for p in good),28)
  self.assertTrue(any('timeout' in p.get('error','') for r,p in got if r['slug']=='r28'))
  self.assertTrue(any('boom' in p.get('error','') for r,p in got if r['slug']=='r29'))
if __name__=='__main__': unittest.main()
