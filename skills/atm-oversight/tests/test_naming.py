import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from check_naming import check_plan, check_branch
from plan_metadata import read_metadata

PLAN = 'docs/plans/phase-az/sprint-AZ.3-task-handoff.md'
META = '''phase: AZ
sprint: "AZ.3"
branch: feature/az3-task-handoff
worktree: ../demo-worktrees/feature/az3-task-handoff
status: planned
'''


class MetadataTests(unittest.TestCase):
    def test_real_template_layout_and_frontmatter_agree(self):
        self.assertEqual(read_metadata('---\n' + META + '---\n# Plan'),
                         read_metadata('# Plan\n```yaml\n' + META + '```\n## Goal'))

    def test_nested_authority_is_not_identity(self):
        text = '---\n' + META + 'authority:\n  phase: WRONG\n---\n'
        self.assertEqual(check_plan(PLAN, text), [])

    def test_multiple_authorities_and_duplicate_fields_fail(self):
        for text in ['---\n' + META + 'phase: AX\n---',
                     '---\n' + META + '---\n```yaml\n' + META + '```']:
            with self.subTest(text=text):
                self.assertEqual(check_plan(PLAN, text)[0]['code'], 'metadata')

    def test_quoted_hash_and_comment(self):
        text = '---\n' + META.replace('status: planned', 'status: "planned # literal" # note') + '---'
        self.assertEqual(read_metadata(text)['status'], 'planned # literal')

    def test_plan_branch_worktree_mismatch_is_reported(self):
        text = '---\n' + META.replace('feature/az3-task-handoff', 'feature/az2-storage') + '---'
        codes = {e['code'] for e in check_plan(PLAN, text)}
        self.assertEqual(codes, {'sprint-branch', 'worktree'})

    def test_cross_host_paths_do_not_need_to_exist(self):
        for path in ['/work/demo-worktrees/feature/az3-task-handoff',
                     'C:/repos/demo-worktrees/feature/az3-task-handoff']:
            text = '---\n' + META.replace('../demo-worktrees/feature/az3-task-handoff', path) + '---'
            self.assertEqual(check_plan(PLAN, text), [])

    def test_phase_and_sprint_must_agree(self):
        self.assertTrue(check_plan(PLAN, '---\n' + META.replace('phase: AZ', 'phase: AX') + '---'))

    def test_detached_or_non_sprint_branches_are_not_guessed(self):
        self.assertEqual(check_branch('fix/daemon-timeout'), [])
        self.assertEqual(check_branch('integrate/phase-az'), [])
        self.assertTrue(check_branch('feature/Bad_Name'))


class GitSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q', '-b', 'develop')
        self.git('config', 'user.name', 'Naming Test')
        self.git('config', 'user.email', 'naming@example.invalid')
        self.git('config', 'core.hooksPath', str(self.repo / 'disabled-hooks'))
        self.git('commit', '--allow-empty', '--no-gpg-sign', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '-qb', 'feature/az3-task-handoff')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True,
                                       stderr=subprocess.PIPE)

    def put(self, text):
        p = self.repo / PLAN
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def run_check(self, *args, stdin=None):
        p = subprocess.run([sys.executable, str(SCRIPTS / 'check_naming.py'),
                            '--repo', str(self.repo), '--json', *args],
                           input=stdin, text=True, capture_output=True)
        return p.returncode, json.loads(p.stdout)

    def test_unstaged_fix_cannot_hide_bad_staged_content(self):
        self.put('---\n' + META.replace('sprint: "AZ.3"', 'sprint: "AZ.4"') + '---')
        self.git('add', PLAN)
        self.put('---\n' + META + '---')
        code, data = self.run_check('--staged')
        self.assertEqual(code, 1)
        self.assertIn('sprint-id', {e['code'] for e in data['issues']})

    def test_bad_working_copy_cannot_block_good_staged_content(self):
        self.put('---\n' + META + '---')
        self.git('add', PLAN)
        self.put('broken')
        code, data = self.run_check('--staged')
        self.assertEqual(code, 0, data)
        self.assertEqual(data['checked_plans'], 1)

    def test_push_checks_supplied_commit_not_current_checkout(self):
        self.put('---\n' + META.replace('sprint: "AZ.3"', 'sprint: "AZ.4"') + '---')
        self.git('add', PLAN)
        self.git('commit', '--no-gpg-sign', '-qm', 'bad plan')
        sha = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '-q', 'develop')
        line = f'refs/heads/feature/az3-task-handoff {sha} refs/heads/feature/az3-task-handoff {self.base}\n'
        code, data = self.run_check('--pre-push', stdin=line)
        self.assertEqual(code, 1, data)
        self.assertIn('sprint-id', {e['code'] for e in data['issues']})

    def test_new_branch_push_checks_final_tree(self):
        self.put('---\n' + META + '---')
        self.git('add', PLAN)
        self.git('commit', '--no-gpg-sign', '-qm', 'plan')
        sha = self.git('rev-parse', 'HEAD').strip()
        line = f'HEAD {sha} refs/heads/feature/az3-task-handoff {"0" * 40}\n'
        code, data = self.run_check('--pre-push', stdin=line)
        self.assertEqual(code, 0, data)
        self.assertEqual(data['checked_plans'], 1)

    def test_branch_deletion_skips_deleted_ref(self):
        code, data = self.run_check('--pre-push', stdin=f'(delete) {"0" * 40} refs/heads/OLD {self.base}\n')
        self.assertEqual(code, 0, data)

    def test_renamed_plan_is_checked(self):
        old = self.repo / 'docs/plans/phase-az/sprint-old.md'
        old.parent.mkdir(parents=True)
        old.write_text('---\n' + META + '---')
        self.git('add', '.')
        self.git('commit', '--no-gpg-sign', '-qm', 'legacy')
        self.git('mv', str(old.relative_to(self.repo)), PLAN)
        code, data = self.run_check('--staged')
        self.assertEqual(code, 0, data)
        self.assertEqual(data['checked_plans'], 1)

    def test_invalid_repo_does_not_report_healthy(self):
        code, data = self.run_check('--all')
        self.assertEqual(code, 2)
        self.assertEqual(data['status'], 'error')


if __name__ == '__main__':
    unittest.main()
