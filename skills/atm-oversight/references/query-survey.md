# Monitoring query survey

## Current adapter target

The observations below are historical. Runtime queries now follow Phase BA
guidance from Fenix (`01M29JDFFCSTB9RVVXXP4H5T4Z`): inspect
`atm doctor --team TEAM --json` and its `daemon_context.http_api_version`.
Use `atm task list --all --team TEAM --as ACTOR --json` and
`atm task events ID --team TEAM --as ACTOR --json` for API major 1 at version
1.6.0 or later. Pre-BA, unknown, future-major, and transitional 1.5.x task APIs
are unavailable in this adapter; do not query the ledger through old flags or
SQLite. Doctor/members use an explicitly configured `ATM_IDENTITY` environment
because those commands lack `--as`; mail/task commands pass `--as` directly.
The authority is Phase BA's `nudge-task-design.md` at `18db5acc3`, BA.2's typed
rows, and BA.4's task CLI. Preserve unknown state/event/outcome strings and
match escalation summaries by prefix without an enum of escalation kinds.

## Historical observations

Observed 2026-09-10 around 05:40 UTC (September 9 Pacific).
This records discovery evidence, not agreed monitoring policy or a live status report.
ATM queries were scoped to `atm-dev`. Source inspection used `../atm-core`
at develop commit `9f70bbcf0`; the installed CLI reported `atm 1.5.11`.
The source checkout and installed runtime must not be assumed to have identical capabilities.

## Verified query surfaces

| Purpose | Command | Observed output |
|---|---|---|
| Team roster | `atm members --team atm-dev --json` | Object with `team` and `members`; member identity, harness, backend, state, state-change time/source, and optional last-active time |
| Task ledger | `atm list --team atm-dev --tasks --json` | Array of task rows including assignee, assigner, state, assignment message ID, timestamps, reminder count, and lead notification count |
| One assignee's task events | `atm list --team atm-dev --task-events FIX-1325-R2-1788841690 --member fenix --json` | Array of sequenced assignment, acknowledgment, reminder, lead notification, and completion events |
| Recent mailbox metadata | `atm list --team atm-dev team-lead --all --limit 3 --json` | Bounded `rows` plus mailbox bucket counts; includes message IDs, summaries, read state, pending acknowledgment, and task ID |
| Bounded team search | `atm search --team atm-dev --limit 3 --json` | `hits`, optional `aggregate`, `next_cursor`, optional `lifecycle` |
| Task-linked template variables | `atm search --team atm-dev --var task_id=phase-az-s3-qa-3 --limit 2 --json` | Found the structured QA report for that task |
| Sprint-linked template variables | `atm search --team atm-dev --var sprint=AX.6 --limit 3 --json` | Found historical QA assignments; additional matches available through `next_cursor` |
| Discover stored template classifications | `atm search --team atm-dev --group-by template_type --limit 1 --json` | Aggregate groups include dev-task, fix-task, qa-task, qa-report, and unclassified messages |
| Inspect selected evidence | `atm peek --team atm-dev team-lead --message-id 01M24WXSCHY07WRVVXKQDMDBPE --json` | Full selected QA report, explicitly `mutation_applied: false` |
| Stack diagnostic | `gh stack view --json` in the existing AZ.3 worktree | Trunk and branches, PR IDs/states, commit IDs, merged/queued flags, and `needsRebase` |
| Current PR checks | `gh pr view 1379 --json number,headRefOid,baseRefName,state,mergeable,mergeStateStatus,statusCheckRollup` in atm-core | Current PR head/base and individual CI results |

The stack query was run in
`/Users/randlee/Documents/github/atm-core-worktrees/feature/az3-task-command-handoff`.
Running the same command in the root checkout returned exit 2 because `develop`
was not part of a stack. A monitor must select an existing appropriate checkout
and record which stack it inspected. One successful stack view does not establish
coverage of every stack or every open PR in the repository.

## Findings that affect script design

### Recorded work and live activity are separate

The roster returned seven members, including two active agents. The task query
returned 85 rows, all complete. Recent mailbox messages nevertheless described
AZ.3 QA and AZ.4 development. The AZ.3 QA assignment message
`01M24WDCVJAKM19FAMHTEZ20NZ` had a task ID inside its XML body but a null
mailbox `task_id` field.

