# State and query design

Design contract. The implementation lives in `scripts/runtime/`;
[runtime.md](runtime.md) gives executable entrypoints and current evidence limits.
The four outputs and acceptance requirements are defined in
[requirements.md](requirements.md). Agent operation is defined in
[SKILL.md](../SKILL.md). These documents have different jobs; this document owns
the data, query and composition contracts below.
The [query command catalog](queries.md) contains the exact command forms and
verification boundaries for development; it is the command reference for this design.

## 1. Boundaries and direction of data

| Piece | Responsibility | Must not do |
|---|---|---|
| Immutable data structures | Represent source observations, composed state, query results and problems | Query, persist, send messages, or contain workflow methods |
| Independent queries | Read a named source for a stated question and return typed source state | Invoke other monitoring queries, combine sources, mutate shared monitoring state, or alert |
| Answer functions | Reconcile source state and answer the four oversight questions; pure functions with explicit inputs | Perform I/O, hide source disagreement, or schedule work |
| Cron | Run due queries, combine successful results, save state, compare old/new state and execute decisions | Contain source parsing or an entire agent investigation |

These are code boundaries, not separate services or a framework. Answer functions
are small functions called by cron. Persistence is an explicit read/write at the
cron boundary. Omega handles targeted investigation and repairs under the skill.

The flow is **queries → source state → composed state → answers/decisions**.
Cron retains the old state for `new_state != old_state`, then saves the new state
and action intents before attempting delivery. No query depends on another
query having run in the same tick; required inputs come from explicit arguments
or previously saved state.

## 2. Immutable data structures

All structures are immutable values, including nested fields: tuples and frozen
records, not mutable dictionaries/lists hidden inside a frozen outer object.
The tables below describe types, not classes with behavior. Serialization,
validation, reconciliation and decisions are separate functions.

| Type | Fields | Supports |
|---|---|---|
| `RepoKey` | Provider, owner/name, ATM team | Isolation and joins for O1–O4 |
| `PhaseKey`, `SprintKey` | RepoKey + phase; PhaseKey + sprint | Stable table rows, including work without tasks/PRs |
| `TaskKey`, `AgentKey` | ATM team + task ID; ATM team + agent ID | Ownership and idle detection |
| `PRKey`, `CheckKey` | RepoKey + PR number; PRKey + head SHA + check identity + attempt | Exact-revision CI and conflict status |
| `StackState` | RepoKey, identified stack/context, trunk, ordered branch members, parent relation, head/base SHA observations, PR reference, queued/merged/needsRebase facts | O1 hierarchy and O3 stack readiness; missing optional fields remain unknown |
| `EvidenceRef` | Source, entity/event ID, source revision/sequence when available | Explain answers and deduplicate repeated evidence |
| `PlanState` | Phase/sprint inventory, order, branch relations, plan revision | Complete O1 row inventory |
| `TaskState` | TaskKey, sprint association, assignee, assigned/active/closed status, assigned/start times, queue position, dependency status, runnable/waiting/unknown fact, assignment/start/outcome evidence | O1/O2; assigned is not started, closed is not QA accepted |
| `AgentState` | AgentKey, idle/working/blocked/unknown, state-since time or conservative first-confirmed time, background-work observation when available | O2; process state is not task state |
| `ReviewState` | SprintKey, review ID/round, reviewed SHA, verdict, findings | O1; verdict applies to its reviewed revision |
| `FindingState` | SprintKey, finding ID, B/C/I severity or unknown, open/resolved/withdrawn, review/evidence IDs | O1 counts and history |
| `PRState` | PRKey, sprint association, head SHA, base branch, open/merged/closed, mergeability and requirement states | O1/O3; mergeability and CI are distinct |
| `CheckState` | CheckKey, required/optional/unknown, absent/queued/running/passed/failed/cancelled/skipped/unknown, source start/completion times | O3; no checks is not a pass |
| `SprintState` | SprintKey, plan order/branch, task/owner facts, DEV and QA facts, review rounds, B/C/I counts, PR/check facts, blocker and next action | O1 row and input to O2/O3 |
| `PhaseState` | PhaseKey, configured plan revision, inventory coverage, ordered SprintStates, evidence-backed status summary | O1 grouping; reporting phase status does not automate phase lifecycle management |
| `RepoState` | RepoKey, configured phase/sprint states, task/agent/PR/check records | Persisted domain state for O1–O3 |
| `AnswerState` | O1 row values/coverage; O2 stall classification; O3 conflict/check classifications; O4 recovery-needed and follow-up-due markers | Stable condition values, never action-attempt or delivery receipt objects |
| `State` | Exactly `(RepoState, AnswerState)` | The exact value compared with old_state |
| `IncidentState` | Stable key, subject/revision, condition, owner, first evidence, action intent, delivery/ack/resolution receipts | Deduplication and follow-through for O2–O4 |
| `QueryReceipt` | Query ID + scope, window/cursor, last attempt/success, coverage, problem, retry deadline, evidence timestamps | O4 and provenance; not domain equality |

