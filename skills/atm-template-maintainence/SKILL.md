---
name: atm-template-maintainence
description: Maintain ATM template tags and workflow metadata for reliable oversight queries. Use when defining detection signals, auditing template revisions, changing planning/development templates, or investigating missing workflow records.
---

# ATM template maintenance

The atm-monitor maintainer owns the oversight metadata contract: which facts
must be emitted, their declared fields/tags, the queries that consume them, and
verification across template releases. Do not hand this responsibility back to
Omega-prime or expect it to infer workflow states from prose. Template authors
and runtime owners implement source changes in their repositories; this owner
coordinates the contract and verifies actual admitted records.

This skill is maintained in `atm-monitor/skills/atm-template-maintainence`. It is a
maintainer skill, not a periodic LLM cron job. Use supported ATM CLI/API reads,
Python, and source-template review. Rand has authorized narrow catalog type
maintenance; use the backed-up procedure below, never arbitrary ledger edits.

## Source of truth in code

The maintained query-type standard is
[`references/standards.json`](references/standards.json), checked into this repo.
It defines expected `metadata.type`, literal tags, workflow fields, and known
revision-to-source mappings. Classification follows the work performed by the
template, not its filename, rendered prose, or a convenient tag guessed later.

The producer's authoritative `.j2` frontmatter must explicitly contain
`metadata.type`; top-level `name: dev-task` does not assign a catalog type.
In atm-core, `crates/atm-core/src/send/async_persistence.rs`, function
`template_admission_parts`, reads `verified.inspection.frontmatter.metadata`
key `type`. The inspected implementation warns when missing but accepts an
untyped registration. Do not claim native enforcement already exists.

Each edited-and-used template creates a new immutable SHA. Validate every
revision on admission/use; checking a filename once does not cover its future
edits. Original content and admitted message snapshots remain unchanged. Administrative
catalog classification corrections require explicit receipts. The Git gate
checks the live catalog on every push, including revisions created outside
this working tree.

## Maintained standard

[standards.json](references/standards.json) is the machine-readable list of
standard template types and expected declared metadata. It includes explicit
source/type bindings for historical untyped revisions supplied by Rand. Maintain
this file whenever an expected type, query field, or producer mapping changes.
The audit checks every catalog revision against it, allowing additive metadata
while reporting missing/mismatched required values and unknown types.

## Working procedure

1. Identify the consumer decision and source fact before choosing tags. Read
   [the contract rules](references/contract.md). Separate generic ATM metadata
   syntax from project-owned vocabulary. Preserve Rand's planning PR signals
   alongside metadata-only message detection.
2. Inventory the running CLI/daemon versions and template revisions. Run the
   read-only audit below, then inspect relevant `atm templates schema SHA --json`
   records. Treat catalog presence, source template edits, local installation,
   and actual admitted-message metadata as four distinct facts. Historical
   untyped revisions require verified classification before authorized remediation.
3. Map the required signal to its producer template(s), variables, source repo
   and path, installed copy, and consuming query. Record observed revisions,
   compatibility selectors, and remaining producer gaps in an adoption receipt.
   Template type, literal tags, instance tags, generated tags, and workflow
   snapshot fields are distinct; never label type counts as all effective tags.
4. Prepare fixes in the authoritative source template repository under its
   instructions. Add/repair declared metadata and required producer emissions,
   rather than consumer regexes. Review affected assignments and report templates
   together so a start/completion pair has compatible scope/revision/iteration
   identities. Keep schemas generic; do not add team-specific states to ATM
   runtime enums to support a consumer convention.
5. Validate syntax/registration and consumer queries using an isolated fixture
   or existing authorized emissions. Metadata audits are read-only; do not send
   production messages merely to test a tag. If a real workflow emits a record,
   use its ID and immutable snapshot as live evidence. Background reviewers need
   an explicit metadata-bearing notice from their workflow owner if they emit
   no ATM record themselves.
6. Follow [adoption and query verification](references/adoption.md). Record the
   source commit, new SHA, installed producer, runtime/API version, emitted
   message IDs, selector results/cursors, and semantic interpretation. Old
   messages retain their old snapshots; new metadata is not a historical
   backfill. Preserve compatible structured-variable queries where justified.
7. Update the consuming oversight/onboarding skills and requirements in master
   first, test relevant scripts, and distribute verified bundles within the
   current task's authority. Communicate concrete producer/consumer changes and
   remaining gaps to the owners. Do not call rollout complete until emitted
   records—not just installed files—satisfy the selectors.

## Audit helper

Run from this skill directory:

```sh
python scripts/audit_metadata.py --strict
python scripts/audit_metadata.py --catalog /path/to/catalog.json --schemas-dir /path/to/schemas
python -m unittest discover -s tests -q
```

