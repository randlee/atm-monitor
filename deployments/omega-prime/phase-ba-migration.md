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

The release-version boundaries for deployed BA.2 and BA.4 builds must be
recorded from Fenix's switch receipts, not inferred from an unpublished branch
version. Before those receipts exist, the live API contract determines the
query form. Release 1.5.14 / API 1.3.0 was observed on the host before migration.

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
`01M29M65GBDXNJ2TYRMCKJBMV9`; its result is pending. Scheduling and incident
delivery remain disabled. Fenix received the development fixture summary and
accepted-contract interpretation in `01M29M4KCHWZF2VPBVPRPC7PKX`.