Every decision-relevant field is a `Fact[T]` with one of these variants:

| Fact variant | Meaning |
|---|---|
| `known(value, support, evidence)` | Support is authoritative, corroborated or fallback. Include a discrete fresh/stale marker; stale values are displayable history, not a basis for new negative claims. |
| `unknown(reason, last_known?)` | No usable current evidence; an optional prior value is visibly historical. |
| `conflict(candidates, evidence)` | Usable sources disagree and the field's authority rule cannot resolve them. Preserve alternatives. |

A source query returns source state; it does not decide the reconciled `Fact`
for another source. Answer functions construct those facts using the rules in
section 4. Whole rows need not be unknown because one field is unknown.

### Equality and disk representation

Normalize ordering by stable keys before value comparison. Keep event times
that describe real state (assignment/check start) in the values. Keep poll time,
retrieval latency, retries and changing display text in receipts outside domain
equality. Retain stable evidence references, not a new evidence ID per poll.

Freshness and configured deadlines are evaluated using an explicit `now` input.
Time passing may change a fact from fresh to stale or make pending work overdue;
those discrete changes affect state/answers. The raw current clock does not.
Thus a quiet tick stays equal while a stalled check can still trigger on time.

Precisely, `new_state != old_state` compares `State`, not the persistence
envelope. Incidents' transport receipts, query receipts and retry attempts live
alongside it. Their actionable conditions (for example delivery overdue) are
represented in the O4 answer, so crossing a deadline remains observable.
Formatting and human-readable diagnostic text do not participate in equality.
`IncidentState` is not a field of `State`. Answer functions receive incidents and
receipts as explicit inputs only to derive condition/deadline markers; their raw
delivery IDs and attempt counters are never copied into AnswerState.

Each source contract declares a freshness anchor and maximum age: provider
observation time for agent snapshots; validated retrieval time only for an API
contract that promises current state; source revision for immutable plans/reports.
Report age alone does not invalidate a verdict for its exact reviewed revision.
Future timestamps beyond configured clock-skew tolerance yield unknown timing
and a diagnostic, never negative age or an immediate overdue finding. Persist
the resulting discrete freshness/overdue markers in State; raw clocks stay in
receipts. Grace periods are policy inputs, not assumptions about timestamp order.

Serialize an envelope containing schema version, repo identity, generation,
State, incidents and query receipts. Validate on read/write; atomically
replace after a complete write. A failed write retains the prior generation and
prevents new actions for that uncommitted generation. Keep a last valid copy for
recovery. Unknown schema/corrupt state is an O4 error, never an empty fresh start.

Separate repo files/locks permit independent progress. Persist only current
projections, necessary evidence references, findings history and action receipts;
do not mirror the ATM database or re-fetch closed histories every tick.

## 3. Independent query contracts