An empty open-task set means no open tasks in the queried ledger. It cannot,
on its own, establish that the team has no work. Monitoring should expose
coverage discrepancies without inventing missing task state.

### ATM already records interventions

The sampled fenix task had 13 reminders and one lead notification before
completion. Its 19 events included an assignment resend, activation, repeated
reminders, a lead notification, and completion. Oversight can inspect this
history before choosing another intervention. Reminder events are not evidence
of agent progress.

The current legacy ledger uses `(team, task_id, assignee)` identity. The same
task ID appeared under both fenix and quality-mgr. Preserve the assignee when
joining events or reporting elapsed times.

### Structured search needs verified selectors

Rand subsequently clarified that `dev-task`, `fix-task`, `qa-task`, and
`qa-report` are queryable by tag, and worktree paths are supplied in task
assignments and the project plan. This is the intended discovery contract.
The empty results below record unsuccessful selector/runtime verification;
they do not establish that tagged discovery is unavailable. Resolving the
exact working invocation remains implementation work.

`--type qa-task` filters template frontmatter `metadata.type`; it is not a
filter on the returned `template_type` classification. The inspected dev/QA
templates have `name` fields but no `metadata.type` declaration. Live grouping
showed classified QA assignments, while `--type qa-task` returned no hits.

`--tag` searches instance tags; `--effective-tag` searches the stored effective
tag projection. The source documents generated prefixes such as
`template-type:qa-task`. However, live queries for
`template-type:dev-task`, `template-type:qa-task`, and
`template-type:qa-report` all returned no hits during this survey. These are
documented interfaces with unverified coverage in this runtime/data set,
not yet validated assignment selectors. Sampled search hits had null workflow
projections. Do not equate null projection with absence of work.

Variable filters did return useful evidence. The QA report lookup by `task_id`
provided a precise message ID for a subsequent non-mutating peek. The report
contained machine-readable JSON with reviewed commit, PR, verdict, finding
counts, blocking IDs, next action, and owner. Its body-authored generated time
was later than ATM's message time; elapsed-time checks should retain timestamp
provenance and use recorded transport/event times for receipt and transition
timing.

### CI and stack maintenance are independent observations

AZ.2 / PR #1379 reported `needsRebase: true` in the local stack view while all
17 returned CI checks for head `4e3ba54d03072b8ab3e2397c4e7c4b9612bfa08f`
reported success. GitHub mergeability fields were `UNKNOWN` in that sample.
This establishes a stack diagnostic separate from CI failure; it does not
prove a merge conflict or authorize an automatic repair. Preserve local stack
evidence separately from GitHub's current PR evidence.

### Query limits differ between surfaces

Search provides a cursor. Mailbox list provides a row limit and bucket counts.
The inspected task-ledger reader takes team and optional member, or task ID
and optional member, and returns the matching task/event collection. It has no
cursor or time/state/event-type filter in that reader contract. Task events
are ordered by sequence ascending. Do not assume mailbox `--limit` or `--since`
bounds a task-ledger read merely because the flags share `atm list`.

The original requirements draft's newest-first, page-size, blocked-task-state,
and direct-database assumptions are not established by these live queries.
Current task documentation describes assigned/active/complete. ADR-063
describes newer task identity, blocked and terminal states, and a migration;
it is a future-facing design relative to the installed CLI used here.

## Source references

- `../atm-core/docs/user-documents/tasks.md`
- `../atm-core/docs/atm-query-surface.md`
- `../atm-core/docs/template-workflow-metadata.md`
- `../atm-core/crates/atm-storage-rusqlite/src/search_store.rs`
- `../atm-core/crates/atm-storage-rusqlite/src/task_sql.rs`
- `../atm-core/crates/atm-storage-rusqlite/src/task_ledger_reader.rs`
- `../atm-core/docs/adr/ADR-063-phase-az-task-and-attention-capabilities.md`

Direct Herdr collection was subsequently verified with `herdr agent list`;
see [monitoring-workflow.md](monitoring-workflow.md) for its envelope and fields.
Populated lifecycle/tag queries, complete stack discovery, and daemon-unavailable
roster behavior remain to be verified.
This survey sent no messages, changed no task state, and performed no stack
maintenance or source edits in atm-core.
