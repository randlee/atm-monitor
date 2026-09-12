# ATM Team Monitoring Requirements

## Overview

ATM team monitoring provides visibility into agent fleet activity and task progress. The system exposes five core query primitives for retrieving herdr member activity, ATM team member activity, task event logs, task queues by member, and task state queries.

---

## Query Primitives

The monitor SHALL expose five core query primitives.

### Q1: Herdr Member Activity

Query the Herdr workspace for live agent process state.

- **Q1.1** Input: Herdr workspace ID (optional, defaults to the local workspace).
- **Q1.2** Output: list of agents with `name`, `agent` (harness: claude/codex/etc.), `agent_status` (working/idle/done), `cwd`, `focused`, `terminal_title`, `terminal_title_stripped`, `pane_id`, `workspace_id`, `revision`, `state_change_seq`.
- **Q1.3** This query hits the Herdr API directly (`herdr agent list` or equivalent HTTP endpoint). It does NOT go through the ATM daemon.
- **Q1.4** Results reflect the agent's actual process state at the time of the Herdr poll, not the ATM roster's cached interpretation.
- **Q1.5** If the Herdr API is unreachable, the query SHALL return `unavailable` for all agents, not `offline`.

### Q2: ATM Team Member Activity

Query the ATM daemon for the team's roster membership and observed status.