Each function lives in `<target>_<query>.py`, fewer than 100 source lines excluding
blanks/comments. The function takes explicit scope/window/entity IDs and returns
one discriminated result. It does not read global monitoring state. Its adapter
and fixtures establish the exact supported command/API before implementation
is accepted. Shared data/result definitions do not turn queries into a collector.

| Proposed query file | Question / returned source state | Scope and scheduling |
|---|---|---|
| `git_sprints.py` | What sprints and branch relationships are in the configured plan? → PlanState | Named plan/revision; initialize once, refresh when revision changes |
| `atm_tasks.py` | Who has outstanding work and has it started? → TaskState portion | Configured team/current queue; no per-task history fan-out |
| `atm_workflow.py` | What assignment/DEV/QA changes occurred? → task/review evidence portion | Declared phase/sprint scope and bounded message window; preserve metadata gaps |
| `atm_report.py` | What verdict/findings does this identified report contain? → ReviewState | One newly relevant message ID; not every message body |
| `herdr_agents.py` | What are the selected agents doing? → AgentState portion | Current agents with outstanding work; one source surface |
| `atm_members.py` | What agent observations does ATM have? → AgentState portion | Fallback with original observation time, not fresh merely because fetched now |
| `gh_prs.py` | What are the relevant PR heads, bases, dispositions, merge states and stack identities? → PRState portion + stack references | GraphQL search over a bounded window; retain active identities for subsequent polls |
| `gh_pr_stack.py` | Which remote stack contains this PR? → stack membership portion | Conditional REST fallback if GraphQL membership is unavailable; cache/deduplicate |
| `gh_stack.py` | What is this identified stack's topology and status? → StackState | Primary command `gh stack view --json`, run in its identified existing worktree; one call per distinct stack, not per sprint |
| `gh_checks.py` | What is current readiness for identified active stack/member or standalone PRs? → remote StackState/PRState/CheckState portions | One bounded GraphQL node batch; exact heads and nested pageInfo; poll retained active work without relying on PR updatedAt |
| `gh_requirements.py` | Which checks are expected for this branch/event? → required-check evidence | Cache explicit branch/workflow policy by revision; refresh when policy changes |
| `gh_qa.py` | Does this PR have a revision-addressed QA report? → ReviewState portion | Conditional fallback for missing ATM report; do not equate a generic approval with QA |
| `scheduler_runs.py` | Did the expected job/action actually execute? → execution receipt portion | Scheduler receipts; watchdog runs outside the supervised job |

This is the available question set, not a command to run every query every tick.
Normal ticks refresh current assignments, relevant workflow changes and active
PR/check state. Load plans/policy on change and invoke detail/fallback queries
only when their fact is needed. Budget pagination and batches explicitly; a
query may return a continuation instead of exhausting the repository's budget.

Not all sources necessarily expose each proposed field. Each adapter contract
must document that capability and return unknown coverage where absent. Do not
invent a flag, infer completeness from exit zero, or expand to all history to
make a question appear answerable.

### gh-stack contract (O1/O3)

Once a stack is identified, `gh_stack.py` uses `gh stack view --json` as the
primary stack-status observation. Stack context is an explicit existing worktree
whose checked-out branch identifies that stack unambiguously. Do not use an
arbitrary repo root, interactive view, or a checkout mutation inside the query.
The adapter validates the installed version's JSON shape.
GraphQL supplies remote stack identity/order and current PR/check state in the
two verified batches in [queries.md](queries.md). gh-stack supplies local
maintenance status. Its view may refresh its own tracking cache; it does not
write the monitor's state or authorize branch modification.

Preserve trunk and ordered branch membership. Derive parent branch from order;
the branch's `base` value is a SHA observation, not a parent branch name. Preserve
`head`, `isMerged`, `isQueued`, `needsRebase` and PR association independently.
Absent optional fields are unknown. A branch without a PR still belongs in the
table. One phase may reference multiple stacks and non-stack PRs; do not force
parallel work into one linear stack or equate a stack with a sprint.

