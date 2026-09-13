# Runtime operator reference

The runtime is a bounded, read-only observation pipeline. It composes independent
queries into O1 phase rows, O2 assignment investigations, O3 CI/merge findings,
and O4 recovery conditions. It does not advance phase lifecycle, alter ATM or
GitHub state, wake an agent as a substitute for evidence, or claim deployment.

## Configuration and commands

Each repository entry supplies its repo path, ATM team and actor, plan revision
and plan path, bounded workflow window, query timeout, and policy deadlines.
Queries use argument arrays and explicit scopes:

```text
atm task list --team TEAM --as ACTOR --all --json
atm search --team TEAM --workflow-scope-kind sprint --since START --until END --limit 100 --json
atm peek --team TEAM --as MAILBOX --message-id MESSAGE_ID --json
herdr agent list
atm members --team TEAM --json
git -C REPO show REVISION:PLAN_FILE
```

The installed ATM task command rejects `--all` with `--limit`; the adapter
enforces its row budget after decoding the current queue. Workflow results must
retain explicit sprint scope, stage, template type, state, transition and
iteration metadata. QA assignments (`qa-task`) are not QA reports.

Plan inventory is authoritative at the configured revision. Phase-BB currently
contains seven sprint documents and their explicit branch frontmatter. Missing
tree or file coverage is `partial`, never an empty complete inventory.

## Result and recovery rules

Every query returns `ok`, `partial`, or `error` with immutable typed records.
`partial` preserves positive observations and includes missing coverage,
continuation and a typed problem. `error` includes the exact argument array,
scope, bounded diagnostics, retryability and repair owner. A failed primary
query retains its checkpoint and does not become successful because a fallback
was available.

Herdr's `agent_status` is a current harness observation. Retrieval time anchors
freshness; `state_changed_at` is retained only when supplied. Missing background
activity or state-since evidence remains unknown and should produce an
investigation condition rather than an idle accusation. ATM roster data is a
fallback observation with its original observation time.

Reports are peeked only after a workflow hit identifies a report message. The
parser accepts revision-addressed structured JSON and actionable prose reports.
Aggregate blocking/important/minor counts remain aggregate evidence; they are
not fabricated finding IDs and are not mapped into B/C/I. Revision-addressed QA
history retains rounds, while a verdict is applied only to the matching current
revision.

Cron stores the intent; `record_action` attaches an actual delivery receipt
separately from domain state. A requested wake is not a delivered alert, and an unresolved
delivery does not clear its incident. Retry transient failures within configured
budgets, use a same-question fallback when supported, and escalate persistent
repair ownership with the preserved diagnostics.

## Current implementation limits

Passing a manual tick is not evidence of unattended operation. Required-check policy and scheduler receipt adapters may leave O3/O4
timed assertions unknown. Local stack observations cannot establish current
GitHub mergeability. Missing task-to-sprint metadata remains provisional until
workflow or configured plan evidence associates it. These gaps are displayed in
coverage and must not be rendered as zero findings or completion.

## Run and operate the replacement

Start from `assets/runtime.example.json`. Replace its repository path, pinned
plan revision, `since` timestamp, scope/branch aliases, stack worktree and
scheduler binding with verified deployment values. Every policy field is
explicit and validated. Initial backlog advances in bounded windows; partial
pages keep their window/cursor until complete. Watch the checkpoint, not just
an empty current result. `gh_checks` refreshes known open PRs even without a
recent PR update. Nested GraphQL cursors belong to one parent and resume on
subsequent ticks. Query workers default to four; repo processes are isolated.

```sh
python3 scripts/runtime/runtime_main.py --config /deployment/monitor-v2.json --state-dir /deployment/runtime --shadow
python3 scripts/runtime/runtime_main.py --config /deployment/monitor-v2.json --state-dir /deployment/runtime
python3 scripts/runtime/watchdog_main.py --config /deployment/monitor-v2.json --state-dir /deployment/runtime --watchdog-dir /deployment/watchdog
cat /deployment/runtime/randlee--atm-core/report.md
```

