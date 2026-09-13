"""Read-only reconciliation of Hermes handoff receipts."""
import sqlite3
from datetime import datetime, timezone
from answer_types import Incident

def _ts(v):
    if not v: return None
    try: return datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()
    except (TypeError,ValueError): return None

def reconcile(incident, receipt, executions_db=None, sessions_db=None, now=0, followup_seconds=300, verify=None):
    """Return one updated Incident; only an explicit verified message receipt delivers."""
    if incident.delivery == 'delivered': return incident
    attempt=_ts(incident.last_attempt); aged=attempt is not None and now-attempt >= followup_seconds
    valid=bool(isinstance(receipt,dict) and receipt.get('message_id') and receipt.get('timestamp') == incident.last_attempt)
    if valid and (verify is None or verify(receipt.get('message_id'))):
        return Incident(incident.key,incident.condition,incident.active,'delivered',incident.first_seen,incident.last_attempt,receipt.get('receipt_id') or receipt['message_id'])
    if aged and incident.delivery == 'attempting':
        c=incident.condition
        c=type(c)(c.key,'handoff-overdue',c.subject,c.revision,'active',c.owner,'Hermes handoff has no verified session receipt; investigate delivery.',c.evidence)
        return Incident(incident.key,c,incident.active,'uncertain',incident.first_seen,incident.last_attempt,incident.receipt)
    return incident
