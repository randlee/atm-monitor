# Oversight notification policy

These routing rules come from Rand's September 9 instructions. Healthy
operation is silent on Telegram. Keep local observations and history; send a
status table when Rand asks for it.

| Condition | Action | Recipients |
|---|---|---|
| Current CI failure | Identify the PR/head and failing checks; request remediation | Team-lead |
| Confirmed merge conflict | Identify the affected PR/branch and evidence; request resolution | Team-lead |
| Stack needs routine maintenance | Identify the diagnostic and responsible work | Team-lead |
| Confirmed stack-maintenance rule violation | Cite the rule, evidence, and corrective action | Team through team-lead **and Rand on Telegram** |
| Out-of-order branch/PR merge | Cite parent/child relationship and merge evidence | Team through team-lead **and Rand on Telegram** |
| Serious problem | Explain impact, affected work, prior attempts, and needed decision/action | Rand on Telegram; involve the responsible team as appropriate |
| Healthy operation | Record locally; no unsolicited operator report | None |

Serious problems include loss of reliable monitoring for a team, lost or
incorrectly integrated work, repeated failed recovery, and unresolved problems
that the team cannot correct. An isolated partial query or ordinary long task
does not establish a serious incident. For ambiguous cases, the oversight
agent investigates the evidence and states its uncertainty.

## Stack rules

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
