---
name: atm-oversight
description: Detect significant project activity, establish phase planning and development state from evidence, record phase events, and report or investigate monitored ATM work.
---

# ATM oversight

This is a self-contained skill. Run commands from the directory containing
this `SKILL.md`, using the deployment's configured Python interpreter, config,
and state paths. All scripts and references are inside this directory.
The configuration and current snapshot identify the monitored teams.

The authoritative source is `atm-monitor/skills/atm-oversight`. Installed copies
are distribution artifacts: propose fixes in atm-monitor, test, then distribute
the whole bundle. Do not patch a deployed script or policy as a permanent fix.
Read the deployment's rollout instructions before enabling schedules or sends.

## Your responsibility: discover and follow the work

Do not wait for an existing PR or phase configuration to tell you planning has
started. The general activity cron must establish planning/development work
from structured message and Git evidence before waking you; agent activity
alone is insufficient. You validate a qualified handoff and establish its
phase context. Repos already pending/active in the monitoring registry must
not trigger you from the activity cron again; their repo cron owns the work. A couple of questions to an agent is
not a new phase. A newly used planning branch plus phase-bound plan-hardening
assignments/artifacts is evidence of substantive planning. An open PR from a
`plan/*` source branch also establishes planning; its merge signals plan ready.
Record these PR milestones with source timestamps. Plan ready is distinct from
development started or phase complete.

On activity discovery, planning work, or a lifecycle change, read and follow
[phase detection and event recording](references/phase-discovery.md). It defines
significance, your next action, hardening-round counting, phase-event logging,
and the general-cron → repo-specific-cron handoff. Record evidence before
reporting state or metrics. Never substitute a watch-list entry, an idle agent,
or queue disappearance for a phase state transition.

## New phase onboarding

When phase monitoring returns `onboarding_requests`, invoke the separate
`oversight-onboarding` skill for each request. It verifies the project and saves
its repository, phase, evidence-backed `start_time`, and worktree settings in
the deployment config. Do not guess the start time or replace an active scope
to dismiss a request. If the skill is unavailable, return the pending request
to the caller. Legacy configs without a start time collect repository history
and report `unscoped_projects`; they require onboarding before continuous use.

## Reporting

Read the phase event log for planning/lifecycle status and hardening metrics.
The current report script supplies sprint/branch tables, not those metrics.
Run `python scripts/oversight/report.py --state-dir <state> --team <team>`
from the skill directory. Return its `Sprint | DEV | QA | CI | FND` table. Preserve
freshness and coverage notes; `—` means evidence is missing, not success.
Read-only report requests do not require a model to reconstruct status from
memory. The script can include structured QA evidence produced below.

For current QA details, use
`python scripts/oversight/mine_messages.py --team <team> --as <actor> --kind qa-report --with-bodies`
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
file to force concurrent collection. See [installation](references/installation.md).
The lower-level `tick.py` remains available for a deliberate scan of all
configured teams; it is not an additional scheduled job.

## Findings and follow-up

Read [notification policy](references/notification-policy.md) when handling
findings. Run `python scripts/cron/check_health.py --state-dir <state>` for
deterministic findings and pending recipients. CI failure and merge conflict
go to team-lead. Confirmed stack-rule violations and out-of-order merges go
to the team and Rand on Telegram. Serious problems escalate to Rand.
Healthy operation stays silent on Telegram; return status when asked.

Use task events, roster/Herdr observations, git activity, CI, and stack
diagnostics as distinct evidence. `working`, `idle`, and `done` describe
Herdr process observations, not task or sprint completion. CI success does
not establish QA approval or a maintained stack.

When the cause needs investigation, read the
[investigation procedure](references/investigation.md). A high QA-round count
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

See [operations](references/operations.md) for scheduling, recovery, and exit
codes, and [the improvement plan](references/improvement-plan.md) for rollout.
For a planned naming/hook rollout, use the
[repository consistency procedure](references/repo-consistency.md). Its validator
is `scripts/check_naming.py`; hook examples are under `assets/hooks/`.
