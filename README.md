# atm-monitor

Small, tested tools for ATM team oversight. The first stage runs on one
computer with JSON state and an oversight event journal; ATM and Git retain
the canonical source facts. A second database is not required for this stage.

`skills/atm-oversight/` contains the monitoring runtime. The separate
`skills/oversight-onboarding/` skill establishes phase settings when new work
is discovered. Each skill contains its own scripts and tests and is distributed
as a complete directory. Multiple overlapping phases can share a repository,
with independent start times and local worktrees. This repository is the
authoritative source; deployed copies are upgraded together using
`scripts/distribute_skill.py`. See [distribution](docs/distribution.md).

| Layer | Contents |
|---|---|
| Scheduled collection | `skills/atm-oversight/scripts/cron/`: read-only collectors, recoverable JSON snapshots, source timeouts, routed health findings |
| Oversight agent | `skills/atm-oversight/scripts/oversight/` and `skills/`: sprint reports, message-history investigation, intervention checkpoints |
| Repository improvements | Naming checks and hooks, consistency conventions, and a prioritized rollout plan |

```sh
python -m unittest discover -s skills/atm-oversight/tests -v
python skills/atm-oversight/scripts/cron/detect_activity.py --config <configured-monitor.json> --state-dir <activity-state-directory> --json
python skills/atm-oversight/scripts/cron/monitor_phase.py --config <configured-monitor.json> --activity-dir <activity-state-directory> --state-dir <phase-state-directory> --json
python skills/atm-oversight/scripts/oversight/report.py --state-dir <phase-state-directory> --team atm-dev
```

Python 3.11+ and Git are sufficient for tests. Live collectors also require
ATM, Herdr, and authenticated GitHub CLI access. Config paths resolve relative
to the config file. Use a temporary state directory for the pilot.
Copy `skills/atm-oversight/assets/monitor.example.json` and set the actual repo
path before running collection; the supplied path is deliberately a placeholder.

CI runs tests on Linux, macOS, and Windows with Python 3.11 and 3.13. Fixtures
cover source failures, partial results, identity isolation, staged/pushed Git
snapshots, interrupted writes, lock recovery, stale evidence, notification
routing, and intervention persistence.

See [installation and usage](skills/atm-oversight/references/installation.md) for the two scheduled jobs
and oversight workflow, [the Hermes adapter](skills/atm-oversight/references/hermes-installation.md) for
harness setup, [operations](skills/atm-oversight/references/operations.md) for recovery,
[notification policy](skills/atm-oversight/references/notification-policy.md) for oversight directions,
[naming conventions](skills/atm-oversight/references/naming-conventions.md) for repository rollout, and
[improvement plan](skills/atm-oversight/references/improvement-plan.md) for the next gates and OTel priorities.

Healthy operation stays silent on Telegram. CI failures, conflicts, and explicit
PR merge-requirement diagnostics go to team-lead for stacked and non-stacked
branches; confirmed stack-rule/order violations go to the team and operator;
serious problems escalate to the operator. The kit emits routed findings and
records confirmed interventions. Notification transport and an unattended
delivery worker must be integrated with the selected gateway before rollout.

## Agent skill discovery

Codex and Claude project entrypoints are committed under `.agents/skills/` and
`.claude/skills/`. Both load the authoritative
[template maintenance skill](skills/atm-template-maintainence/SKILL.md), keeping
one type/metadata standard and one set of scripts. `AGENTS.md` and `CLAUDE.md`
also route template work there. This provides discovery for agents working in
this repository; it does not install a global skill in every other repository.
Restart an existing agent session if it has not discovered the new directory.

The locations follow [Codex skill discovery](https://developers.openai.com/codex/skills/)
and [Claude project skills](https://code.claude.com/docs/en/skills). The portable
entrypoints are regular files so checkout behavior does not depend on symlinks.

See the [comprehensive skills/scripts review](docs/oversight-review-2026-09-12.md)
for fixed defects, the multi-phase lifecycle, manual closure, and remaining
runtime/scheduler integration gates.
