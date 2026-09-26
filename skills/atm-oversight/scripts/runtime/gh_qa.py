"""One PR's recent revision-addressed QA reports, without generic approval inference."""
from dataclasses import replace
from gh_common import gql, api_error, envelope
from command_query import failure
from query_types import Error, Problem
from query_guard import guarded
from report_parse import parse_report

QUERY = '''query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){
 pullRequest(number:$number){id headRefOid body comments(last:50){
 pageInfo{hasPreviousPage startCursor}nodes{id body}}}}}'''


def resemblant(text):
    return isinstance(text, str) and any(marker in text.lower() for marker in
        ('final quality report', 'final verdict:', 'qa pass:', 'reviewed revision:'))


@guarded('gh_qa', 'github')
def query(repo_slug, pr_number, reviewed_sha, *, scope='qa-fallback', timeout=30):
    owner, name = repo_slug.split('/')
    payload = gql('gh_qa', 'github', scope, QUERY,
                  {'owner': owner, 'name': name, 'number': int(pr_number)}, timeout=timeout)
    if isinstance(payload, Error):
        return payload
    problems = list(api_error(payload, 'gh_qa', 'github', scope))
    pr = ((payload.get('data') or {}).get('repository') or {}).get('pullRequest')
    if not isinstance(pr, dict):
        return failure('gh_qa', 'github', scope, 'invalid-response', 'Requested PR missing')
    comments = pr.get('comments') or {}
    candidates = [(pr.get('id', 'pr-body'), pr.get('body', ''))]
    candidates.extend((c['id'], c['body']) for c in comments.get('nodes', ()))
    reports = []
    for identity, text in candidates:
        if not resemblant(text):
            continue
        try:
            report = parse_report(text, identity)
            if report.revision and len(report.revision) >= 7 and reviewed_sha.startswith(report.revision):
                reports.append(replace(report, revision=reviewed_sha))
        except (TypeError, ValueError) as exc:
            problems.append(Problem('invalid-response', str(exc),
                repair=f'Inspect explicit QA comment {identity}; repair its revision/count metadata.'))
    if (comments.get('pageInfo') or {}).get('hasPreviousPage'):
        problems.append(Problem('pagination', 'Only the latest 50 comments were inspected.',
            repair='Use the identified ATM report or a targeted older-comment lookup if current QA is still missing.'))
    return envelope(reports, 'gh_qa', 'github', scope, problems)
