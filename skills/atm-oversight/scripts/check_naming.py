#!/usr/bin/env python3
"""Audit plan names, or validate staged/pushed snapshots without changing Git."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

from plan_metadata import read_metadata

PHASE = r'[A-Z]+'
NUMBER = r'[1-9][0-9]*(?:\.[1-9][0-9]*)*'
SLUG = r'[a-z0-9]+(?:-[a-z0-9]+)*'
SPRINT_FILE = re.compile(rf'sprint-({PHASE})\.({NUMBER})-({SLUG})\.md')
PREFIXES = {'feature', 'fix', 'hotfix', 'docs', 'chore', 'test', 'refactor',
            'perf', 'ci', 'build', 'release', 'plan', 'integrate'}


def git(repo, *args, input_data=None, check=True):
    p = subprocess.run(['git', '-C', str(repo), *args], input=input_data,
                       capture_output=True, timeout=30)
    if check and p.returncode:
        raise ValueError(p.stderr.decode(errors='replace').strip() or 'Git query failed')
    return p


def problem(path, code, message):
    return {'path': str(path), 'code': code, 'message': message}


def check_branch(branch):
    if branch in {'main', 'master', 'develop'}:
        return []
    prefix, sep, tail = branch.partition('/')
    if not sep or prefix not in PREFIXES or not re.fullmatch(SLUG, tail):
        return [problem(branch, 'branch-name',
                        'use a documented prefix and one lowercase kebab-case name')]
    if prefix == 'integrate' and not re.fullmatch(r'phase-[a-z]+', tail):
        return [problem(branch, 'integration-name', 'expected integrate/phase-<lowercase-phase>')]
    if prefix == 'plan' and not re.fullmatch(rf'phase-[a-z]+-{SLUG}', tail):
        return [problem(branch, 'planning-name', 'expected plan/phase-<lowercase-phase>-<slug>')]
    return []


def is_plan(path):
    p = PurePosixPath(path)
    return (len(p.parts) >= 3 and p.parts[:2] == ('docs', 'plans')
            and p.suffix == '.md'
            and (p.name.startswith('sprint-') or
                 p.name.startswith('phase-') and p.name.endswith('-plan.md')))


def check_plan(path, text):
    errors = []
    def fail(code, message):
        errors.append(problem(path, code, message))
    try:
        meta = read_metadata(text)
    except ValueError as exc:
        return [problem(path, 'metadata', str(exc))]
    phase = meta.get('phase', '')
    if not re.fullmatch(PHASE, phase):
        fail('phase-id', 'phase must be uppercase letters, e.g. AZ')
        return errors
    folder = f'docs/plans/phase-{phase.lower()}'
    p = PurePosixPath(path)
    if str(p.parent) != folder:
        fail('plan-directory', f'expected {folder}/')
    if p.name.startswith('phase-'):
        expected = f'{folder}/phase-{phase.lower()}-plan.md'
        if str(p) != expected:
            fail('phase-filename', f'expected {expected}')
        if 'canonical_path' in meta and meta['canonical_path'] != expected:
            fail('canonical-path', f'expected canonical_path: {expected}')
        return errors
    match = SPRINT_FILE.fullmatch(p.name)
    if not match:
        fail('sprint-filename', 'expected sprint-AZ.3-lowercase-slug.md (no leading-zero numbers)')
        return errors
    file_phase, number, slug = match.groups()
    expected_id = f'{phase}.{number}'
    if file_phase != phase or meta.get('sprint') != expected_id:
        fail('sprint-id', f'filename and metadata must both identify {expected_id}')
    expected_branch = f'feature/{phase.lower()}{number.replace(".", "-")}-{slug}'
    if meta.get('branch') != expected_branch:
        fail('sprint-branch', f'expected branch: {expected_branch}')
    worktree = meta.get('worktree', '')
    normalized = worktree.replace('\\', '/')
    rooted = (normalized.startswith('/') or re.match(r'^[A-Za-z]:/', normalized)
              or re.fullmatch(r'\.\./[^/]+-worktrees/' + re.escape(expected_branch), normalized))
    if (not rooted or not normalized.endswith('/' + expected_branch)
            or '..' in PurePosixPath(normalized).parts[1:]
            or normalized.endswith('/') or not worktree):
        fail('worktree', f'worktree must end in /{expected_branch}; use an absolute path or ../<repo>-worktrees/{expected_branch}')
    return errors


def split_paths(raw):
    return {p.decode('utf-8') for p in raw.split(b'\0') if p}


def staged(repo):
    paths = split_paths(git(repo, 'diff', '--cached', '--name-only', '-z',
                            '--diff-filter=ACMR').stdout)
    return [(p, git(repo, 'show', ':' + p).stdout.decode('utf-8'))
            for p in sorted(paths) if is_plan(p)]


def at_ref(repo, sha, base):
    args = ['rev-list', sha]
    known = base and set(base) != {'0'} and git(repo, 'cat-file', '-e',
                    base + '^{commit}', check=False).returncode == 0
    args += ['^' + base] if known else ['--not', '--remotes']
    commits = git(repo, *args).stdout
    if not commits.strip():
        return []
    paths = split_paths(git(repo, 'diff-tree', '--stdin', '--root', '-r',
                            '--no-commit-id', '--name-only', '-z',
                            '--diff-filter=ACMR', input_data=commits).stdout)
    files = []
    for path in sorted(paths):
        if not is_plan(path):
            continue
        blob = git(repo, 'show', sha + ':' + path, check=False)
        if blob.returncode == 0:  # A plan may have been deleted later in the push.
            files.append((path, blob.stdout.decode('utf-8')))
    return files


def audit(repo):
    # Standalone extracted repos work too; no Git mutation or checkout needed.
    if not (repo / 'docs' / 'plans').is_dir():
        raise ValueError('docs/plans does not exist; cannot audit plan coverage')
    return [(p.relative_to(repo).as_posix(), p.read_text(encoding='utf-8'))
            for p in sorted((repo / 'docs' / 'plans').rglob('*.md'))
            if is_plan(p.relative_to(repo).as_posix())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--all', action='store_true', help='audit existing plan files')
    modes.add_argument('--staged', action='store_true', help='check index blobs, not working files')
    modes.add_argument('--pre-push', action='store_true', help='read Git ref updates from stdin')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    repo = args.repo.resolve()
    errors, checked = [], 0
    try:
        if args.pre_push:
            batches = []
            for line in sys.stdin:
                fields = line.split()
                if len(fields) != 4:
                    raise ValueError('expected four fields per pre-push ref update')
                local_ref, sha, remote_ref, base = fields
                if set(sha) == {'0'} or not remote_ref.startswith('refs/heads/'):
                    continue
                errors.extend(check_branch(remote_ref.removeprefix('refs/heads/')))
                batches.append(at_ref(repo, sha, base))
        elif args.staged:
            branch = git(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False)
            if branch.returncode == 0:
                errors.extend(check_branch(branch.stdout.decode().strip()))
            batches = [staged(repo)]
        else:
            batches = [audit(repo)]
        for batch in batches:
            for path, content in batch:
                checked += 1
                errors.extend(check_plan(path, content))
    except (ValueError, OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        errors.append(problem(repo, 'query-failed', str(exc)))
        code = 2
    else:
        code = 1 if errors else 0
    result = {'schema_version': 1, 'checked_plans': checked, 'issues': errors,
              'status': 'error' if code == 2 else 'fail' if code else 'ok'}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for error in errors:
            print(f'{error["path"]}: {error["code"]}: {error["message"]}')
        print(f'Naming {result["status"]}: {checked} plans, {len(errors)} issues')
    return code


if __name__ == '__main__':
    sys.exit(main())
