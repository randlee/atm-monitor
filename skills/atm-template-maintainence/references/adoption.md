# Adoption receipts and verification

An adoption receipt is evidence, not a second template registry. Keep immutable
runtime snapshots in ATM and authoritative template sources in their repo.
Store local query/audit results and source references under ignored deployment
validation state; summarize decisions in the maintained requirements/skills.

For each required signal record:

- Consumer decision and literal field selectors, including scope semantics.
- Source repository/path/commit and responsible producer workflow.
- Template SHA and relevant runtime CLI/daemon/API versions.
- Installation receipt per producer, separate from source merge status.
- Actual admitted message IDs, occurrence times, workflow snapshot/provenance.
- Query command, time bounds, results/cursors, negative cases and compatibility.
- Remaining sender adoption or historical coverage gaps.

New content produces a new immutable template SHA. Preserve original content and message snapshots. Authorized catalog type
corrections use the maintenance helper with backup and provenance receipts;
never manufacture historical workflow declarations to make an audit green. Template
registration proves recognition, not use. A shared schema can be used by multiple
teams; host catalog counts alone do not establish a team's active coverage.
Cross-host rendered/plain fallbacks may lack decomposed workflow snapshots;
record that limitation rather than manufacture metadata from their text.

## Verified atm-dev planning recipe

Fenix receipt `01M2BD1NRG4J6DAZ3ZX6V0BKT3` reports source PR #1434 adding
metadata to orchestration and plan-hardening templates. The maintainer verified
these live queries on ATM 1.5.16. Runtime capabilities must be rechecked when
versions change; search identity here is pinned in the environment because
`atm search` does not accept `--as` in that build.

```sh
ATM_IDENTITY=omega-prime atm search --team atm-dev --workflow-stage plan --since '<checkpoint ISO>' --json
ATM_IDENTITY=omega-prime atm search --team atm-dev --var review_mode=plan --since '<checkpoint ISO>' --json
```

Union the two result sets by team/message ID. Follow each query's cursor before
advancing a successful shared checkpoint; persist an overlap/dedup strategy so
boundary equality and interrupted pages lose no records. Apply active/pending
repo suppression before any agent handoff. Returned `notice` events can describe
old work, not newly started work at their send time.

For metadata-bearing planning records, `--type 'plan-*'` and
`--effective-tag workflow-stage:plan` found the same verified notice; those are
alternative selectors, not extra events. `--type qa-task --var review_mode=plan`
is narrower and missed the untyped historical plan-QA message; retain the
variable-only compatibility clause until the relevant history is accounted for.
Do not infer that lack of metadata equals no planning.

Verification evidence:

| Selector | Observed message | Interpretation |
|---|---|---|
| workflow stage `plan` | `01M2BCX5F84MF2757DJSPVEKYG` | Phase BB plan-review notice; scope BB, transition notice, iteration 2 |
| type `plan-*` / effective `workflow-stage:plan` | Same message | Equivalent selectors for this admitted record |
| type qa-task + review_mode=plan | No hit in checked window | Historical dispatch was untyped |
| review_mode=plan only | `01M2BBZ2NW70Y6B8V2J20EHV5D` | Plan QA assignment with stored discriminator |

The notice revision is
`6e12f1ba274cb41d12f6f809649b286769cf8bd6c4be6bbad88b4b58ae047398`, first
observed September 12, 2026, 18:08:36 UTC. It contains literal `stage:plan` and
derived workflow tags; type alone is not the effective-tag set. Earlier
planning messages had `workflow: null`. The notice does not retroactively
populate them, prove two total rounds, or establish plan ready.

Fenix reports updated hardening workflows emitting a notice after each
background reviewer round. Verify those actual emissions for each producer;
background subagents do not generate ATM traffic automatically. Adoption by
one installed sender does not establish adoption by another sender.

## Negative cases to verify on a change

