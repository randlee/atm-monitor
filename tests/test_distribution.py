import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('distribution', ROOT / 'scripts/distribute_skill.py')
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'SKILL.md').write_text('---\nname: example\ndescription: example\n---\n')
        self.target = self.root / 'skills/atm-oversight'
        self.archive = self.root / 'archive'

    def install(self):
        return distribution.install(self.source, self.target, self.archive)

    def test_install_and_repeat_verify_identical_content(self):
        result = self.install()
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(distribution.verify(self.target)['bundle_sha256'], result['bundle_sha256'])
        self.assertEqual(self.install()['status'], 'unchanged')

    def test_upgrade_preserves_old_bundle_and_removes_obsolete_files(self):
        (self.source / 'obsolete.txt').write_text('old')
        self.install()
        (self.source / 'obsolete.txt').unlink()
        (self.source / 'new.txt').write_text('new')
        result = self.install()
        self.assertFalse((self.target / 'obsolete.txt').exists())
        self.assertTrue((Path(result['backup']) / 'obsolete.txt').exists())
        distribution.verify(Path(result['backup']))

    def test_local_edit_or_unmanaged_target_is_not_overwritten(self):
        self.target.mkdir(parents=True)
        (self.target / 'user-file').write_text('keep')
        with self.assertRaises(OSError):
            self.install()
        shutil.rmtree(self.target)
        self.install()
        (self.target / 'SKILL.md').write_text('local edit')
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual((self.target / 'SKILL.md').read_text(), 'local edit')

    def test_failed_swap_restores_previous_bundle(self):
        old = self.install()['bundle_sha256']
        (self.source / 'new.txt').write_text('new')
        real_rename = distribution.os.rename
        def fail_stage(source, target):
            if Path(source).name.startswith('.atm-oversight-stage-'):
                raise OSError('simulated publication failure')
            return real_rename(source, target)
        with patch.object(distribution.os, 'rename', side_effect=fail_stage):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(distribution.verify(self.target)['bundle_sha256'], old)

    def test_corrupt_receipt_is_not_trusted(self):
        self.install()
        path = self.target / distribution.RECEIPT
        data = json.loads(path.read_text())
        data['bundle_sha256'] = 'incorrect'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.install()

    def test_archive_cannot_be_discovered_as_a_skill(self):
        with self.assertRaises(ValueError):
            distribution.install(self.source, self.target, self.target.parent / 'archive')

    def test_partial_copy_keeps_old_installation(self):
        old = self.install()['bundle_sha256']
        (self.source / 'new.txt').write_text('new')
        with patch.object(distribution.shutil, 'copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(distribution.verify(self.target)['bundle_sha256'], old)

    def test_entire_bundle_runs_without_source_checkout(self):
        distribution.install(ROOT / 'skills/atm-oversight', self.target, self.archive)
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(self.target / 'tests'), '-q'],
                                cwd=self.root, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('OK', result.stderr)


if __name__ == '__main__':
    unittest.main()
