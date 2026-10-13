import json, sqlite3, tempfile, unittest
from dataclasses import dataclass
from pathlib import Path
import sys
ROOT=Path(__file__).parents[1]
sys.path[:0]=[str(ROOT/'skills/atm-oversight/scripts/runtime'),str(ROOT/'skills/atm-oversight/scripts/cron')]
from state_codec import CodecError, encode, decode
from state_disk import save, load, StateError
from query_runner import run
from query_types import Ok, Error
from scheduler_runs import read
from answer_types import Condition, Incident
from incident_decisions import decide, reserve

@dataclass(frozen=True)
class Box: value: tuple[int,...]
REG={Box:'Box'}

class RecoveryTests(unittest.TestCase):
 def test_quiet_domain_and_persist_before_wake_contract(self):
  c=Condition('k','ci-failure','1','h','active','owner','detail')
  first=decide((c,),(),100); second=decide((c,),first,100)
  self.assertEqual(first,second)
  persisted,events=reserve(first,100)
  self.assertEqual(events,(c,)); self.assertEqual(persisted[0].delivery,'attempting')
  self.assertEqual(reserve(persisted,101)[1],())

 def test_clear_requires_prior_incident_and_recovery_receipt_stays_history(self):
  c=Condition('k','ci-failure','1','h','active','owner','detail'); prior=decide((c,),(),100)
  clear=Condition('k','ci-failure','1','h','clear','owner','detail')
  recovered=decide((clear,),prior,101)[0]
  self.assertFalse(recovered.active); self.assertEqual(recovered.condition.status,'clear')
 def test_codec_nested_mutable_and_shape(self):
  with self.assertRaises(CodecError): encode(Box([1]),REG)
  raw=encode(Box((1,)),REG); raw['extra']=2
  with self.assertRaises(CodecError): decode(raw,Box,REG)
  with self.assertRaises(CodecError): decode({'__type__':'Box','value':['x']},Box,REG)
  with self.assertRaises(CodecError): decode({'__type__':'Box','value':None},Box,REG)
  with self.assertRaises(CodecError): decode([],object,REG)

 def test_corrupt_fallback_reports_diagnostic(self):
  with tempfile.TemporaryDirectory() as d:
   save(d,Box((1,)),Box,REG); save(d,Box((2,)),Box,REG); Path(d,'state.json').write_text('{bad')
   state,path=load(d,Box,REG)
   self.assertEqual(state,Box((1,)))
   Path(d,'state.last-valid.json').write_text('{"schema_version":2}')
   with self.assertRaises(StateError): load(d,Box,REG)

 def test_atomic_failure_keeps_backup(self):
  with tempfile.TemporaryDirectory() as d:
   save(d,Box((1,)),Box,REG)
   import state_disk
   old=state_disk._write; state_disk._write=lambda *a: (_ for _ in ()).throw(OSError('full'))
   try:
    with self.assertRaises(OSError): save(d,Box((2,)),Box,REG)
   finally: state_disk._write=old
   self.assertEqual(load(d,Box,REG)[0],Box((1,)))

 def test_corrupt_primary_never_replaces_valid_backup(self):
  with tempfile.TemporaryDirectory() as d:
   save(d,Box((1,)),Box,REG); save(d,Box((2,)),Box,REG)
   Path(d,'state.json').write_text('{corrupt')
   save(d,Box((3,)),Box,REG)
   self.assertEqual(load(d,Box,REG)[0],Box((3,)))
   self.assertEqual(decode(json.loads(Path(d,'state.last-valid.json').read_text())['state'],Box,REG),Box((1,)))

 def test_invalid_union_retries_without_sleep(self):
  calls=[]
  result=run('q','s','x',lambda: calls.append(1) or object(),retries=2)
  self.assertIsInstance(result,Error); self.assertEqual(len(calls),3); self.assertTrue(result.problem.retry_after)
  self.assertIsInstance(run('q','s','x',lambda: Ok('q','s','x',(),'')),Ok)

 def test_scheduler_missing_and_unknown_schema_are_errors(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertIsInstance(read(Path(d)/'missing.db','job'),Error)
   p=Path(d)/'x.db'; c=sqlite3.connect(p); c.execute('create table nope (x int)'); c.commit(); c.close()
   self.assertIsInstance(read(p,'job'),Error)

if __name__=='__main__': unittest.main()
