#!/usr/bin/env python3
"""Read-only audit of ATM template metadata (stdlib only)."""

import argparse
import json
import re
from pathlib import Path
import subprocess
import sys

MAX_TEXT = 240
RESERVED_TAG_PREFIXES = (
    "template-type:", "content-format:", "workflow-state:",
    "workflow-stage:", "workflow-transition:", "workflow-scope-kind:",
)


def _short(value):
    text = str(value).replace("\n", " ")
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 1] + "…"


def _json_object(value, source):
    if not isinstance(value, (dict, list)):
        raise ValueError(f"{source} JSON must be an object or array")
    return value


def _catalog_rows(value):
    rows = value if isinstance(value, list) else None
    if isinstance(value, dict):
        rows = next((value[key] for key in ("templates", "revisions", "items", "data")
                     if isinstance(value.get(key), list)), None)
    if rows is None:
        raise ValueError("catalog JSON has no template list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("catalog entry is not an object")
        sha = row.get("template_sha")
        if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
            raise ValueError("catalog entry requires a full lowercase template SHA")
        if sha in seen:
            raise ValueError("duplicate template SHA in catalog: " + sha)
        seen.add(sha)
        if row.get("template_type") is not None and not isinstance(row["template_type"], str):
            raise ValueError("catalog template_type must be a string or null")
    return rows


def _schema_body(value):
    if not isinstance(value, dict):
        raise ValueError("schema JSON must be an object")
    body = value.get("schema_json", value)
    if isinstance(body, str):
        body = json.loads(body)
    if not isinstance(body, dict):
        raise ValueError("schema_json must be an object")
    return body


def _variable_names(schema):
    names = set()
    required = schema.get("required_variables", [])
    if isinstance(required, list):
        for item in required:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.add(item["name"])
    for container in (schema, schema.get("metadata", {})):
        defaults = container.get("defaults", {}) if isinstance(container, dict) else {}
        if isinstance(defaults, dict):
            names.update(str(k) for k in defaults)
    return names


def _finding(code, detail=None, severity="warning"):
    result = {"code": code, "severity": severity}
    if detail:
        result["detail"] = _short(detail)
    return result


def validate_standards(value):
    """Validate and return the small, public standards registry."""
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("standards must be an object with schema_version 1")
    types = value.get("types")
    if not isinstance(types, dict) or not types:
        raise ValueError("standards.types must be a non-empty object")
    for name, definition in types.items():
        if not isinstance(name, str) or not isinstance(definition, dict):
            raise ValueError("standards type definitions must be objects")
        metadata = definition.get("metadata")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("type"), str) or metadata["type"] != name:
            raise ValueError(f"standards type {name!r} must declare matching metadata.type")
    expectations = value.get("revision_expectations", {})
    if not isinstance(expectations, dict):
        raise ValueError("standards.revision_expectations must be an object")
    for sha, expectation in expectations.items():
        if not isinstance(sha, str) or not isinstance(expectation, dict):
            raise ValueError("revision expectations must be objects")
        expected = expectation.get("expected_type")
        if expected is not None and expected not in types:
            raise ValueError(f"revision {sha!r} references unknown expected_type")
    return value


def inspect_schema(sha, schema_value, catalog_type=None):
    findings = []
    try:
        schema = _schema_body(schema_value)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return [_finding("schema_invalid", exc, "error")]
    metadata = schema.get("metadata")
    if not isinstance(metadata, dict):
        return [_finding("metadata_missing", "metadata object is absent", "error")]
    metadata_type = metadata.get("type")
    if not isinstance(metadata_type, str) or not metadata_type.strip():
        findings.append(_finding("metadata_type_missing", "metadata.type is absent"))
    elif catalog_type and isinstance(catalog_type, str) and catalog_type != metadata_type:
        findings.append(_finding("catalog_type_mismatch", f"catalog={catalog_type!r}, metadata={metadata_type!r}"))

    tags = metadata.get("tags", [])
    if tags is not None and not isinstance(tags, list):
        findings.append(_finding("tags_not_list", "metadata.tags must be an array", "error"))
    elif isinstance(tags, list):
        seen = set()
        for tag in tags:
            if not isinstance(tag, str):
                findings.append(_finding("tag_not_string", "metadata.tags contains a non-string value", "error"))
                continue
            if tag in seen:
                findings.append(_finding("duplicate_tag", "metadata.tags contains a duplicate", "error"))
            seen.add(tag)
            if any(tag.startswith(prefix) for prefix in RESERVED_TAG_PREFIXES):
                findings.append(_finding("reserved_tag_prefix", "metadata.tags contains a reserved prefix", "error"))
            if "${" in tag or "{{" in tag or "}}" in tag:
                findings.append(_finding("tag_interpolation", "metadata tags must be literal", "error"))

    if "workflow" in metadata and metadata["workflow"] is not None:
        workflow = metadata["workflow"]
        if not isinstance(workflow, dict):
            findings.append(_finding("workflow_not_object", "metadata.workflow must be an object", "error"))
        else:
            scope = workflow.get("scope")
            if not isinstance(scope, dict):
                findings.append(_finding("workflow_scope_missing", "workflow.scope is required when workflow is declared", "error"))
            else:
                for key in ("kind", "variable"):
                    if not isinstance(scope.get(key), str) or not scope[key].strip():
                        findings.append(_finding("workflow_scope_field_missing", f"workflow.scope.{key} is required", "error"))
            for key in ("stage", "state", "transition"):
                if not isinstance(workflow.get(key), str) or not workflow[key].strip():
                    findings.append(_finding("workflow_field_missing", f"workflow.{key} is required", "error"))
            names = _variable_names(schema)
            references = []
            if isinstance(scope, dict) and isinstance(scope.get("variable"), str):
                references.append(scope["variable"])
            if isinstance(workflow.get("iteration_variable"), str):
                references.append(workflow["iteration_variable"])
            for variable in references:
                if variable not in names:
                    findings.append(_finding("variable_unresolved", f"workflow references {variable!r}; dispatch evidence is required"))
    return findings


