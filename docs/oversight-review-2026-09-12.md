# Oversight skills and scripts review — September 12, 2026

Reviewed the three master skills, their references and Python helpers/tests,
repository hooks, deployment/distribution tooling, and the lifecycle requirements.
Two Luna passes independently reviewed runtime behavior and lifecycle coverage;
a follow-up traced both agent discovery routes and reviewed the metadata fixes.
This review did not change production crons, close any live phase, or write the
live ATM database. Repository-access problems in the daemon are out of scope.

## Main conclusion

Collection and evidence tools are usable, but automatic phase oversight is not
complete. The runnable detector remains a candidate watch-list collector; the
repo ownership registry, lifecycle reducer, and scheduler handoff are absent.
Phase closure has an actionable manual procedure, but appending its event does
not automatically retire configured scopes or stop a cron. Do not enable an
LLM wake on every detector observation and call that the completed design.

## Accepted lifecycle

The activity cron runs continuously. Qualified planning/development activity
triggers Omega-prime, who enables the repo-specific phase-monitoring cron.
Pending/active ownership then suppresses subsequent activity-monitor agent
triggers for that repo. Cron detection and agent-managed startup are distinct;
this does not require the detector itself to create scheduler jobs. Inactivity
is not a reason to pause a repo with open phases.

| State/event | Evidence | Repository cron consequence |
|---|---|---|
| activity-detected | Candidate process/roster/Git observation | No agent wake from this alone |
| new-phase-planned | Qualified structured planning evidence or a phase-associated planning PR/branch | Start one repo job if none is owned; otherwise add this phase to the existing job |
| active-development | Development assignment/work evidence | Continue the same job |
| integration-closed | The phase's exact integrate/* source-branch PR merges | Close that phase; stop the repo cron only if no other phase is open |
| Integration PR closed without merge | Investigate, then escalate findings/proposed disposition to Rand | Retain monitoring until continuation, abandonment, or supersession is established |
| manually-closed | Omega-prime records actor, reason, time, evidence, and outcome | Close that phase even if no integration PR exists |
| phase reopened | Explicit evidence referencing prior closure | Resume/reuse monitoring and record the transition |

The repo cron stays running while **any phase remains open**. Plan readiness,
hardening rounds, reviews and integration progress are subordinate milestones,
not reasons to create separate repo crons. Manual abandonment/supersession must
not fabricate an integration PR. See the authoritative
[closure procedure](../skills/atm-oversight/references/phase-closure.md).

## Findings fixed in this review

| Finding | Fix and evidence |
|---|---|
| Maintenance skill existed outside native project discovery directories | Added portable `.agents/skills/` and `.claude/skills/` entrypoints plus root AGENTS.md/CLAUDE.md routing. Both load the same canonical skill and standards. Relative targets and frontmatter validated; Luna traced remediation from an unknown-SHA hook failure. No fresh native Codex/Claude process was launched to prove runtime auto-selection. |
| Roster detector read legacy state but ignored documented status | Accept status and legacy state; reject contradictory/malformed values. Regression fixtures cover both schemas and detection. |
| Standalone health accepted future snapshots | Reject negative age, matching phase monitor freshness checks. |
| Audit skipped standard iteration_variable and could crash on malformed metadata | Check the iteration binding; malformed metadata produces findings. Preserve unknown-type diagnostics alongside other findings; whitespace types remain untyped. |
| Audit accepted duplicate/invalid SHA values, including offline path traversal | Require full lowercase SHA and unique catalog rows before resolving schema filenames or invoking queries. |
| Administrative DB commit preceded any durable receipt | Persist prepared intent with backup, before/after hashes and classifications before mutation; atomically replace with committed receipt. Failure after commit explicitly reports committed DB and retained intent. No-op apply produces no backup. Fault-injection tests cover both receipt failure windows. |
| Event reader accepted malformed writer timestamps and duplicate IDs in stored logs | Validate timezone-aware observed_at and reject duplicate IDs; tests reject reads/appends against corrupt history. |
| Closure and template source authority were insufficiently explicit | Added manual closure runbook, multi-phase cron rule, manual actor/reason/evidence, retained incident ownership, and scheduler stop/release ordering. Repository templates are authoritative; home copies remain historical incidental evidence. |

## Remaining implementation gaps

### P1: qualify activity before any agent handoff

`detect_activity.py` observes roster/Herdr activity. It does not query planning
metadata or phase-related PR milestones. `scheduled_output.py` reports attention
from new watch-list membership or collection failures. That output must not be
wired directly to an LLM trigger. Implement structured qualification, successful
source checkpoints, and stable handled-evidence IDs. Test casual questions,
no-change polls, historical notices, replay, failures, and direct development.

