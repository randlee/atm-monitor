# Verified deployment and recovery (O4)

Edit the master skills in this repository, test the affected behavior, and
publish a verified bundle. Preserve runtime state and unrelated profile memory.
Do not call a successful install proof that the four outcomes work.

```sh
python3 -m unittest discover -s skills/atm-oversight/tests -v
python3 -m unittest discover -s skills/oversight-onboarding/tests -v
python3 -m unittest discover -s tests -v
python3 scripts/distribute_skill.py --target /deployment/skills/atm-oversight --archive-dir /deployment-archives
python3 scripts/distribute_skill.py --target /deployment/skills/atm-oversight --verify
```

Quiesce scheduled callers during bundle replacement and resume them afterward.
The target and archive must share a filesystem; keep the archive outside skill
discovery directories. The installer verifies staged hashes, preserves the prior
bundle and attempts restoration if publication fails. Modified deployed files
are preserved for reconciliation rather than overwritten blindly.

The optional oversight-onboarding bundle configures the table's repository/phase
scope. Install it with `--source skills/oversight-onboarding` and a corresponding
target. It does not implement lifecycle automation.

Omega's destinations are `hendrix/omega-prime/skills/atm-oversight` and the
optional `hendrix/omega-prime/skills/oversight-onboarding`. Profile fragments in
`deployments/omega-prime/profile/` route to the operating skill. Preserve other
profile settings when applying them. Keep machine paths, secrets and receipts
outside committed configuration.

For rollback, quiesce callers, preserve the failed target, restore the recorded
backup and verify it before resuming. Check state-schema compatibility; rollback
does not undo sent messages. After any update or recovery, verify an actual
scheduled run and its table/alert/error behavior. A missed run needs a watchdog
outside the failed job. Escalate persistent defects to amon@atm-monitor with
question/job identity, failure evidence, attempted recovery and impact.

The four-outcome scope cleanup is a repository change. It has not replaced the
installed runtime or established that missing idle/stuck-CI behavior exists.
