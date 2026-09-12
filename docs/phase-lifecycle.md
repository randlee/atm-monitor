# Phase lifecycle in oversight

Design response to Omega-prime message `01M2BAQ6K72JJN0A8BA3CANP36`.
Follow-up `01M2BASTQT6B0PMSY29MWAXB07` concerns the same separation.
This records the implementation requirements; runtime support is not yet
implemented and existing deployment phases have not been marked complete.

## Expected discovery and planning flow (Rand)

Rand clarified the required oversight behavior on September 12, 2026. This
flow governs the lifecycle design below; it is not a description of runtime
capabilities already implemented.

1. A general activity-monitoring cron uses deterministic checks to detect
   agents doing new work in a
   repository/team, for example agents working on `atm-core` / `atm-dev`.
2. The cron checks structured message and Git evidence to establish substantive
   planning/development before waking Omega-prime. Casual questions or agent
   activity alone do not trigger an agent. After qualification, oversight
   examines message and Git history to recognize that the team is
   planning its next phase and identify that phase, for example `phase-bb`.
   Discovery must not depend on an existing phase configuration, development
   tasks, or an open PR. Agent activity is the trigger; messages and Git supply
   evidence of the work and its phase identity.
3. That discovery signals Omega-prime to start active monitoring for the
   identified phase. This starts an additional repository-specific cron.
   Pending/active repo ownership suppresses further general-activity wakes.
   The repo-specific cron owns discovery of additional phases for that repo;
   the general activity monitor continues checking other eligible repos.
4. Active phase monitoring begins during planning. It tracks plan hardening,
   including how many iterations occurred, how long hardening took, and when
   the plan became ready for development.

Retain the supporting messages, Git revisions, and timestamps so those
planning milestones and measurements can be explained and checked. A polling
count is not a hardening-iteration count, and a first-observed timestamp must
not silently replace an earlier milestone timestamp established by evidence.
The precise hardening-iteration and readiness evidence rules still need to be
specified as the full oversight workflow is captured.

The current activity detector and PR/plan-based discovery do not implement
this entire handoff or these planning metrics. A preconfigured phase scope
and a generic team watch list are insufficient substitutes. This document
records the requirement; no additional cron has been installed by this update.

## Separate lifecycle from team evidence

A phase is a scope of project work, not the team's lifetime. Its completion
must not stop team roster, planned-work queue, immutable event-log collection,
or discovery of subsequent phases. Queue snapshots describe what is planned;
events establish what happened across queue movement and reassignment.

Retain completed phases in config, with their original start timestamp,
start evidence, and worktree settings. Add explicit `status` (`active` or
`complete`), `completed_at`, and `completion_evidence`. Missing status means
active for existing configs. Completion requires a timezone-aware timestamp
no earlier than the start, and authoritative phase acceptance/completion
evidence. It must not be inferred solely from all discovered PRs being merged:
discovery can be incomplete and integration or acceptance may remain.

Omega-prime reports AZ and BA complete, but their actual config transition
requires the corresponding receipts and timestamps. Those were requested in
`01M2BAS8RQJFDK6GPPYCNZXMA4`.

## Completion transition

Before retiring routine phase-specific scans, collect and preserve a final
phase observation with its timestamp, source provenance, PR heads/checks,
sprint associations, historical event evidence, and any coverage failures.
Store an immutable snapshot reference protected from routine retention pruning.
A source failure must not be disguised as complete evidence, and pending
findings must not be silently resolved by phase completion.

Record lifecycle completion independently from observation completeness:
phase acceptance can be authoritative while a monitor source is unavailable.
Retain that evidence gap and finish or explicitly disposition pending final
collection rather than silently dropping it. A deliberate refresh of completed
history must remain possible without automatically reopening the phase.
Reopening requires an explicit, recorded lifecycle transition.

After the final observation, routine collection excludes work done solely to
refresh a completed phase's old CI/Git/worktree scope. Active overlapping phases
keep their own boundaries. Shared resources needed by an active phase or team
oversight remain eligible. Activity identity matching may still need historical
worktree paths; use separate helpers for identity evidence and scan selection.
Reports show completed phases as historical with
completion evidence and observation time, not as fresh active work or missing
PR evidence. Historical reports remain available after later ticks.

## Boundaries and discovery

`completed_at` records lifecycle closure. It is not a blanket PR-created-time
upper bound: commits, checks, outcomes, and integration can occur after a PR's
creation. A timestamp alone also cannot prove phase membership. Preserve
explicit phase/sprint associations for final evidence.

Current collection uses the earliest configured phase start for team CI/Git
queries and retains teams with any tracked sprint. Merely ignoring completed
entries in that minimum would leave the no-active-phase case unbounded, or
could suppress new-phase discovery. Implementation must separate discovery
from active phase refresh: maintain a bounded, durable discovery checkpoint
and advance it only after a successful observation, including when no phases
are active. Do not reset it to the current time and lose work during outages.

Config changes currently invalidate tracked sprint and last-good caches.
Lifecycle transitions must preserve the final historical record rather than
relying on those disposable caches. Onboarding an existing completed phase
must preserve its lifecycle unless explicitly reopened.

## Validation requirements

Verify active and completed overlapping phases, all phases complete, missing
legacy status, invalid completion metadata, completion during a source outage,
new-phase discovery after completion, and explicit reopening. Assert that
phase-only scans stop while team queue/event collection continues. Verify
historical reports and known task IDs survive lifecycle changes, onboarding,
and snapshot pruning; no failed observation becomes successful or idle.

A Luna review confirmed the relevant code paths and baseline suites (141
monitoring tests and 10 onboarding tests). The existing watch list deliberately
persists previously observed teams; that behavior is not a phase-completion
signal. Guidance was sent to Omega-prime in `01M2BATY4CTZDX5E9ZJNHATT6B`.

## Operational detection and event-log contract

The maintained deployment skill procedure is
[phase discovery and event recording](../skills/atm-oversight/references/phase-discovery.md).
It specifies significance gating, durable pending/active repo ownership,
planning evidence and round identity, state/event recording, and capability gaps.
The phase-event writer provides durable local recording; automatic emission
and state projection in the active repo cron remain runtime integration work.

The active cron must track current state and all observed transformations.
Source-event history, not differences between two queue snapshots, supplies
intermediate transitions. Log events before updating derived state/checkpoints;
replays must be idempotent and outages must preserve explicit coverage gaps.
