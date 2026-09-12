# Scoped collection and onboarding validation

The September 11 update supersedes the initial bundle's 100-PR and per-tick
task-event budgets. It also adds the separate `oversight-onboarding` skill and
independent settings for overlapping phases. Scheduling and incident delivery
remain disabled during Stage 1.

## Live query results

Three Luna agents were assigned independent read-only CI, event, and onboarding
checks against atm-dev/atm-core. The event check found 157 task rows and 157
unique task IDs. Two ticks each queried every task: zero deferred tasks, 139
successful event histories (757 events), and 18 failed event histories.
Successful histories were identical across ticks and had refreshed observation
times. A sequential sweep reproduced the same 18 failures, excluding collector
concurrency as their cause.

The CI collector returned identical records using page sizes two and ten in
a test-only September 11 window. The proposed AZ start window, September 9 at
15:49 UTC, returned 21 PRs. Live testing found merged PR #1386 with an empty
commit connection: the collector now retains its metadata and marks check
evidence unavailable. An unnamed Herdr terminal (name null or absent) also now remains
in the inventory without invalidating named agents. Both have regression tests.

Independent Luna CI checks matched GitHub CLI PR identities and check contexts:
21 PRs/305 contexts for the AZ window with page sizes 1, 7, and 100; 5 PRs/71
contexts for the BA window with page sizes 1 and 100. A boundary test excluded
PR #1397 at its exact creation timestamp. An all-history probe returned 1,197
PRs and confirmed #1386 as the sole empty head-commit connection.

Onboarding preserved separate AZ and BA entries, four local worktrees, and
idempotent repeated configuration. Verified phase-start evidence was AZ task
message `01M23DQCS105AKJKZWERBTMVNY` at September 9, 15:49:00.321784 UTC, and
BA dev-task `01M273DG8NAD17279PFN7FH1WS` at September 11, 02:05:48.181157 UTC.
All sampled phase PRs were created later than these boundaries. BA subsequently
superseded AZ (review message `01M28EG88P265WXJYPN7RVN63E`); the observed overlap
was historical. Reconcile lifecycle evidence before describing AZ as active.

These observations establish collection behavior, not complete phase discovery
or permission to start continuous monitoring. Phase start settings must be
verified from evidence during onboarding rather than copied from test windows.

## ATM event compatibility issue

The 18 failures are genuine source failures. Seventeen affected histories have
`migrated` events; one has a `started` event. The checked ATM storage reader's
`parse_event` accepts only assigned, acked, completed, rejected, reminded, and
lead_notified. Unsupported event decoding becomes a generic unavailable-reader
error. Increasing retries or bypassing the collector's validation cannot
establish complete history.

Reproduce without mutating tasks:

```sh
atm list --team atm-dev --task-events BA1-FIX-R2-1789162822 --json
atm list --team atm-dev --task-events BA2-TASK-IDENTITY-QUEUE-SOLAR-1789162312 --json
```

Both returned exit 4 with `bounded mailbox reader lane request failed` during
the check. Relevant atm-core source locations at that checkout:

- `crates/atm-storage-rusqlite/src/task_store.rs`: `parse_event`.
- `crates/atm-storage-rusqlite/src/task_ledger_reader.rs`: event decoding and
  conversion to `ReadLaneError::Unavailable`.
- `crates/atm-storage/src/contract.rs`: generic reader-error mapping.
- `crates/atm-storage-rusqlite/src/task_sql.rs`: event SQL, without a row limit.

The upstream improvement should preserve supported historical event variants
and report decoding/schema errors distinctly from daemon outages, with fixtures
for both variants. After the ATM reader is corrected, rerun both commands and
two full ticks; require every listed task history to be readable before claiming
complete event coverage. atm-core was not modified by this rollout.

Private snapshots and exact machine configuration stay in ignored local
validation storage. The installed monitor must continue showing these failures
until the source is fixed; do not mark them successful to pass acceptance.

