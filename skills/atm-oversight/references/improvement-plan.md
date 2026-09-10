# Monitoring implementation and rollout

## Repository layers

1. **Cron scripts:** small deterministic collectors and checks, structured
   output, bounded execution, isolated source failures, and extensive unit
   tests. They retain state and provide evidence for reports and escalation.
2. **Oversight skills and scripts:** render reports, retrieve tagged work
   records, mine dialogue on demand, investigate repeated QA rounds, and choose
   interventions with evidence. They use the same collected state as cron.
3. **Repository improvements:** conventions, template adjustments, validators,
   hooks, and small ATM query changes where needed to improve data coverage.
   These are rolled out with audits and tests, not inferred from empty queries.

## Storage and scale stages

| Stage | Scope | Storage |
|---|---|---|
| Prototype | A couple of teams on one computer | JSON in a temporary state directory |
| Local operation | 5–10 teams on one computer | SQLite |
| Later expansion | About 30 teams across computers | Server database |

Multiple-computer collection and transport are deferred. Keep the collector
output and record identity independent of storage. Store observation time,
source time where provided, source health, and enough evidence to explain a
reported state. Do not present first observation as the actual work start time.
Temporary-directory state may disappear; the prototype must report a fresh
start and rediscover work rather than pretend it has retained history.

## Delivery sequence

1. Establish a tested collector contract and a local JSON monitoring tick.
   Verify on atm-dev without changing tasks or sending interventions. Add a
   second selected team after the first team's records are understood.
2. Discover phases from activity and structured assignment/plan records.
   Preserve discovered phases through quiet periods. Join sprints to worktrees,
   branch history, stacked PRs, and CI. Resolve the tag selector/runtime gap
   documented in the query survey before treating absence as no work.
3. Produce the existing five-column sprint report from sourced facts. Add
   bounded mining tools for the oversight agent to investigate findings and
   repeated QA. Integrate the selected Telegram gateway for report requests
   and escalation; delivery failures stay visible.
4. Run continuously with explicit polling intervals, overlap protection,
   source timeouts, alert deduplication, and persisted intervention outcomes.
   Verify recovery from process restart and missing/corrupt state. Exercise
   an overnight pilot and inspect its output before claiming sustained reliability.
5. Audit naming and template consistency in target repositories. Roll out
   conventions and hooks while preserving existing gates. Correct structured
   assignment coverage and project-plan references at their source.
6. Move the same state contract to SQLite when expanding to 5–10 local teams.
   Verify migration and report parity. Plan server storage and multi-computer
   operation when that stage is requested.

## Test requirements

Cron scripts need heavy unit testing, including malformed output, empty valid
results, timeout/nonzero exit, partial source failure, stale observations,
identity isolation, duplicate/reordered events, and restart recovery. State
updates must be atomic; concurrent ticks must not overwrite one another.
Report tests must distinguish unknown, queued, blocked, complete, and failed
CI without guessing from an unrelated signal.

Hook tests must use actual temporary Git repositories: staged versus working
content, outgoing ref versus checkout, renamed files, new branches, deletions,
and multiple pushed refs. Live validation remains read-only unless a concrete
change or intervention is part of the current rollout.

## Current deliverables

- [Monitoring workflow](monitoring-workflow.md): user requirements and discovery model.
- [Query survey](query-survey.md): observed interfaces and coverage gaps.
- [Naming conventions](naming-conventions.md): proposed naming and hook rollout.
- `scripts/check_naming.py`, `scripts/plan_metadata.py`, and `assets/hooks/`: initial
  naming validator and hook entrypoints, with snapshot tests in `tests/`.
- `scripts/cron/`: independent collectors, JSON state/recovery, one-shot tick,
  phase discovery through PR/plan associations, and routed health findings.
  `detect_activity.py` maintains a watch list from a configured team catalog;
  `monitor_phase.py` performs team-specific collection for watched teams and
  emits findings. Their silent-success/attention/failure/overlap contract is
  documented in [installation](installation.md), with a separate Hermes adapter.
- `scripts/oversight/`: report rendering, bounded message mining, and
  intervention checkpoints; `SKILL.md` and `references/` describe their operational use.
- The source repo's `.github/workflows/tests.yml`: Linux/macOS/Windows unit-test matrix on
  Python 3.11 and 3.13, without service credentials.

The naming checker does not yet enforce project-index completeness, assignment
schema coverage, or duplicate sprint identities across every plan. Those checks
belong to the rollout work above and should have concrete fixtures before
becoming gates.

## Highest-impact near-term improvements

| Priority | Improvement | Completion evidence |
|---|---|---|
| 1 | Close structured-discovery gaps: assignments, plan/worktree fields, task IDs, and actual installed tag/query behavior | The same live phase joins correctly through assignment, plan, task events, and PRs; deliberately missing metadata reports a gap |
| 2 | Enable the selected Telegram/ATM gateway with the explicit notification policy | A controlled failure routes correctly, each delivery has a receipt, unchanged incidents deduplicate, and healthy ticks send nothing |
| 3 | Prove recovery and continuous operation | Fault tests plus an overnight pilot: source outage, restart, disappearing worktree, partial results, and failed delivery recover without manual state repair |
| 4 | Add collector-specific polling schedules and focused refresh of retained PRs | Idle teams avoid repeated expensive queries; a slow team does not starve another; old tracked PRs remain current despite bounded discovery pages |
| 5 | Adopt naming and project/assignment schema checks in one active phase | Existing hooks preserved; one template change produces queryable, consistent records and passes the monitor's join tests |
| 6 | Move state to SQLite at the 5–10 local-team stage | Import JSON, compare reports/history, exercise rollback and recovery, and verify per-team identity isolation |

## OTel: monitor health first

Use ATM's existing telemetry where it can answer these questions before adding
another collector. Keep JSON state authoritative for the prototype; telemetry
export failure must not block ticks, state commits, or reports.

High-impact metrics: last successful tick time/age, tick duration, collector
duration/error/timeout counts, stale-source count, task-event backlog, unresolved
association count, notification delivery failures, and time from finding to
acknowledgment/resolution. These expose silent breakage and the time Rand spends
recovering it. Polling output already carries durations, statuses, timestamps,
deferred event counts, and discovery diagnostics.

Use one span per tick with child spans for each source query and delivery
attempt. Put task/PR/message IDs on diagnostic spans, not high-cardinality
metric labels. Bound labels to collector, result, and configured team; exclude
message bodies and credentials. Link to ATM trace IDs when its API exposes
them, rather than creating a competing task history.

Before enabling an exporter, test unavailable and slow collectors, export
queue saturation, disabled export, and restart. The same monitoring result
must persist with telemetry enabled, disabled, or failing. Multi-computer
collection/transport and server-database design remain deferred.
