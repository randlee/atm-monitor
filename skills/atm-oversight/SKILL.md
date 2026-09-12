---
name: atm-oversight
description: Report phase and sprint status, investigate assigned-but-idle agents and CI or merge blockers, and recover monitoring failures.
---

# ATM oversight

Deliver exactly four outcomes: a useful phase/sprint table, assigned-but-idle
alerts, CI/merge-readiness alerts, and self-healing. The
[requirements](references/requirements.md) define the contract. Existing scripts
are not proof it is implemented; report their actual limitations.

## Continuous operation

Read configured repos/phases, saved state, query checkpoints and pending
incidents. Verify actual scheduled execution. Restore authorized missing
monitoring and recover missed windows; registration or manual testing alone
is not proof of operation. Keep each repo independent and routine ticks quiet.

Cron runs independent questions, combines successful state, saves it and decides
from changes plus current state. Do not turn an investigation into one collector.
Do not scan all historical tasks every tick. A failure in one question does not
stop healthy questions or other repos.

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
work stalled. An idle observation alone is not a stalled task. If action is
needed, alert the responsible owner with task, agent, evidence/time and next
step. Do not restart agents or close tasks merely because monitoring flags them.

## CI and merge readiness

Check conflicts and merge requirements as well as failed, missing and stuck
required checks. Inspect the exact active PR head. A conflict can prevent CI
from starting; repeated polling is not an investigation. Distinguish pending,
failed, absent and unknown evidence. Apply configured start/runtime thresholds.

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
