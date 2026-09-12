# Working in atm-monitor

Authoritative skills and scripts live in `skills/`. Change masters here before
updating a deployment. Keep local ATM configuration, database backups, and
runtime state out of commits.

For ATM template classification, tags, workflow metadata, or a blocked template
pre-push check, read [atm-template-maintainence](skills/atm-template-maintainence/SKILL.md).
Its maintained standard is `skills/atm-template-maintainence/references/standards.json`.
The skill is discoverable under `.agents/skills/` for Codex and `.claude/skills/`
for Claude; these entrypoints delegate to the same authoritative skill.

For oversight behavior, read `skills/atm-oversight/SKILL.md`; for adding phase
settings, read `skills/oversight-onboarding/SKILL.md`. Treat capability boundaries
as real: a written lifecycle or cron procedure is not implemented automation.
Repository template files are authoritative. Daemon repository-access fixes
are outside this repository's oversight work.

Run the relevant unittest suites listed in `.github/workflows/tests.yml`.
