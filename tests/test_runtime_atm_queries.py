import json, sys, os, subprocess, tempfile, unittest
from pathlib import Path

RUNTIME = Path(__file__).parents[1] / 'skills/atm-oversight/scripts/runtime'
sys.path.insert(0, str(RUNTIME))
from atm_tasks import parse_tasks
from atm_workflow import parse_events
from atm_members import parse_members
from herdr_agents import parse_agents
from git_sprints import parse_plan, query
from query_types import Ok, Partial
from report_parse import parse_report


def _git_repo(root, files):
    subprocess.run(['git','init','-q','-b','main',str(root)],check=True)
    env=dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
             GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    for rel, text in files.items():
        p=root/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
    subprocess.run(['git','-C',str(root),'add','-A'],check=True,env=env)
    subprocess.run(['git','-C',str(root),'commit','-qm','plan'],check=True,env=env)
    return subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],
                          capture_output=True,text=True,check=True).stdout.strip()


class SprintInventoryTests(unittest.TestCase):
    def test_atm_core_style_frontmatter_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'bb'
            files={'docs/plans/phase-bb/phase-bb-plan.md':'# plan\n'}
            for i in range(1,8):
                files[f'docs/plans/phase-bb/sprint-BB.{i}-name.md']=f'---\nphase: BB\nsprint: BB.{i}\nbranch: feature/bb{i}-name\nstatus: active\n---\nbody\n'
            rev=_git_repo(root,files)
            result=query(str(root),rev,'docs/plans/phase-bb/phase-bb-plan.md',timeout=15)
        self.assertIsInstance(result,Ok)
        self.assertEqual(len(result.data),7)
        self.assertEqual(result.data[0].branch,'feature/bb1-name')

    def test_sc_obs_style_bullets_exclude_sanity_and_keep_parent_target(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'d'
            files={'docs/plans/phase-d/plan-phase-d.md':'# Phase D plan\n'}
            for n in (1,2,3):
                files[f'docs/plans/phase-d/sprint-d-{n}-s.md']=(
                    f'# d-{n}: t\n\n## Plan metadata\n\n'
                    f'- Wave: 1\n- Branch: `sprint/d-{n}-s`\n'
                    f'- PR target (merge order only): `integrate/phase-d`\n- Status: planned\n\nbody\n')
                files[f'docs/plans/phase-d/sprint-d-{n}-sanity-x.md']='- Branch: `sprint/dx`\n'
            rev=_git_repo(root,files)
            result=query(str(root),rev,'docs/plans/phase-d/plan-phase-d.md',timeout=15,expected_sprints=3)
            self.assertIsInstance(result,Ok)
            self.assertEqual({s.sprint for s in result.data},{'D.1','D.2','D.3'})
            self.assertEqual(result.data[0].branch,'sprint/d-1-s')
            self.assertEqual(result.data[0].integration_branch,'integrate/phase-d')
            short=query(str(root),rev,'docs/plans/phase-d/plan-phase-d.md',timeout=15,expected_sprints=2)
        self.assertIsInstance(short,Partial)
        self.assertEqual(short.problems[0].kind,'incomplete-plan-inventory')
        self.assertEqual(len(short.data),3)

class RuntimeQueryTests(unittest.TestCase):
    def test_parsers_keep_typed_immutable_records(self):
        task, more = parse_tasks(json.dumps({'tasks': [{'id':'T1','assignee':'dev','status':'queued'}]}))
        self.assertEqual(task[0].task_id, 'T1')
        self.assertFalse(more)
        self.assertEqual(parse_events('[{"id":"e1","workflow_scope":{"id":"P.1"}}]')[0][0].sprint, 'P.1')
        self.assertTrue(parse_members('[{"id":"a","observed_at":"2026-01-01T00:00:00Z"}]')[0].observed_at.startswith('2026'))
        self.assertEqual(parse_agents('[{"name":"omega","state":"working"}]')[0].agent_id, 'omega')

    def test_herdr_snapshot_uses_retrieval_anchor_without_inventing_state_time(self):
        agent = parse_agents('{"result":{"agents":[{"name":"omega","agent_status":"idle"}]}}', '2026-09-13T02:00:00Z')[0]
        self.assertEqual(agent.observed_at, '2026-09-13T02:00:00Z')
        self.assertIsNone(agent.state_since)

    def test_workflow_exposes_report_direction_and_round_metadata(self):
        text = '{"hits":[{"message_id":"m1","template_type":"qa-quality-report","workflow":{"snapshot":{"scope_id":"BB.5","stage":"qa","state":"qa-approved","iteration":"1"}}}]}'
        event = parse_events(text)[0][0]
        self.assertEqual(event.template_type, 'qa-quality-report')
        self.assertEqual(event.workflow_state, 'qa-approved')
        self.assertEqual(event.iteration, '1')

    def test_report_requires_revision_and_preserves_findings(self):
        report=parse_report('{"revision":"abc","round":"C","verdict":"reject","findings":[{"id":"f1","severity":"B"}]}','m1')
        self.assertEqual(report.report_id, 'm1')
        self.assertEqual(report.findings, (('f1','B','open'),))

    def test_prose_report_keeps_revision_and_counts(self):
        report = parse_report('Final Verdict: **PASS**\nQA Pass: 2\nCommit: `abcdef1234567`\n```json\n{"findings":{"blocking":0,"important":1,"minor":0}}\n```', 'm2')
        self.assertEqual(report.round, '2')
        self.assertEqual(report.revision, 'abcdef1234567')
        self.assertIn(('important', 1), report.aggregate)

    def test_plan_supports_explicit_json_inventory(self):
        rows=parse_plan('{"sprints":[{"phase":"BB","sprint":"BB.2","branch":"feature/bb2","order":2}]}')
        self.assertEqual(rows[0].branch, 'feature/bb2')
        self.assertEqual(rows[0].order, 2)