def _standard_findings(metadata, expected):
    findings = []
    expected_metadata = expected.get("metadata", {})
    if not isinstance(expected_metadata, dict):
        return [_finding("standard_metadata_invalid", "standards metadata is invalid", "error")]
    if metadata.get("type") != expected_metadata.get("type"):
        findings.append(_finding("expected_type_mismatch", "metadata.type does not match expected type", "error"))
    expected_tags = expected_metadata.get("tags", [])
    actual_tags = metadata.get("tags", [])
    if isinstance(expected_tags, list) and (not isinstance(actual_tags, list) or any(tag not in actual_tags for tag in expected_tags)):
        findings.append(_finding("expected_tags_missing", "one or more standard tags are missing", "error"))
    expected_workflow = expected_metadata.get("workflow")
    if expected_workflow is not None:
        actual_workflow = metadata.get("workflow")
        if not isinstance(actual_workflow, dict):
            findings.append(_finding("expected_workflow_missing", "standard workflow declaration is missing", "error"))
        else:
            for field in ("scope", "state", "stage", "transition", "iteration_variable"):
                if field not in expected_workflow:
                    continue
                if field == "scope":
                    expected_scope = expected_workflow[field]
                    actual_scope = actual_workflow.get(field)
                    if not isinstance(actual_scope, dict) or not isinstance(expected_scope, dict) or any(actual_scope.get(k) != v for k, v in expected_scope.items()):
                        findings.append(_finding("expected_workflow_mismatch", "workflow scope does not match standard", "error"))
                elif actual_workflow.get(field) != expected_workflow[field]:
                    findings.append(_finding("expected_workflow_mismatch", f"workflow.{field} does not match standard", "error"))
    return findings


def audit(catalog_value, schemas, source_failures=None, standards=None):
    failures = list(source_failures or [])
    rows = _catalog_rows(catalog_value)
    type_counts = {}
    untyped = []
    findings = {}
    expectations = {}
    counts = {"compliant": 0, "noncompliant": 0, "unclassified": 0, "errors": 0}
    if standards is not None:
        standards = validate_standards(standards)
    known_types = set(standards.get("types", {})) if standards else set()
    bindings = standards.get("revision_expectations", {}) if standards else {}
    for row in rows:
        if not isinstance(row, dict):
            failures.append({"source": "catalog", "error": "catalog entry is not an object"})
            continue
        sha = row.get("template_sha")
        if not isinstance(sha, str) or not sha:
            failures.append({"source": "catalog", "error": "catalog entry has no template_sha"})
            continue
        catalog_type = row.get("template_type")
        if isinstance(catalog_type, str) and catalog_type.strip():
            type_counts[catalog_type] = type_counts.get(catalog_type, 0) + 1
        else:
            untyped.append(sha)
        binding = bindings.get(sha, {})
        expected_type = binding.get("expected_type") if isinstance(binding, dict) and "expected_type" in binding else None
        schema_for_type = schemas.get(sha)
        if expected_type is None and sha not in bindings and schema_for_type is not None:
            try:
                metadata = _schema_body(schema_for_type).get("metadata")
                candidate = metadata.get("type") if isinstance(metadata, dict) else None
                expected_type = candidate if isinstance(candidate, str) else None
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
        if expected_type is None and catalog_type in known_types:
            expected_type = catalog_type
        if standards is not None:
            expectations[sha] = {"expected_type": expected_type, "source_path": binding.get("source_path") if isinstance(binding, dict) else None}
            if expected_type not in known_types:
                findings.setdefault(sha, []).append(_finding("unclassified_revision", "no known expected type", "warning"))
                counts["unclassified"] += 1
        if sha not in schemas:
            failures.append({"source": "schema", "template_sha": sha, "error": "schema unavailable"})
            continue
        result = inspect_schema(sha, schemas[sha], catalog_type)
        if standards is not None and expected_type in known_types:
            try:
                metadata = _schema_body(schemas[sha]).get("metadata")
                if isinstance(metadata, dict):
                    result.extend(_standard_findings(metadata, standards["types"][expected_type]))
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                result.append(_finding("schema_invalid", exc, "error"))
        if result:
            findings.setdefault(sha, []).extend(result)
        if standards is not None and expected_type in known_types:
            if result:
                counts["noncompliant"] += 1
                counts["errors"] += sum(1 for item in result if item.get("severity") == "error")
            else:
                counts["compliant"] += 1
    status = "unavailable" if failures else ("attention" if findings or untyped else "ok")
    if standards is not None and any(item.get("code") == "unclassified_revision" for values in findings.values() for item in values):
        status = "attention" if status == "ok" else status
    return {"status": status, "catalog_revision_count": len(rows), "type_counts": type_counts,
            "untyped_revisions": untyped, "metadata_findings": findings, "source_failures": failures,
            "expectations": expectations, "counts": counts}


