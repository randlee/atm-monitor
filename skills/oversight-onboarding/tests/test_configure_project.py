import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from configure_project import configure, locked


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = self.root / 'config with spaces.json'

    def add(self, phase='BA', start='2026-09-11T00:00:00Z', actor='monitor', **kwargs):
        return configure(self.config, 'a', self.root, phase, start, 'task:start', actor=actor, **kwargs)

    def test_overlapping_phases_keep_independent_settings_and_repeat_is_idempotent(self):
        self.add('AZ', '2026-09-10T00:00:00Z', worktrees=[self.root / 'az'])
        self.add(worktrees=[self.root / 'ba'])
        self.add()
        data = json.loads(self.config.read_text())
        projects = data['teams'][0]['projects']
        self.assertEqual([p['phase'] for p in projects], ['AZ', 'BA'])
        self.assertEqual(projects[0]['start_time'], '2026-09-10T00:00:00Z')
        self.assertEqual(projects[1]['worktrees'], [str(self.root / 'ba')])

    def test_other_teams_options_and_relative_paths_are_preserved(self):
        initial = {'schema_version': 1, 'retain_snapshots': 4321,
                   'teams': [{'name': 'other', 'repo': '.', 'custom': 'keep'},
                             {'name': 'a', 'repo': '.', 'actor': 'existing', 'worktrees': ['existing-tree']}]}
        self.config.write_text(json.dumps(initial))
        self.add(actor=None)
        data = json.loads(self.config.read_text())
        self.assertEqual(data['teams'][0], initial['teams'][0])
        self.assertEqual(data['retain_snapshots'], 4321)
        self.assertEqual(data['teams'][1]['worktrees'], ['existing-tree'])
        self.assertEqual(data['teams'][1]['actor'], 'existing')

    def test_new_team_requires_actor_without_writing_config(self):
        with self.assertRaisesRegex(ValueError, 'actor is required'):
            configure(self.config, 'a', self.root, 'BA', '2026-09-11T00:00:00Z', 'task:start')
        self.assertFalse(self.config.exists())

    def test_existing_team_missing_actor_requires_actor_without_writing_config(self):
        initial = {'schema_version': 1, 'teams': [{'name': 'a', 'repo': str(self.root), 'projects': []}]}
        self.config.write_text(json.dumps(initial))
        before = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, 'existing team needs'):
            self.add(actor=None)
        self.assertEqual(self.config.read_bytes(), before)

    def test_blank_actor_is_rejected_without_writing_config(self):
        with self.assertRaisesRegex(ValueError, 'nonempty ATM identity'):
            self.add(actor='   ')
        self.assertFalse(self.config.exists())

    def test_conflicting_same_phase_boundary_does_not_overwrite(self):
        self.add()
        before = self.config.read_bytes()
        with self.assertRaises(ValueError):
            self.add(start='2026-09-12T00:00:00Z')
        self.assertEqual(self.config.read_bytes(), before)

    def test_invalid_timestamps_and_missing_evidence_do_not_write(self):
        for value in ('yesterday', '2026-09-11', '2026-09-11T00:00:00'):
            with self.assertRaises(ValueError):
                self.add(start=value)
        with self.assertRaises(ValueError):
            configure(self.config, 'a', self.root, 'BA', '2026-09-11T00:00:00Z', '')
        self.assertFalse(self.config.exists())

    def test_atomic_replace_failure_keeps_old_settings(self):
        self.add()
        before = self.config.read_bytes()
        with patch('configure_project.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.add('BB')
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse(list(self.root.glob('.project-settings-*')))

    def test_concurrent_writer_is_rejected_and_lock_recovers(self):
        lock = self.root / ('.' + self.config.name + '.lock')
        with locked(lock):
            with self.assertRaises(OSError):
                self.add()
        self.add()

    def test_self_contained_cli_help(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/configure_project.py'), '--help'],
                                cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--phase', result.stdout)
        self.assertIn('--as ACTOR', result.stdout)


if __name__ == '__main__':
    unittest.main()
