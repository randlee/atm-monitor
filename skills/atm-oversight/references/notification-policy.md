# Oversight notification policy

These routing rules come from Rand's September 9 instructions. Healthy
operation is silent on Telegram. Keep local observations and history; send a
status table when Rand asks for it.

| Condition | Action | Recipients |
|---|---|---|
| Current CI failure | Identify the PR/head and failing checks; request remediation | Team-lead |
| Confirmed merge conflict | Identify the affected PR/branch and evidence; request resolution | Team-lead |
| Open PR blocked, behind its required base, or unstable | Identify the PR and exact merge-state diagnostic; request investigation/remediation | Team-lead |
| Stack needs routine maintenance | Identify the diagnostic and responsible work | Team-lead |
| Confirmed stack-maintenance rule violation | Cite the rule, evidence, and corrective action | Team through team-lead **and Rand on Telegram** |
| Out-of-order branch/PR merge | Cite parent/child relationship and merge evidence | Team through team-lead **and Rand on Telegram** |
| Serious problem | Explain impact, affected work, prior attempts, and needed decision/action | Rand on Telegram; involve the responsible team as appropriate |
| Excessive, duplicate, or unjustified oversight wakes; unclear operational skill instructions | Report the monitoring defect with wake/event evidence for a master script/skill fix | atm-monitor maintainer (`amon@atm-monitor`) |
| Healthy operation | Record locally; no unsolicited operator report | None |

Serious problems include loss of reliable monitoring for a team, lost or
incorrectly integrated work, repeated failed recovery, and unresolved problems
that the team cannot correct. An isolated partial query or ordinary long task
does not establish a serious incident. For ambiguous cases, the oversight
agent investigates the evidence and states its uncertainty.

## Agent wake gate (Rand, September 12)

A phase-monitoring cron tick collects and records evidence without invoking an
agent. Routine development assignments, commits, activity observations, and
per-sprint B/C/I finding counts update the phase record silently. An agent is
triggered only when deterministic evaluation detects a notable event requiring
investigation or intervention, or Rand explicitly requests an agent action.

Qualifying examples:

- CI transitions into failure for the relevant PR/head/check.
- A new CI/merge requirement block or merge conflict affects the monitored PR.
- An identified agent becomes idle while still owning an active task, based on
  fresh assignment/task-event evidence joined to its process identity. Idle
  without an active assignment is not a trigger. Apply a configured handoff
  grace interval where needed; do not invent a universal timeout.
- An integration PR closes without merging: investigate, then escalate to Rand
  under the phase-closure procedure.

Detect changes relative to durable prior observations and retain stable event
and incident identities. A persistent CI failure, unchanged merge block, or
continuing idle condition is not a new event each tick. A verified recovery
followed by recurrence can trigger again. Unknown/unavailable evidence must not
be treated as healthy recovery and rearm the same failure. A first observation
of an existing actionable problem may be handled once as newly observed; do
not claim a previously healthy state when no baseline exists.

Persist a pending handoff before invoking the agent, and suppress duplicate
wakes while that handoff is pending or handled. Wake deduplication is separate
from notification delivery/acknowledgment checkpoints: an undelivered route
must not automatically wake an LLM every poll. Retry failed handoffs through a
bounded, recorded retry policy. An unchanged incident can wake again only for
an explicit follow-up deadline, material escalation, or other new notable event.

The current health/incident helpers provide some incident keys and delivery
checkpoints, but the durable agent-wake gate and idle-with-active-task rule
still require runtime integration. Do not wire all `attention` output or all
new snapshots directly to an agent.

## Stack rules

Inspect local stacks with `gh stack view --json`. Active branches may omit
their head SHA; retain rebase diagnostics with an explicitly unknown head.
Missing head evidence must not discard the stack or suppress maintenance
findings. A branch outside a stack is a valid absence result, and its PR still
receives the same CI and mergeability checks from the repository PR inventory.

