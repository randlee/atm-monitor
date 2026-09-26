"""Strict parser for revision-addressed report payloads."""
import json
import re
from work_types import Report

def parse_report(text, report_id='unknown'):
    try:
        raw=json.loads(text)
    except json.JSONDecodeError:
        raw=text
    outer = raw.get('message', raw) if isinstance(raw, dict) else {}
    review_id = outer.get('taskId', outer.get('task_id')) if isinstance(outer, dict) else None
    body=raw.get('message',raw) if isinstance(raw,dict) else raw
    if isinstance(body,dict) and isinstance(body.get('data'),dict): body=body['data']
    if isinstance(body,dict) and isinstance(body.get('body'),str): body=body['body']
    if isinstance(body,dict) and isinstance(body.get('text'),str): body=body['text']
    if isinstance(body,str):
        try:
            body=json.loads(body)
        except json.JSONDecodeError:
            revision=re.search(r'(?im)^\s*(?:commit|head|revision|sha):\s*`?([0-9a-f]{7,64})',body)
            verdict=re.search(r'(?im)^\s*(?:final )?verdict:\s*\**([A-Z]+)',body)
            report_round=re.search(r'(?im)^\s*QA Pass:\s*(\S+)',body)
            if not revision:
                raise ValueError('report prose has no reviewed revision')
            findings=[]
            aggregate=[]
            for severity,count in re.findall(r'(?im)["`*]?(blocking|important|minor)["`*]?\s*:\s*\**(\d+)',body):
                aggregate.append((severity.lower(),int(count)))
            aggregate=list(dict(aggregate).items())
            return Report(str(report_id),revision.group(1),report_round.group(1) if report_round else None,verdict.group(1).lower() if verdict else None,tuple(findings),tuple(aggregate),review_id)
    if not isinstance(body,dict): raise ValueError('report body is not an object')
    revision=body.get('revision',body.get('head_sha',body.get('sha')))
    if not revision: raise ValueError('reviewed revision missing')
    findings=[]
    for item in body.get('findings',[]):
        if not isinstance(item,dict) or not item.get('id'): raise ValueError('finding identity missing')
        findings.append((str(item['id']),str(item.get('severity','unknown')),str(item.get('status','open'))))
    return Report(str(report_id),str(revision),body.get('round'),body.get('verdict'),tuple(findings),review_id=review_id)
