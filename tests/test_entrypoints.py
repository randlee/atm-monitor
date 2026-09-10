from pathlib import Path
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EntrypointTests(unittest.TestCase):
    def test_report_outputs_utf8_even_with_ascii_stdout_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'snapshots'
            folder.mkdir()
            data = {'schema_version': 1, 'observed_at': '2026-09-10T00:00:00Z',
                    'teams': [{'name': 'a'}], 'sources': {'a/ci': {'status': 'ok', 'data': []}},
                    'tracked_sprints': {'a': {}}}
            (folder / '000000000001.json').write_text(json.dumps(data), encoding='utf-8')
            env = dict(os.environ, PYTHONIOENCODING='ascii')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/oversight/report.py'),
                                     '--state-dir', directory, '--team', 'a'],
                                    capture_output=True, env=env, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('—', result.stdout.decode('utf-8'))

    def test_cli_help_loads_without_services_or_credentials(self):
        paths = [ROOT / 'scripts' / 'check_naming.py']
        paths += list((ROOT / 'scripts' / 'cron').glob('collect_*.py'))
        paths += [ROOT / 'scripts' / 'cron' / name for name in ('tick.py', 'check_health.py')]
        paths += list((ROOT / 'scripts' / 'oversight').glob('*.py'))
        for path in paths:
            with self.subTest(path=path.name):
                result = subprocess.run([sys.executable, str(path), '--help'],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout.lower())

    def test_skill_entrypoints_and_local_reference_links(self):
        paths = sorted((ROOT / 'skills').glob('*/SKILL.md'))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding='utf-8')
                self.assertTrue(text.startswith('---\n'))
                frontmatter = text.split('---', 2)[1]
                self.assertRegex(frontmatter, r'(?m)^name: [a-z0-9-]+$')
                self.assertRegex(frontmatter, r'(?m)^description: .+')
                for target in re.findall(r'\]\(([^)]+)\)', text):
                    if '://' not in target:
                        self.assertTrue((path.parent / target.split('#')[0]).exists(), target)


if __name__ == '__main__':
    unittest.main()
