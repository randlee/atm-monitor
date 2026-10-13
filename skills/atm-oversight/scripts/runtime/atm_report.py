"""Peek and parse one identified ATM QA report."""
import json
from query_types import Ok, Partial, Error, Problem
from command_query import execute, now_iso, failure
from work_types import Report
from report_parse import parse_report

from query_guard import guarded


@guarded('atm_report','atm')
def query(team, mailbox_agent, message_id, timeout=30):
    scope=f'{team}:message:{message_id}'; args=('atm','peek','--team',team,'--as',mailbox_agent,'--all','--message-id',message_id,'--json')
    result=execute('atm_report','atm',scope,args,timeout=timeout)
    if isinstance(result,Error): return result
    try:
        payload = json.loads(result.stdout)
        if isinstance(payload, dict) and payload.get('count') == 0 and 'message' not in payload:
            return failure('atm_report','atm',scope,'report-not-found',
                'Identified report was not found in any mailbox bucket.',args,
                repair='Verify the report ID, recipient mailbox and team on the owner store.')
        report=parse_report(result.stdout,message_id)
    except (ValueError,json.JSONDecodeError) as exc: return failure('atm_report','atm',scope,'invalid-response',str(exc),args,repair='Have an agent inspect the identified report payload; do not invent findings.')
    if isinstance(result.stdout, str) and 'Machine Status' not in result.stdout and '"verdict"' not in result.stdout:
        problem=Problem('unstructured-report','Parsed prose report; machine findings and round metadata may be incomplete',args,None,'',False,None,'Have an agent verify the report and recover structured metadata.','amon@atm-monitor')
        return Partial('atm_report','atm',scope,(report,),now_iso(),(problem,))
    return Ok('atm_report','atm',scope,(report,),now_iso())
run=query
