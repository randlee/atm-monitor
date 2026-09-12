# Phase discovery, planning, and event recording

Use this procedure when activity changes, a planning assignment appears, or a
phase milestone needs interpretation. Omega-prime owns discovering the work,
starting its phase-monitoring handoff, recording what happened, and following
it through planning and development. Do not just return agent process states.

## From activity to significant work

The general activity cron runs deterministic checks without an LLM. It resolves
actor/team/repository from roster and worktree evidence, then checks bounded
message metadata, rendered planning/development assignments, and Git artifacts
for significant work. Herdr `working`, a question, or a bare branch name is not
permission to wake Omega-prime. The cron must establish planning/development
work before issuing a discovery handoff. If evidence is ambiguous, persist the
candidate and continue cheap checks; do not wake the agent on every interval.

Check the active-repository registry before discovery work. A repository/team
already owned by a repo-specific monitoring job is excluded from general
activity wakes. Its repo cron owns all phase monitoring and discovery of
additional phases. Overlapping phases do not create duplicate repo jobs.
A restart must reload ownership and handled evidence IDs, not wake every agent
again. New evidence for an already active repo belongs to its repo cron.

The first qualifying handoff carries repo/team identity, evidence establishing
planning/development, phase if resolvable, source timestamps, and a stable
handoff ID. Omega-prime validates/enriches that evidence and starts monitoring;
it is not woken merely to find out whether anything significant is happening.
Preserve inspection checkpoints through outages. Expand backward after a
qualified handoff to establish actual start times where work predates detection.

| Evidence | Meaning | Omega-prime action |
|---|---|---|
| Agent working briefly; Rand asks a few questions; no project artifact or assignment | Ordinary interaction; phase not established | Cron records the inspection locally; no agent wake and no phase cron |
| Planning-looking branch alone; old template exists; phase name mentioned in passing | Candidate requiring context | Cron checks structured branch/assignment evidence; retain candidate locally, no agent wake yet |
| Open PR whose source/head branch is `plan/*`, such as `plan/phase-ab` | Planning in progress | Qualify substantive work without an LLM; associate phase and hand off only if repo is not already pending/active |
| That planning PR is merged | Plan ready | Record readiness at `mergedAt`, with PR and accepted revision evidence; active repo cron owns this transition |
| Planning PR is closed without merge | Closed/cancelled planning proposal; readiness not established | Record closure and seek disposition evidence; do not emit `plan_ready` |
| New planning branch and actual phase-bound use of plan-hardening templates, with matching repo/phase/plan | Planning is underway | Record phase discovery/start, onboard that phase, and request its repo-specific monitoring job |
| Explicit phase-planning directive or assignment with unambiguous repo/phase and source references | Substantive work even before a PR or branch exists | Establish phase from that evidence and follow the same handoff; record missing artifacts separately |
| Existing phase gets another hardening assignment, correction, or review | Continuation, not a new phase | Append activity/round evidence to the existing phase log |

A planning branch plus template use is a strong concrete example, not a
mandatory naming convention. Read actual repository conventions. Mere presence
of `.j2` files is not template use; a rendered assignment, dispatch metadata,
vars artifact linked to execution, or resulting review supplies that evidence.
Identify the phase from explicit message/template/plan fields and confirm the
branch/worktree association. Never guess 'next phase' by incrementing letters.
Conflicting identities stay unresolved; report what evidence would resolve them.

For atm-core, observed planning inputs include
`.claude/skills/plan-hardening/01-plan-scope-review.xml.j2`,
`02-sprint-scope-hardening.xml.j2`, and `03-consistency-hardening.xml.j2`.
Assignments expose `phase`, `task_id`, `branch`, `worktree_path`, `round_id`,
`round_index`, and replay/supersession information. Review results can expose
reviewer, reviewed commit, verdict, findings counts/hash, and prior-round IDs.
Inspect the current template contract; retain its revision/hash as evidence.
Do not mistake a template filename or task tag alone for a completed review.

