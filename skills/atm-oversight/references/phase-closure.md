# Phase closure and repository ownership

This is the manual procedure until scheduler, ownership-registry, and phase
projection integration exists. It uses the configured deployment scheduler and
the existing read-only collectors; it does not invent commands or claim that a
job is running when no scheduler receipt exists.

## Lifecycle contract

Use these states in order when evidence supports them:

`activity-detected` → `new-phase-planned` → `active-development` →
`integration-closed`.

`activity-detected` is only a candidate observation. Structured planning
metadata, a phase-bound assignment/plan, or a qualifying planning branch must
establish `new-phase-planned`; that handoff starts one repo-specific cron and
does not mean the plan is ready. Development assignment or work evidence
establishes `active-development`.

The integration closure must identify the exact `integrate/*` source/head
branch, repository and phase, unique PR number/URL, full head SHA, and the PR's
terminal closed timestamp and outcome. A closed but unmerged PR is terminal
closure evidence but is not successful integration/merge evidence. An
abandoned or superseded phase has no required integration PR: Omega-prime may manually close it and
records the closing actor, reason, timestamp, and supporting evidence.
Preserve the final report evidence and its coverage failures in an immutable
snapshot outside routine snapshot retention. For each pending incident, retain its owner and next action or record an
explicit disposition. Acknowledgment alone is not resolution, and closure
does not silently resolve incidents.

A closed but unmerged integration PR remains separate from successful merge
evidence. Reopening, superseding, and abandoning a phase are explicit events
that reference the prior closure or pending disposition.

## Stop and release ordering

1. Run one final repository observation. Preserve PR heads/checks, sprint and
   phase associations, task/event history, source timestamps, and all
   unavailable or partial sources.
2. Append the closure or disposition event to the durable phase
   journal. Apply the current-state projection only after the event is
   durably written; advance source checkpoints after the projection. Replays
   must reuse event identity, and missing source history becomes a coverage-gap
   event rather than a guessed transition.
3. If no phase in the repository remains open, stop the one repo scheduler job.
   Persist the scheduler's stopped receipt before releasing repository
   ownership. An individual phase closure leaves that shared job running while
   any other phase remains open.
4. Advance the durable discovery checkpoint only after the stop/release
   observation succeeds. A restart must not retrigger historical activity or
   recreate the closed phase. If another phase remains open, retain the repo
   job and its ownership; close only the individual phase scope.

An unavailable source, an empty queue, an idle agent, disappearing worktree, or
all currently discovered PRs being merged is not closure evidence. Record the
coverage gap and keep the phase in its prior state unless independent closure evidence or an explicit manual closure decision
establishes the lifecycle outcome. An outage cannot veto an authoritative
closure, but unfinished final collection remains a recorded follow-up.

Manual closure is the alternate terminal state `manually-closed`; it must not
claim integration occurred. Use outcome `abandoned`, `superseded`, or an
explicitly evidenced `complete`. Reopening either terminal state requires a
new event referencing the closure and resumes the shared cron if necessary.

For a manual abandonment, prepare an event file such as (replace all example
identities, timestamps, and references with the actual decision):

```json
{
  "event_id": "phase-BB-closed-abandoned-2026-09-12T20:00:00Z",
  "team": "atm-dev",
  "repo": "/path/to/atm-core",
  "phase": "BB",
  "kind": "phase_closed",
  "occurred_at": "2026-09-12T20:00:00Z",
  "evidence": ["decision:actual-abandonment-record-id"],
  "payload": {
    "actor": "omega-prime",
    "reason": "phase work abandoned; see referenced decision",
    "outcome": "abandoned",
    "from": "active-development",
    "to": "manually-closed"
  }
}
```

Append and inspect it with the existing helper:

```sh
python scripts/oversight/phase_events.py append \
  --state-dir /path/to/phase-event-log --event-file /path/to/phase-closed.json
python scripts/oversight/phase_events.py list \
  --state-dir /path/to/phase-event-log --team atm-dev --phase BB --json
```

The append records the closure decision in the journal. It does not edit
deployment config, stop a scheduler job, release repository ownership, or
advance a projection automatically; those actions remain manual until runtime
integration is implemented.

## Current capability boundary

The repository currently provides read-only collection, onboarding settings,
and the append-only phase-event helper. Automatic lifecycle emission,
projection/checkpoint integration, durable ownership states, scheduler
provisioning/stopping, and protected final-report archiving are not implemented
by these scripts. Until those integrations exist, Omega-prime must record the
evidence and exact external scheduler receipts explicitly, or return the
handoff as pending. Do not use a proposed cron line or a saved config as proof
of active or stopped monitoring.
