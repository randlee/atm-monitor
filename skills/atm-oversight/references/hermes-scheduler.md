# Hermes scheduler bridge

`scripts/cron/hermes_monitor.py --config <monitor.json> --state-dir <state>`
runs activity collection followed by configured phase collection. Its last line
is a Hermes `wakeAgent` decision. Attach it through a profile-local Python
launcher with `cron create --script`; do not use `--no-agent` for this job.
The launcher must explicitly supply the installed bundle path and command PATH.

Only newly pending incidents and collection-health changes wake the agent.
Unchanged incidents are silent. Recovery requires clean coverage before a later
recurrence can wake again. Collection failures route to `amon@atm-monitor`.
The bridge records `state/scheduler/last_run.json` on every completed collection,
including quiet ticks. Verify that receipt from a real scheduled execution;
registration alone does not prove filesystem access or collection health.

Wake reservation is persisted before Hermes starts the agent. This prevents
repeat wakes but is not a delivery acknowledgment: after an agent-start failure,
inspect the scheduler failure and reconcile the incident before deliberate
retry. Never clear all gate state as a routine retry. Delivery checkpoints remain
separate in the intervention ledger. A corrupt gate is an operational defect,
not permission to discard deduplication history.

This bridge schedules collection for configured work. It does not yet implement
qualified new-phase discovery, repository ownership handoff, automatic closure,
or the complete phase report. Do not describe it as the finished lifecycle loop.
In particular, Herdr activity alone does not wake the agent through this bridge.

On hosts where OS cron cannot access Documents, test the existing Hermes gateway
execution context with a scheduled read probe. Do not assume launchd bypasses
privacy controls, reset system-wide permissions, or move repositories. Remove
only the superseded monitor crontab entry after its replacement is verified.