Use the installed message-query adapter with explicit team/actor, Git branch
and commit history, rendered assignments, and plan artifacts. Follow returned
pagination/cursors. The existing `mine_messages.py --help` describes supported
filters; unsupported planning tags must be investigated through the installed
ATM query surface, not fabricated as accepted flags. All reads use supported
CLI/API contracts, never direct ATM database access.

## The handoff you must complete

Use durable repository/team ownership states: candidate, handoff-pending,
active, and retired. Qualifying evidence atomically claims one pending handoff;
repeated polls do not resend it. Store its evidence IDs and delivery/acknowledgment
receipt. Mark active only after the repo scheduler job exists and its first run
is observed. Pending handoffs also suppress duplicate wakes; a failed start is
an explicit handoff failure with bounded retry/backoff, not a fresh wake every
poll. Do not hide failed startup by labelling the repo active. Repository
retirement is distinct from an individual phase completing; only an explicit
ownership release returns the repo to general discovery eligibility.


1. Establish repository/team/phase, actual planning-start evidence, and any
   earlier activity needing backfill. Persist phase events with their source
   timestamps and references.
2. Invoke `oversight-onboarding` to retain the phase and evidence-backed start
   alongside existing phases. Planning-only phases need no development PR.
3. Prepare/start one repo-specific monitoring schedule through the deployment
   scheduler, with a stable repository/team identity and separate state ownership.
   Repeated discovery reuses that job. Keep overlapping phase scopes distinct
   inside the repo job; it owns discovery of subsequent phases as well. The
   general activity cron continues checking only repos it does not already own
   through pending/active handoffs.
4. Record the scheduler receipt and first successful run as `monitoring_started`.
   A saved config or proposed cron line is not a running job. If current runtime
   lacks this integration, record the handoff as pending with the exact gap and
   continue deliberate observations through supported tools.
5. Each phase observation updates the event log, then derives current state,
   planning metrics, and the next action from that log and evidence coverage.

## Active repo cron owns state and transitions

The currently-active repo cron tracks repository and phase state, not just a
series of independent snapshots. On each run it resumes durable source
checkpoints, collects new evidence, associates it with phases, and appends all
observed activity and state-transition events. It then updates the current
state projection and records the last applied event sequence. Persist events
before advancing projections/checkpoints, so a crash can replay committed
records without losing a transition. No new evidence means no invented state
change or additional hardening iteration.

Track planning, hardening, readiness, development, review/integration, completion,
supersession, and reopening when supported by the workflow evidence. Store
`from`, `to`, phase/repo identity, source occurrence time, observation time, and
evidence for each transition; include plan revision and round identity where
relevant. Keep phase state separate from task state, agent process state, and
monitor health. A source outage changes coverage/health, not the phase to idle,
complete, or a previous lifecycle stage.

The source history and derived phase journal must account for intermediate
transitions occurring between polls: read
source history/cursors rather than compare only current queue/agent snapshots.
If history is unavailable, record the missing interval/coverage gap instead
of inventing the transitions. Preserve source ordering where supplied; late
historical events must not regress current state merely because they have a
later local append sequence. Corrections reference earlier events explicitly.

The active repo cron also detects additional phases in that repo and records
their discovery. It owns those handoffs without waking the general activity
monitor. Agent reasoning, when needed for ambiguous substantive evidence or an
actionable finding, is a deliberate escalation from this cron, not an automatic
LLM invocation on every timer tick.

## Phase event log is the durable record

Keep durable JSON current state/checkpoints and a small append-only journal
keyed by repository, team, and phase for oversight-owned decisions and
monitoring transitions. Do not duplicate the ATM event/message database. Reference
ATM events/messages and Git artifacts as source evidence; do not rewrite or
replace the task ledger. Queues describe planned work; their snapshots are not
phase history and their disappearance is not completion evidence.

