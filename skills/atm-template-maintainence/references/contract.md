# Metadata contract rules

ATM is a generic fact store. The oversight maintainer owns the consumer's
workflow vocabulary and producer/consumer agreement. Upstream authority is the
monitored ATM repository's `docs/template-workflow-metadata.md` and
`docs/adr/ADR-046-template-declared-workflow-metadata.md`; check the source
revision matching the running runtime before changing declarations.

## What belongs where

| Field/source | Meaning | Management rule |
|---|---|---|
| `metadata.type` | Work-record classification, normally template-declared | Keep stable and queryable; receipt authorized historical administrative corrections separately; legacy catalog `template_type` does not prove this key exists |
| `metadata.tags` | Literal template labels | No interpolated variables, secrets, duplicates, or reserved generated prefixes |
| Sender instance tags | Labels for the individual admitted message | Preserve separate provenance; do not substitute them for missing workflow declarations |
| `metadata.workflow` | Explicit scope, state, stage, transition, optional iteration-variable declaration | Use the actual workflow's facts; no extraction from message prose |
| Admitted `workflow.snapshot` | Values resolved when the message was admitted | Canonical evidence; later template edits cannot rewrite it |
| Effective tags | Search projection combining instance, applied-template, and derived tags | Verify results and provenance; do not author ATM-generated tags |
| GitHub planning PR | Planning-in-progress / plan-ready milestone | Separate canonical source from ATM; retain PR/revision/timestamps |
| Oversight JSON | Repo ownership, checkpoints, phase associations and derived decisions | Reference canonical ATM/Git facts rather than copy their databases |

ATM-generated prefixes are `template-type:`, `content-format:`,
`workflow-state:`, `workflow-stage:`, `workflow-transition:`, and
`workflow-scope-kind:`. Producers must not supply them as literal or instance
tags. A plain tag such as `stage:plan` is distinct from derived
`workflow-stage:plan`.

## Declaration review

Example shape for a planning review notice (names are producer conventions,
not mandatory ATM enums):

```yaml
metadata:
  type: plan-review-notice
  tags: [stage:plan]
  workflow:
    scope:
      kind: phase
      variable: phase
    state: plan-review-notice
    stage: plan
    transition: notice
    iteration_variable: round_index
```

If workflow is declared, scope/state/stage/transition must be complete under
the installed contract; iteration is optional. Scope and iteration variable
names must resolve from the actual admitted merged variables. A variable not
listed in required/default fields may be supplied at dispatch: inspect real
admission evidence before calling it invalid. Labels are literal and generic;
per-message scope/iteration values come from declared variables, not Jinja
interpolation inside metadata tags. Retain unknown additive fields.

Use stable scope identity across a paired start/completion. A generic phase
scope with iteration '2' may be shared by several reviewers: consumers also
need reviewer/stage/round/revision identity for round counting. Do not claim
that one aggregate count of messages equals completed hardening iterations.

## Signals the oversight contract requires

- **Planning:** template-declared stage `plan`, or a stored plan-QA discriminator
  `review_mode=plan`. Opening a PR whose source/head branch is `plan/*` is an
  independent deterministic planning signal. Casual conversation, a busy agent,
  template registration, or task-description keyword matches are not triggers.
- **Plan ready:** completion by merge of that `plan/*` PR, with accepted revision
  and `mergedAt`. Closed without merge is distinct. Other branch conventions
  use their explicit acceptance contract. A review notice or round PASS is
  not automatically the whole plan's readiness event.
- **Development:** declared development assignment/start evidence, distinguished
  from QA/review and from a task merely queued for future execution. Verify
  producer state/stage values instead of inventing them from a type label.
- **Iterations:** emitted review start/result/notice records with source round
  identity, reviewer, reviewed revision, outcome, and timestamps as applicable.
  Replays, acknowledgments, and multiple corrections in one round do not count
  as new rounds. A summary notice preserves historical round references.
- **Lifecycle:** task state, phase state, agent process state, and monitor health
  remain separate. Queue disappearance does not establish completion.

Deterministic activity detection qualifies work before waking Omega-prime.
Repo/team ownership in pending/active state suppresses general activity wakes;
the repo-specific cron then owns transitions and subsequent phase discovery.
Metadata availability is necessary evidence, not an implementation of that
scheduler registry or state projection.

## Per-revision enforcement

Every `.j2` content change used in a dispatch can register another immutable
revision. Classifying the old SHA or auditing the pathname once is insufficient.
The producer declares the type in frontmatter; admission snapshots it for the
new revision and message. In the inspected code, missing `metadata.type` emits
a warning and remains valid but untyped. The pre-push gate is an external
read-only guard, not a replacement for native admission enforcement.

`standards.json` is the checked-in standard for expected query classifications.
It is not an alternate mutable label store for ATM. A revision binding supplies
expected classification in an audit, but cannot satisfy the gate's requirement
that the actual ATM catalog record has a type.
