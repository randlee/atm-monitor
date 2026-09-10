# Self-contained skill distribution

`atm-monitor` is the authoritative source for all oversight scripts, skills,
and documents. Edit and test here first, then distribute. The complete runtime
unit is `skills/atm-oversight/`:

```text
atm-oversight/
  SKILL.md
  scripts/cron/          # the two scheduled jobs and their collectors/state code
  scripts/oversight/     # reports, investigation, intervention records
  scripts/              # naming/plan helpers
  references/           # policies, procedures, installation, improvement plan
  assets/               # config and hook examples
  tests/                # standalone unit/Git integration tests
```

Investigation and repository consistency are procedures within this skill;
there are no sibling runtime dependencies or separate skill versions to align.
Run the documented `scripts/...` commands from the installed skill directory.
Runtime config and monitoring state live outside the installed bundle.

## Install or upgrade

Quiesce scheduled callers before upgrading. Run from the atm-monitor checkout:

```sh
python3 scripts/distribute_skill.py --target /deployment/skills/atm-oversight --archive-dir /deployment-archives
python3 scripts/distribute_skill.py --target /deployment/skills/atm-oversight --verify
python3 -m unittest discover -s /deployment/skills/atm-oversight/tests -q
```

The target and archive must be on the same filesystem. Keep the archive outside
every skill discovery directory; otherwise a harness could load retired skills.
The installer stages and checks the complete bundle before publication, records
a content-hash receipt, and retains the old installed directory for rollback.
The two rename operations require quiescent callers; they are not a transaction
for a concurrently executing agent. A failed publication attempts to restore
the previous installation. Staging failures leave the old installation intact.

An identical install is a no-op. Changed or untracked deployed files cause an
upgrade to stop rather than overwrite local work. Preserve those changes,
port intended fixes into atm-monitor, validate, then redistribute. Do not put
state/config/logs inside the bundle. Python bytecode caches are ignored.

To roll back, quiesce callers, preserve the current target in another archive
directory, then move the reported backup to the target and run `--verify`.
Keep the matching deployment configuration and state-schema compatibility in
view; restoring code does not undo external messages or state transitions.

## Omega-prime rollout

The deployment destination is `hendrix/omega-prime/skills/atm-oversight/`.
Hermes loads it as an external skill directory through the selected profile's
configuration. No runtime-only copy is maintained. Deployment-specific profile
documents originate under `deployments/omega-prime/` in this repository.

The staged rollout and acceptance criteria are in
[the rollout document](../deployments/omega-prime/rollout.md). Local legacy
archives, generated machine configuration, and test evidence live under
`.local/` in this repository; they are intentionally excluded from Git because
they contain machine paths and historical agent context. The legacy archive's
manifest records each original path, archive member, and SHA-256 hash.
