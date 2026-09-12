# Running the local prototype

Start with the harness-independent [installation guide](installation.md) for
the two scheduled jobs and return codes. The commands below describe the
lower-level collector and state tools. `tick.py` remains useful for a manual
all-configured-teams scan; do not schedule it alongside `monitor_phase.py`.

Python 3.11+ and Git are required. The collectors additionally need authenticated
`atm`, `herdr`, and `gh` commands on the scheduler's PATH. Unit tests require
only Python and Git and never contact these live services.

## Configure and run

Copy `assets/monitor.example.json` to a local config. Set each team's name and repository
path. Paths resolve relative to the config file, not the caller's directory.
The example repo path is a placeholder and must be configured. Add a second team by adding
another object to `teams`; duplicate names are rejected.

`worktrees` optionally adds explicit paths. The tick also discovers existing
worktrees for open PR branches and checks their Git history and stack state.
It never checks out branches, fetches, rebases, or starts agents.

From the skill directory:

```sh
python scripts/cron/tick.py --config assets/monitor.example.json --state-dir <temporary-state-directory>
python scripts/oversight/report.py --state-dir <temporary-state-directory> --team atm-dev
python scripts/oversight/mine_messages.py --team atm-dev --as <actor> --kind qa-report --with-bodies > <qa-evidence-file>
python scripts/oversight/report.py --state-dir <temporary-state-directory> --team atm-dev --qa-evidence <qa-evidence-file>
```

Pass an actual path for angle-bracket placeholders. Choose the temporary state
directory with the platform's temp-directory mechanism or an operator-selected
location. Production code embeds no machine-specific paths. The application
does not expand shell variables in JSON paths.

Independent entrypoints under `scripts/cron/` collect Herdr, roster, tasks,
task events, Git history, worktree inventory, CI, and stacks. Each accepts
`--help`, returns a versioned JSON envelope, and has a per-command timeout.
Valid empty responses remain different from unavailable sources. A Git/PR
result at its configured bound is explicitly partial.

## Scheduling

Prefer the two-job schedule in [installation](installation.md). For a deliberate
all-configured-teams collection test, start with a manual tick and inspect its snapshot/report. For the first pilot,
a five-minute schedule is a conservative starting setting, not a requirement
or a validated production interval. In a cron entry, substitute absolute paths
from the actual installation:

```text
*/5 * * * * /path/to/python /path/to/atm-oversight/scripts/cron/tick.py --config /path/to/monitor.json --state-dir /path/to/temp-state >> /path/to/tick.log 2>&1
```

Set cron's PATH to the directories containing this installation's ATM, Herdr,
Git, and gh executables. Do not copy a developer's PATH or home directory into
the distributed scripts. On Windows, configure Task Scheduler to run the same
Python command and arguments. On macOS, launchd can run that command too.
The POSIX hook examples run under Git's hook shell; `ATM_MONITOR_PYTHON` can
select `python` or an absolute interpreter where `python3` is not available.

No scheduler or notification delivery is installed by these scripts. Do not
claim continuous monitoring until the scheduled environment has produced
successful ticks and the overnight pilot has been inspected. Configure log
rotation for the scheduler's text log.

## State and recovery

The tick holds an OS file lock for its entire run. Concurrent runs return
`busy`; process termination releases the lock automatically. Do not delete
the lock file while another process might be using it.

Each completed snapshot is written to a temporary file, flushed, and atomically
renamed into `snapshots/<sequence>.json`. Partial writes are ignored. Reading
state finds the newest valid snapshot and exposes any corrupt newer snapshots
as recovery warnings. `sources` records current successes/failures; `last_good`
retains earlier successful observations with their original timestamps.

The default retention is 1,000 snapshots (about 3.5 days at five-minute ticks).
Set `retain_snapshots` to another value of at least two. Older snapshots are
removed only after a complete new snapshot is published. Retained snapshots
contain accumulated last-good observations, but they are not a permanent event
archive. Preserve the directory before a migration or historical export. Temp
cleanup causes an explicit fresh start; durable history is a SQLite-stage goal.

Every task returned by the team ledger has its complete event history queried
each tick, including tasks whose state has not changed. New events can arrive
without a task-state change. The old `event_tasks_per_tick` option is accepted
but ignored during upgrades; `deferred_event_tasks` remains zero. Failed
queries stay unavailable and are retried next tick. Up to four queries run
concurrently. A request timeout is a failure, never a successful truncation.

Exit codes: collectors/tick/report use 0 for success and 2 for failure/degraded
collection; tick uses 3 for overlap. Mining returns 0 for readable results,
including explicitly partial pages, and 2 when evidence is unavailable. Inspect
its JSON status, cursors, remaining revisions, and omitted body count.

## Report limits

Phase discovery currently joins parsed plan branch fields to a scoped PR
inventory, then retains all parsed sprints in each discovered phase. It also
retains already-discovered phases through quiet periods. Unmapped branches
are listed in `discovery_errors`. This is a working discovery path; structured
assignment-driven discovery and explicit phase retirement remain rollout work.

Each team/repository has a `projects` array of simultaneously monitored phases.
Each phase records `phase`, `start_time`, `start_time_evidence`, and optional
local `worktrees`. Repository collection starts at the earliest configured
phase start and reads every PR page in that window, including open, closed,
and merged PRs. Reports select each phase's own boundary. A PR exactly at the
start boundary is excluded. No PR count cap applies. Git reads all commits
since the same earliest start on each collected branch, without a count cap.
Missing phase settings are reported as `unscoped_projects`; legacy configs
collect repository history until onboarding establishes their scope.

CI uses GraphQL cursor pagination for PRs and for check contexts at each head
commit. A valid historical PR with an empty commit connection remains in the
inventory with `check_evidence: head-commit-unavailable` and unknown checks.
Timeout, malformed pages, repeated cursors, changing head identities,
or failed later pages invalidate that inventory; prior successful state stays
available as explicitly old evidence. Timeouts apply per request and the
16 MiB safety bound applies per response page. They are operational failure
guards, not reporting filters. Long complete scans can exceed one polling
interval; overlap protection skips competing ticks.

A missing PR is not assumed merged. Only matched QA
reports at the exact PR head contribute QA/FND state. Unknown DEV/QA remains
`—`; a merged PR is evidence of delivered development. Plan status alone is
not treated as a live completion signal.

The current kit does not run an LLM, send Telegram/ATM notifications, or perform
repairs. The skills define how an oversight agent uses its reports and mining
tools. Delivery integration and supervised pilot validation are the next
rollout gates in [the improvement plan](improvement-plan.md).

## Testing

```sh
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

GitHub Actions runs the suite on Linux, macOS, and Windows with Python 3.11
and 3.13. Tests use isolated temporary Git repositories and mocked service
responses. A passing local run establishes only the local platform result;
the matrix establishes the other platform results when it runs.

## Phase closure and shared cron lifetime

Use [phase closure](phase-closure.md) for integration PR closure or manual
closure by Omega-prime. One repo cron serves all open phases and stops only
after the last closes, with a recorded scheduler stop before ownership release.
The current scripts do not implement this lifecycle/ownership integration;
the cron examples above are collection prototypes, not automatic phase handoffs.
Do not connect watch-list additions directly to agent wakeups: structured
significance qualification and active-repo suppression remain required work.
