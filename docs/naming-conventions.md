# Proposed naming conventions, version 1

This is the rollout proposal for new phase/sprint work. It follows the recent
AZ spelling in atm-core. Existing repositories have not been renamed or had
their hooks changed. Historical deviations can be audited before adoption.

## Identity and paths

| Item | Convention | Example |
|---|---|---|
| Phase ID | Uppercase letters | `AZ` |
| Sprint ID | Phase, dot, positive number; dot-separated subsprints allowed | `AZ.3`, `AZ.3.1` |
| Phase directory | `docs/plans/phase-<lowercase-phase>/` | `docs/plans/phase-az/` |
| Phase plan | `phase-<lowercase-phase>-plan.md` | `phase-az-plan.md` |
| Sprint plan | `sprint-<sprint-id>-<slug>.md` | `sprint-AZ.3-task-handoff.md` |
| Sprint branch | `feature/<lowercase-phase><number>-<slug>` | `feature/az3-task-handoff` |
| Subsprint branch | Replace number's dots with hyphens | `feature/az3-1-task-handoff` |
| Integration branch | `integrate/phase-<lowercase-phase>` | `integrate/phase-az` |
| Planning branch | `plan/phase-<lowercase-phase>-<slug>` | `plan/phase-az-task-lifecycle` |
| Worktree suffix | The full sprint branch path | `../atm-core-worktrees/feature/az3-task-handoff` |

Slugs use lowercase ASCII letters/digits separated by single hyphens. No spaces,
underscores, leading-zero sprint numbers, alternate `s`/`p` prefixes, or numeric
YAML interpretation of IDs. The phase and sprint IDs are strings. The branch
and plan filename share the same slug. Worktree roots may differ by computer;
use either an absolute local path or the portable repository-relative form
`../<repo>-worktrees/<branch>`. Creating the worktree is not a prerequisite to
committing its plan, and checks do not require that the directory exists.

Keep QA and fix rounds attached to the same sprint identity. A new round does
not create a new sprint ID. ATM task IDs remain opaque; this convention does
not rename existing task IDs or prescribe a task lifecycle.

## Plan identity fields

Use the existing template location `docs/templates/`. The checker accepts
identity in YAML frontmatter or the rendered template's fenced YAML block.
There must be one identity block. Fields used for naming are top-level scalar
strings, not aliases, nested objects, or multiline YAML values.

```yaml
phase: AZ
sprint: "AZ.3"
branch: feature/az3-task-handoff
worktree: ../atm-core-worktrees/feature/az3-task-handoff
status: planned
```

Phase plans require `phase`; if `canonical_path` is present, it must match the
phase plan path. Sprint plans require `phase`, `sprint`, `branch`, and
`worktree`. The validator checks their agreement. It deliberately does not
interpret lifecycle status, dependencies, QA results, or merge readiness.
The project plan remains `docs/project-plan.md`; project-index coverage and
assignment-to-plan checks are separate rollout work, not claims of this checker.

Branches outside sprint work use one prefix and a lowercase kebab-case name:
`feature`, `fix`, `hotfix`, `docs`, `chore`, `test`, `refactor`, `perf`, `ci`,
`build`, or `release`. `main`, `master`, and `develop` are allowed trunks.
`plan` and `integrate` have the phase forms above. Checked sprint metadata must
use its exact sprint branch; general branch syntax alone does not prove that a
branch has an associated plan.

## Checks and rollout

Run with Python 3.9 or later; no third-party dependencies:

```sh
python3 scripts/check_naming.py --repo /path/to/repo --all --json
python3 scripts/check_naming.py --repo /path/to/repo --staged
python3 -m unittest discover -s tests -v
```

Exit codes: 0 means checked inputs pass, 1 means naming violations, 2 means
the audit could not complete. JSON includes checked-plan count and explicit
issue codes. Audit mode checks existing working-tree plans, including untracked
plans. Staged mode reads the Git index, so an unstaged edit cannot conceal a
bad commit. Pre-push mode consumes Git's ref updates from stdin and checks the
final pushed tree for plans changed in outgoing commits. It supports multiple
refs, new branches, branch deletion, and pushing a ref other than the checkout.
Tags are outside its branch/plan gate. Detached commits skip branch-name checks;
the pushed branch name is checked at pre-push.

Copy `scripts/check_naming.py` and `scripts/plan_metadata.py` into the target
repository's `scripts/` directory before adding hooks. The supplied executable
`hooks/pre-commit` and `hooks/pre-push` work directly in repositories without
existing hooks. For a repository with no existing active hooks, copy `hooks/`
and enable it with `git config core.hooksPath hooks`.

For repositories with existing hooks, integrate the checker into those hooks;
do not replace them or change `core.hooksPath`. In particular, atm-core already
uses `.githooks/pre-push`. A pre-push hook that has several consumers must capture
stdin once and replay it to each consumer:

```sh
updates=$(mktemp)
trap 'rm -f "$updates"' EXIT HUP INT TERM
cat > "$updates"
python3 "$repo_root/scripts/check_naming.py" --repo "$repo_root" --pre-push < "$updates" || exit $?
# Feed the same file to existing pre-push checks.
```

Start with an audit and an agreed adoption boundary. Hooks check changed plans,
so editing a nonconforming historical plan requires migrating that plan too.
They do not force a whole-history rename. A repository-wide CI audit should
become blocking only after that repository's baseline is clean. Git hooks can
be bypassed, so repository policy and eventual CI enforcement remain necessary.

