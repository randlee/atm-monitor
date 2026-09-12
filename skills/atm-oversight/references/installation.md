# Monitoring installation and usage

The monitor is independent of the agent harness. Two deterministic scripts
run on a scheduler; an oversight agent handles findings and report requests.
The initial implementation uses local JSON state and a configured catalog of
candidate teams and repositories.

## The two scheduled jobs

| Job | Inputs | Persistent result | When it needs oversight |
|---|---|---|---|
| `detect_activity.py` | Herdr activity and ATM rosters for configured teams | Watch list with membership evidence and observation times | Ambiguous matching identities or failed detection sources |
| `monitor_phase.py` | Watch list; team-specific tasks/events, Git, CI, worktrees, stacks, and plans | Phase/sprint observations and current source health | Pending health findings or monitoring failures |

Detection runs cheaply across candidate teams. It enrolls a team when its
roster reports active/working/blocked work, or a working Herdr agent matches
both roster identity and repository/worktree context. Names alone are not
sufficient. Enrollment is a local state update, not an operator notification.
Unmatched agents outside the configured catalog are recorded for discovery
review; they are not silently enrolled or repeatedly sent to oversight.

Phase monitoring reads that list and makes queries scoped to each watched
team. One invocation currently loops over watched teams; separate per-team
scheduler jobs are not required. It retains discovered phases through quiet
periods. Activity disappearing does not establish phase completion or retire
the watch entry. If detection is stale or missing, it checks all configured
teams; unavailable roster evidence also keeps the affected team eligible.

Discovery currently joins plan identities to PR branches. Activity establishes
that a team needs monitoring, not which historical phase is currently active.
Assignment-driven phase identification, explicit retirement, and automatic
enrollment of previously unconfigured teams remain improvement work.

## Output and return-value contract

These codes apply to the two scheduled entrypoints above. Lower-level tools
retain their existing documented diagnostic codes.

| Exit | Meaning | Default stdout | Scheduler/adapter action |
|---|---|---|---|
| 0 | Completed; no new oversight action needed | Empty | Keep quiet |
| 1 | Actionable finding or ambiguous team identity | JSON payload | Hand to oversight, not directly to the operator |
| 2 | Monitoring/configuration/source failure | JSON payload, including any collected findings | Retain evidence and route a monitoring-failure investigation |
| 3 | Another invocation holds the state lock | Empty | Skip this overlap; allow the running job to finish |

Use `--json` for manual diagnostics; it prints a summary even on exits 0 and 3.
Snapshots retain observations regardless of whether stdout is silent.
Onboarding requests return exit 1 for oversight, not an operator incident.
Exit 0 means no pending action from these checks, not proof that phase/plan
associations or QA evidence are complete.

Scripts own the classification. An adapter only routes the returned payload
through the deployment's ATM or harness transport. Do not use a generic
"every nonzero means notify Rand" rule: findings, monitor failure, and overlap
have different meanings. No sender is installed by these scripts.

## Install and configure

1. Install the complete `atm-oversight` skill directory from a recorded tested
   atm-monitor revision. Its deployment receipt identifies the bundle contents.
   Run the commands below from that installed directory.
2. Make Python 3.11+, Git, `atm`, `herdr`, authenticated `gh`, and `gh stack`
   available in the scheduler and oversight execution environments. These
   environments must reach the monitored repos and local ATM/Herdr services.
3. Copy `assets/monitor.example.json` to a deployment-owned config file. Set each
   candidate team's `name`, explicit querying `actor`, `repo`, and optional `worktrees`. Paths resolve
   relative to the config file; absolute paths are also accepted. JSON paths
   do not expand shell variables or `~`.
   Install the separate `oversight-onboarding` skill and use it to add each
   active phase to the team's `projects` array with an evidence-backed
   `start_time`. Multiple overlapping phases in the same repo are supported.
   The empty example array requires onboarding; it is not a production scope.
   The actor is never inferred from `.atm.toml` or the caller environment.
   ATM task and mail queries pass `--as` and `--team`; `doctor` and `members`
   expose only `--team`, so their subprocess environment explicitly pins
   `ATM_IDENTITY` and `ATM_TEAM`. The global template catalog has no actor/team
   selector. Standalone ATM collectors and message mining require `--as` too.
   Each phase tick records `atm doctor --json` and gates on
   `daemon_context.http_api_version`, not the release number. Task collection
   uses BA.2's `atm list --tasks --json` / `atm list --task-events ID --json`
   for HTTP API 1.5.x, and BA.4's `atm task list --all --json` /
   `atm task events ID --json` for major 1 at version 1.6.0 or later.
   BA.2 task queries already return every state; its `--all` flag is a
   conflicting mailbox selector and must not be supplied. Pre-BA, unknown,
   and future-major task APIs remain explicitly unavailable. A failed query
   is not retried using another schema/command family. Mail, members, doctor,
   and repository observations can still be collected during this transition.
   Retain the daemon release and HTTP API with observations. Validate the
   current development builds before deployment, then have omega-prime retest
   the installed bundle against each newly switched patch build. A published
   release is not a prerequisite for query validation or migration.
   Current BA.4 `--all` is an all-members open queue, not historical listing;
   list and events default to 200 rows. The adapter marks the task inventory
   partial, retains observed task IDs across outages, and keeps querying their
   events after closure. Event responses reaching 200 rows remain partial.
   Tasks created and closed between polls are an explicit discovery gap.
   Full-state listing and pagination are tracked in atm-core #1411; no release
   boundary for that capability is assumed.
