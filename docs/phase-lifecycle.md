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
   tasks, or an open PR. Agent activity prompts token-free qualification;
   substantive message/Git/PR evidence gates the agent handoff.
3. That discovery establishes the `new-phase-planned` state and signals
   Omega-prime to start active monitoring for the identified repository. This
   starts one additional repository-specific cron; planning and hardening are
   already underway, but the phase is not ready for development yet.
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
For the `plan/*` workflow, Rand specified explicit PR milestones: an open PR
from a planning source branch establishes planning in progress; merging that
PR signals plan ready. A closed/unmerged proposal is not ready. The active repo
cron records creation/merge timestamps and PR/revision identity. Additional
QA-message approval is not required after that accepted merge. This does not
mean development has started or the phase is complete. Other branch conventions
need their own acceptance evidence. Preserve earlier planning evidence and
account for discovery after both PR milestones already occurred.

The current activity detector and PR/plan-based discovery do not implement
this entire handoff or these planning metrics. A preconfigured phase scope
and a generic team watch list are insufficient substitutes. This document
records the requirement; no additional cron has been installed by this update.

## Separate lifecycle from team evidence

A phase is a scope of project work, not the team's lifetime. Its lifecycle
states are `activity-detected`, `new-phase-planned`, `active-development`, and
`integration-closed`. `activity-detected` is a candidate observation and does
not establish a phase. A qualified handoff establishes `new-phase-planned` and
starts the repository cron. Accepted development evidence transitions to
`active-development`. An authoritative integration closure transitions to
`integration-closed`; closing the integration PR stops the single repository
cron only when no other phase in that repository remains open. Reopening,
supersession, or abandonment is an explicit lifecycle transition and must
retain the prior closure record.

Its completion must not stop team roster, planned-work queue, immutable
event-log collection, or discovery of subsequent phases. Queue snapshots
describe what is planned; events establish what happened across queue movement
and reassignment.

Retain integration-closed phases in config, with their original start timestamp,
start evidence, and worktree settings. Add explicit `status` (`active` or
`complete`), `completed_at`, and `completion_evidence`. Missing status means
active for existing configs. Completion requires a timezone-aware timestamp
no earlier than the start, and authoritative phase acceptance/completion
evidence or an explicitly recorded abandonment/supersession decision. It must
not be inferred solely from all discovered PRs being merged:
discovery can be incomplete and integration or acceptance may remain.

Omega-prime reports AZ and BA complete, but their actual config transition
requires the corresponding receipts and timestamps. Those were requested in
`01M2BAS8RQJFDK6GPPYCNZXMA4`.

## Completion transition

For an integration closure, evidence is the exact `integrate/*` head branch for
the phase and repository, joined to its unique PR identity and terminal closed
outcome. Record the full head SHA, PR URL/number, source branch,
phase/repository association, and source timestamps. A closed but unmerged PR
is a terminal closure outcome but is not successful integration/merge evidence;
retain that distinction in the lifecycle record. An abandoned or superseded
phase may be closed without an integration PR: the operator records the actor,
reason, timestamp, and supporting evidence.

Before retiring routine phase-specific scans, collect and preserve a final
phase observation with its timestamp, source provenance, PR heads/checks,
sprint associations, historical event evidence, and any coverage failures.
Store an immutable final report/snapshot reference protected from routine
retention pruning.
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
Reports show integration-closed phases as historical with
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
When the repository cron stops, persist its scheduler stopped receipt before
releasing repository ownership. Advance the durable discovery checkpoint only
after that successful stop/release observation, so a restart does not
retrigger historical activity or recreate the old phase.

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
The manual closure and ownership procedure is
[phase closure](../skills/atm-oversight/references/phase-closure.md).
It specifies significance gating, durable pending/active repo ownership,
planning evidence and round identity, state/event recording, and capability gaps.
The phase-event writer provides durable local recording; automatic emission
and state projection in the active repo cron remain runtime integration work.

The active cron must track current state and all observed transformations.
Source-event history, not differences between two queue snapshots, supplies
intermediate transitions. Log events before updating derived state/checkpoints;
replays must be idempotent and outages must preserve explicit coverage gaps.

## Verified metadata-only message detection

Fenix receipt `01M2BD1NRG4J6DAZ3ZX6V0BKT3` supplies the concrete message
selection contract: union `--workflow-stage plan` with stored-variable
`--var review_mode=plan` hits, deduplicated by team/message ID. The typed QA
filter is narrower and misses pre-metadata admissions. Automatic message
classification must not scan prose/task descriptions. Planning PR opening/merge
signals remain independent evidence. The skill's phase-discovery reference
records verified commands, producer migration limits, cursor handling, and
pending/active repo suppression. These query checks do not implement cron
ownership or phase-state projections by themselves.

## Manual terminal outcome

Omega-prime can manually close a phase without an integration PR, recording
actor, reason, occurrence time, evidence, and outcome (`abandoned`, `superseded`,
or evidenced `complete`). Use `manually-closed` for that terminal state, keeping
it distinct from `integration-closed`. Neither closure stops the repo job while
another phase remains open. Preserve unresolved incidents with owners and next
actions; acknowledgement is not resolution. See the deployed closure procedure
for the actual journal command and the remaining manual scheduler steps.
