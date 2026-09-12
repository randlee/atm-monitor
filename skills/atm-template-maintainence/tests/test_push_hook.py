import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_push", ROOT / "scripts/check_push.py")
check_push = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_push)

SHA1 = "a" * 64
SHA2 = "b" * 64


class PushHookTests(unittest.TestCase):
    def run_gate(self, doctor, catalog=None, *, available=True, doctor_rc=0, catalog_rc=0):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if command[1] == "doctor":
                return SimpleNamespace(returncode=doctor_rc, stdout=json.dumps(doctor), stderr="doctor error")
            return SimpleNamespace(returncode=catalog_rc, stdout=json.dumps(catalog), stderr="catalog error")

        result = check_push.check_push("atm", which=lambda _: "/bin/atm" if available else None,
                                      runner=fake_run)
        return result, calls

    def test_unavailable_atm_skips_without_running(self):
        result, calls = self.run_gate({}, available=False)
        self.assertEqual(result, 0)
        self.assertEqual(calls, [])

    def test_stopped_daemon_skips_catalog(self):
        result, calls = self.run_gate({"runtime_status": {"liveness": "stopped"}})
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)

    def test_stopped_daemon_with_diagnostic_exit_still_skips(self):
        result, calls = self.run_gate({"runtime_status": {"liveness": "stopped"}}, doctor_rc=2)
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)

    def test_running_daemon_blocks_all_untagged_with_mapping(self):
        result, calls = self.run_gate({"runtime_status": {"liveness": "running"}},
                                      {"templates": [{"template_sha": SHA1}, {"template_sha": SHA2, "template_type": "dev-task"}]})
        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 2)

    def test_running_daemon_all_tagged_allows(self):
        result, _ = self.run_gate({"daemon_context": {"status": "running"}},
                                  [{"template_sha": SHA1, "template_type": "qa-report"}])
        self.assertEqual(result, 0)

    def test_malformed_doctor_and_catalog_fail_closed(self):
        result, _ = self.run_gate({"runtime_status": {"liveness": "maybe"}})
        self.assertEqual(result, 2)
        result, _ = self.run_gate({"runtime_status": {"liveness": "running"}}, {"templates": [{"template_sha": "bad"}]})
        self.assertEqual(result, 2)

    def test_query_failure_fails_closed(self):
        result, _ = self.run_gate({"runtime_status": {"liveness": "running"}}, {}, catalog_rc=1)
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
