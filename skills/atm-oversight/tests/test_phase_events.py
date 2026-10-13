import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'scripts' / 'oversight'))
from phase_events import append, list_events


class PhaseEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'phase-log'

    def event(self, **changes):
        event = {'event_id': 'evt-1', 'team': 'alpha', 'repo': 'repo-a', 'phase': 'J2',
                 'kind': 'planning_started', 'occurred_at': '2026-09-12T12:00:00Z',
                 'evidence': ['branch:planning/j2'], 'payload': {}}
        event.update(changes)
        return event

    def test_durable_sequence_and_order(self):
        first = append(self.directory, self.event())
        second = append(self.directory, self.event(event_id='evt-2', kind='hardening_iteration_started',
                                                    payload={'iteration_id': 'i-1'}))
        self.assertEqual([row['seq'] for row in (first, second)], [1, 2])
        self.assertEqual([row['event_id'] for row in list_events(self.directory)], ['evt-1', 'evt-2'])
        self.assertTrue((self.directory / 'events/000000000001.json').exists())

    def test_same_id_replays_and_conflict_rejects(self):
        stored = append(self.directory, self.event())
        self.assertEqual(append(self.directory, self.event()), stored)
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            append(self.directory, self.event(kind='plan_ready'))
        self.assertEqual(len(list_events(self.directory)), 1)

    def test_filters_isolate_team_repo_and_phase(self):
        append(self.directory, self.event())
        append(self.directory, self.event(event_id='evt-2', team='beta'))
        append(self.directory, self.event(event_id='evt-3', phase='J3'))
        self.assertEqual([e['event_id'] for e in list_events(self.directory, team='alpha', phase='J2')], ['evt-1'])
        self.assertEqual([e['event_id'] for e in list_events(self.directory, team='beta')], ['evt-2'])

    def test_invalid_evidence_and_corrupt_log_fail(self):
        with self.assertRaisesRegex(ValueError, 'nonempty array'):
            append(self.directory, self.event(evidence=[]))
        append(self.directory, self.event())
        (self.directory / 'events/000000000001.json').write_text('{', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'corrupt event log'):
            list_events(self.directory)


    def test_invalid_writer_timestamp_prevents_read_and_append(self):
        append(self.directory, self.event())
        path = self.directory / 'events/000000000001.json'
        stored = json.loads(path.read_text())
        for value in ('', 'not-a-date', '2026-09-12T12:00:00'):
            stored['observed_at'] = value
            path.write_text(json.dumps(stored))
            with self.assertRaisesRegex(ValueError, 'writer timestamp'):
                list_events(self.directory)
            with self.assertRaisesRegex(ValueError, 'writer timestamp'):
                append(self.directory, self.event(event_id='evt-2'))

    def test_duplicate_event_ids_in_existing_log_are_corruption(self):
        append(self.directory, self.event())
        second = append(self.directory, self.event(event_id='evt-2'))
        second['event_id'] = 'evt-1'
        (self.directory / 'events/000000000002.json').write_text(json.dumps(second))
        with self.assertRaisesRegex(ValueError, 'duplicate event_id'):
            list_events(self.directory)


if __name__ == '__main__':
    unittest.main()
