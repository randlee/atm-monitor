# atm-monitor

Small, tested tools for ATM team oversight. The first stage runs on one
computer with JSON state; SQLite and multiple computers are later stages.

| Layer | Contents |
|---|---|
| Scheduled collection | `scripts/cron/`: read-only collectors, recoverable JSON snapshots, bounded ticks, routed health findings |
| Oversight agent | `scripts/oversight/` and `skills/`: sprint reports, message-history investigation, intervention checkpoints |
| Repository improvements | Naming checks and hooks, consistency conventions, and a prioritized rollout plan |

```sh
python -m unittest discover -s tests -v
python scripts/cron/detect_activity.py --config config/example.json --state-dir <activity-state-directory> --json
python scripts/cron/monitor_phase.py --config config/example.json --activity-dir <activity-state-directory> --state-dir <phase-state-directory> --json
python scripts/oversight/report.py --state-dir <phase-state-directory> --team atm-dev
```

Python 3.11+ and Git are sufficient for tests. Live collectors also require
ATM, Herdr, and authenticated GitHub CLI access. Config paths resolve relative
to the config file. Use a temporary state directory for the pilot.

CI runs tests on Linux, macOS, and Windows with Python 3.11 and 3.13. Fixtures
cover source failures, partial results, identity isolation, staged/pushed Git
snapshots, interrupted writes, lock recovery, stale evidence, notification
routing, and intervention persistence.

See [installation and usage](docs/installation.md) for the two scheduled jobs
and oversight workflow, [the Hermes adapter](docs/hermes-installation.md) for
harness setup, [operations](docs/operations.md) for recovery,
[notification policy](docs/notification-policy.md) for oversight directions,
[naming conventions](docs/naming-conventions.md) for repository rollout, and
[improvement plan](docs/improvement-plan.md) for the next gates and OTel priorities.

Healthy operation stays silent on Telegram. CI failures and conflicts go to
team-lead; confirmed stack-rule/order violations go to the team and operator;
serious problems escalate to the operator. The kit emits routed findings and
records confirmed interventions. Notification transport and an unattended
delivery worker must be integrated with the selected gateway before rollout.
