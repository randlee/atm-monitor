"""Portable local JSON snapshots with OS-released locking and atomic commits."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile


class BusyError(RuntimeError):
    pass


@contextmanager
def locked(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / '.lock'
    with path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise BusyError('another tick holds the state lock') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)


def snapshots(directory):
    return sorted((Path(directory) / 'snapshots').glob('[0-9]' * 12 + '.json'))


def read_latest(directory):
    errors = []
    for path in reversed(snapshots(directory)):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('sources'), dict):
                raise ValueError('unsupported snapshot shape/version')
            return data, errors
        except (OSError, ValueError) as exc:
            errors.append({'file': path.name, 'error': str(exc)})
    return None, errors


def save(directory, data, retain=1000):
    """Caller holds locked(directory). A complete snapshot is the commit point."""
    if not isinstance(retain, int) or retain < 2:
        raise ValueError('retain must be at least two snapshots')
    folder = Path(directory) / 'snapshots'
    folder.mkdir(parents=True, exist_ok=True)
    existing = snapshots(directory)
    sequence = int(existing[-1].stem) + 1 if existing else 1
    data = dict(data, sequence=sequence)
    fd, name = tempfile.mkstemp(prefix='.writing-', dir=folder)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as out:
            json.dump(data, out, ensure_ascii=True, separators=(',', ':'))
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        destination = folder / f'{sequence:012d}.json'
        os.replace(name, destination)
        if os.name != 'nt' and hasattr(os, 'O_DIRECTORY'):
            directory_fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        for old in snapshots(directory)[:-retain]:
            old.unlink()
        return destination
    finally:
        if os.path.exists(name):
            os.unlink(name)
