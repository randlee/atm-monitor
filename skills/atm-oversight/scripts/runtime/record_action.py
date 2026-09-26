"""Operator command to attach a verified ATM delivery receipt."""
import argparse, sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from answer_types import Envelope
from runtime_registry import REGISTRY
from state_disk import load, save, locked

def record(envelope, incident_key, message_id, route, status='delivered'):
    if not message_id or not route or status not in {'delivered','acknowledged'}: raise ValueError('invalid receipt')
    found=next((i for i in envelope.incidents if i.key==incident_key),None)
    if found is None: raise ValueError('unknown incident')
    if route not in {found.condition.owner,'team-lead','amon@atm-monitor'}: raise ValueError('route is not owner/delegate')
    item=replace(found,delivery=status,receipt=f'{route}:{message_id}')
    return replace(envelope,incidents=tuple(item if i.key==incident_key else i for i in envelope.incidents))

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--state-dir',required=True); ap.add_argument('--incident',required=True); ap.add_argument('--message-id',required=True); ap.add_argument('--route',required=True); ap.add_argument('--status',default='delivered'); a=ap.parse_args(argv)
    d=Path(a.state_dir)
    with locked(d/'runner'):
        env,_=load(d,Envelope,REGISTRY)
        if env is None: raise SystemExit('state does not exist')
        save(d,record(env,a.incident,a.message_id,a.route,a.status),Envelope,REGISTRY)
    return 0

if __name__=='__main__': raise SystemExit(main())
