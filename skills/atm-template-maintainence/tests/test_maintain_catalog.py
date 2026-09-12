import importlib.util
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("maintain_catalog", ROOT / "scripts/maintain_catalog.py")
maintain_catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintain_catalog)

SHA = "a" * 64
OTHER = "b" * 64
SHA2 = "c" * 64
SHA3 = "d" * 64


class MaintainCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.database = root / "catalog.db"
        self.receipts = root / "receipts"
        self.standards = root / "standards.json"
        self.standards.write_text(json.dumps({"revision_expectations": {
            SHA: {"expected_type": "dev-task", "source_path": "dev.j2"}}}))
        db = sqlite3.connect(self.database)
        db.execute("CREATE TABLE message_templates (template_sha TEXT PRIMARY KEY, template_type TEXT, schema_json TEXT, content_bytes BLOB, message TEXT, workflow TEXT)")
        schema = json.dumps({"metadata": {"tags": ["keep"]}, "required_variables": ["x"]})
        db.execute("INSERT INTO message_templates VALUES (?, ?, ?, ?, ?, ?)", (SHA, None, schema, b"content", "message", "workflow"))
        db.execute("INSERT INTO message_templates VALUES (?, ?, ?, ?, ?, ?)", (OTHER, "qa-task", '{"metadata":{"type":"qa-task"}}', b"other", "m", "w"))
        db.commit(); db.close()

    def tearDown(self):
        self.temp.cleanup()

    def _row(self, sha=SHA, database=None):
        db = sqlite3.connect(database or self.database)
        row = db.execute("SELECT * FROM message_templates WHERE template_sha=?", (sha,)).fetchone()
        db.close()
        return row

    def test_dry_run_and_apply_preserve_columns_and_backup(self):
        before = self._row()
        preview = maintain_catalog.maintain(self.database, self.standards)
        self.assertEqual(preview["rowcount"], 1)
        self.assertEqual(self._row(), before)
        result = maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        self.assertEqual(result["rowcount"], 1)
        after = self._row()
        self.assertEqual(after[0], SHA)
        self.assertEqual(after[1], "dev-task")
        self.assertEqual(after[3:], before[3:])
        self.assertEqual(json.loads(after[2])["metadata"]["type"], "dev-task")
        backup = sqlite3.connect(result["backup_path"])
        self.assertEqual(backup.execute("SELECT template_type, schema_json FROM message_templates WHERE template_sha=?", (SHA,)).fetchone(), (None, before[2]))
        backup.close()

    def test_apply_is_idempotent(self):
        maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        second = maintain_catalog.maintain(self.database, self.standards)
        self.assertEqual(second["rowcount"], 0)
        self.assertEqual(self._row()[1], "dev-task")

    def test_conflict_fails_before_any_write(self):
        db = sqlite3.connect(self.database)
        db.execute("INSERT INTO message_templates VALUES (?, ?, ?, ?, ?, ?)", (SHA2, None, '{"metadata":{}}', b"second", "m2", "w2"))
        db.execute("UPDATE message_templates SET template_type='qa-task' WHERE template_sha=?", (SHA,))
        db.commit(); db.close()
        before = self._row()
        before_second = self._row(SHA2)
        self.standards.write_text(json.dumps({"revision_expectations": {
            SHA: {"expected_type": "dev-task"}, SHA2: {"expected_type": "qa-task"}}}))
        with self.assertRaises(ValueError):
            maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        self.assertEqual(self._row(), before)
        self.assertEqual(self._row(SHA2), before_second)
        self.assertFalse(self.receipts.exists())

    def test_missing_mapped_sha_rejects_without_mutation(self):
        before = self._row()
        missing = "e" * 64
        self.standards.write_text(json.dumps({"revision_expectations": {
            SHA: {"expected_type": "dev-task"}, missing: {"expected_type": "qa-task"}}}))
        with self.assertRaises(ValueError):
            maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        self.assertEqual(self._row(), before)
        self.assertFalse(self.receipts.exists())

    def test_partial_blanks_repair_only_missing_field_and_preserve_metadata(self):
        db = sqlite3.connect(self.database)
        schema_meta_blank = '{"metadata":{"tags":["one"],"owner":"keep"},"x":1}'
        schema_catalog_blank = '{"metadata":{"type":"dev-task","tags":["two"],"owner":"keep"},"x":2}'
        db.execute("INSERT INTO message_templates VALUES (?, ?, ?, ?, ?, ?)",
                   (SHA2, "dev-task", schema_meta_blank, b"partial-one", "m2", "w2"))
        db.execute("INSERT INTO message_templates VALUES (?, ?, ?, ?, ?, ?)",
                   (SHA3, None, schema_catalog_blank, b"partial-two", "m3", "w3"))
        db.commit(); db.close()
        self.standards.write_text(json.dumps({"revision_expectations": {
            SHA: {"expected_type": "dev-task"}, SHA2: {"expected_type": "dev-task"},
            SHA3: {"expected_type": "dev-task"}}}))
        before_one, before_two = self._row(SHA2), self._row(SHA3)
        result = maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        self.assertEqual(result["rowcount"], 3)
        after_one, after_two = self._row(SHA2), self._row(SHA3)
        self.assertEqual(after_one[1], "dev-task")
        self.assertEqual(json.loads(after_one[2])["metadata"], {"tags": ["one"], "owner": "keep", "type": "dev-task"})
        self.assertEqual(after_one[3:], before_one[3:])
        self.assertEqual(after_two[1], "dev-task")
        self.assertEqual(after_two[2], before_two[2])
        self.assertEqual(after_two[3:], before_two[3:])


    def test_receipt_failure_before_commit_leaves_database_unchanged(self):
        before = self._row()
        with patch.object(maintain_catalog, "_write_receipt", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        self.assertEqual(self._row(), before)

    def test_completion_receipt_failure_retains_prepared_recovery_evidence(self):
        writer = maintain_catalog._write_receipt
        def fail_completion(path, receipt):
            if receipt["status"] == "committed":
                raise OSError("disk full")
            writer(path, receipt)
        with patch.object(maintain_catalog, "_write_receipt", side_effect=fail_completion):
            with self.assertRaisesRegex(OSError, "database committed"):
                maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        self.assertEqual(self._row()[1], "dev-task")
        receipt = json.loads(next(self.receipts.glob("*.json")).read_text())
        self.assertEqual(receipt["status"], "prepared")
        self.assertTrue(Path(receipt["backup_path"]).is_file())
        self.assertEqual(receipt["rows"][0]["schema_after_sha256"], maintain_catalog._sha(self._row()[2]))

    def test_noop_apply_creates_no_second_backup_or_receipt(self):
        maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        files_before = sorted(p.name for p in self.database.parent.rglob("*"))
        result = maintain_catalog.maintain(self.database, self.standards, apply=True, receipt_dir=self.receipts)
        self.assertEqual(result["rowcount"], 0)
        self.assertEqual(files_before, sorted(p.name for p in self.database.parent.rglob("*")))


if __name__ == "__main__":
    unittest.main()
