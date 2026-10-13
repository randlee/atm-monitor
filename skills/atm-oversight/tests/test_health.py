import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'cron'))
sys.path.insert(0, str(ROOT / 'scripts' / 'oversight'))
from check_health import evaluate
from state_store import locked, save, read_latest
from record_intervention import record
from tick import run_tick


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.pr = {'number': 1, 'headRefOid': 'abc', 'headRefName': 'feature/a', 'state': 'OPEN',
                   'mergeable': 'UNKNOWN', 'mergeStateStatus': 'UNKNOWN',
                   'statusCheckRollup': [{'name': 'tests', 'conclusion': 'SUCCESS'}]}
        self.snapshot = {'schema_version': 1, 'observed_at': '2026-09-10T00:00:00Z',
                         'teams': [{'name': 'a'}], 'sources': {'a/ci': {'status': 'ok', 'data': [self.pr]}}}

    def test_healthy_and_unknown_mergeability_are_silent(self):
        self.assertEqual(evaluate(self.snapshot), [])

    def test_cli_rejects_future_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            future = copy.deepcopy(self.snapshot)
            future['observed_at'] = '2999-01-01T00:00:00Z'
            with locked(directory):
                save(directory, future)
            script = ROOT / 'scripts' / 'cron' / 'check_health.py'
            result = subprocess.run([sys.executable, str(script), '--state-dir', directory],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)['status'], 'unavailable')

    def test_ci_failure_routes_only_to_lead(self):
        self.pr['statusCheckRollup'][0]['conclusion'] = 'FAILURE'
        finding = evaluate(self.snapshot)[0]
        self.assertEqual(finding['routes'], ['team-lead@a'])
        self.assertEqual(finding['kind'], 'ci-failure')

    def test_confirmed_conflict_routes_to_lead(self):
        self.pr['mergeable'] = 'CONFLICTING'
        self.assertEqual(evaluate(self.snapshot)[0]['routes'], ['team-lead@a'])

    def test_behind_is_not_conflict_or_rule_violation(self):
        self.pr['mergeStateStatus'] = 'BEHIND'
        finding = evaluate(self.snapshot)[0]
        self.assertEqual(finding['kind'], 'merge-blocked')
        self.assertEqual(finding['routes'], ['team-lead@a'])

    def test_merge_problems_route_to_lead_with_or_without_stack(self):
        for in_stack in (False, True):
            for status in ('DIRTY', 'BLOCKED', 'BEHIND', 'UNSTABLE'):
                with self.subTest(in_stack=in_stack, status=status):
                    self.pr['mergeStateStatus'] = status
                    self.snapshot['sources']['a/stack/worktree'] = {
                        'status': 'ok', 'data': {'branches': [
                            {'name': 'feature/a', 'needsRebase': False}]} if in_stack else None}
                    findings = evaluate(self.snapshot)
                    self.assertEqual(len(findings), 1)
                    self.assertEqual(findings[0]['routes'], ['team-lead@a'])
                    self.assertEqual(findings[0]['pending_routes'], ['team-lead@a'])

    def test_merged_and_closed_prs_do_not_raise_merge_blockers(self):
        self.pr['mergeStateStatus'] = 'BLOCKED'
        for state in ('MERGED', 'CLOSED'):
            self.pr['state'] = state
            self.assertEqual(evaluate(self.snapshot), [])

    def test_missing_stack_heads_preserve_maintenance_and_deduplicate(self):
        from collectors import collect
        import json
        import subprocess
        data = {'trunk': 'integrate/phase-ba', 'branches': [
            {'name': 'feature/ba2-task-identity-queue', 'needsRebase': False, 'isMerged': False},
            {'name': 'feature/ba3-nudge-invariant', 'needsRebase': True, 'isMerged': False,
             'pr': {'number': 1402, 'state': 'OPEN'}},
            {'name': 'feature/merged', 'needsRebase': True, 'isMerged': True}]}
        source = collect('stack', run=lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, json.dumps(data), ''))
        self.snapshot['sources']['a/stack/ba2'] = source
        self.snapshot['sources']['a/stack/ba3'] = copy.deepcopy(source)
        findings = evaluate(self.snapshot)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], 'stack-maintenance')
        self.assertEqual(findings[0]['routes'], ['team-lead@a'])
        self.assertIsNone(findings[0]['evidence']['head'])
        self.assertEqual(findings[0]['evidence']['pr']['number'], 1402)

    def test_stack_maintenance_alone_does_not_notify_operator(self):
        source = {'status': 'ok', 'data': {'branches': [
            {'name': 'feature/a', 'head': 'abc', 'needsRebase': True, 'isMerged': False}]}}
        self.snapshot['sources']['a/stack/worktree1'] = source
        self.snapshot['sources']['a/stack/worktree2'] = copy.deepcopy(source)
        findings = evaluate(self.snapshot)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['routes'], ['team-lead@a'])

    def test_order_violation_notifies_team_and_operator(self):
        self.pr.update(state='MERGED', mergedAt='2026-09-10T02:00:00Z')
        child = dict(self.pr, number=2, headRefName='feature/b', mergedAt='2026-09-10T01:00:00Z')
        self.snapshot['sources']['a/ci']['data'].append(child)
        self.snapshot['tracked_sprints'] = {'a': {'AZ/AZ.1': {'branch': 'feature/a'},
                                                'AZ/AZ.2': {'branch': 'feature/b', 'integration_branch': 'feature/a'}}}
        finding = evaluate(self.snapshot)[0]
        self.assertEqual(finding['routes'], ['team-lead@a', 'operator:telegram'])
        self.assertEqual(finding['severity'], 'serious')
        self.pr['mergedAt'] = child['mergedAt']
        self.assertEqual(evaluate(self.snapshot), [])

    def test_missing_parent_does_not_prove_wrong_merge_order(self):
        self.pr.update(state='MERGED', mergedAt='2026-09-10T01:00:00Z')
        self.snapshot['tracked_sprints'] = {'a': {'AZ/AZ.1': {'branch': 'feature/a', 'integration_branch': 'missing'}}}
        self.assertEqual(evaluate(self.snapshot), [])

    def test_final_phase_integration_pr_correctly_merges_after_sprints(self):
        self.pr.update(state='MERGED', mergedAt='2026-09-10T01:00:00Z')
        integration = dict(self.pr, number=2, headRefName='integrate/phase-az', mergedAt='2026-09-10T02:00:00Z')
        self.snapshot['sources']['a/ci']['data'].append(integration)
        self.snapshot['tracked_sprints'] = {'a': {'AZ/AZ.1': {'branch': 'feature/a', 'integration_branch': 'integrate/phase-az'}}}
        self.assertEqual(evaluate(self.snapshot), [])

    def test_total_observability_failure_is_serious(self):
        for key in ('herdr', 'a/roster', 'a/tasks'):
            self.snapshot['sources'][key] = {'status': 'unavailable'}
        finding = evaluate(self.snapshot)[0]
        self.assertEqual(finding['kind'], 'monitor-blind')
        self.assertEqual(finding['routes'], ['operator:telegram'])

    def test_delivered_route_is_suppressed_ack_is_not_resolution(self):
        self.pr['mergeable'] = 'CONFLICTING'
        incident = evaluate(self.snapshot)[0]['incident_key']
        self.snapshot['interventions'] = {incident: {'team-lead@a': {'status': 'acknowledged'}}}
        finding = evaluate(self.snapshot)[0]
        self.assertEqual(finding['pending_routes'], [])
        self.assertEqual(finding['kind'], 'merge-conflict')
        self.snapshot['interventions'][incident]['team-lead@a']['status'] = 'resolved'
        self.assertEqual(evaluate(self.snapshot)[0]['pending_routes'], ['team-lead@a'])

    def test_new_head_gets_new_incident(self):
        self.pr['mergeable'] = 'CONFLICTING'
        old = evaluate(self.snapshot)[0]['incident_key']
        self.pr['headRefOid'] = 'def'
        self.assertNotEqual(old, evaluate(self.snapshot)[0]['incident_key'])

    def test_operator_delivery_remains_pending_when_only_team_was_notified(self):
        self.pr.update(state='MERGED', mergedAt='2026-09-10T02:00:00Z')
        child = dict(self.pr, number=2, headRefName='feature/b', mergedAt='2026-09-10T01:00:00Z')
        self.snapshot['sources']['a/ci']['data'].append(child)
        self.snapshot['tracked_sprints'] = {'a': {'AZ/AZ.1': {'branch': 'feature/a'},
                                                'AZ/AZ.2': {'branch': 'feature/b', 'integration_branch': 'feature/a'}}}
        incident = evaluate(self.snapshot)[0]['incident_key']
        self.snapshot['interventions'] = {incident: {'team-lead@a': {'status': 'sent'}}}
        self.assertEqual(evaluate(self.snapshot)[0]['pending_routes'], ['operator:telegram'])

    def test_recorded_intervention_survives_tick(self):
        with tempfile.TemporaryDirectory() as directory:
            with locked(directory):
                save(directory, self.snapshot)
            record(directory, 'incident', 'team-lead@a', 'sent', 'actual-message-id')
            config = {'teams': [{'name': 'a', 'repo': directory, 'worktrees': []}]}
            run_tick(config, directory, collector=lambda *a, **k: {'status': 'ok', 'data': []})
            state, _ = read_latest(directory)
            self.assertEqual(state['interventions']['incident']['team-lead@a']['evidence_id'], 'actual-message-id')
            self.assertEqual(len(state['intervention_history']), 1)

    def test_retention_keeps_newest_complete_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            with locked(directory):
                for _ in range(4):
                    save(directory, self.snapshot, retain=2)
            self.assertEqual(len(list((Path(directory) / 'snapshots').glob('*.json'))), 2)
            self.assertEqual(read_latest(directory)[0]['sequence'], 4)


if __name__ == '__main__':
    unittest.main()
