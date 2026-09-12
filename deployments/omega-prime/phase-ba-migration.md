# Phase BA oversight migration

Omega-prime dogfoods the features added during Phase BA. The atm-monitor
maintainer owns query compatibility, development-build verification, bundle
upgrades, and defect reports to the ATM sprint owners. Validation happens as
features arrive; a published release is not a prerequisite.

## Query selection

Record the installed daemon release at every switch; Fenix increments its
patch version. Also retain the live doctor HTTP API and source commit so an
unreleased fixture build cannot be mistaken for the installed build merely
because both report the same workspace version.

| Observed HTTP API | Task rows | Task events | Expected coverage |
|---|---|---|---|
| Pre-BA / unknown major | Explicit incompatibility | Explicit incompatibility | No claim of empty/complete coverage |
| 1.5.x (BA.2) | `atm list --tasks --json` | `atm list --task-events ID --json` | All states and complete histories; no mailbox `--all` flag |
| Major 1, 1.6.0+ (BA.4) | `atm task list --all --json` | `atm task events ID --json` | Open tasks across members; 200-row list/event limits in the pinned build |

BA.4 is a queue view by design: `--all` selects all members, not closed tasks.
Fenix confirmed this in `01M29KQK0ZKTKVTBX971N4HFVN`. Full-state queries and
pagination are the follow-on capability [atm-core #1411](https://github.com/randlee/atm-core/issues/1411),
with no release assigned yet. Do not misclassify the queue behavior as a BA.4
defect. The monitor stores observed task IDs durably, keeps querying them after
they leave the queue, and preserves IDs across outages and phase onboarding.
Unseen tasks that open and close between polls and potentially truncated event
histories remain coverage gaps. Returned data is retained even when partial.

Each team query carries `--team TEAM --as ACTOR`. Doctor and members lack
`--as`, so their subprocess environment explicitly sets the configured
`ATM_IDENTITY` alongside `--team`. Queries use the daemon; no direct ledger
access or failed-command retry into another schema is permitted.

The first deployed BA.2 boundary is release **1.5.15 / HTTP API 1.5.0**,
confirmed by Fenix's switch receipt `01M29N2NHP3987A8DKT7PVYEY3` and a live
doctor observation. Source: `integrate/phase-ba` at `fd242df7a`, plus version
bump `7736ec31b`, tag `prerelease/v1.5.15`. BA.4's deployed release boundary
is still pending its own receipt. Do not infer it from an unpublished branch
version. The observed HTTP API continues to select the query form, including
fixture builds sharing a workspace release number. The previous host pair
was release 1.5.14 / API 1.3.0.

## Verification and rollout checkpoints

1. Pin the development SHA and build its matched CLI/daemon pair. Fenix's
   initial targets are BA.2 `4187131649b721f5480811553aaab94fcbb309c3` and
   BA.4 `5ab184d7520ad6505026623f1fce7fe3f19fd2d2`. Use a container or the Colima
   testbed for the fixture daemon; never start a second daemon under the host
   account, even with a different ATM_HOME.
2. Seed isolated fixture tasks through the supported test harness. Compare
   actual list/event output to the known open and complete task inventory,
   close outcomes, queue positions, and event sequences. Run the monitor's
   actual query adapter over the same fixture twice. Verify queue-only and
   capped output as the pinned BA.4 contract, and quantify what is missing for
   oversight rather than claiming full-state coverage. Preserve exact commands,
   versions, source SHA, expected versus observed rows, and failures.
3. Upgrade omega-prime only while its collectors are quiescent. Verify both
   skill receipts and their tests, preserve evidence-backed phase starts, and
   make query identity explicit in the deployment config.
4. At each host patch switch, omega-prime returns doctor metadata, selected
   query form, full row/history counts, two collection results, and evidence
   gaps. Preserve last-good observations as historical evidence; never report
   a failed source as idle or complete.
5. Re-pin and re-verify at BA.4 landing, including the BA.3/BA.5 forward merges.
   Track escalation summaries by prefix and retain unknown kinds, task
   states/outcomes, and additive row fields. At phase release, review the
   accumulated build and installed-dogfooding results.

## Defects and ownership

Send Fenix each defect with source SHA, daemon release/API, exact command,
expected and observed rows, and reproduction evidence. He routes it to the
owning sprint. Schema error classification remains atm-core #1410; the earlier
reader shim and #1409 were retired as superseded by Phase BA. Host-pair
switching and schema remediation remain with Fenix/team-lead.

## Current evidence

- Omega-prime confirmed quiescence and existing bundle
  `ddadee1cd1bf94266e615f63e4ec84e701370653304d5bfe7c7d4eb2b49471fe` in
  message `01M29KEQBYKQY7EFG59V1NXH1B`.
- Query-form selection and failure handling have local regression coverage.
- Real matched CLI/daemon fixtures passed at both pinned source commits in
  isolated Linux containers. BA.2 selected `list`, returned assigned
  `legacy-open` and complete `legacy-close`, and read the closed task's
  `assigned` → `completed` history with `close_outcome: completed`.
  BA.4 selected `task`, returned only assigned `ba4-open`, and read the closed
  `ba4-close` task's same two-event sequence. The old `list --tasks` command
  failed on BA.4 with exit 3, confirming the need for version selection.
- These fixtures establish open/closed query behavior; they do not establish
  migrated/started-event compatibility or live host acceptance. The 200-row
  boundary has source and regression evidence, not a large live fixture yet.
- Local validation passed 141 monitoring, 10 onboarding, and 9 distribution
  tests. The next installed retest remains a separate rollout checkpoint.

## Installed upgrade receipt

Source commit `4715588` was distributed after Omega-prime's quiescence receipt.
Both installed inventories match their receipts; installed tests passed
141 monitoring and 10 onboarding tests (9 distribution tests also passed).

| Bundle | SHA-256 |
|---|---|
| atm-oversight | `fbcf4d7f46328a1e14398770237384e3843e0d3ed64198c2f3ee551256a14699` |
| oversight-onboarding | `df3e2ae83042bf05b8a345afe3b98225908a8cbbfa0627ef88c8282900460104` |

The config now explicitly uses actor `omega-prime`; both existing phase starts
and their evidence are preserved. Previous bundles and config were archived.
The two-pass installed collection/report retest was requested in
`01M29M65GBDXNJ2TYRMCKJBMV9`; Omega-prime completed it in
`01M29N5E1FSXE2JSXSKMRMJQCG` after the 1.5.15 switch. Scheduling and incident
delivery remain disabled. Fenix received the development fixture summary and
accepted-contract interpretation in `01M29M4KCHWZF2VPBVPRPC7PKX`.

## Host 1.5.15 verification

Two complete ticks using the installed bundle and deployment config ran in
separate validation state at September 12, 2026, 01:53:25 and 01:53:40 UTC.
Doctor confirmed 1.5.15 / API 1.5.0; both selected the BA.2 `list` interface.
Fenix's receipt reports the switch at 01:56 UTC, later than receipt arrival
and these observations; retain that as the reported time, not a verified time.

Both ticks observed 158 tasks, requested all 158 histories, and read 156
histories containing 1,645 events. They persisted 158 known task IDs, with
zero partial sources or deferred queries. Two histories failed on both ticks
and on sequential direct retries (exit 4, bounded mailbox reader error):

- `BA2-TASK-IDENTITY-QUEUE-SOLAR-1789162312`
- `ba-plan-critical-review`

The original `BA1-FIX-R2-1789162822` reproducer now succeeds with seven events.
The query migration works on the live host; complete event coverage remains
unaccepted. No root cause is inferred from the generic reader error. Fenix
received the reproduction/evidence report in `01M29N5D29QBE99KENXAKFDCAK`;
Omega-prime received the remaining-failure guidance in
`01M29N5D2VJWSD60G9CPSCNM2E`. Raw doctor output, snapshots, summary, and direct
reproducers are retained under `.local/validation/host-1.5.15/`. Omega-prime's deployment-state retest also completed, as recorded below. No host daemon or database was modified.

Omega-prime's receipt `01M29N5E1FSXE2JSXSKMRMJQCG` independently reproduced
177 sources, the same two failures, zero partial sources and zero deferrals.
Inspection of deployed snapshots 11 and 12 confirms **158 tasks, 156 readable
histories, and 158 persisted known IDs**; these supersede the receipt's stale
155/157 counts. The receipt's suggestion of corrupted data is unconfirmed;
root cause remains pending Fenix analysis. The deployed snapshot records no
intervention deliveries. Query migration is verified with explicit remaining
event coverage failures; BA.4 host-switch verification remains the next step.
