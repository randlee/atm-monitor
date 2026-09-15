#!/usr/bin/env python3
"""Install a complete, verified skill bundle; preserve and detect local changes."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

SOURCE = Path(__file__).resolve().parents[1] / 'skills' / 'atm-oversight'
sys.path.insert(0, str(SOURCE / 'scripts' / 'cron'))
from state_store import locked

RECEIPT = '.deployment.json'


def inventory(root):
    rows = {}
    for path in sorted(Path(root).rglob('*')):
        relative = path.relative_to(root)
        if '__pycache__' in relative.parts or path.suffix == '.pyc' or str(relative) == RECEIPT:
            continue
        if path.is_symlink():
            raise ValueError('bundle contains a symlink: ' + str(relative))
        if path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def verify(target):
    receipt = json.loads((target / RECEIPT).read_text(encoding='utf-8'))
    files = inventory(target)
    if receipt.get('schema_version') != 1 or files != receipt.get('files') or digest(files) != receipt.get('bundle_sha256'):
        raise ValueError('deployed files differ from receipt; preserve and review local edits before upgrading')
    return receipt


def install(source, target, archive_dir):
    if Path(target).is_symlink() or Path(source).is_symlink():
        raise ValueError('source and target must be real directories, not symlinks')
    source, target, archive_dir = (Path(p).resolve() for p in (source, target, archive_dir))
    if archive_dir.is_relative_to(target.parent):
        raise ValueError('archive must be outside the skill discovery directory')
    for left, right in ((source, target), (target, source), (archive_dir, target), (archive_dir, source)):
        if left.is_relative_to(right):
            raise ValueError('source, destination and archive paths must not overlap')
    if not (source / 'SKILL.md').is_file():
        raise ValueError('source does not contain SKILL.md')
    expected = inventory(source)
    bundle_sha = digest(expected)
    with locked(archive_dir):
        if target.exists():
            current = verify(target)
            if current['bundle_sha256'] == bundle_sha:
                return {'status': 'unchanged', 'target': str(target), 'bundle_sha256': bundle_sha}
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.atm-oversight-stage-', dir=archive_dir))
        backup = None
        try:
            for relative in expected:
                destination = stage / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / relative, destination)
            if inventory(stage) != expected or inventory(source) != expected:
                raise ValueError('source changed while staging; retry from a stable release')
            receipt = {'schema_version': 1, 'skill': target.name, 'bundle_sha256': bundle_sha,
                       'installed_at': datetime.now(timezone.utc).isoformat(), 'files': expected}
            (stage / RECEIPT).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
            verify(stage)
            if target.exists():
                verify(target)
                backup = archive_dir / ('atm-oversight-' + uuid.uuid4().hex)
                # Renames require one filesystem; fail without replacing target otherwise.
                os.rename(target, backup)
            try:
                os.rename(stage, target)
            except OSError:
                if backup is not None:
                    os.rename(backup, target)
                raise
            return {'status': 'installed', 'target': str(target), 'bundle_sha256': bundle_sha,
                    'backup': str(backup) if backup else None, 'files': len(expected)}
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--archive-dir', type=Path)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        if args.verify:
            receipt = verify(args.target)
            result = {'status': 'verified', 'bundle_sha256': receipt['bundle_sha256'], 'files': len(receipt['files'])}
        elif not args.archive_dir:
            raise ValueError('--archive-dir is required for installation')
        else:
            result = install(args.source, args.target, args.archive_dir)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
