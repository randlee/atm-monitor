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
            {"template_sha": "old", "template_type": "legacy"},
            {"template_sha": "new", "template_type": "workflow"},
            {"template_sha": "empty"},
        ]}
        schemas = {
            "old": {"schema_json": {"metadata": {"tags": []}}},
            "new": {"schema_json": {"metadata": {
                "type": "workflow", "tags": ["x", "x", "template-type:bad", "{{x}}"],
                "workflow": {"scope": {"kind": "account", "variable": "account_id"},
                              "stage": "run", "state": "ready", "transition": "go"}
            }, "required_variables": ["account_id"]}},
            "empty": {"schema_json": {"metadata": {"type": "different"}}},
        }
        result = audit_metadata.audit(catalog, schemas)
        self.assertEqual(result["status"], "attention")
        self.assertEqual(result["catalog_revision_count"], 3)
        self.assertEqual(result["type_counts"], {"legacy": 1, "workflow": 1})
        self.assertEqual(result["untyped_revisions"], ["empty"])
        codes = {item["code"] for item in result["metadata_findings"]["old"]}
        self.assertIn("metadata_type_missing", codes)
        codes = {item["code"] for item in result["metadata_findings"]["new"]}
        self.assertTrue({"duplicate_tag", "reserved_tag_prefix", "tag_interpolation"} <= codes)

    def test_partial_workflow_and_unresolved_dispatch_variable(self):
        result = audit_metadata.audit(
            [{"template_sha": "sha"}],
            {"sha": {"schema_json": {"metadata": {"type": "x", "workflow": {
                "scope": {"kind": "account", "variable": "account_id"}, "stage": "run"
            }}}}},
        )
        codes = {item["code"] for item in result["metadata_findings"]["sha"]}
        self.assertIn("workflow_field_missing", codes)
        self.assertIn("variable_unresolved", codes)

    def test_offline_cli_and_missing_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.json").write_text(json.dumps({"templates": [{"template_sha": "sha"}]}))
            (root / "sha.json").write_text(json.dumps({"schema_json": {"metadata": {"type": "x"}}}))
            completed = subprocess.run([sys.executable, str(ROOT / "scripts/audit_metadata.py"),
                                        "--catalog", str(root / "catalog.json"), "--schemas-dir", str(root)],
                                       capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(json.loads(completed.stdout)["status"], "attention")
            (root / "sha.json").unlink()
            completed = subprocess.run([sys.executable, str(ROOT / "scripts/audit_metadata.py"),
                                        "--catalog", str(root / "catalog.json"), "--schemas-dir", str(root)],
                                       capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(completed.stdout)["status"], "unavailable")

    def test_strict_attention_and_selected_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.json").write_text(json.dumps({"templates": [{"template_sha": "sha", "template_type": "dev-task"}]}))
            (root / "sha.json").write_text(json.dumps({"schema_json": {"metadata": {"type": "dev-task"}}}))
            standards = ROOT / "references" / "standards.json"
            command = [sys.executable, str(ROOT / "scripts/audit_metadata.py"), "--catalog", str(root / "catalog.json"),
                       "--schemas-dir", str(root), "--standards", str(standards), "--strict"]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 1)
            command += ["--template-sha", "missing"]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(completed.stdout)["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