Stack `needsRebase` is local ancestry evidence, not proof of a GitHub merge conflict
or authority to rebase. Compare local heads/base refs with current GitHub SHAs;
if stale, use `git merge-base --is-ancestor` on the exact remote SHA pair when
objects are available, otherwise return unknown with context-repair guidance.
A successful exact-SHA comparison can supersede a stale local needsRebase value.
Verify current conflicts/checks through exact PR/head
state. Queue membership is a legitimate wait state; queue-specific check/head
expectations must be established before calling CI absent or stuck. Parent merge
or retargeting changes branch relationships and invalidates affected head/base
assumptions; preserve unaffected history and avoid declaring a child complete.

If stack view fails, remote GraphQL stack membership/order, queue and PR/CI facts
remain usable; only local ancestry coverage degrades. If remote stack metadata
also fails, use known PR head/base relationships for a degraded hierarchy, without
inventing membership, queue state or needsRebase. A positively
identified non-stack PR is normal supported work. Failure to find local stack
context is not proof that the remote PR has no stack.

Ambiguous membership, missing extension, unavailable GitHub and malformed JSON
return classified problems with context and repair guidance. No query initializes,
links, unlinks, checks out, rebases, synchronizes or merges stacks. Alert the
responsible agent instead. Scope discovery/binding and a successful exact-version
live fixture remain prerequisites to claiming verified stack compatibility.

### Query result union

Every variant requires query ID, source, scope, window or `current-state`, and
receipt. Payloads and envelopes are immutable typed records in memory; JSON
objects/arrays are only their wire/disk encoding, validated back into records.
The `status` discriminator determines the payload:

| Variant | Payload | Composition/checkpoint behavior |
|---|---|---|
| `ok` | Immutable source state + complete coverage for stated scope | Accept facts, save and advance this query's checkpoint. Empty means empty only within that scope. |
| `partial` | Immutable state received + missing coverage + typed continuation | Accept positive evidence without claiming absence/completeness. Keep window checkpoint; save continuation cursor and dedupe IDs. |
| `error` | Typed Problem; no successful state implied | Retain prior facts with failed-refresh coverage; run fallback/recovery independently. |

Returning one portion of full repo state is ordinary `ok`, not `partial`.
An `ok` source can also explicitly report that a field is unavailable; complete
retrieval is different from knowing every domain fact.
Each query declares its completeness predicate: requested entities/pages were
retrieved and mandatory schema fields decoded. Unsupported optional fields are
explicitly unknown in an `ok` result; missing pages are `partial`; malformed
mandatory fields are `error`. Consumers cannot redefine these cases ad hoc.
Each query contract enumerates required identity/schema fields and the facts
it supplies to decisions. A required fact slot may explicitly contain unknown
with a reason when its source lacks the fact; it may not be silently omitted.
Missing decision evidence then makes that predicate unknown, not the transport
query unsuccessful. This distinction permits the other source to fill the gap.

Problem fields: kind, source/query/scope/window, failed command or API, exit/status
code, bounded sanitized diagnostics, retryable, retry-after if supplied,
suggested repair, and repair owner. Distinguish timeout, rate limit, service
unavailable, missing executable, access/authentication, unsupported capability,
invalid input and invalid response. Catch boundary exceptions into this union;
do not expose a bare traceback as the only recovery instruction.
If a query cannot start, crashes or produces no valid union, its cron invocation
boundary converts that execution failure into `error` with the same diagnostics
and recovery contract. The failed query need not be healthy to report its failure.

