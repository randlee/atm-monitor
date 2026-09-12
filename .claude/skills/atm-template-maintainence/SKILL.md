---
name: atm-template-maintainence
description: Maintain ATM template types, tags, and workflow query metadata; audit untyped revisions and resolve the ATM pre-push gate. Use for template classification and metadata maintenance in atm-monitor.
---

Read and follow the [authoritative maintenance skill](../../../skills/atm-template-maintainence/SKILL.md)
before doing template maintenance. This is a repository discovery entrypoint;
the complete skill, scripts, tests, and standard live in
`skills/atm-template-maintainence/` at the repository root.

Resolve that link relative to this file. Run commands from the authoritative
skill directory, not this entrypoint directory. The single source of truth is
`skills/atm-template-maintainence/references/standards.json`. Preserve the
canonical skill's dry-run, authorization, backup, and receipt requirements.
Repository template source files are authoritative; incidental home-directory
copies do not define the producer contract.
