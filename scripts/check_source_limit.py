#!/usr/bin/env python3
"""Reject changed source blobs over 100 substantive lines in commits/pushes."""
import subprocess
import sys
import tokenize
from source_lines import count_source, is_source

LIMIT = 100


def git(*args):
    return subprocess.check_output(['git', *args])


def changed(base, tip):
    return git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z',
               '--diff-filter=ACMRT', base, tip).decode().split('\0')


def blobs(mode, remote, updates):
    if mode == 'commit':
        paths = git('diff', '--cached', '--name-only', '-z', '--diff-filter=ACMRT').decode().split('\0')
        return [('', path) for path in paths if is_source(path)]
    pairs = set()
    for update in updates.splitlines():
        _, local, _, old = update.split()
        if set(local) == {'0'}:
            continue
        revision = [local, '--not', '--remotes=' + remote] if set(old) == {'0'} else [old + '..' + local]
        for commit in git('rev-list', *revision).decode().splitlines():
            parents = git('rev-list', '--parents', '-n', '1', commit).decode().split()[1:]
            if parents:
                paths = set(path for parent in parents for path in changed(parent, commit))
            else:
                paths = git('ls-tree', '-r', '--name-only', '-z', commit).decode().split('\0')
            pairs.update((commit, path) for path in paths if is_source(path))
    return sorted(pairs)


def main():
    mode = sys.argv[1]
    failures = []
    try:
        rows = blobs(mode, sys.argv[2] if len(sys.argv) > 2 else '',
                     sys.stdin.read() if mode == 'push' else '')
        for revision, path in rows:
            data = git('show', revision + ':' + path)
            count = count_source(path, data)
            if count > LIMIT:
                failures.append(f'{path}: {count} source lines ({revision[:12] or "staged"})')
    except (ValueError, OSError, SyntaxError, tokenize.TokenError, subprocess.CalledProcessError) as exc:
        print(f'Source-size check failed: {exc}. Fix the input/check before retrying.', file=sys.stderr)
        return 1
    if failures:
        print('Blocked: source files must be at most 100 lines, excluding blanks/comments.', file=sys.stderr)
        print('\n'.join(failures), file=sys.stderr)
        print('Split the file into focused units and stage the result. Do not bypass the hook.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