Delta windows retain source-defined inclusivity, overlap the last accepted
boundary and deduplicate by evidence ID. Never assume timestamps uniquely order
events. Complete current queue absence means no longer in that queue; it does
not prove task completion. Fallback success never advances a failed primary's
checkpoint. Store `last_accepted_checkpoint` separately from the pending
window/cursor. Partial success updates only pending continuation and dedupe
receipts; a failed continuation preserves both for retry. Only completion of
the whole pending window advances the accepted checkpoint. An expired cursor
restarts the same bounded window with ID deduplication.
Example: accepted boundary A; request [A, B]; pages 1 and 2 are partial. Their
cursors and evidence IDs are saved, but the accepted boundary remains A. Only
the final complete page commits B. A failure after page 2 leaves A and page 2's
continuation intact; it does not advance the accepted boundary to a page cursor.
Sources without a safe change query use a small explicit current
entity set, not an unbounded historical scan.

## 4. Combining approximately two sources per fact

Two sources are useful redundancy, not a quorum requirement. A single fresh
authoritative source is sufficient. Query fallback sources when needed, not
automatically at double cost. Apply authority per field, not per repository.

| Fact | Preferred evidence | Other evidence and its limit |
|---|---|---|
| Sprint inventory/order | Configured plan revision | Explicit structured sprint assignments/PR associations can add provisional rows; cannot prove the entire inventory |
| Assignment/task start/outcome | ATM task state or exact task transition | Assignment/start/close message evidence can fill a gap; plain progress or ACK is not completion |
| Agent idle/working | Fresh harness observation | ATM roster observation is a fallback; if derived from Herdr it is the same underlying observation, not independent confirmation |
| QA verdict/B/C/I | Revision-addressed QA report in ATM | Matching PR QA report can substitute; same report copied twice counts once. A generic GitHub approval cannot supply findings counts |
| PR merge/conflict state | GitHub's exact PR/head state | Local Git or agent reports are corroboration/last-known evidence, not proof of current GitHub mergeability |
| CI result | GitHub checks for exact head/attempt | Workflow-run detail or explicit runner receipt can fill a diagnosed gap; an agent's “tests pass” is not GitHub CI success |
| Required-check expectation | Applicable branch/workflow policy | Explicit configured expectation with revision is fallback; lack of a check row does not establish that a check is required |
| Scheduled execution/delivery | Scheduler execution or transport receipt | A fresh persisted query/state receipt can prove collection ran, but not that an alert was delivered |

Revision rules are field-specific: configured plan revision owns inventory;
ATM's task sequence/current row owns task state and assignee; the explicit QA
review ID/round and reviewed SHA own verdict/findings; GitHub PR head and check
attempt own merge/check state; applicable policy revision owns required checks.
Later observations supersede only within a source's documented revision/order
contract. Incomparable source revisions remain conflict/unknown; timestamps
from different clocks cannot invent an ordering. Generic plan status and merged
PR status are separate facts, not competing values for one field.

Reconciliation rules, in order:

1. Match stable identity, repo/team/sprint scope and revision. Do not join by a
   display name or use old-head QA/CI as proof for a new head.
2. Separate **complementary** facts from substitutes. A task assignment plus an
   idle observation are both needed for O2; neither is a fallback for the other.
3. Prefer usable field-authoritative evidence. A fresh authoritative result may
   override an older secondary report; retain the secondary evidence as history.
4. Use a contract-approved fallback when primary evidence is missing, stale or
   failed. Mark fallback support/coverage. Use it for decisions only to the extent
   that it actually establishes the required predicate.
5. If equally authoritative evidence disagrees without a source ordering or
   revision rule that resolves it, emit a conflicted fact and an actionable
   reconciliation problem. Never choose by arrival order or majority vote.
6. With no usable source, expose unknown/stale for that field and keep the rest
   of the row. Preserve unresolved incidents; missing evidence cannot resolve them.
7. Deduplicate shared origins. Two transports of one QA report or one harness
   observation do not create two rounds, two findings or stronger confirmation.

Missing a preferred source creates an O4 recovery obligation even if fallback
makes the O1–O3 answer usable. Conversely, missing an optional corroborating
source is not automatically an agent-waking failure. Wake only if recovery needs
agent action or the available evidence establishes an actionable domain condition.

## 5. Answers and decisions

