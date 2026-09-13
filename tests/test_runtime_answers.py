import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'skills/atm-oversight/scripts/runtime'))
from ci_answers import answer as ci
from idle_answers import answer as idle
from pr_types import PR, Check
from work_types import Task, Agent
from answer_types import Timer
from runtime_policy import Policy

P=Policy(30,300,60,60,60,60,5,2,10,100,50,2,30,30,60,5,120)
PR0=lambda **k: PR('n',1,'','OPEN','main','h','main','b',False,'MERGEABLE','CLEAN',False,**k)

class AnswerTests(unittest.TestCase):
 def test_ci_closed_rollup_mismatch_and_incomplete_unknown(self):
  closed=PR('n',1,'','MERGED','main','h','main','b',False,'CONFLICTING','DIRTY',False,rollup_sha='old')
  c=Check(1,'h','build','COMPLETED','FAILURE')
  out,_=ci((closed,),(c,),P,100,complete=False)
  self.assertTrue(all(x.status=='clear' for x in out))
  openpr=PR0(rollup_sha='old'); out,_=ci((openpr,),(),P,100,complete=False,expected=(('main',('build',)),))
  self.assertEqual(out[1].status,'unknown')

 def test_attempt_key_and_pending_anchor_and_stable_timer(self):
  p=PR0(rollup_sha='h'); c=Check(1,'h','build','QUEUED',queued_at='1970-01-01T00:00:00+00:00',attempt='2')
  out,t=ci((p,),(c,),P,100); self.assertIn(':2:stuck',out[1].key)
  out2,t2=ci((p,),(c,),P,110,timers=t); self.assertEqual(t,t2)

 def test_idle_unknown_background_and_stale_does_not_clear(self):
  task=Task('t',status='active',assignee='a'); agent=Agent('a','idle','1970-01-01T00:00:00+00:00','t',None)
  out,t=idle((task,),(agent,),P,100); self.assertEqual(out[0].status,'clear')
  agent2=Agent('a','idle','1970-01-01T00:01:00+00:00','t','none')
  out,t=idle((task,),(agent2,),P,1000,timers=(Timer('idle:t','1970-01-01T00:00:00+00:00'),))
  self.assertEqual(out[0].status,'unknown'); self.assertEqual(t,())

if __name__=='__main__': unittest.main()