## Omega-prime installed retest

Omega-prime reported the installed retest in message
`01M29B3YWHSBFGB3EP62MS6SX4`. Both receipt hashes matched the delivered bundles;
116 monitoring tests and 7 onboarding tests passed. The saved snapshot at
September 11, 22:58:17.364044 UTC independently confirmed 169 sources, 18 known
ATM event failures, no partial sources, no deferred tasks, and 15 unresolved
branch associations. Both phase scopes retained their evidence-backed starts.

Four findings had pending team-lead routes: CI failures on #1400 and #1394,
a conflict on #1394, and AZ.4 stack maintenance. No intervention deliveries
were recorded. These are observations at the snapshot time, not current
unqualified claims about the PRs. AZ.1–AZ.4 were reported merged. The retest
establishes installed-script behavior with the upstream event-coverage gap;
it does not establish full monitoring acceptance or enable scheduling.

## Active stack heads and merge requirements

Follow-up request `01M29H57HGCYR32MX60W7C68TG` reported a failure collecting
`feature/ba3-nudge-invariant`. A read-only check at September 12, 00:46 UTC
reproduced valid `gh stack view --json` output with no `head` field on either
active BA.2 or BA.3 entry. The previous decoder incorrectly required a head
on every unmerged branch and discarded the whole stack.

The decoder now preserves those entries and validates the name and boolean
diagnostics. Maintenance findings retain an explicitly unknown head rather
than guessing a commit. The live BA.3 collector returned `ok`, retaining its
`needsRebase: true` diagnostic. At the same check, PR #1402 was `MERGEABLE`
with merge state `BLOCKED`; this means merge requirements need attention,
not that a Git conflict was established.

Both stacked and non-stacked open PRs now route `BLOCKED`, `BEHIND`, and
`UNSTABLE` diagnostics to team-lead, alongside existing conflict/CI routes.
Unknown mergeability alone remains silent. Closed/merged PRs do not trigger
these routes. These are pending findings during Stage 1, not deliveries.

Rand approved a Markdown branch table with hierarchy in its first column.
The report now nests named PR bases and ordered stack dependencies, retains
non-stacked siblings, and labels conflicting/unknown parent evidence and
cycles. A fresh BA-window preview at September 12, 00:51 UTC included nine
PRs and the BA.3 stack; both source queries succeeded. Monitoring validation
passed 127 tests, including missing heads, lead routing, tree topology,
duplicate worktree observations, historical branches, and deep parent chains.
The installed bundle has not inherited this validation automatically; it
requires distribution and an installed retest before rollout acceptance.

## Reviewed upstream event patch

Omega-prime supplied a local-fix authorization and patch in
`01M29H57HGCYR32MX60W7C68TG`. Review confirmed the missing `Migrated` and
`Started` variants, but the supplied patch also needed SQLite's `event_name`
mapping and an exhaustive event replay test match updated before the workspace
could compile. The completed upstream fix is atm-core commit `12f9eb3a0` on
`codex/task-event-reader-fix`, prepared in an isolated worktree without changing
the shared develop checkout or running daemon.

Database-backed regression coverage inserts the historical strings directly
and reads them through both the synchronous task store and bounded async
ledger reader, including daemon and member actors. Validation passed:

- `cargo test -p atm-storage --lib`: 56 passed.
- `cargo test -p atm-storage-rusqlite --lib`: 181 passed, 1 ignored.
- `cargo check --workspace --all-targets` and formatting checks passed.

Rust review considered the typed event contract and error behavior (RBP-001,
RBP-007). Unknown strings still fail rather than being silently accepted.
The existing generic unavailable-reader error still obscures decoding failures;
distinguishing schema failures from outages remains follow-up work. The patch
does not itself establish installed-daemon compatibility or close
`omega-prime-bpt`: integrate and deploy the upstream fix, then rerun the two
reproducers and two complete collection ticks before claiming full coverage.
