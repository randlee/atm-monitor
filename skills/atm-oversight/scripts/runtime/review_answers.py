"""Current-revision QA plus deduplicated historical review rounds."""
from answer_types import Fact


def round_order(report):
    value = str(report.round or '')
    return (int(value) if value.isdigit() else -1, report.report_id)


def reviews(reports, heads):
    unique = {r.report_id: r for r in reports}
    references = tuple(sorted(unique))
    rounds = {(r.review_id, r.round) for r in unique.values() if r.review_id and r.round}
    round_fact = Fact(str(len(rounds)) if rounds else 'unknown',
                      'authoritative' if rounds else 'unknown', evidence=references)
    current = {}
    for report in sorted(unique.values(), key=round_order):
        matches = [head for head in heads if report.revision and len(report.revision) >= 7 and head.startswith(report.revision)]
        if len(matches) == 1:
            current[matches[0]] = report
    historical = False
    if not current and unique:
        latest = max(unique.values(), key=round_order)
        current = {latest.revision: latest}
        historical = True
    if not current:
        return Fact('unknown', 'unknown'), round_fact, Fact('B:? C:? I:?', 'unknown')
    chosen = tuple(current.values())
    evidence = tuple(sorted(r.report_id for r in chosen))
    verdicts = sorted({r.verdict for r in chosen if r.verdict})
    complete_heads = set(current) >= set(heads)
    verdict = ', '.join(verdicts) or 'unknown'
    if not historical and not complete_heads:
        verdict += '; other heads unknown'
    qa = Fact(verdict, 'authoritative' if verdicts else 'unknown', 'stale' if historical else 'fresh', evidence)
    findings = {identity: (severity, status) for r in chosen for identity, severity, status in r.findings}
    values = {}
    names = {'B': 'blocking', 'C': 'critical', 'I': 'important'}
    for code, name in names.items():
        totals = [dict(r.aggregate).get(name, dict(r.aggregate).get(code)) for r in chosen]
        if all(v is not None for v in totals):
            values[code] = str(sum(totals))
        elif findings and all(r.findings for r in chosen):
            values[code] = str(sum(s in {code, name} and status == 'open' for s, status in findings.values()))
        else:
            values[code] = '?'
    counts = Fact(' '.join(f'{c}:{values[c]}' for c in names),
                  'partial' if '?' in values.values() else 'authoritative',
                  'stale' if historical else 'fresh', evidence)
    return qa, round_fact, counts