Decision prerequisites are shared contracts, not adapter choices: O1 completeness
requires the configured plan inventory; an O2 stalled claim requires identified
runnable work, fresh idle evidence and an established grace anchor; O3 timed
claims require exact head/attempt, applicable expectation, complete check coverage
and the relevant time anchor. A positive conflict/failed-check claim instead
requires its own fresh exact-head evidence. Unknown prerequisites block only
the corresponding assertion. O4 requires an identified failed capability and
impact, not complete O1–O3 data.

| Answer function | Inputs | Output and action |
|---|---|---|
| Phase/sprint table (O1) | Plan inventory + reconciled task/review/PR/check facts | Every sprint in the configured plan revision, plus separately marked provisional rows, with hierarchy, ownership, DEV/QA, rounds, B/C/I, blocker/next action and field-level coverage. If that inventory is unavailable, retain known rows and an explicit inventory-coverage problem; never claim a complete phase table. |
| Assigned-but-idle (O2) | Runnable outstanding assignment + fresh idle observation + queue/dependency/context evidence + configured grace | `stalled`, `legitimately-waiting`, `working`, or `unknown`. Alert stalled work once to owner/lead; investigate missing context without falsely accusing an agent. |
| CI/merge readiness (O3) | Exact-head PR state + applicable expectations + checks/attempt times + configured deadlines | Independent conflict/failure/not-started/stuck findings. Unknown policy/timing prevents “never started” claims but does not suppress a proven conflict or failed check. |
| Recovery (O4) | Query/execution problems + fallback coverage + prior attempts/deadlines | Bounded retry, local repair, targeted fallback or one maintainer escalation; retain failed checkpoint and verify recovery. |

For O2, a head-of-queue assigned task can become stalled before it is active;
do not restrict detection to started tasks. A later queued assignment or known
dependency explains waiting. Task-specific grace and fresh background-work
evidence prevent false alarms. Acknowledgment alone does not prove progress.

O2 precedence: closed/no assignment → no stalled assignment; fresh working
evidence → working; explicit queue/dependency hold → legitimately waiting;
otherwise require fresh idle + runnable assignment + elapsed grace to assert
stalled. Missing/contradictory prerequisites → unknown. Measure grace from the
later of runnable-since and idle-since; if either transition time is unavailable,
use the first confirmed simultaneous runnable-and-idle observation conservatively.
Unknown background-work coverage stays visible and requires investigation before
intervention; a proven background task explains waiting rather than stalling.

For O3, check merge conflicts immediately. A proven conflict must not wait for
a CI-start timer. To call a check not-started, establish its applicability,
trigger/head time, complete check coverage and elapsed configured start grace.
To call it stuck, establish queued/running time and the relevant deadline.
Cancelled/skipped/draft/approval-gated work needs policy interpretation, not an
automatic failure label. If a conflict explains absent checks, send one causal
alert containing both facts rather than duplicate unexplained CI alarms.

An absent check is synthesized only when applicable expectations and complete
exact-head check coverage establish absence; otherwise it is unknown. Not-started
uses the evidenced eligible-trigger time plus start grace; queued uses queued-at
plus queue deadline; running uses started-at plus runtime deadline. Missing
anchors prevent that timed classification. A new head or check rerun selects a
new attempt identity; cancelled attempts are retained as history, not kept running.

Answers are recalculated from current state and explicit time/policy. A changed
answer is not necessarily actionable. Record routine progress quietly; a new
actionable condition reserves one incident intent. Existing assigned repairs
become the next action rather than repeated “unowned blocker” alerts. A current
incident can require deadline-based follow-up even without a new source event.

## 6. Cron, recovery and scale

For each due repo: load/validate state; run the bounded due queries; reconcile
their results; compute answers; atomically save state/checkpoints/action intents;
then attempt the required actions and save actual receipts. A failure of one
query must not discard another query's success. Serialise writers per repo;
bound concurrency across repos and providers. No global all-or-nothing tick.