Track every observed phase activity and state transition, including planning
assignments, branch/plan edits, review findings, corrections, round starts and
finishes, readiness decisions, development starts, monitoring starts/stops,
completion, supersession, reopening, and coverage gaps. Use canonical ATM message/event IDs and Git revisions for upstream facts.
Append a local decision only when phase association, interpretation, or monitor
ownership is not already recorded upstream; checkpoints/projections reference
the original events without copying their bodies. Unrelated casual activity stays in discovery observations because no
phase identity has been established. Once associated, backfill relevant earlier
activity with its actual timestamp and a later observation timestamp.

Each event contains a stable `event_id`, `team`, `repo`, `phase`, `kind`,
`occurred_at`, nonempty `evidence` references, and structured `payload`.
The writer assigns `seq` and `observed_at`. Payloads retain actors, task/message
IDs, branch and full commit IDs, template revision, round/reviewer identity,
findings/outcome, and transition `from`/`to` when relevant. Preserve source
fields rather than guessing absent values. Late observations append in receipt
order while keeping original occurrence time; they do not rewrite old entries.
If occurrence time is unknown, use the observation time only for an explicitly
labelled observation event; do not invent a milestone timestamp.

Use the deployed helper with an event JSON file:

```sh
python scripts/oversight/phase_events.py append --state-dir /path/to/phase-event-log --event-file /path/to/event.json
python scripts/oversight/phase_events.py list --state-dir /path/to/phase-event-log --team atm-dev --phase BB
```

Use a dedicated durable directory outside rotating snapshot directories. Reuse
an event ID for an identical source event on subsequent polls. A conflicting
replay must fail; append a new `evidence_corrected` event referencing the old ID
and reason instead of altering history. Several real events may cite the same
message, so include the event meaning in the stable ID. A replay nonce alone
must not create a second logical hardening iteration.

## Hardening iterations, duration, and readiness

Record `hardening_iteration_started` and `hardening_iteration_completed` with
an explicit iteration identity: phase, review stage, reviewer, source round ID,
and reviewed revision/attempt where necessary. Keep started, completed, and
in-progress counts separate, and present counts by stage/reviewer before an
aggregate. Follow source round identity and supersession: duplicate delivery,
acknowledgments, polling ticks, each commit, and a correction within the same
round do not increment the round count. Preserve each actual new review round,
including failed and superseded rounds; a final PASS does not erase hardening
history. Ambiguous round boundaries produce an unknown/incomplete count.

Report planning start separately from hardening start. Hardening elapsed time
runs from the first evidenced hardening start to evidenced plan readiness; if
not ready, report elapsed time as of the observation. This is wall-clock elapsed
time, not inferred engineering effort. Retain per-round start/end times and
report missing endpoints, rather than substituting first polling times.

For Rand's `plan/*` workflow, the planning PR is a direct lifecycle signal:
opening the PR establishes planning in progress, and its completed merge
establishes `plan_ready`. Use the source/head branch (`headRefName`), not a PR
merely targeting a planning branch. Record the PR identity/URL, branch, phase,
`createdAt`/`mergedAt`, reviewed head and merge commit when available. A closed
but unmerged PR is not a completed plan. CI success or reviewer PASS alone
is not PR completion. Do not impose an additional QA-message requirement after
the planning PR has merged; its accepted completion is the readiness signal.

Opening time proves planning by that time, not that no earlier planning took
place. Preserve earlier start evidence when available. If the planning PR is
first discovered already merged, retain both its creation and merge milestones
without starting a new hardening round or issuing duplicate activity handoffs.
Phase completion and development start remain separate from plan readiness.
`development_started` requires its own assignment or work evidence. A new plan
revision/reopened planning effort gets its own lifecycle evidence; preserve
readiness of the older revision without applying it blindly to the new one.
For a workflow using another branch convention, use its explicit acceptance
contract rather than assume the `plan/*` rule applies to every docs PR.

