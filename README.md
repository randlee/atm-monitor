# atm-monitor

This repository has four outputs:

| ID | Output | Acceptance |
|---|---|---|
| O1 | Phase/sprint status table | Every sprint, ownership, DEV/QA/CI, iterations, B/C/I findings, blockers, next action and evidence/as-of time |
| O2 | Assigned-but-idle alerts | Identify idle agents with outstanding work; distinguish legitimate queueing and escalate stalled work to its owner |
| O3 | CI and merge-readiness alerts | Detect conflicts, failed checks, required checks that never start and stuck checks; alert with a concrete cause/action |
| O4 | Self-healing | Return typed actionable errors; diagnose, repair/retry or escalate while unaffected monitoring continues |

The [requirements](skills/atm-oversight/references/requirements.md) define the
four outcomes. The [design](skills/atm-oversight/references/design.md) specifies
immutable state, independent queries, source reconciliation and cron decisions.
The [command catalog](skills/atm-oversight/references/queries.md) gives fenced
commands, verified GraphQL operations and explicit failure/recovery behavior.
The [operating skill](skills/atm-oversight/SKILL.md) tells Omega how to use them
and recover failures. [Distribution](docs/distribution.md) explains verified
upgrades and recovery. No template administration, naming campaign or
phase-lifecycle platform is part of this repository.

## Retained files and their purpose

| Files | Outcome supported |
|---|---|
| `skills/atm-oversight/scripts/runtime/`, `assets/runtime.example.json`, `references/runtime.md` | O1–O4: replacement typed queries, immutable answers, persistence, scheduled runtime and watchdog |
| `skills/atm-oversight/scripts/oversight/report.py`, `branch_tree.py`, `mine_messages.py`, `phase_events.py` | O1: table, branch hierarchy, QA evidence and status history |
| `scripts/cron/discovery.py`, `scripts/plan_metadata.py`, `assets/monitor.example.json`, `skills/oversight-onboarding/` | O1: associate sprint plans and configure the table's repository/phase scope |
| `scripts/cron/collectors.py`, `collect_*.py`, `github_inventory.py` within the oversight skill | O1–O3: source adapters and inputs; O4: source failure reporting |
| `scripts/cron/detect_activity.py`, `monitor_phase.py`, `tick.py` within the oversight skill | O1–O3: existing scheduled acquisition/selection; legacy implementation requiring replacement by independent question queries |
| `scripts/cron/check_health.py`, `agent_gate.py`, `hermes_monitor.py`, `scheduled_output.py` within the oversight skill | O3–O4: findings, deduplication and scheduled error handoff |
| `scripts/cron/state_store.py`, `scripts/oversight/record_intervention.py` within the oversight skill | O1–O4: durable observations and actual alert delivery receipts |
| `scripts/distribute_skill.py`, `docs/distribution.md`, `deployments/omega-prime/profile/` | O4: verified installation, rollback and operator instructions |
| Skill tests, `tests/`, `.github/workflows/tests.yml`, `.githooks/`, source-limit helpers | Verification and source-size enforcement for O1–O4 |
| `AGENTS.md`, `CLAUDE.md`, native skill entrypoints | Ensure agents find the four-outcome instructions |

## Actual implementation status

The replacement runtime is in `skills/atm-oversight/scripts/runtime/`.
Frozen source records feed independent queries, per-field answer functions and
per-repository persisted state. It implements idle investigations, exact-head CI
failure/conflict/start/stuck checks, durable wake deduplication and a separate
watchdog. See the [runtime manual](skills/atm-oversight/references/runtime.md)
for commands and honest coverage limits. The old cron modules remain for
compatibility and rollback; the replacement does not read task histories.

```sh
python3 -m unittest discover -s skills/atm-oversight/tests -v
python3 -m unittest discover -s skills/oversight-onboarding/tests -v
python3 -m unittest discover -s tests -v
```

Git uses `.githooks`. Commit checks inspect changed staged source; push checks
inspect changed source in outgoing commits. Files over 100 substantive lines
are rejected, excluding blank/comment lines. Existing oversized files have not
been grandfathered when changed. Do not bypass the guard.
