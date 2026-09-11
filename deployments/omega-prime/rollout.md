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

Current deployment intent: stage 1. Do not start stages 2–4 as a side effect of
receiving the test instructions. Advance only after the previous stage's
evidence has been reviewed with Rand. This staged validation is the requested
rollout process, not a general restriction on reading evidence or fixing bugs.

The [stage-1 acceptance record](stage-1-acceptance.md) confirms the manual
functional smoke test and lists its remaining coverage limits. Scheduled
capture is the next stage; acceptance itself does not enable scheduling.

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
hooks, enable schedules, or send incident notifications during this stage.
The selected team's source repository remains read-only.

## Later-stage constraints

Routing follows the packaged notification policy: CI/conflicts to team-lead;
confirmed stack-rule/order violations to the team and Rand; serious incidents
to Rand; healthy operation quiet. Transport and wake-up reliability remain
implementation work, not established by passing stage 1. Follow-up work is
tracked in Beads issue `omega-prime-emv` and its subsequent rollout issues.