A planning report states phase, current evidenced stage, start times, completed
and in-progress hardening rounds, elapsed hardening time, readiness time/revision
if established, latest outcome/blocker, next action, and evidence coverage.
Link the phase event records supporting each conclusion. The current sprint
Markdown renderer does not compute these metrics; Omega-prime must derive them
from recorded evidence without claiming unavailable automation exists.

## Classify milestone reports precisely

- A message saying 'round 2 is running' is `activity_observed` at the message
  time. It establishes in-progress state, not `hardening_iteration_started` at
  that time. Keep the actual start unknown until the assignment/start evidence
  is found; do not compute elapsed hardening from that observation.
- A message saying 'hardening is complete' and listing five rounds is
  `hardening_completion_reported`, with the reported round identities. It is
  not one `hardening_iteration_completed` event. Individual round records,
  when collected, reconcile with those identities rather than double-counting.
- Apply `evidence_corrected` records when interpreting the journal. Their
  payload identifies `supersedes_event_id`, reason, and replacement meaning;
  never count both the superseded interpretation and its correction. The
  helper lists raw records; it does not apply semantic corrections for you.

## Current capability boundary

Activity/roster polling, Git/CI/task collection, message-query tools, onboarding
settings, and the phase-event writer exist. Deterministic significance gating and active-registry suppression,
planning discovery before PRs, scheduler provisioning, automatic phase-event
emission, and a deterministic planning-metrics report still need runtime
integration. Until then, Omega-prime performs the evidence investigation and
recording explicitly. Do not label these steps complete merely because the
skills describe them. Respect the deployment's actual scheduler configuration.

## Observed ATM boundary (1.5.16)

An earlier live check on September 12 found `atm search --workflow-scope-kind phase`
returned no atm-dev hits. Literal searches for 'plan started' and 'plan ready'
also returned none. Planning messages were searchable, with `workflow: null`.
This is observed coverage, not proof those concepts never occur elsewhere.
For BB, message `01M2B9PEEA05FQVYRWX4NFH17X` establishes hardening already in
progress; `01M2BBV4VABKZ69EMPWPGA7RHZ` says hardening complete but plan QA PASS
still required; `01M2BBZ2NW70Y6B8V2J20EHV5D` dispatches that QA gate. These
support a phase projection referencing ATM IDs without duplicating messages.

In this installed CLI, `search` does not accept `--as`; pin `ATM_IDENTITY` in
the subprocess environment and pass `--team` explicitly. `peek` still exposes
`--as`. The message wrapper pins actor/team in the environment for search and retains
explicit `--as` for peek. Failed searches remain unavailable evidence.

A subsequent check found the first structured planning record at
`2026-09-12T18:08:36.328570Z`: message `01M2BCX5F84MF2757DJSPVEKYG`, template
`plan-review-notice`, SHA
`6e12f1ba274cb41d12f6f809649b286769cf8bd6c4be6bbad88b4b58ae047398`.
Its workflow snapshot supplies phase `BB`, stage `plan`, state
`plan-review-notice`, transition `notice`, and iteration `2`. Both direct
queries returned it on ATM 1.5.16:

```sh
ATM_IDENTITY=omega-prime atm search --team atm-dev --workflow-scope-kind phase --workflow-scope-id BB --workflow-stage plan --limit 20 --json
ATM_IDENTITY=omega-prime atm search --team atm-dev --effective-tag stage:plan --count --json
```

This is a concrete deterministic planning signal. Apply new-evidence/time
checkpoints and pending/active repo suppression before any agent handoff;
a historical notice is not automatically new work. `template_type` is not the
entire effective-tag set: inspect the message's workflow/tag provenance.
Catalog presence alone proves registration, not phase activity. Refresh catalog
revisions rather than freeze a list of four types or hard-code this one SHA.

The notice is informational and reports prior rounds; iteration `2` is not the
phase's total hardening count or a new round start. Its body explicitly says
plan QA remains in flight. Keep `notice` distinct from readiness. The known
source fact remains in ATM; the phase projection references its ID. Earlier
untagged records are not retroactively covered by the new structured query.