### P1: one durable repository owner across overlapping phases

`watched_teams` is not a pending/active ownership registry. Introduce atomic
repo/team ownership with phase membership, pending handoff identity, scheduler
job/receipt, first successful run, retry state, and explicit release. Concurrent
claims and restarts must create one job/wake. Closing phase A while B is open
must neither stop the job nor rearm general discovery for that repository.

### P1: connect lifecycle evidence, journal, projection, and scheduler

The phase journal only appends/lists records; no collector calls it to emit
lifecycle transitions. `configure_project.py` has no close/reopen command, and
`tick.py` ignores completion fields and scans all configured phases. Implement
the state reducer and integration-PR association, explicit manual close/reopen,
active-scope filtering, and event-before-projection/checkpoint recovery. Last
phase closure needs a confirmed scheduler stop before ownership release.
Record source failures without changing phase state. Do not infer successful
integration from an arbitrary PR closure or PR base branch.

### P1: retain closed history and rearm discovery safely

Current rotating snapshots and config-dependent caches are insufficient final
phase archives. Preserve a final report/snapshot reference, evidence coverage,
incident owners/dispositions, and phase-to-sprint/task/PR associations outside
pruning. Retire only closed-phase refresh work, keep overlapping scopes active,
and use a successful durable discovery checkpoint to find later phases without
replaying closed work. Reopening is explicit; historical refresh is not reopening.

### P2: deterministic planning metrics and correction handling

The sprint renderer does not project lifecycle history or compute hardening
round counts/duration. Apply explicit round/reviewer/revision identities,
start/end evidence, and correction/supersession links. Separate source occurrence
from observation time; late evidence must not regress state. Unknown endpoints
must stay unknown. Tests need full before/after-restart planning through closure,
including aggregate notices that must not double-count individual rounds.

### P2: producer coverage and supported metadata administration

Live audit at review time: 16 revisions, zero untyped, four fully compliant,
12 with historical metadata gaps, no query failures. A type does not prove a
workflow snapshot exists. Verify planning/development producer revisions through
real admissions. The Git gate enforces type presence only; the separate strict
audit enforces this project's richer contract. Native admission enforcement,
scoped standards, supported historical classification and source provenance
remain atm-core #1435. No daemon-access workaround is adopted here.

## Validation and rollout boundary

- Monitoring: 151 tests pass.
- Onboarding: 10 tests pass.
- Template audit/gate/maintenance: 23 tests pass.
- Distribution and isolated bundles: 9 tests pass.
- Three canonical skills and both discovery entrypoints pass skill validation.
- Canonical links resolve; git diff whitespace checks pass.

These 193 tests validate existing helpers and the scoped fixes, not the missing
lifecycle/scheduler integration. Required end-to-end cases include overlapping
phase closure, all phases closed, abandonment without a PR, closed-unmerged
integration, reopening, late/corrected events, outage at closure, concurrent
handoffs, stop failure, and preserved history after pruning/config changes.

The master changes belong to atm-monitor PR #2. Updating source files is distinct
from distribution into Hendrix and confirmation that Omega-prime consumed the
updated skill. Keep deployment receipts and that final briefing explicit.

## Follow-up requirement: phase cron wakes only for notable events

Rand clarified that assignments/activity and per-sprint B/C/I counts are routine
recording, not LLM triggers. Add deterministic notable-event evaluation and a
durable wake handoff checkpoint, distinct from delivery state. Acceptance must
cover CI fail edges, unchanged failure silence, recovery/recurrence, new merge
blocks, fresh idle-with-active-task evidence, and no wake for ordinary idle or
routine counts. Existing incident helpers do not complete this wake integration.

## Follow-up requirement: immediate complete phase report

Rand must be able to obtain the whole phase and every sprint's status on demand
from recorded state, without waiting for a tick. Include planned/unstarted and
closed sprints from the plan inventory even without PRs, assignments/activity,
DEV/QA/CI and B/C/I, blockers, phase milestones, evidence and as-of/coverage.
The current renderer is not a full phase projection. Acceptance must cover
requesting a report during collection/outage, unstarted sprints, overlapping
phases, and historical reports after closure and snapshot pruning.

## Follow-up requirement: maintainer owns operational defects

Omega-prime follows skills without requiring Rand to direct routine work.
Excessive or unjustified triggering escalates to amon@atm-monitor with durable
wake/event evidence. The maintainer fixes masters and verifies redistribution.
Add wake audit/defect deduplication to the runtime acceptance cases; a monitoring
defect must not create another repeated escalation loop or disable required
monitoring. Project decisions still follow their separate escalation routes.
