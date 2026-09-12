import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit_metadata", ROOT / "scripts/audit_metadata.py")
audit_metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_metadata)


class AuditMetadataTests(unittest.TestCase):
    def test_old_and_new_metadata_and_diagnostics(self):
        catalog = {"templates": [
            {"template_sha": ("a" * 64), "template_type": "legacy"},
            {"template_sha": ("b" * 64), "template_type": "workflow"},
            {"template_sha": ("c" * 64)},
        ]}
        schemas = {
            ("a" * 64): {"schema_json": {"metadata": {"tags": []}}},
            ("b" * 64): {"schema_json": {"metadata": {
                "type": "workflow", "tags": ["x", "x", "template-type:bad", "{{x}}"],
                "workflow": {"scope": {"kind": "account", "variable": "account_id"},
                              "stage": "run", "state": "ready", "transition": "go"}
            }, "required_variables": ["account_id"]}},
            ("c" * 64): {"schema_json": {"metadata": {"type": "different"}}},
        }
        result = audit_metadata.audit(catalog, schemas)
        self.assertEqual(result["status"], "attention")
        self.assertEqual(result["catalog_revision_count"], 3)
        self.assertEqual(result["type_counts"], {"legacy": 1, "workflow": 1})
        self.assertEqual(result["untyped_revisions"], [("c" * 64)])
        codes = {item["code"] for item in result["metadata_findings"][("a" * 64)]}
        self.assertIn("metadata_type_missing", codes)
        codes = {item["code"] for item in result["metadata_findings"][("b" * 64)]}
        self.assertTrue({"duplicate_tag", "reserved_tag_prefix", "tag_interpolation"} <= codes)

    def test_partial_workflow_and_unresolved_dispatch_variable(self):
        result = audit_metadata.audit(
            [{"template_sha": ("d" * 64)}],
            {("d" * 64): {"schema_json": {"metadata": {"type": "x", "workflow": {
                "scope": {"kind": "account", "variable": "account_id"}, "stage": "run"
            }}}}},
        )
        codes = {item["code"] for item in result["metadata_findings"][("d" * 64)]}
        self.assertIn("workflow_field_missing", codes)
        self.assertIn("variable_unresolved", codes)

    def test_offline_cli_and_missing_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.json").write_text(json.dumps({"templates": [{"template_sha": ("d" * 64)}]}))
            (root / ("d" * 64 + ".json")).write_text(json.dumps({"schema_json": {"metadata": {"type": "x"}}}))
            completed = subprocess.run([sys.executable, str(ROOT / "scripts/audit_metadata.py"),
                                        "--catalog", str(root / "catalog.json"), "--schemas-dir", str(root)],
                                       capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(json.loads(completed.stdout)["status"], "attention")
            (root / ("d" * 64 + ".json")).unlink()
            completed = subprocess.run([sys.executable, str(ROOT / "scripts/audit_metadata.py"),
                                        "--catalog", str(root / "catalog.json"), "--schemas-dir", str(root)],
                                       capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(completed.stdout)["status"], "unavailable")

    def test_strict_attention_and_selected_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.json").write_text(json.dumps({"templates": [{"template_sha": ("d" * 64), "template_type": "dev-task"}]}))
            (root / ("d" * 64 + ".json")).write_text(json.dumps({"schema_json": {"metadata": {"type": "dev-task"}}}))
            standards = ROOT / "references" / "standards.json"
            command = [sys.executable, str(ROOT / "scripts/audit_metadata.py"), "--catalog", str(root / "catalog.json"),
                       "--schemas-dir", str(root), "--standards", str(standards), "--strict"]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 1)
            command += ["--template-sha", "missing"]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(completed.stdout)["status"], "unavailable")


    def test_invalid_catalog_cannot_escape_schema_directory(self):
        for rows in ([{"template_sha": "../outside"}],
                     [{"template_sha": "a" * 64}] * 2):
            with self.assertRaises(ValueError):
                audit_metadata.audit(rows, {})

    def test_malformed_metadata_and_unknown_type_preserve_findings(self):
        standards = {"schema_version": 1, "types": {"known": {"metadata": {"type": "known"}}}}
        for metadata in (None, [], {"type": []}, {"type": "unknown", "tags": 4}):
            result = audit_metadata.audit([{"template_sha": "a" * 64}],
                                          {"a" * 64: {"metadata": metadata}}, standards=standards)
            self.assertEqual(result["status"], "attention")
            self.assertIn("unclassified_revision", [f["code"] for f in result["metadata_findings"]["a" * 64]])

    def test_standard_iteration_binding_is_checked(self):
        metadata = {"type": "plan", "workflow": {"iteration_variable": "wrong"}}
        expected = {"metadata": {"type": "plan", "workflow": {"iteration_variable": "round_index"}}}
        findings = audit_metadata._standard_findings(metadata, expected)
        self.assertTrue(any(f["code"] == "expected_workflow_mismatch" for f in findings))

    def test_whitespace_catalog_type_is_untyped(self):
        result = audit_metadata.audit([{"template_sha": "a" * 64, "template_type": "  "}],
                                      {"a" * 64: {"metadata": {"type": "known"}}})
        self.assertEqual(result["untyped_revisions"], ["a" * 64])


if __name__ == "__main__":
    unittest.main()