- **Q2.1** Input: team name.
- **Q2.2** Output: list of team members with `id` (agent@team), `name`, `status` (active/idle/blocked/offline/unknown/unavailable), `host`, `cwd`, `observed_at`, `state_changed_at`.
- **Q2.3** This query reads from the canonical runtime roster record (the single ephemeral master-roster record established by issue #1378 / PR #1381). It does NOT run the full doctor pipeline.
- **Q2.4** The status values SHALL reflect the latest Herdr poll observation projected through the roster, per the fix in PR #1381.
- **Q2.5** If the daemon is unreachable, the query SHALL return `unavailable` for the entire team with a diagnostic, not `dead` for each member.
- **Q2.6** The query SHALL be team-scoped: it SHALL NOT return members from other teams, even if agent names overlap.

### Q3: Task Event Log

Query the ATM daemon for the chronological event log of task state transitions.

- **Q3.1** Input: team name, optional filters (agent, task_id, event type, time range).
- **Q3.2** Output: ordered list of task events with `team`, `task_id`, `assignee`, `seq`, `at` (timestamp), `event` (assigned/activated/completed/etc.), `from_state`, `to_state`, `actor`, `message_id`, `outcome`, `detail`.
- **Q3.3** This query reads from the `task_events` table in the ATM daemon database (read-only).
- **Q3.4** Results SHALL be ordered by `at` descending (most recent first) by default, with an `--oldest-first` flag for chronological order.
- **Q3.5** The query SHALL support pagination for large event logs (default page size: 100 events).
- **Q3.6** The query SHALL support filtering by event type (e.g., only `assigned` events, only state transitions).
- **Q3.7** The query SHALL support time-range filtering (e.g., events in the last hour, since a specific timestamp).

### Q4: Task Queue (by Member)

Query the ATM daemon for the current task assignments grouped by team member.

- **Q4.1** Input: team name, optional filter (specific agent).
- **Q4.2** Output: map of agent → list of tasks, where each task includes `task_id`, `state` (assigned/active/complete/blocked), `assigner`, `assigned_at`, `updated_at`, `description` (summary), `reminder_count`, `lead_notified_count`.
- **Q4.3** This query reads from the `tasks` table in the ATM daemon database (read-only).
- **Q4.4** The query SHALL group tasks by assignee, showing each agent's current workload.
- **Q4.5** The query SHALL support filtering by task state (e.g., only `active` tasks, only incomplete tasks).

### Q5: Task State Queries

Query the ATM daemon for specific task state by task ID or by state.

- **Q5.1** Input: team name, and one of:
  - task_id (exact lookup)
  - state filter (e.g., all `active` tasks, all `blocked` tasks)
  - assignee filter (all tasks for a specific agent)
- **Q5.2** Output: list of matching tasks with full state: `task_id`, `assignee`, `assigner`, `state`, `assignment_message_id`, `description`, `assigned_at`, `updated_at`, `last_reminded_at`, `reminder_count`, `lead_notified_count`.
- **Q5.3** This query reads from the `tasks` table in the ATM daemon database (read-only).
- **Q5.4** The query SHALL support compound filters (e.g., all `active` tasks for agent `arch-ctm`).
- **Q5.5** The query SHALL return the full task record, not a summary, to support diagnostic use cases.
- **Q5.6** The query SHALL support `--with-events` flag to include the task's event log (Q3) inline with each task record.

---

## Query Composition

- **QC-1** All five queries SHALL support `--json` output for machine consumption.
- **QC-2** Queries SHALL be composable: an operator can run Q1 and Q2 side-by-side to compare Herdr process state vs. ATM roster state, surfacing discrepancies.

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.2.0 | 2026-09-10 | omega-prime | Removed unapproved features (FR-1 through FR-5, FR-7, NFR-1 through NFR-4, IR-1 through IR-3, Constraints, Out of Scope, Open Questions) |
| 0.1.0 | 2026-09-10 | omega-prime | Initial draft |

## Notable-event agent triggering (Rand, September 12)

- The phase cron continuously records all development assignments/activity and
  per-sprint B/C/I findings with evidence, round identity, and coverage.
- Routine ticks do not invoke an agent. Only notable events requiring action
  trigger oversight: CI becoming failed, a new merge block/conflict, or an idle
  agent still owning an active task are examples.
- Detect edges against durable prior evidence; deduplicate pending/handled
  handoffs across ticks/restarts independently of outbound delivery receipts.
- A persistent unchanged condition stays silent. Recovery/recurrence, a
  material escalation, or an explicit follow-up deadline can justify another
  wake. Query failure does not establish recovery.
- Fresh identity and assignment evidence distinguish actionable idle-with-task
  from ordinary idle. Findings absent from unavailable reports remain unknown.

The deployed skill's notification policy defines this gate. Full runtime wake
integration and idle-with-active-task detection are outstanding implementation.

## Immediate whole-phase reporting (Rand, September 12)

At any time, Rand can request a report of the entire phase and every sprint.
Return the latest recorded state without waiting for a cron tick or requiring
full live recollection. Identify the phase, lifecycle, planning/hardening
milestones, and completion/disposition evidence. For every sprint in the phase
plan show status, owner and current assignments, development/QA/CI state,
B/C/I finding counts, blockers, latest activity, and evidence references.

The plan supplies the sprint inventory, including future/unstarted sprints and
sprints without PR/task evidence. Retain completed/abandoned/superseded history.
Each report states its as-of time and source freshness/coverage; unavailable
facts remain unknown. Counts must not double-count recurring review findings.
An explicit report request is independent of the cron notable-event wake gate.

The current report.py renders discovered sprint evidence, not this complete
phase projection. Full planned-sprint inventory, lifecycle/metrics/findings
projection, and retained closed-phase reports remain implementation work.

## Operational ownership and excessive triggering

Omega-prime must act from maintained skills without step-by-step direction from
Rand. Excessive/unjustified/duplicate wakes escalate to the atm-monitor
maintainer (`amon@atm-monitor`), who diagnoses and fixes scripts/skills and
verifies deployment. Include stable wake/event IDs, reason, timing, repository,
phase, previous handling state, and bundle version. Deduplicate the defect
report to avoid an escalation loop. Do not suppress the required monitoring job
or route tooling diagnosis back to Rand. Project decisions remain separate.

Durable wake auditing and automatic excessive-trigger detection are remaining
runtime requirements; manual observed-defect reporting uses the same route.
