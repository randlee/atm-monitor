---
name: atm-repo-consistency
description: Audit and roll out ATM plan, branch, and worktree naming conventions with tested Git hooks while preserving existing repository checks.
---

# Repository consistency

Read [naming conventions](../../docs/naming-conventions.md) for the proposed
identity contract and [improvement plan](../../docs/improvement-plan.md) for
the adoption sequence. Audit first with
`python scripts/check_naming.py --repo <repo> --all --json`.

Treat existing historical differences as migration evidence. Agree an adoption
boundary before making a repository-wide legacy audit blocking. The supplied
hooks check staged or outgoing changed plans, not all history. Snapshot tests
verify that unstaged fixes cannot hide bad staged content and that pushed refs
are checked even when another branch is checked out.

Preserve the target repository's existing `core.hooksPath` and hook checks.
Integrate the validator into existing hooks; if several pre-push consumers
need stdin, capture the ref updates once and replay them to each. Do not install
the sample hooks over an existing gate. Plan schema changes need corresponding
template and query fixtures; do not claim that a naming check validates the
whole plan schema or project index.

Make the smallest source correction that improves deterministic discovery.
Keep worktree roots configurable per computer and task IDs opaque. Verify
corrected records through the monitoring query/report path before considering
the rollout successful.