The live audit reads the immutable host catalog and each stored schema through
`atm templates`; it sends nothing. Offline schema files are named `SHA.json`.
Strict mode exits 0 for compliance, 1 for metadata findings, and 2 for
source/query failure. Without strict mode, findings remain visible in JSON but
return 0; query failures still return 2. Output separates findings from failures. It does not
establish which templates a team currently uses, inspect message bodies, or
prove actual dispatch adoption. A missing workflow declaration is not inherently
an invalid template; whether a workflow requires one comes from its consumer
contract. Catalog/global findings must be scoped to actual producer usage before
being called a current team regression.

## Repository pre-push gate

This repo's `.githooks/pre-push` invokes `scripts/check_push.py` from this skill.
It uses no model tokens and does not consume Git's ref-update stdin. If ATM is
not installed or the daemon is explicitly not running, the check reports a
skip and allows the push. With a running daemon it queries `atm templates list
--json` and blocks for any null/empty `template_type`. A failed query or unknown
diagnostic result blocks as unverifiable, not as an empty clean catalog.

The error identifies each SHA, its known expected type/source path, this skill,
and `standards.json`. To address a finding:

1. Identify the source and expected standard type. Review/dev/QA templates map
   to review-task/dev-task/qa-task; plan-hardening types declare plan stage;
   plan QA retains qa-task with stored `review_mode=plan` for classification.
2. Fix the authoritative producer frontmatter and validate the resulting new
   revision. Coordinate source merge, installed copies, and real emissions.
3. Re-audit every catalog revision. A corrected new SHA does **not** remove the
   old untyped SHA. Apply the authorized catalog maintenance procedure for
   verified historical mappings, then recheck the live catalog. Source-path
   mappings alone do not tag the database.

Do not rewrite message history, delete registrations, add automatic exemptions,
or bypass the gate. Catalog maintenance is separate from this read-only hook.

Repository installation uses `git config --local core.hooksPath .githooks`.
Preserve/combine an existing hooks path and checks when installing elsewhere;
this repo's installation does not install a hook in atm-core.

## Hook for a newly registered revision

```sh
assets/hooks/check-template-metadata TEMPLATE_SHA
```

This token-free hook audits only the supplied catalog revision against the
same standard and returns strict exit codes. Run it after registration in the
producer's authorized template workflow; wiring it into a producer is separate
from providing the hook. It detects noncompliance but cannot retroactively
prevent a registration that already occurred. It changes no templates or
messages. For pre-registration enforcement, feed the rendered schema through
an offline audit before admission; do not approximate YAML/Jinja with regex.

Run the full-catalog audit independently to maintain historical coverage. The
hook should not repeatedly fail a new valid revision solely because unrelated
old revisions are untagged. Do not manufacture historical workflow snapshots or weaken the standard
to silence remaining findings.

## Completion evidence

Return the maintained contract, authoritative files changed or proposed,
observed runtime/template revisions, actual query results, compatibility
coverage, and unresolved emissions. When no upstream change is needed, say so.
Metadata management succeeds when ordinary deterministic queries can identify
the required work without waking an agent to interpret incidental conversation.

## Authorized historical classification

Rand authorized maintaining catalog `template_type` and useful query metadata.
The interim helper changes only `message_templates.template_type` and
`schema_json.metadata.type` for full SHAs explicitly mapped in `standards.json`.
This is an administrative classification correction, not a claim that the
original source emitted that declaration. Never change template content/SHA,
message snapshots, workflow history, or generated effective tags. Missing
historical workflow declarations remain visible audit findings.

```sh
python scripts/maintain_catalog.py --database /absolute/path/to/mail.db
python scripts/maintain_catalog.py --database /absolute/path/to/mail.db --apply --receipt-dir /private/local/receipts
```

Review the dry-run against source evidence first. Apply requires an online
SQLite backup and receipt, rejects conflicting nonempty values, and updates
only verified mapped revisions transactionally. Keep backups and receipts
local and outside version control. Verify both `atm templates list/schema`
and actual `atm search --type` results afterward: on ATM 1.5.16 the type query
reads `schema_json.metadata.type`, so the catalog column alone is insufficient.
Prefer a supported native maintenance API when available; upstream request
[atm-core #1435](https://github.com/randlee/atm-core/issues/1435) covers scoped
standards, admission enforcement, remediation, and source provenance.

## Locating source revisions

Record repository, relative filename/path, source commit when known, installed
path, and the exact content SHA separately. A SHA cannot recover a pathname;
the same bytes may occur at several paths, and old revisions may exist only in
Git history or catalog content. Keep user-provided and independently verified
mappings distinguishable. Do not assume a current file matches a historical SHA.

`atm compose --template PATH --vars vars.json --dry-run --json` previews through
the core renderer without mailbox writes. Required variables must be supplied.
The inspected CLI returns body/dry_run/template, without a SHA; do not hash the
rendered body as the source revision. Use the verified producer hash contract
when comparing file bytes with catalog IDs: strict UTF-8, CRLF/lone CR
normalized to LF, BOM and final newline preserved (see adoption evidence).
A source path in future catalog
provenance will remain a locator hint, with content identity checked by SHA.
