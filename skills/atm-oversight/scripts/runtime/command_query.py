"""Bounded subprocess boundary; commands are argument arrays, never shell text."""
from dataclasses import dataclass
from datetime import datetime, timezone
import subprocess

from query_types import Error, Problem


@dataclass(frozen=True)
class CommandSuccess:
    stdout: str
    stderr: str
    exit_code: int


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def failure(query, source, scope, kind, message, command=(), exit_code=None,
            diagnostics='', retryable=False, repair='Inspect and repair the named query.', retry_after=None):
    return Error(query, source, scope, now_iso(), Problem(
        kind, message, tuple(command), exit_code, diagnostics[-2000:], retryable,
        retry_after, repair))


def execute(query, source, scope, args, cwd=None, timeout=30, accepted=(0,)):
    command = tuple(str(x) for x in args)
    try:
        p = subprocess.run(command, cwd=cwd, timeout=timeout, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return failure(query, source, scope, 'missing-executable', str(exc), command,
                       repair='Verify the executable and working directory in the scheduler PATH.')
    except subprocess.TimeoutExpired:
        return failure(query, source, scope, 'timeout', f'Exceeded {timeout}s', command,
                       retryable=True, repair='Retry within the configured budget; inspect provider health if repeated.')
    except (OSError, ValueError, UnicodeError) as exc:
        return failure(query, source, scope, 'execution', str(exc), command,
                       repair='Inspect scheduler access, encoding, and the explicit command arguments.')
    if p.returncode in accepted:
        return CommandSuccess(p.stdout, p.stderr[-2000:], p.returncode)
    diagnostic = (p.stderr or p.stdout)[-2000:]
    lower = diagnostic.lower()
    kind, retry, repair = 'command-failed', False, 'Inspect the command diagnostic and repair the adapter or scope.'
    if any(x in lower for x in ('rate limit', '429')):
        kind, retry, repair = 'rate-limit', True, 'Honor provider retry/reset time, then retry this scope.'
    elif any(x in lower for x in ('401', '403', 'permission', 'not authenticated', 'authentication')):
        kind, repair = 'access', 'Check scheduler credentials and repository access; escalate required permission repair.'
    elif any(x in lower for x in ('connect', 'unavailable', '502', '503', '504', 'timed out')):
        kind, retry, repair = 'unavailable', True, 'Retry with backoff; inspect the named service if the failure persists.'
    return failure(query, source, scope, kind, 'Command did not return usable evidence', command,
                   p.returncode, diagnostic, retry, repair)
