# Four oversight outcomes

This is the proposed contract, not a claim that the deployed collectors meet it.
Only the following four outcomes are in scope, continuously across dozens of repos.

| ID | Requirement | Acceptance evidence |
|---|---|---|
| O1 | Phase/sprint table: every sprint, branch hierarchy, owner/task state, DEV/QA, iterations, B/C/I, PR/CI, blockers and next action | Compare the table to a known plan, assignments, QA reports and PRs. Include unstarted/completed work, evidence and as-of/coverage. Missing counts are unknown; repeated reports do not double-count. |
| O2 | Detect assigned-but-idle agents | Fresh agent observation joined to outstanding task evidence distinguishes legitimately queued work from a stalled assignment. Investigate and alert the responsible owner; repeat unchanged observations remain quiet. |
| O3 | Detect broken CI and merge readiness | Exercise merge conflicts, failed checks, required checks that never start, and stuck queued/running checks. Alert with cause, affected head/PR and action; do not wait indefinitely for checks blocked by a conflict. |
| O4 | Self-heal query/script failures | Failure returns typed diagnostics and repair guidance. Retry/repair or escalate with evidence; continue healthy questions/repos. Verify actual recovery and scheduled execution, not merely a registered cron. |

## State

Use immutable data-only structures for repository/phase/sprint status, tasks,
agent observations, findings and check states. No query, I/O or workflow logic
belongs in these structures. Serialize state to JSON with schema validation and
atomic replacement; reload after restart. Partial observations compose into
full state. Retain evidence needed for reports, not a duplicate task database.

`state != old_state` detects change. Keep poll timestamps and diagnostic bookkeeping
outside domain equality. Last-good evidence from a failed query remains explicitly
stale, never evidence of success, completion, zero findings or recovery.

## Queries

Each query answers one question, is an independent Python function in
`<target>_<query>.py`, and is fewer than 100 lines excluding whitespace/comments.
It returns immutable state or part of state; it neither mutates nor persists.
Each query has explicit inputs, scope/time semantics, a call/row budget and an
independent test. An empty complete answer is distinct from failure.

Every result is a discriminated union:

- `ok`: typed state data, evidence and complete coverage for the stated scope.
- `partial`: data received, missing coverage and continuation/recovery details.
- `error`: problem kind, message, command/API, scope/window, exit/status code,
  bounded diagnostics, retryability/retry-after and an actionable repair/owner.

A normal portion of full state is `ok`; `partial` means retrieval was incomplete.
Errors distinguish timeout, unavailable service, access/authentication, missing
command, unsupported capability and invalid input/response. Exclude secrets.

| Question | Outcome | Scope |
|---|---|---|
| What is each sprint's current progress and findings? | O1 | Configured phase plan, recent workflow/QA evidence and known sprint PRs |
| Who has outstanding work and is idle? | O2 | Current task assignment and fresh agent state; queue order/dependencies matter |
| Which active PRs have CI/merge problems? | O3 | Current required-check and merge state for relevant PR heads; PR updatedAt alone does not establish CI freshness |
| Which observation failed, and how can it recover? | O4 | Per-query result and scheduled execution/delivery receipts |

Expand these into individual query contracts before implementation. Tests must
verify the answers, boundaries and error variants, not just successful execution.

## Cron and decisions

Cron runs a set of queries, combines successful results, updates/persists state,
and decides from what changed and current state. Failed questions retain their
own checkpoint; unaffected questions advance. Bounded windows overlap and dedupe
by evidence identity. Do not repeatedly fetch all remembered task histories.

Record meaningful changes. Wake Omega only for actionable new conditions or a
failure needing repair. Keep notification/incident state so unchanged failures
stay quiet. A wake requested, agent started, alert delivered and issue resolved
are separate facts. Missing observations cannot falsely rearm alerts.

Each repo has independent state and execution limits. One hung query/repo must
not stall others. Deduplicate shared-service outages. Monitor missed scheduled
runs from outside the failed job. Configure freshness, retry/backoff and stuck/idle
thresholds explicitly; do not invent universal thresholds in the implementation.

## Completion

Demonstrate all four outputs against real atm-dev evidence and unattended runs.
Exercise empty/error/partial answers, recovery, duplicate events and restart.
Then verify 30-repo isolation and bounded request/token use. Source counts and
test totals alone are not completion. Automatic phase lifecycle management,
metadata administration and repository naming enforcement are outside this scope.