def _run_atm(args, standards, selected=None):
    command = [args.atm, "templates", "list", "--json"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, [{"source": "catalog", "error": _short(exc)}]
    if completed.returncode:
        return None, [{"source": "catalog", "error": _short(completed.stderr or f"exit {completed.returncode}")}]
    try:
        catalog = _json_object(json.loads(completed.stdout), "catalog")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return None, [{"source": "catalog", "error": _short(exc)}]
    schemas, failures = {}, []
    try:
        rows = _catalog_rows(catalog)
    except ValueError as exc:
        return None, [{"source": "catalog", "error": str(exc)}]
    if selected is not None:
        available = {row.get("template_sha") for row in rows if isinstance(row, dict)}
        missing = sorted(selected - available)
        if missing:
            return audit([], {}, [{"source": "catalog", "error": "selected template_sha not found: " + ", ".join(missing)}], standards), []
    for row in rows:
        sha = row.get("template_sha") if isinstance(row, dict) else None
        if not isinstance(sha, str) or not sha:
            continue
        if selected is not None and sha not in selected:
            continue
        try:
            result = subprocess.run([args.atm, "templates", "schema", sha, "--json"], capture_output=True,
                                    text=True, timeout=args.timeout, check=False)
            if result.returncode:
                failures.append({"source": "schema", "template_sha": sha, "error": _short(result.stderr or f"exit {result.returncode}")})
                continue
            schemas[sha] = json.loads(result.stdout)
        except subprocess.TimeoutExpired as exc:
            failures.append({"source": "schema", "template_sha": sha, "error": _short(exc)})
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            failures.append({"source": "schema", "template_sha": sha, "error": _short(exc)})
    return audit(catalog if selected is None else [row for row in rows if isinstance(row, dict) and row.get("template_sha") in selected], schemas, failures, standards), []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, help="offline catalog JSON")
    parser.add_argument("--schemas-dir", type=Path, help="offline directory containing SHA.json")
    parser.add_argument("--atm", default="atm", help="ATM executable")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--standards", type=Path, default=Path(__file__).resolve().parents[1] / "references" / "standards.json")
    parser.add_argument("--strict", action="store_true", help="exit 1 when audit status is attention")
    parser.add_argument("--template-sha", action="append", dest="template_shas", metavar="SHA",
                        help="audit only this catalog revision (repeatable)")
    args = parser.parse_args(argv)
    try:
        if bool(args.catalog) != bool(args.schemas_dir):
            raise ValueError("--catalog and --schemas-dir must be supplied together")
        standards = validate_standards(json.loads(args.standards.read_text(encoding="utf-8")))
        selected = set(args.template_shas or []) or None
        if args.catalog:
            catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
            rows = _catalog_rows(catalog)
            if selected is not None:
                available = {row.get("template_sha") for row in rows if isinstance(row, dict)}
                missing = sorted(selected - available)
                if missing:
                    raise ValueError("selected template_sha not found in catalog: " + ", ".join(missing))
                catalog = [row for row in rows if isinstance(row, dict) and row.get("template_sha") in selected]
            schemas, failures = {}, []
            for row in _catalog_rows(catalog):
                sha = row.get("template_sha") if isinstance(row, dict) else None
                if not isinstance(sha, str) or not sha:
                    continue
                path = args.schemas_dir / f"{sha}.json"
                try:
                    schemas[sha] = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                    failures.append({"source": "schema", "template_sha": sha, "error": _short(exc)})
            result = audit(catalog, schemas, failures, standards)
        else:
            # Fetch the catalog once, then only retrieve requested schemas.
            if selected is not None:
                # _run_atm validates selection after catalog retrieval below.
                pass
            result, failures = _run_atm(args, standards, selected)
            if result is None:
                result = {"status": "unavailable", "catalog_revision_count": 0, "type_counts": {},
                          "untyped_revisions": [], "metadata_findings": {}, "source_failures": failures}
        print(json.dumps(result, sort_keys=True, indent=2))
        return 2 if result["status"] == "unavailable" else (1 if args.strict and result["status"] == "attention" else 0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "unavailable", "catalog_revision_count": 0, "type_counts": {},
                          "untyped_revisions": [], "metadata_findings": {},
                          "source_failures": [{"source": "input", "error": _short(exc)}]}, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