For both stacked and non-stacked open PRs, `CONFLICTING`/`DIRTY` produces a
conflict finding; `BLOCKED`, `BEHIND`, and `UNSTABLE` produce a team-lead
attention finding. Preserve the diagnostic: blocked requirements or unstable
checks do not prove a Git conflict or a stack-rule violation. `UNKNOWN` alone
is not evidence of a problem; closed and merged PRs do not trigger these routes.
These findings require team-lead delivery when delivery is enabled; the Stage 1
pilot continues recording pending routes without sending incident messages.

- **STACK-ORDER-001:** A dependent sprint's PR must merge after its declared
  parent PR. Use the plan's parent-branch relationship and recorded PR merge
  times; do not infer order from names or array position. Equal timestamps do
  not prove a violation, and a missing parent record is a coverage gap.
  The parent must be another identified sprint. A final phase integration PR
  contains its sprint merges and correctly lands after them; it is not a
  prerequisite sprint PR.
- **STACK-MAINT-001:** Follow the repository's declared merge-forward/rebase
  rules before starting the next dependent development/fix round. Confirm
  the relevant parent change, round boundary, and missing maintenance before
  classifying a violation. A single `needsRebase` flag establishes maintenance
  work, but alone does not prove that a required round boundary was violated.

The deterministic checker covers current CI failures, explicit conflict
diagnostics, stack-maintenance flags, observable parent-before-child merge
violations, and simultaneous loss of Herdr/roster/task collection. Other serious
or rule-violation cases are decisions for evidence-based oversight investigation.

## Delivery and follow-up

`scripts/cron/check_health.py --state-dir <state>` emits findings, evidence,
stable incident keys, required routes, and pending routes. It sends nothing.
The oversight agent delivers through its configured ATM and Telegram tools.
`operator:telegram` is a routing label, not a chat ID or an ATM recipient.

After confirmed delivery, run `scripts/oversight/record_intervention.py` with
the incident key, the exact route label, `--status sent`, and the actual
message ID. Each destination is checkpointed separately; a team notification
does not count as delivery to Rand. A delivery error must remain pending and
visible; never mark an attempted send as delivered.

Record acknowledgments separately. Mark `resolved` only after evidence shows
the underlying condition is corrected. This permits a later recurrence to
notify again. Review unresolved incidents on later ticks; escalate serious or
unresolved problems to Rand instead of sending the same team reminder forever.
An unchanged incident already delivered to its required recipients is not
resent on every poll. Follow-ups that need a new message should explain what
changed or why an intervention deadline has been exceeded.

Record the minimal useful context: team, phase/sprint/task, PR/head, symptom,
evidence times/IDs, owner, and concrete next action. For eight rounds of QA,
mine the discussion before proposing a repair. Notifications are not permission
to restart agents, rewrite branches, merge PRs, or close tasks automatically.

The monitoring kit does not yet include a Telegram transport or an unattended
delivery worker. Select and validate the deployment's gateway and complete the
pilot before enabling automatic delivery. Healthy tick logs stay local even
after delivery is enabled.

## Monitoring defects belong to the maintainer

Omega-prime follows the deployed skills and the event-driven handoff; Rand
should not have to tell him what to do on each wake. If a wake has no new
notable event, duplicates a pending/handled event, or repeated triggering
indicates faulty qualification/deduplication, escalate the defect to the
atm-monitor maintainer (`amon@atm-monitor`). Include repo/phase, scheduler job,
wake/event IDs and timestamps, trigger reason, prior handled/pending state,
relevant source evidence, and deployed bundle revision. Preserve unknown fields.

The maintainer owns diagnosis, regression coverage, master script/skill fixes,
and verified redistribution. Omega-prime should not ask Rand to debug wake
frequency or silently patch deployed copies. Duplicate defect reports share
one incident with new evidence appended; do not create another wake/report
loop while the original defect is open. Do not stop required monitoring merely
to hide excessive wakes. User-facing decisions about the monitored project,
such as unresolved unmerged integration closure, still escalate to Rand.

Automated wake-rate and duplicate-reason diagnostics require the durable wake
ledger. Until implemented, Omega-prime must report observed excessive triggering
through this same maintainer route; do not claim automatic detection exists.
