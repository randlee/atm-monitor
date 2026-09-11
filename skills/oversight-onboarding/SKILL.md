---
name: oversight-onboarding
description: Establish monitoring settings when a new phase is discovered in a repository on the repo-monitoring list, or when an existing monitored project lacks a verified start time.
---

# Oversight onboarding

Use this skill for an `onboarding_requests` item from phase monitoring, or an
explicit request to onboard a phase. The deployment's `monitor.json` teams array
is the current repo-monitoring list: each entry binds one team to one repository.
An activity observation is a discovery clue, not proof of a phase start time.

1. Check that the repository is on that list and that the ATM team, phase plan,
   sprint branches, and worktrees agree. Read the plan and relevant assignment
   or task-event evidence. Do not enroll an unrelated repository from an agent
   name match alone. Unlisted repositories need an explicit catalog addition.
2. Establish the phase's actual start time from its plan, initial assignment,
   task event, or Rand's instruction. Record the evidence reference. Never use
   the current time or first monitor observation as a substitute: that would
   exclude work already in progress. If evidence is ambiguous, return the
   missing fact to the caller and leave the request pending.
3. Keep `name` (team) and `repo` on the catalog entry. Add phase settings to its
   `projects` array: `phase`, `start_time` (ISO 8601 with timezone),
   `start_time_evidence`, and locally accessible `worktrees`. The start time
   defines the PR scope: include PRs created strictly after it, retaining their
   records when closed or merged. If an essential PR predates the proposed
   boundary, resolve the boundary before applying it; do not silently omit it.
4. Save these deployment-owned settings using the script below. Existing
   unrelated options, teams, and phases are preserved. Overlapping phases are
   normal: onboard each independently, never replace an existing phase to add
   a new one. A conflicting start time for the same phase needs evidence
   reconciliation. Phase identity is repository/team plus phase, independent
   of its computer. Add only locally accessible worktrees today; report remote
   execution as a coverage gap until multi-computer collection is implemented.
5. Run activity detection and phase monitoring once using the deployment's
   `atm-oversight` installation. Check that the scoped PRs include the known
   sprint PRs, all pages were collected, task-event deferral is zero, and source
   failures remain visible. Return settings, evidence, collected PR count, and
   remaining gaps to the caller. Onboarding does not enable cron or delivery.

Run from this skill directory with the configured Python interpreter:

```sh
python scripts/configure_project.py --config /path/to/monitor.json --team atm-dev --repo /path/to/repo --phase BA --start-time 2026-09-11T00:00:00Z --evidence '<actual plan/task/message reference>'
python -m unittest discover -s tests -q
```

Substitute an evidence-backed time; the example date is not a default. The
script is self-contained and edits only local monitoring settings. It does not
change monitored repositories or send messages. `atm-oversight` is the separate
runtime consumer; if unavailable, return the saved settings and verification
gap without claiming monitoring works.

Master instructions, scripts, and tests live in `atm-monitor/skills/oversight-onboarding`.
Make policy/code changes there before distributing a whole verified bundle.
Per-project settings and evidence belong in deployment state, not in the skill.
