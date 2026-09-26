import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from source_lines import count_source


class SourceLimitTests(unittest.TestCase):
    def test_comments_blanks_and_strings(self):
        self.assertEqual(count_source('a.py', b'# comment\n\nx = "# text" # comment\n'), 1)
        self.assertEqual(count_source('a.ts', b'/* comment\ncomment */\nlet x = "//text";\n'), 1)
        self.assertEqual(count_source('a.sh', b'# comment\necho "#text"\n'), 1)

    def test_index_boundary_and_push_commits(self):
        with tempfile.TemporaryDirectory() as folder:
            def git(*args, data=None):
                return subprocess.check_output(['git', *args], cwd=folder, input=data,
                    stderr=subprocess.DEVNULL)
            git('init')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            path = Path(folder) / 'query.py'
            path.write_text('x = 1\n' * 100 + '# comment\n' * 20)
            git('add', 'query.py')
            def check(mode, data=None):
                return subprocess.run([sys.executable, str(ROOT / 'scripts/check_source_limit.py'),
                    mode, 'origin'], cwd=folder, input=data, capture_output=True, text=True)
            self.assertEqual(check('commit').returncode, 0)
            path.write_text('x = 1\n' * 101)
            self.assertEqual(check('commit').returncode, 0)  # Reads index, not worktree.
            git('add', 'query.py')
            result = check('commit')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('101 source lines', result.stderr)
            # Build an isolated fixture object to exercise push rejection.
            tree = git('write-tree').decode().strip()
            commit = git('commit-tree', tree, data=b'fixture\n').decode().strip()
            update = f'refs/heads/test {commit} refs/heads/test {"0" * 40}\n'
            self.assertNotEqual(check('push', update).returncode, 0)
            path.write_text('x = 1\n')
            git('add', 'query.py')
            tree = git('write-tree').decode().strip()
            good = git('commit-tree', tree, data=b'good\n').decode().strip()
            update = f'refs/heads/test {good} refs/heads/test {"0" * 40}\n'
            self.assertEqual(check('push', update).returncode, 0)
            deletion = f'(delete) {"0" * 40} refs/heads/test {good}\n'
            self.assertEqual(check('push', deletion).returncode, 0)


if __name__ == '__main__':
    unittest.main()