Run these from the installed skill directory. Schedule the primary and watchdog
as separate five-minute jobs. Shadow writes observations but never reserves an
alert or wakes an agent. Production saves the incident intent before returning
`wakeAgent:true`. A repeated unchanged incident stays quiet after restart.
`state.json` is the current typed envelope; `state.last-valid.json` is recovery
backup; `events/<generation>/state.json` records changed domain state. Query
receipts and attempt timestamps do not participate in domain equality.

For every wake, investigate the supplied current evidence and follow the skill.
Send the actionable finding to its listed route using ATM. Record the actual
returned message ID; never manufacture a receipt from a session or wake ID:

```sh
atm send team-lead@TEAM --team MONITOR_TEAM --file /tmp/oversight-finding.txt
python3 scripts/runtime/record_action.py --state-dir /deployment/runtime/OWNER--REPO --incident 'EXACT_INCIDENT_KEY' --route team-lead@TEAM --message-id ACTUAL_ATM_MESSAGE_ID
```

A grouped shared-service repair includes `receipt_targets`; one message covers
those affected repos, then record that receipt against every listed target.
For a watchdog event use its supplied watchdog state directory and incident key.
A receipt is delivery evidence, not resolution. Resolution needs fresh domain
evidence. If investigation shows the owner already has the fix, report that
context to the route rather than issuing duplicate work. The watchdog escalates
missing receipts after `followup_seconds`; inspect transport before resending.

Live adapter validation used ATM 1.5.16 and GH 2.98.0. Unsupported command or
schema behavior returns an actionable error; it is never silently skipped while
waiting for ATM 1.6. Required-check policy uses legacy protection plus effective
rules; missing policy leaves absent-check assertions unknown. A queued/running
check without provider timing starts a conservative first-observed timer.

The known B/I aggregate counts are retained; C is unknown when absent, and Minor
is not remapped. Current assignments cannot prove completed DEV work: merged PRs
are shown with their actual base, while missing owner/history stays unknown.
Automatic phase discovery/closure is outside these four-output requirements;
multiple configured phases share their repository tick. The watchdog is separate
from the primary job but shares its machine and Hermes gateway.

For local `gh stack view` exit 2/6, the adapter tries at most two discovered
member worktrees in one query. A GitHub stack does not guarantee every member
worktree has local gh-stack tracking. Errors retain the stack ID and actual
`cwd` paths; retryable context failures escalate after the configured budget.
The legacy `monitor.json` worktrees array is not used by this runtime. Remote
stack/check and exact-SHA ancestry evidence continues independently. Do not
initialize, check out or rewrite a monitored stack to repair observation.


## Idle investigation evidence and resolution

The conditional `atm_owner_activity.py` query asks whether an owner sent any
message inside the configured idle-grace window. `atm search --team TEAM --from
OWNER --since START --until END --limit 1 --json` returns at most one positive
witness; more pages are unnecessary for this existence question. Host provenance
is retained. A failed query leaves this evidence unknown; an empty local result
is not proof of owner-host inactivity. Positive recent sends reset the idle timer.
The adapter only schedules these queries for runnable assignments with idle
harness observations, within the detail budget; owners rotate fairly.

After a verified owner reply or owner-host investigation, persist the outcome:

```sh
python3 scripts/runtime/record_resolution.py --state-dir /deployment/runtime/OWNER--REPO --incident 'EXACT_IDLE_KEY' --outcome false-positive --reason 'Owner confirmed active orchestration' --evidence ACTUAL_OWNER_REPLY_MESSAGE_ID
```

Use `resolved` for a completed investigation and `reopen` only with new evidence
and an explicit reason. These durable dispositions survive working/idle changes,
restart and repeated observation windows. They do not suppress a new assignment
identity. The command preserves delivery receipts and records the domain change.
Preserve a pre-upgrade state archive when installing this version: earlier bundles
cannot decode its new activity/disposition record types.
