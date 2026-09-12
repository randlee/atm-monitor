#!/usr/bin/env python3
"""Safely backfill expected metadata on known ATM template revisions."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
from datetime import datetime, timezone


DEFAULT_STANDARDS = Path(__file__).resolve().parents[1] / "references" / "standards.json"


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _schema(raw, sha):
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{sha}: schema_json is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{sha}: schema_json must be an object")
    metadata = value.get("metadata")
    if metadata is None:
        metadata = {}
        value["metadata"] = metadata
    if not isinstance(metadata, dict):
        raise ValueError(f"{sha}: schema_json.metadata must be an object")
    return value, metadata


def _load_expectations(path):
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read standards: {exc}") from exc
    expectations = document.get("revision_expectations") if isinstance(document, dict) else None
    if not isinstance(expectations, dict):
        raise ValueError("standards.revision_expectations must be an object")
    result = {}
    for sha, item in expectations.items():
        if not isinstance(sha, str) or len(sha) != 64 or not all(c in "0123456789abcdefABCDEF" for c in sha):
            raise ValueError(f"invalid revision expectation SHA: {sha!r}")
        if not isinstance(item, dict) or not isinstance(item.get("expected_type"), str) or not item["expected_type"].strip():
            raise ValueError(f"invalid revision expectation for {sha}")
        result[sha] = item["expected_type"]
    return result


def _connect(path, apply):
    mode = "rw" if apply else "ro"
    uri = Path(path).resolve().as_uri() + f"?mode={mode}"
    return sqlite3.connect(uri, uri=True)


def _inspect(connection, expectations):
    connection.row_factory = sqlite3.Row
    rows = connection.execute("SELECT template_sha, template_type, schema_json FROM message_templates").fetchall()
    selected, conflicts, found = [], [], set()
    for row in rows:
        sha = row["template_sha"]
        expected = expectations.get(sha)
        if expected is None:
            continue
        found.add(sha)
        schema, metadata = _schema(row["schema_json"], sha)
        actual_type, actual_meta = row["template_type"], metadata.get("type")
        for field, actual in (("template_type", actual_type), ("metadata.type", actual_meta)):
            if not _blank(actual) and actual != expected:
                conflicts.append(f"{sha}: {field}={actual!r}, expected {expected!r}")
        if _blank(actual_type) or _blank(actual_meta):
            after = dict(schema)
            after_metadata = dict(metadata)
            if _blank(actual_meta):
                after_metadata["type"] = expected
            after["metadata"] = after_metadata
            after_raw = row["schema_json"] if not _blank(actual_meta) else json.dumps(
                after, ensure_ascii=False, separators=(",", ":"))
            selected.append({"template_sha": sha, "expected_type": expected,
                             "old_template_type": actual_type, "old_schema_json": row["schema_json"],
                             "new_template_type": expected if _blank(actual_type) else actual_type,
                             "new_schema_json": after_raw,
                             "metadata_before": actual_meta,
                             "metadata_after": expected if _blank(actual_meta) else actual_meta})
    if conflicts:
        raise ValueError("conflicting nonblank metadata:\n" + "\n".join(conflicts))
    missing = sorted(set(expectations) - found)
    if missing:
        raise ValueError("mapped template revisions missing from database: " + ", ".join(missing))
    return selected


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _backup(connection, database):
    target = Path(database).resolve().with_name(Path(database).name + f".backup-{secrets.token_hex(8)}")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    destination = sqlite3.connect(str(target))
    try:
        connection.backup(destination)
        destination.commit()
    finally:
        destination.close()
    os.chmod(target, 0o600)
    return target


def maintain(database, standards, *, apply=False, receipt_dir=None):
    expectations = _load_expectations(Path(standards))
    connection = _connect(database, apply)
    try:
        selected = _inspect(connection, expectations)
        preview = [{"template_sha": item["template_sha"], "expected_type": item["expected_type"]} for item in selected]
        result = {"mode": "apply" if apply else "dry-run", "rowcount": len(selected), "rows": preview}
        if not apply:
            return result
        directory = Path(receipt_dir)
        directory.mkdir(parents=True, exist_ok=True)
        if not directory.is_dir() or not os.access(directory, os.W_OK):
            raise ValueError(f"receipt directory is not writable: {directory}")
        backup = _backup(connection, database)
        connection.execute("BEGIN IMMEDIATE")
        try:
            # Re-read and compare before the first UPDATE, so a concurrent change
            # causes a complete rollback rather than a partial repair.
            current = {row["template_sha"]: row for row in connection.execute(
                "SELECT template_sha, template_type, schema_json FROM message_templates")}
            for item in selected:
                row = current.get(item["template_sha"])
                if row is None or row["template_type"] != item["old_template_type"] or row["schema_json"] != item["old_schema_json"]:
                    raise ValueError(f"precondition changed for {item['template_sha']}")
            for item in selected:
                cursor = connection.execute(
                    "UPDATE message_templates SET template_type=?, schema_json=? "
                    "WHERE template_sha=? AND template_type IS ? AND schema_json IS ?",
                    (item["new_template_type"], item["new_schema_json"], item["template_sha"],
                     item["old_template_type"], item["old_schema_json"]))
                if cursor.rowcount != 1:
                    raise ValueError(f"update conflict for {item['template_sha']}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        timestamp = datetime.now(timezone.utc).isoformat()
        receipt = {"timestamp": timestamp, "database": str(Path(database).resolve()),
                   "backup_path": str(backup), "source_mapping": expectations,
                   "rowcount": len(selected), "rows": []}
        for item in selected:
            receipt["rows"].append({"template_sha": item["template_sha"], "expected_type": item["expected_type"],
                                    "template_type_before": item["old_template_type"], "template_type_after": item["new_template_type"],
                                    "metadata_type_before": item["metadata_before"], "metadata_type_after": item["metadata_after"],
                                    "schema_before_sha256": _sha(item["old_schema_json"]),
                                    "schema_after_sha256": _sha(item["new_schema_json"])})
        receipt_path = directory / f"catalog-maintenance-{timestamp.replace(':', '').replace('+00:00', 'Z')}.json"
        with receipt_path.open("x", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        result.update({"backup_path": str(backup), "receipt_path": str(receipt_path)})
        return result
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--standards", type=Path, default=DEFAULT_STANDARDS)
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.receipt_dir is None:
        parser.error("--receipt-dir is required with --apply")
    try:
        print(json.dumps(maintain(args.database, args.standards, apply=args.apply,
                                  receipt_dir=args.receipt_dir), indent=2))
        return 0
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"catalog maintenance failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
