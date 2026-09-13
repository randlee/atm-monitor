"""Render immutable answers as a compact Markdown phase table."""
from pathlib import Path
import os
import tempfile


def cell(value):
    if hasattr(value, 'support'):
        suffix = ' [stale]' if value.freshness == 'stale' else ''
        suffix += ' [conflict]' if value.support == 'conflict' else ''
        value = value.value + suffix
    return str(value).replace('|', '\\|').replace('\n', ' ')


def render(envelope):
    state = envelope.state
    lines = [f'# {state.repo} oversight', '', f'As of {envelope.observed_at}; inventory: {state.inventory}.', '',
        '| Phase / sprint | Owner / task | DEV | QA / rounds | Open B/C/I | PR / CI / merge | Blocker / next action |',
        '|---|---|---|---|---|---|---|']
    phase = None
    for row in state.rows:
        if phase != row.phase:
            phase = row.phase
            lines.append(f'| **{cell(phase)}** | | | | | | |')
        lines.append('| ' + ' | '.join((f'↳ {cell(row.sprint)}: {cell(row.branch)} ← {cell(row.parent)}',
            cell(row.owner) + ' / ' + cell(row.tasks), cell(row.development),
            cell(row.qa) + ' / ' + cell(row.rounds), cell(row.findings),
            cell(row.prs) + ' / ' + cell(row.ci), cell(row.next_action))) + ' |')
    if state.branches:
        lines.extend(['', '| Stack / branch | Parent | PR | Status | Current ancestry |', '|---|---|---|---|---|'])
        group = None
        for branch in state.branches:
            if branch.stack != group:
                group = branch.stack
                lines.append(f'| **{cell(group)}** | | | | |')
            lines.append('| ↳ ' + ' | '.join(cell(v) for v in (branch.branch, branch.parent,
                         branch.pr, branch.status, branch.maintenance)) + ' |')
    lines.extend(['', 'Evidence and coverage:', ''])
    for slot in envelope.slots:
        status = slot.latest.status
        line = f'- {slot.key}: {status}; observed {slot.latest.observed_at}'
        if status == 'error':
            line += f'; {slot.latest.problem.kind}: {slot.latest.problem.repair}'
        if status == 'partial':
            line += '; ' + '; '.join(p.kind + ': ' + p.repair for p in slot.latest.problems)
        lines.append(line)
    for row in state.rows:
        refs = sorted({e for field in (row.tasks, row.qa, row.prs) for e in field.evidence})
        if refs:
            lines.append(f'- {row.sprint}: ' + ', '.join(refs))
    return '\n'.join(lines) + '\n'


def write_report(path, envelope):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.report-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(render(envelope))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