Casual untemplated questions must not match the planning clauses. Plain QA
without `review_mode=plan` must not be classified as plan QA. A registered but
unused planning template must not trigger activity. Duplicate messages/replays
must not add iterations. Already active/pending repo ownership must suppress
general activity wakes even when a valid new planning record exists. Missing
history, failed queries, or unsupported flags remain coverage failures.

Use offline fixtures for negatives and replay tests; inspect existing live
records for positive adoption. Do not emit production test messages without
specific send authorization. The authorized catalog-only procedure does not authorize daemon switches or
changes to task/message history.

## Historical untyped revisions mapped by Rand

These mappings are stored in `standards.json` and are expected-type bindings,
used for the separately authorized, receipted catalog type correction. Paths are relative to
atm-core. Both dev SHAs are distinct revisions of the same source template.

| Revision prefix | Source under `.claude/skills/codex-orchestration/` | Expected type |
|---|---|---|
| `5df2a8350ae8` | `review-template.xml.j2` | `review-task` |
| `b5cb960980db` | `dev-template.xml.j2` | `dev-task` |
| `2ce713072182` | `dev-template.xml.j2` | `dev-task` |
| `c26bae55ef3a` | `qa-template.xml.j2` | `qa-task` |

At inspection, the shared atm-core checkout's review/dev/qa source templates
still lacked metadata, while installed `~/.atm/templates/codex-orchestration/`
copies declared the expected metadata. PR #1434 was OPEN at
`d3a7cbca5c925b88d0f9f4f2a7cb3e5fbb7c5329`. This is a source/installed adoption
split, not authorization to edit the shared checkout. A subsequent catalog
audit saw 14 revisions and the same four untyped revisions; 12 historical
schemas lacked declared metadata.type despite eight having legacy catalog
classification. Distinguish those counts explicitly.

## Catalog maintenance receipt — September 12, 2026

Rand authorized the four mapped classification repairs. At 18:30:17 UTC the
maintainer applied `maintain_catalog.py`: four rows changed, filling catalog
`template_type` and stored `metadata.type`. An online SQLite backup and JSON
receipt are retained locally under `.local/validation/template-maintenance`.
Original template bytes/text were compared with the backup and are unchanged.
No workflow declarations or admitted message snapshots were backfilled.

Post-repair evidence: `atm templates schema` succeeds for all four; exact-SHA
plus expected `--type` searches scoped to atm-dev return existing messages for
each. The formerly untyped QA search now includes `01M2BBZ2NW70Y6B8V2J20EHV5D`.
The earlier zero-hit typed-QA result above is pre-repair evidence. Preserve the
variable-only compatibility query for other historical or remote producers.

The 14-revision catalog has zero unclassified revisions, and the pre-push gate
passes. A repeated maintenance dry-run selects zero rows. The broader audit
still reports 12 revisions with metadata gaps against today's declared
workflow standard; classifying their type does not establish workflow adoption.

## Source provenance check

At atm-core checkout `281e6f54679702847b0325fad300c737d01b084e`, the review
and QA source files above match `5df2a835…` and `c26bae55…` respectively.
Installed copies under `~/.atm/templates/codex-orchestration/` have different,
newer content identifiers. The two dev mappings remain Rand-provided source
associations: the bounded history inspection did not recover their exact Git
revision/local file. Do not label those paths independently verified.

All four catalog content blobs reproduce their stored SHA under the inspected
hash contract, and their frontmatter names agree with review-task/dev-task/qa-task.
ATM's `crates/atm-template-sc-compose/src/lib.rs` calls sc-sha
`calculate_hash(HashInput::TextFileBytes { utf8_file_bytes: raw_file_bytes })`
and takes `.template().to_hex()`. The documented text-file contract normalizes
CRLF and lone CR to LF, preserving BOM and final-newline presence. Hashing
rendered output or assuming unnormalized raw bytes is not equivalent in general.
The current `atm compose --dry-run --json` preview does not expose this SHA.
Source filename/path provenance is requested in atm-core #1435 so future
maintenance need not reconstruct these associations from content alone.
