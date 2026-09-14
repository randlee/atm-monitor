---
name: atm-oversight
description: Report phase and sprint status, investigate assigned-but-idle agents and CI or merge blockers, and recover monitoring failures.
---

# ATM oversight

Deliver exactly four outcomes: a useful phase/sprint table, assigned-but-idle
alerts, CI/merge-readiness alerts, and self-healing. The
[requirements](references/requirements.md) define the contract. Existing scripts
are not proof it is implemented; report their actual limitations.
Use the [design](references/design.md) for state/query contracts and field-level
source authority, fallback and conflict rules.
The runtime adapter and operator boundaries are documented in
[references/runtime.md](references/runtime.md); use its exact commands for reports, recovery and delivery receipts.

## Continuous operation

Read configured repos/phases, saved state, query checkpoints and pending
incidents. Verify actual scheduled execution. Restore authorized missing
monitoring and recover missed windows; registration or manual testing alone
is not proof of operation. Keep each repo independent and routine ticks quiet.

Cron runs independent questions, combines successful state, saves it and decides
from changes plus current state. Do not turn an investigation into one collector.
Do not scan all historical tasks every tick. A failure in one question does not
stop healthy questions or other repos.

## Missing or conflicting information

Keep usable parts of an answer. If ATM QA is unavailable but a matching
revision-addressed PR QA report exists, use it as a marked fallback. If neither
is available, show QA unknown/stale while still reporting known assignments
and PR state. Do not require both sources when one proves the fact.

Sources must establish the same fact to substitute for each other. A task
assignment does not replace an agent-idle observation; local tests do not replace
GitHub CI. Two copies of one report count once. Resolve source conflicts using
the field's authority/revision rule, never by arrival order; otherwise preserve
the disagreement and investigate. Failed primary queries retain repair ownership
even when fallback keeps the report useful. One explicit coverage case is a
remote stack with no local gh-stack tracking: when fresh complete remote topology
and readiness plus exact current ancestry answer O1/O3, accept remote observation
and keep unpublished local branches unknown. A `coverage-note` records that
choice; it does not claim the local query succeeded. Do not initialize tracking
or request an owner decision solely to remove that local limitation. Missing,
stale or partial fallback evidence restores repair escalation; authentication,
provider and malformed-response errors are never covered by this exception.

## Phase/sprint table

Show every sprint in scope, including unstarted and completed ones. Include
branch hierarchy, owner/task state, DEV/QA status, iterations, B/C/I findings,
PR/CI, blocker, next action, evidence and as-of/coverage. Retain history needed
for this table; missing or stale evidence is not success or zero findings.

Use source IDs to avoid duplicate counts. Keep withdrawn/resolved findings in
history but out of open counts. Do not map Minor findings into B/C/I. Use source
workflow metadata rather than assumed template names or hashes. When necessary,
read a specific QA report to obtain its verdict and counts.

## Assigned but idle

Join fresh agent state to outstanding assignments. Check queue position,
dependencies, recent acknowledgment and background/tool activity before calling
work stalled. An idle observation alone is not a stalled task. Orchestrators are commonly idle
between turns while delegated work continues. Recent outbound orchestration
messages, commits and PR work are positive activity evidence. Task-reminder
counts are not stall evidence; a static pane title is never a prompt.

A candidate wake begins an investigation, not an accusation. Record which host,
team and store a command actually queried. Empty observer-side queues, searches,
peeks or event results do not prove absence on the owner host. Before escalating,
obtain verified owner-host evidence or ask the owner directly for progress with
an explicit response deadline. Arrange one deadline follow-up, cancel it when
resolved, and treat silence as an unresolved investigation, not a proven stall.

Persist owner-confirmed working/false-positive outcomes with `record_resolution.py`
using the owner's actual reply ID or verified host evidence. A delivery receipt
alone does not record a resolution. The same assignment remains suppressed until
explicitly reopened with new evidence; time passing or another idle observation
is not new evidence. New assignments have their own incident identity.

Never ask an agent to restart its own harness. A restart is an operator/host-owner
decision requiring verified evidence and authority. If that owner is unknown,
escalate the evidence and decision to amon@atm-monitor; do not recommend or perform
a restart based on an idle finding. If action is
needed, alert the responsible owner with task, agent, evidence/time and next
step. Do not restart agents or close tasks merely because monitoring flags them.

## CI and merge readiness

Check conflicts and merge requirements as well as failed, missing and stuck
required checks. Inspect the exact active PR head. A conflict can prevent CI
from starting; repeated polling is not an investigation. Distinguish pending,
failed, absent and unknown evidence. Apply configured start/runtime thresholds.

GitHub `UNKNOWN` is unfinished evidence, not recovery. Leave the merge incident
unresolved and query again on the next scheduled tick (currently five minutes).
Do not wake an agent merely for this transient state or repeat an unchanged
blocker when GitHub finishes computing it. A new PR head remains new evidence.

Determine whether an owner already has a fix assignment before alerting.
For example, after a QA rejection, inspect that report and its follow-up task:
a known assigned fix is different from an unowned blocker. Send actionable CI
or conflict findings to the configured team lead/owner. Escalate unresolved
serious project decisions to Rand, with evidence and a concrete next action.

## Self-healing

A failed script begins recovery; it does not end oversight:

1. Inspect its typed error: question, cause, exact command/window, diagnostics
   and recommended repair. Retain its checkpoint and mark old evidence stale.
2. Retry transient faults within configured backoff/budget. Repair supported
   command/configuration problems within existing authority; rerun the same
   question and verify its answer. Honor source rate limits.
3. If a helper is broken, use a supported direct ATM/GitHub query for the same
   question. Record fallback evidence and coverage; continue unaffected checks.
4. Escalate persistent defects to amon@atm-monitor with impact, attempted repairs,
   exact failure, fallback coverage and next action. Deduplicate unchanged faults.
   Escalation transfers repair ownership, not responsibility for monitoring.
5. Verify recovery and scheduled runs. Inspect failed agent wakes or deliveries;
   a requested wake is not a delivered alert. Excessive wakes are defects too.

Do not reset system privacy controls, move repositories, alter the ATM database,
restart unrelated services, or modify monitored code as a monitoring repair.
Escalate a concrete decision if recovery requires authority you do not have.

## Follow-through

Persist incident identity, owner, last action, actual delivery ID and resolution
evidence. Do not repeat unchanged alerts or infer recovery from missing data.
Record new meaningful changes; invoke an agent only when attention is warranted.
When Rand asks, return the table and actionable findings, not collection counts,
test totals or claims that a process running proves oversight works.

## Runtime boundary

The replacement runtime runs independent bounded queries and composes immutable
observations. Query results are `ok`, `partial`, or `error`; partial coverage and
typed repair diagnostics remain visible. Cron persists action intent; `record_action` attaches
an actual delivery receipt outside domain equality. Never treat a wake request,
an agent process, or a fallback observation as proof of delivery or recovery.
Use the exact command and evidence rules in [the runtime reference](references/runtime.md).