4. Select separate activity and phase state directories, such as
   `<state>/activity` and `<state>/phases`. Use stable paths throughout the
   pilot. Temporary storage is acceptable initially; losing it loses history.
5. Run `python3 -m unittest discover -s tests -q` from the skill directory.

From the skill directory, run each command independently with actual paths:

```sh
python3 scripts/cron/detect_activity.py --config /absolute/path/to/monitor.json --state-dir /absolute/path/to/state/activity --json
python3 scripts/cron/monitor_phase.py --config /absolute/path/to/monitor.json --activity-dir /absolute/path/to/state/activity --state-dir /absolute/path/to/state/phases --json
python3 scripts/oversight/report.py --state-dir /absolute/path/to/state/phases --team atm-dev
```

Do not chain these with `&&`: an actionable finding or degraded observation
can return nonzero while still committing useful state. Inspect the JSON and
coverage notes. The phase job falls back to broader collection if detection
has not run yet, so scheduler ordering need not be exact.

## Wire up scheduling

Start with local capture, for example every two minutes for detection and
every five minutes for phase monitoring. These are pilot settings, not proven
production intervals. For OS cron, substitute the actual paths:

```text
*/2 * * * * /path/to/python3 /path/to/atm-oversight/scripts/cron/detect_activity.py --config /path/to/monitor.json --state-dir /path/to/state/activity >> /path/to/activity-actions.log 2>&1
*/5 * * * * /path/to/python3 /path/to/atm-oversight/scripts/cron/monitor_phase.py --config /path/to/monitor.json --activity-dir /path/to/state/activity --state-dir /path/to/state/phases >> /path/to/phase-actions.log 2>&1
```

Set the scheduler's PATH for the service executables and rotate these logs.
Use the same executable and arguments with launchd or Windows Task Scheduler.
These entries capture actionable/error output; they do not invoke an agent.
Inspect snapshot ages to verify healthy polls are happening despite empty logs.
Do not also schedule the legacy `tick.py`: the phase job calls it internally.

For an agent harness, keep these same scripts and state contracts and adapt
only registration, wake-up, and delivery. See the
[Hermes adapter](hermes-installation.md) for verified Hermes options.

## How oversight uses the skill

| Procedure within `atm-oversight` | Use | Supporting scripts |
|---|---|---|
| `SKILL.md` | Handle a finding; answer status requests; verify follow-up | `report.py`, `check_health.py`, `record_intervention.py` |
| `references/investigation.md` | Explain stalls, repeated QA, or ambiguous evidence | `mine_messages.py` |
| `references/repo-consistency.md` | Planned rollout of naming and metadata conventions | `check_naming.py` and the sample hooks |

The separate `oversight-onboarding` skill handles `onboarding_requests` from
the phase monitor. Its `scripts/configure_project.py` writes project settings
atomically and preserves other simultaneous phases. It does not install jobs
or deliver incidents. Current automatic discovery requires an open PR joined
to a parsed sprint plan; discovery from assignments before the first PR remains
an improvement item. Explicit onboarding can establish settings earlier.

Give the agent the skill directory, interpreter, config, activity-state and phase-state
paths, allowed team catalog, and deployment notification routes. The main skill
returns `Sprint | DEV | QA | CI | FND`; it does not infer QA approval from CI.
Message mining is bounded and on demand. Naming hooks are installed separately
during an agreed repository rollout, preserving existing gates.

Use this initial pilot instruction with actual paths:

```text
Use atm-oversight. Skill directory: <path>; Python: <path>; config: <path>;
activity state: <path>; phase state: <path>; team: atm-dev.
Run the two scheduled scripts once, inspect source health, render the status
table, and inspect findings. Use the phase state directory for report.py and
check_health.py. Read the notification policy from skill-directory/references.
Preserve unknown/stale/partial evidence. Read references/investigation.md when a finding
needs explanation. Return incident keys, evidence, intended recipients, and
proposed messages here. This is a capture-only pilot: do not send messages or
record proposals as delivered, alter monitored work, or install schedules/hooks.
```

## Delivery policy and rollout boundary

After routing is enabled, CI failures/conflicts go to team-lead. Confirmed
stack-rule/order violations go to team-lead and Rand on Telegram; serious
problems escalate to Rand. Healthy operation stays quiet; return a status table
when asked. See the full [notification policy](notification-policy.md).

An oversight wake-up is distinct from a team/operator delivery. Pending routes
remain pending until their actual receipts are checkpointed. Acknowledgment
is not resolution. The transport adapter still needs verified receipts,
retry/deduplication, and follow-up scheduling before unattended operation.
The scripts currently emit findings; they neither send messages nor launch an
LLM. Complete that integration and the overnight recovery pilot before
claiming continuous oversight.

See [operations](operations.md) for storage/recovery details and the
[improvement plan](improvement-plan.md) for the remaining rollout work.