An incident key includes repo, subject and condition, plus revision/attempt when
the condition is revision-specific. Recovery needs fresh evidence establishing
that condition cleared. Unknown is not recovered. Persist intent before send;
use transport idempotency where supported. If send outcome is ambiguous, query
the transport receipt before retrying; otherwise escalate uncertain delivery.
Do not claim exactly-once delivery from a local reservation alone.

Action states are `pending → attempting → delivered → acknowledged`, with
`attempting → failed` on a confirmed failure and `attempting → uncertain` if the
outcome cannot be established. Failed actions retry only when policy permits;
uncertain actions first reconcile receipts. Condition resolution is separate
from these delivery states. Rearm a domain incident only after its condition
is freshly resolved and then recurs; acknowledgment alone never rearms it.

Retry transient errors within configured bounds; honor retry-after. Exhausted
retries, unsupported capability, bad output or inaccessible state produce an
actionable repair incident. A successful fallback supports continued oversight
while primary repair remains pending. Correlate shared-provider outages to avoid
one agent wake per repo. One stalled repo must not starve the other dozens.
Group a shared failure by provider/endpoint, credential or service scope,
capability and problem kind; store affected query/repo identities as impact.
Do not group independent repository permission errors into a global outage.

A watchdog in an independent scheduled execution context checks expected runs
and outstanding action execution. If both scheduler and watchdog share a failed
host, local self-healing cannot run; an external supervisor is required for that
failure domain. Record this deployment boundary rather than promise perfection.

Required deployment policy: per-question freshness and call/row/time budgets,
window overlap, idle grace, CI-start/queued/running deadlines, retries/backoff,
provider concurrency, escalation/follow-up deadlines and watchdog tolerance.
These are explicit configuration validated before enabling the covered behavior,
not hidden constants invented by a query.

## 7. Acceptance examples

| Case | Required result |
|---|---|
| Same inputs returned on another poll | Equal domain state; refreshed receipts, no repeated wake |
| QA source fails; plan/tasks/PR remain healthy | Table still reports known fields, stale/unknown QA; targeted recovery only |
| ATM QA missing; matching PR report available | Fallback QA value with provenance; no duplicate review/counts |
| Both transports contain the same QA report | One review and one set of findings |
| Fresh ownership sources disagree | Conflict on owner, preserved candidates; no fabricated assignment |
| Idle agent with second queued task | Waiting, not stalled; after becoming runnable, grace applies |
| Agent source unavailable but task remains active | Task remains active; idle answer unknown; no false idle alert |
| PR conflicts and required checks are absent | Conflict alert now, with causal explanation; no indefinite CI polling |
| CI check is absent but required policy is unknown | Unknown start expectation; a different proven failed check still alerts |
| Healthy poll crosses a stuck-check deadline | One new stuck condition despite no new provider event |
| Old-head passing check and new PR head | Current head has unknown/pending coverage; old pass is historical |
| Identified stack with branch lacking a PR | Preserve ordered branch row and unknown PR/CI, not an omitted sprint |
| Parent merged or child retargeted | Refresh affected topology/PR assumptions; no false child completion |
| Queued stack plus pending checks | Preserve queue state; use applicable queue policy before overdue classification |
| Stack view unavailable; PRs readable | Degraded PR hierarchy and stack-query repair problem; no invented stack health |
| Multiple stacks and ordinary PRs in one phase | Distinct stack groups with correct trunk/parent relations and standalone PR rows |
| Partial page plus complete independent query | Positive facts accepted, incomplete checkpoint retained; independent success advances |
| Query fails after an incident was raised | Incident remains unresolved; recovery cannot be inferred from missing data |
| Restart after action reservation | Resume/reconcile delivery; no lost intent or blind repeated send |
| One query hangs among 30 repos | Other repos continue within configured budgets; one repair incident |

Test query variants independently, then these pure composition/decision cases,
then actual scheduled table/alert/recovery behavior. Do not implement the next
piece until its inputs, output type and evidence rules are internally consistent.
