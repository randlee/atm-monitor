# Omega-prime oversight rollout

All master documents and code are maintained in atm-monitor. The skill under
`hendrix/omega-prime/skills/atm-oversight/` is a verified deployment copy.
Do not run self-improvement edits against that copy. Report a defect with its
bundle hash, script, inputs, and evidence; implement and validate the fix in
atm-monitor before distributing an upgrade.

| Stage | Enabled behavior | Evidence required to advance |
|---|---|---|
| 0 — archive and package | Retire legacy oversight skills, scripts, prompts, policies; install one self-contained bundle | Archive checksums verified; no old scheduled callers; deployed hash and isolated tests pass |
| 1 — manual read-only pilot | On-demand discovery, phase collection, report rendering, bounded investigation for atm-dev | Omega-prime loads the new skill, runs the supplied configuration, and returns sourced findings/proposed recipients with explicit gaps |
| 2 — scheduled capture | Two deterministic jobs; local output/state only | Actual scheduled runs, quiet-success behavior, overlap, outage, and restart recovery verified through an overnight run |
| 3 — supervised delivery | Wake oversight and exercise approved team/operator routes | Actual receipt IDs, independent recipients, retry/deduplication, healthy silence, and acknowledgment versus resolution verified |
| 4 — continuous operation | Unattended monitoring for the pilot team, then another team | Follow-up deadlines and serious-problem escalation work without manual recovery; discovery gaps have explicit treatment |

## Current operating instruction — September 12, 2026

Rand has authorized continuous activity monitoring and a repo-specific cron
while any phase remains open. The stages above record rollout history, not a
requirement to ask Rand for another manual test or repeated schedule approval.
Enable/reuse authorized jobs, verify actual scheduled execution, and escalate
failures to amon@atm-monitor. A manual test is useful only to isolate a fault;
it does not replace continuous operation or prove the scheduler works.

Expected operation: full available task history, current source coverage,
qualified activity handoff, suppression for already-owned repos, routine
assignment/B/C/I tracking, notable-event-only agent wakes, and immediate phase
reports. Distinguish code that exists from these required but unfinished
integrations. Escalate gaps with evidence; never explain them away as normal.

The September 12 cron diagnosis found OS cron firing but the Documents-hosted
launcher rejected with `Operation not permitted`. This is a scheduler execution
failure, not lack of cron firing. Empty success logs prove nothing; use run
receipts, snapshot timestamps, exit status, and scheduler failure records.
Current task history on ATM 1.5.16/API 1.7.0 supports `atm task events ID --all`;
the default recent-200 selection is not complete history.

The replacement execution path is the existing omega-prime Hermes gateway
scheduler, using a profile-local launcher for the installed
`scripts/cron/hermes_monitor.py`. Its five-minute job collects configured work
and uses a durable incident gate before agent startup. A scheduled read probe
on September 12 at 13:21 PDT confirmed that this execution context can read the
Documents-hosted skill and config. Actual collection receipts live under
`state/scheduler/last_run.json`; consult those and Hermes execution records before
claiming success. The job does not complete the outstanding qualified-discovery,
repo-ownership, and phase-closure integrations.

The [stage-1 acceptance record](stage-1-acceptance.md) is historical evidence.
The following manual procedure remains a diagnostic reference, not the current
operating-mode restriction.

## Stage 1 test procedure

The collection/onboarding update adds a separate `oversight-onboarding` bundle.
Before treating collection as scoped, onboard all active phases from evidence.
Keep overlapping phases as separate entries in each team's `projects` array;
do not reset older active phases when a new one starts. Re-run both bundles'
tests and the manual procedure after upgrading. A new bundle does not inherit
the previous bundle's live acceptance automatically.
See [collection validation](collection-validation.md) for live findings and the
ATM event compatibility issue that currently prevents complete event coverage.

Use the installed skill root, Python interpreter, config file, activity-state
and phase-state paths supplied in the delivery message. Read its `SKILL.md`
and `references/notification-policy.md` anew; cached legacy operating contracts,
TTL/ontology instructions, fixed-cadence reports, and old worker prompts have
been retired. Preserve missing evidence as unknown.

1. Run the bundle's tests from its installed directory.
2. Run `scripts/cron/detect_activity.py` once with the supplied config/activity
   state and `--json`. Inspect enrollment evidence and unresolved identities.
3. Run `scripts/cron/monitor_phase.py` once with the same config/activity state,
   the phase state, and `--json`. Inspect failures, partial coverage, and findings.
4. Run `scripts/oversight/report.py` with the phase state and `--team atm-dev`.
   Compare one sprint against read-only ATM/plan/PR evidence. If no phase can be
   identified, report that limitation; do not manufacture a table row.
5. If useful, follow `references/investigation.md` to retrieve bounded QA or
   assignment evidence. Do not mark messages read as a side effect of mining.
6. Return bundle hash, command results/exit codes, source health, the table,
   evidence gaps, and proposed notification recipients. No team/Telegram sends
   or delivery checkpoints are part of this capture-only stage.

Report test results to Rand or reply to the originating ATM testing request.
Do not rebase/merge branches, modify monitored repositories/tasks, install
hooks or send test incident notifications during this historical Stage 1
procedure. Current authorized scheduling follows the operating instruction above.
The selected team's source repository remains read-only.

## Later-stage constraints

Routing follows the packaged notification policy: CI/conflicts to team-lead;
confirmed stack-rule/order violations to the team and Rand; serious incidents
to Rand; healthy operation quiet. Transport and wake-up reliability remain
implementation work, not established by passing stage 1. Follow-up work is
tracked in Beads issue `omega-prime-emv` and its subsequent rollout issues.
