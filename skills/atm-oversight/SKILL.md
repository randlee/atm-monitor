---
name: atm-oversight
description: Report on monitored ATM phases and sprints, interpret collection health and CI/stack findings, and route focused investigations using atm-monitor state.
---

# ATM oversight

Use the configured atm-monitor checkout, state directory, and team. Resolve
paths from the checkout; do not embed a developer's home directory in commands.
The configuration and current snapshot identify the monitored teams.

## Reporting

Run `python scripts/oversight/report.py --state-dir <state> --team <team>`
from the checkout. Return its `Sprint | DEV | QA | CI | FND` table. Preserve
freshness and coverage notes; `—` means evidence is missing, not success.
Read-only report requests do not require a model to reconstruct status from
memory. The script can include structured QA evidence produced below.

For current QA details, use
`python scripts/oversight/mine_messages.py --team <team> --kind qa-report --with-bodies`
and save its JSON output to a local evidence file. Pass that path through
the report's `--qa-evidence` option. The renderer requires a matching PR and
full commit SHA before applying a verdict or finding count.

## Collection health before intervention

Read the newest valid snapshot using `scripts/cron/state_store.py` or the
report command. Its `sources` are the current collection results;
`last_good` preserves older observations and must be identified as stale when
used. A failed source, partial query, missing plan association, or empty task
ledger does not establish that an agent has no work.

Cron runs `scripts/cron/detect_activity.py --config <config> --state-dir <activity-state>`
and `scripts/cron/monitor_phase.py --config <config> --activity-dir <activity-state>
--state-dir <phase-state>`. Use the phase state for reports, health checks,
and intervention records. Detection maintains the watch list; phase monitoring
makes team-specific queries. Both are read-only against ATM/GitHub. Their exits
are 0 (silent success), 1 (attention), 2 (monitor failure), and 3 (overlap).
`--json` prints manual diagnostics even on healthy runs. Do not remove a lock
file to force concurrent collection. See [installation](../../docs/installation.md).
The lower-level `tick.py` remains available for a deliberate scan of all
configured teams; it is not an additional scheduled job.

## Findings and follow-up

Read [notification policy](../../docs/notification-policy.md) when handling
findings. Run `python scripts/cron/check_health.py --state-dir <state>` for
deterministic findings and pending recipients. CI failure and merge conflict
go to team-lead. Confirmed stack-rule violations and out-of-order merges go
to the team and Rand on Telegram. Serious problems escalate to Rand.
Healthy operation stays silent on Telegram; return status when asked.

Use task events, roster/Herdr observations, git activity, CI, and stack
diagnostics as distinct evidence. `working`, `idle`, and `done` describe
Herdr process observations, not task or sprint completion. CI success does
not establish QA approval or a maintained stack.

When the cause needs investigation, use the adjacent
[atm-investigate skill](../atm-investigate/SKILL.md). A high QA-round count
is a reason to inspect the dialogue, not a diagnosis or automatic restart.

Before an intervention, inspect existing task reminder and lead-notification
events and the latest relevant team response. Avoid duplicating an intervention
already under way. A useful escalation states the affected sprint/PR/task,
evidence and its time, current owner/blocker, and the smallest concrete next
step. An acknowledgment is not resolution; verify the underlying condition
on a later tick. Never infer permission to restart agents, rebase branches,
merge PRs, or close tasks from a monitoring finding.

After each confirmed send, checkpoint the actual message ID using
`scripts/oversight/record_intervention.py --state-dir <state> --incident <key>
--recipient <route> --status sent --evidence-id <message-id>`. Use the checker's
route label verbatim; checkpoint team and Telegram deliveries independently.
Record `acknowledged` and `resolved` when their evidence arrives. An attempted
or failed delivery is not `sent`. Review unresolved incidents across ticks;
avoid repeating unchanged notifications while escalating serious unresolved
problems to Rand.

The current scripts collect and report; they do not send notifications or
repair repositories. Use the deployment's configured ATM/Telegram delivery
mechanism and the user's intervention policy when those are enabled. If no
delivery mechanism is configured, return the actionable report to the caller
and identify the delivery gap.

See [operations](../../docs/operations.md) for scheduling, recovery, and exit
codes, and [the improvement plan](../../docs/improvement-plan.md) for rollout.
