#!/usr/bin/env python3
"""Gate a git push when a running ATM daemon has untyped templates."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = SKILL_ROOT / "SKILL.md"
STANDARDS_FILE = SKILL_ROOT / "references" / "standards.json"
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")
KNOWN_NO_DAEMON = {"stopped", "unavailable", "none", "not_running", "disabled"}


def _text(result):
    value = getattr(result, "stdout", "")
    return value if isinstance(value, str) else ""


def _error(message):
    print(f"ATM push check failed: {message}", file=sys.stderr)
    print(f"Inspect {SKILL_FILE} for the remediation procedure.", file=sys.stderr)
    return 2


def _run(command, runner, timeout):
    try:
        return runner(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(str(exc)) from exc


def _daemon_state(document):
    """Return running, no-daemon, or unknown from doctor JSON.

    A top-level runtime_status.liveness is authoritative.  If it is absent,
    a daemon_context with an explicit compatible status is accepted.
    """
    if not isinstance(document, dict):
        return "unknown"
    runtime = document.get("runtime_status")
    if isinstance(runtime, dict) and "liveness" in runtime:
        value = runtime["liveness"]
        if isinstance(value, str):
            value = value.strip().lower()
            if value == "running":
                return "running"
            if value in KNOWN_NO_DAEMON:
                return "no-daemon"
        return "unknown"
    context = document.get("daemon_context")
    if isinstance(context, dict):
        for key in ("liveness", "status", "state"):
            value = context.get(key)
            if isinstance(value, str):
                value = value.strip().lower()
                if value == "running":
                    return "running"
                if value in KNOWN_NO_DAEMON:
                    return "no-daemon"
        # Some doctor versions expose an explicit boolean pair.
        if context.get("running") is True or context.get("alive") is True:
            return "running"
        if context.get("running") is False or context.get("alive") is False:
            return "no-daemon"
    return "unknown"


def _catalog_rows(document):
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in ("templates", "revisions", "items", "data"):
            rows = document.get(key)
            if isinstance(rows, list):
                return rows
    raise ValueError("catalog JSON must be an array or object containing a template list")


def _standards():
    try:
        document = json.loads(STANDARDS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read standards SSOT: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("types"), dict):
        raise ValueError("standards SSOT has invalid types")
    expectations = document.get("revision_expectations", {})
    if not isinstance(expectations, dict):
        raise ValueError("standards SSOT has invalid revision_expectations")
    return document["types"], expectations


def _validate_catalog(document):
    rows = _catalog_rows(document)
    untagged = []
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"catalog entry {index} is not an object")
        sha = row.get("template_sha")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise ValueError(f"catalog entry {index} has invalid full template_sha")
        if sha in seen:
            raise ValueError(f"catalog contains duplicate template_sha {sha}")
        seen.add(sha)
        template_type = row.get("template_type")
        if template_type is None or (isinstance(template_type, str) and not template_type.strip()):
            untagged.append(sha)
        elif not isinstance(template_type, str):
            raise ValueError(f"catalog entry {sha} has non-string template_type")
    return untagged


def check_push(atm="atm", *, which=shutil.which, run=subprocess.run, runner=None, timeout=10.0):
    """Run the gate and return a process exit status.

    ``which`` and ``runner`` are injectable so tests never need a live daemon.
    This function does not read stdin, preserving git hook composition.
    """
    # ``runner`` remains accepted as a readable compatibility alias; ``run``
    # is the public injection point named after subprocess.run.
    if runner is not None:
        run = runner
    if which(atm) is None:
        print(f"ATM executable {atm!r} is unavailable; skipping template check.", file=sys.stderr)
        return 0
    try:
        doctor = _run([atm, "doctor", "--json"], run, timeout)
    except RuntimeError as exc:
        return _error(f"cannot inspect daemon health: {exc}")
    try:
        doctor_json = json.loads(_text(doctor))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _error(f"atm doctor returned malformed JSON: {exc}")
    state = _daemon_state(doctor_json)
    if state == "no-daemon":
        print("ATM daemon is stopped or unavailable; skipping template check.", file=sys.stderr)
        return 0
    if getattr(doctor, "returncode", 1) != 0:
        return _error("atm doctor failed without establishing that the daemon is stopped")
    if state != "running":
        return _error("atm doctor did not provide a known daemon liveness state")

    try:
        catalog_result = _run([atm, "templates", "list", "--json"], run, timeout)
    except RuntimeError as exc:
        return _error(f"cannot verify template catalog: {exc}")
    if getattr(catalog_result, "returncode", 1) != 0:
        return _error("cannot verify template catalog: " + (getattr(catalog_result, "stderr", "") or f"exit {catalog_result.returncode}").strip())
    try:
        catalog = json.loads(_text(catalog_result))
        untagged = _validate_catalog(catalog)
        types, expectations = _standards()
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _error(str(exc))
    if not untagged:
        print("ATM template catalog is fully classified; push allowed.", file=sys.stderr)
        return 0
    print("ATM push blocked: untagged template revisions are present:", file=sys.stderr)
    for sha in untagged:
        expected = expectations.get(sha)
        if isinstance(expected, dict):
            expected_type = expected.get("expected_type", "unknown")
            source = expected.get("source_path", "unknown")
        else:
            expected_type, source = "unknown", "unknown"
        if expected_type not in types:
            expected_type = f"{expected_type} (not a known standard type)"
        print(f"  {sha} expected_type={expected_type} source={source}", file=sys.stderr)
    print(f"Classify these revisions using {SKILL_FILE} and {STANDARDS_FILE}.", file=sys.stderr)
    return 1


def main(argv=None, *, which=shutil.which, run=subprocess.run, runner=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atm", default="atm", help="ATM executable")
    parser.add_argument("--timeout", type=float, default=10.0, help="per-command timeout in seconds")
    args = parser.parse_args(argv)
    return check_push(args.atm, which=which, run=run, runner=runner, timeout=args.timeout)


if __name__ == "__main__":
    sys.exit(main())
