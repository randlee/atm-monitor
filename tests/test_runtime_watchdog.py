import sys, tempfile, sqlite3, unittest, subprocess
from dataclasses import dataclass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'skills/atm-oversight/scripts/runtime'))
from watchdog import inspect
from handoff_receipts import reconcile
from answer_types import Condition, Incident, Envelope, DomainState
from runtime_registry import REGISTRY
from state_disk import save, load
from record_action import record
from runtime_policy import Policy
P=Policy(30,300,60,60,60,60,5,2,10,100,50,2,30,30,60,2000,120)
class T(unittest.TestCase):
 def test_watchdog_dedupes_and_future_is_not_missed(self):
  self.assertEqual(inspect('1970-01-01T00:04:50+00:00',300,P)[0].status,'clear')
  x=inspect('1970-01-01T00:00:00+00:00',1000,P); self.assertEqual(len(x),1)
 def test_overdue_and_receipt_requires_session(self):
  c=Condition('k','ci-failure','1','h','active','a','x'); i=Incident('k',c,True,'attempting','', '1970-01-01T00:00:00+00:00')
  self.assertIn('delivery-overdue',[x.kind for x in inspect('1970-01-01T00:00:10+00:00',100,P,(i,))])
  with tempfile.TemporaryDirectory() as d:
   e=Path(d)/'e.db'; s=Path(d)/'s.db';
   ce=sqlite3.connect(e); ce.execute('create table executions(id text,job_id text,status text,claimed_at text)'); ce.execute("insert into executions values('1','j','completed','x')"); ce.commit(); ce.close()
   cs=sqlite3.connect(s); cs.execute('create table sessions(session_key text)'); cs.commit(); cs.close()
   self.assertEqual(reconcile(i,{'job_id':'j','timestamp':i.last_attempt},e,s,100).delivery,'attempting')
   self.assertEqual(reconcile(i,{'message_id':'m','timestamp':i.last_attempt},e,s,100).delivery,'delivered')
   @dataclass(frozen=True)
   class E: incidents: tuple
   env=E((i,)); self.assertEqual(record(env,'k','m','a').incidents[0].delivery,'delivered')
   full=Envelope(1,1,DomainState('x',(),(),''),(),(i,),(), 'now')
   with tempfile.TemporaryDirectory() as td:
    save(td,full,Envelope,REGISTRY)
    subprocess.run([sys.executable,str(Path(__file__).parents[1]/'skills/atm-oversight/scripts/runtime/record_action.py'),'--state-dir',td,'--incident','k','--message-id','m2','--route','a','--status','acknowledged'],check=True)
    got,_=load(td,Envelope,REGISTRY); self.assertEqual(got.incidents[0].delivery,'acknowledged'); self.assertEqual(got.incidents[0].last_attempt,i.last_attempt); self.assertEqual(got.state,full.state)
if __name__=='__main__': unittest.main()
