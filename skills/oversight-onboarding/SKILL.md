---
name: oversight-onboarding
description: Establish monitoring settings when a new phase is discovered in a repository on the repo-monitoring list, or when an existing monitored project lacks a verified start time.
---

# Oversight onboarding

Use this skill when evidence establishes a new planning phase, for an
`onboarding_requests` item, or for an explicit onboarding request. A PR is not
required: a phase-bound planning branch and plan-hardening assignments can
establish planning before development starts. An open PR whose source branch
is `plan/*` is also a direct planning signal; merging it signals plan ready. The deployment's `monitor.json` teams array
is the current repo-monitoring list: each entry binds one team to one repository.
An activity observation is a discovery clue, not proof of a phase start time.

Before onboarding, follow `atm-oversight/references/phase-discovery.md` in the
deployed oversight skill to distinguish casual activity from substantive work
and record discovery evidence. Record `phase_discovered` and `planning_started`
when established; backfill earlier evidenced activity without inventing dates.

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
   If PR creation itself supplies the start evidence, retain that PR by identity
   in the phase evidence: the current strict-after collection filter excludes
   equality. Record that collector limitation; do not invent an earlier timestamp
   to work around it or lose the milestone from the phase record.
4. Save these deployment-owned settings using the script below. Existing
   unrelated options, teams, and phases are preserved. Overlapping phases are
   normal: onboard each independently, never replace an existing phase to add
   a new one. A conflicting start time for the same phase needs evidence
   reconciliation. Phase identity is repository/team plus phase, independent
   of its computer. Add only locally accessible worktrees today; report remote
   execution as a coverage gap until multi-computer collection is implemented.
5. Run activity detection and phase monitoring once using the deployment's
   `atm-oversight` installation. For a planning-only phase, zero PRs is expected; verify planning messages,
   branch/plan evidence, and phase-event recording instead. Where PRs exist,
   check that scoped PRs include the known sprint PRs, all pages were collected, task-event deferral is zero, and source
   failures remain visible. Return settings, evidence, collected PR count, and
   remaining gaps to the caller. Hand off a concrete repo-specific schedule
   specification: repository/team, phase, actor, installed skill/config paths,
   activity/snapshot/phase-event paths, cadence, and scheduler job identity.
   Check the durable active/pending repository registry first; reuse its job
   for an additional phase. Claim a single handoff and suppress repeated general
   activity wakes. The expected workflow starts the repo-specific cron through the
   deployment scheduler and records `monitoring_started` only with its receipt
   and first successful run. The current settings writer does not install a
   schedule: report a missing scheduler integration as pending work, never as
   active monitoring. Respect the deployment's current scheduling setting.

Run from this skill directory with the configured Python interpreter:

```sh
python scripts/configure_project.py --config /path/to/monitor.json --team atm-dev --as <actor> --repo /path/to/repo --phase BA --start-time 2026-09-11T00:00:00Z --evidence '<actual plan/task/message reference>'
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
