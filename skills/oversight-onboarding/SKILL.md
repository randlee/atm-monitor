---
name: oversight-onboarding
description: Configure repository and phase scope for the oversight phase/sprint status table.
---

# Configure table scope

This helper supports O1: the phase/sprint table. It edits local monitoring
settings for an explicitly identified team, repository and phase. It is not
an automatic phase-discovery or phase-closure system.

Use evidence-backed phase identity and start time from the plan or assignment.
Preserve other teams/phases and unrelated configuration. Add accessible worktrees
only. A conflicting start time requires evidence reconciliation, not guessing.

From this skill directory:

```sh
python scripts/configure_project.py --config /path/to/monitor.json --team atm-dev --as <actor> --repo /path/to/repo --phase BB --start-time <evidence-time> --evidence '<source reference>'
```

Verify saved scope against the source evidence. If the helper fails, diagnose
and repair the configuration or escalate an actionable error; do not claim the
table is complete. This helper does not start a cron, change source repositories,
send messages or establish phase completion. It preserves overlapping scopes.
