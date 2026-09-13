# Exact query commands and recovery

Companion to [design.md](design.md). These are development contracts, not Python
implementation. Save the fenced GraphQL documents under the stated names to run
the shown commands. Production adapters use argument arrays, explicit cwd,
timeouts and captured stdout/stderr; placeholders are validated caller inputs.

## Verified GitHub sequence

**A: select changed PRs and stack identities → B: batch current stack/member or
standalone PR readiness → C: gh-stack local status → D: reconcile stale refs.**
All pagination flags and response errors must be checked before accepting coverage.

### A. PRs after X, with stack membership — gh_prs.py

Save as `pr-search.graphql`:

```graphql
query($search: String!, $after: String) {
  search(query: $search, type: ISSUE, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        id number updatedAt state headRefName headRefOid baseRefName baseRefOid
        isDraft mergeable mergeStateStatus isInMergeQueue
        stack { id number baseRefName }
        stackEntry { position }
        statusCheckRollup { state commit { oid } }
      }
    }
  }
  rateLimit { cost remaining resetAt }
}
```

For changed PRs in an explicit window:

```sh
gh api graphql -F query=@pr-search.graphql \
  -f search="repo:$repo_slug is:pr updated:>=$since updated:<=$until"
```

If X means creation time for initialization, use `created` instead of `updated`.
Do not use created-time filtering for incremental changes. Continue a search
page with the same search and `-f after="$end_cursor"` only while its pageInfo
says more pages, subject to the query budget.

This one query returns PR node IDs, exact heads/bases, mergeability, queue state,
check summary, stack ID/number and stack position. Deduplicate non-null stack IDs.
Retain relevant open PR/stack IDs across ticks: CI changes need not change PR
updatedAt. A null stack with no associated GraphQL error means no current stack;
a failed stack field is unknown. Do not infer membership from branch names.

### B. Expand stacks and read current readiness — gh_checks.py

Save as `state-batch.graphql`:

```graphql
query($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... PRStatus
    ... on PullRequestStack {
      id number baseRefName size
      entries(first: 50) {
        pageInfo { hasNextPage endCursor }
        nodes { position pullRequest { ... PRStatus } }
      }
    }
  }
  rateLimit { cost remaining resetAt }
}
fragment PRStatus on PullRequest {
  id number state headRefName headRefOid baseRefName baseRefOid
  mergeable mergeStateStatus isInMergeQueue
  statusCheckRollup {
    state commit { oid }
    contexts(first: 50) {
      pageInfo { hasNextPage endCursor }
      nodes {
        __typename
        ... on CheckRun { name status conclusion startedAt completedAt detailsUrl }
        ... on StatusContext { context state createdAt targetUrl }
      }
    }
  }
}
```

Supply deduplicated stack node IDs plus active non-stack PR node IDs:

```sh
gh api graphql -F query=@state-batch.graphql \
  -f "ids[]=$stack_node_id" -f "ids[]=$non_stack_pr_node_id"
```

Omit an absent selector; do not pass an empty ID. Limit each batch using the
configured entity budget. Sort entries by position, retaining stack trunk/order.
Expand the whole affected stack, including required ancestors outside the initial
window. Check BOTH entries and check-context pageInfo; incomplete nested pages
must return a continuation for that connection, not silently complete the batch.

Run B for retained active work even when A finds no changes. GraphQL gives
current mergeability and checks together; verify rollup.commit.oid matches the
reported head. Preserve failures, pending, cancelled/skipped and unknown separately.
A required check that never appeared still needs expectation/trigger evidence;
this query does not manufacture that evidence.

### C. Local stack status once per identified stack — gh_stack.py

Identify an existing worktree on one unambiguous stack member:

```sh
git -C "$repo_path" worktree list --porcelain -z
```

With cwd set to that worktree, run:

```sh
gh stack view --json
```

The installed v0.1.0 command has no stack-number argument. No interactive view,
implicit checkout, init, sync or rebase is part of this query. It may refresh
its local gh-stack tracking cache. Preserve trunk, ordered branches, PRs,
isMerged/isQueued/needsRebase. Its `base` is a SHA, not a branch name.

### D. Validate local ancestry context; recover stale observations

Read local heads once and compare them with B's headRefOid/baseRefOid:

```sh
git -C "$repo_path" for-each-ref --format='%(refname:short) %(objectname)' refs/heads/
```

`needsRebase` in v0.1.0 uses local ancestry, not necessarily current remote refs;
its false value can also mask an ancestry-command error. For a stale/uncertain
relation, query the current remote SHA pair directly, without editing branches:

```sh
git -C "$repo_path" merge-base --is-ancestor "$base_oid" "$head_oid"
```

Exit **0**: current base is included. Exit **1**: current base is not included
(maintenance evidence, not a command failure). Other exits: ancestry unavailable;
return typed error/unknown with stderr and missing-object/context repair guidance.
Do not move an active agent's branches to make the query work. If objects are
missing, Omega arranges a scoped fetch in the monitoring context and retries;
until then remote PR/CI reporting continues with local ancestry unknown.

Do not equate canBeRebased, MERGEABLE, needsRebase or a should-rebase recommendation.
The last also depends on team policy: frozen/append-only layers may need a new
fix layer or a merge-forward rather than a rebase. Alert with the evidence and
allowed maintenance action; the monitor never rebases automatically.

## Known command failures and recovery

| Observation | Result | Exact response |
|---|---|---|
| GraphQL HTTP success containing errors | `partial` if unaffected typed subtrees remain useful; otherwise `error` | Inspect errors/path, retain unaffected evidence, mark affected fields unknown, preserve their accepted checkpoints |
| hasNextPage at either connection | `partial` | Save connection/parent ID/cursor and window; continue within budget, advance accepted boundary only when complete |
| Null node for a requested known ID | Unknown entity + coverage problem | Retain identity; resolve through current PR/stack lookup instead of silently deleting it |
| Unsupported field/validation error | `error`, non-transient | Compare schema/CLI version and repair query; use REST/CLI fallback below; no repeated identical retries |
| Rate limit or transient HTTP/network failure | `error`, retryable | Honor retry-after/resetAt; bounded configured backoff, retain checkpoint, continue other providers |
| Authentication/access failure | `error` | Run `gh auth status --hostname github.com`; diagnose credential/repo access and escalate required repair without exposing credentials |
| `gh stack view --json` exit 2 | Context problem unless remote non-stack status is independently known | Inspect stderr; missing state/repo and no membership are different. Bind a known existing member worktree; keep GraphQL reporting useful |
| gh-stack exit 6 | Ambiguous stack context | Bind an existing non-shared member worktree; do not blindly checkout or unstack |
| gh-stack lock error | Retryable context problem | Bounded retry; persistent lock requires scoped diagnosis, not deleting locks blindly |
| Stale local heads/base | Local observation incomplete | Use exact remote-SHA ancestry command above; never promote stale needsRebase into a current recommendation |
| Failed check / merge conflict | `ok` domain state | Alert responsible owner with PR/head/cause; do not classify a real CI failure as a broken query |
| Query process crash/timeout/invalid JSON | `error` | Invocation boundary supplies query/cwd/arguments/exit/stderr/timeout and repair action; keep previous state and healthy query results |

Retries, watchdog tolerance and escalation deadlines are explicit deployment
policy. Exhausted retry or a repair needing agent action creates one deduplicated
O4 incident. Fallback success does not advance the failed primary's checkpoint
or claim it is repaired. Verify its retry before resolving the defect.

## Fallback commands (conditional, not an extra full scan)

For missing GraphQL stack membership capability — gh_pr_stack.py:

```sh
gh api --method GET "repos/$repo_slug/stacks?pull_request=$pr_number"
gh api --method GET "repos/$repo_slug/stacks/$stack_number"
```

Choose the lookup by the identity already known; do not issue both unnecessarily.
For one PR's current state — gh_prs.py:

```sh
gh pr view "$pr_number" --repo "$repo_slug" \
  --json number,headRefName,headRefOid,baseRefName,baseRefOid,state,isDraft,mergeable,mergeStateStatus,statusCheckRollup,url
```

For reported required checks — gh_requirements.py:

```sh
gh pr checks "$pr_number" --repo "$repo_slug" --required \
  --json name,state,bucket,startedAt,completedAt,event,workflow,link
```

Exit 8 means pending. Inspect valid domain output before treating other nonzero
exits as transport failures. This does not prove which absent checks should
have run. Applicable branch/workflow policy and trigger/head evidence must be
configured or supplied by a verified adapter. **The exact policy adapter remains
unresolved; never-started assertions are unknown until it is available.**

## ATM, plan and agent commands

### git_sprints.py — configured plan at a pinned revision

```sh
git -C "$repo_path" ls-tree -r --name-only "$plan_revision" -- "$plan_directory"
git -C "$repo_path" show "$plan_revision:$plan_file"
```

Read only selected plan files, on initialization or revision change. Parse sprint
IDs/order/branches; missing mandatory plan metadata is an explicit coverage issue.

### atm_tasks.py — current ownership/start state

```sh
atm task list --team "$team" --as "$actor" --all --json
```

The installed ATM CLI rejects combining `--all` and `--limit`; the `--all`
surface is the bounded current open-task queue and must be accepted only after
validating its response size against the configured adapter budget. Current queue
only; reaching the bound requires continuation by supported scope or an incomplete
result. This is not a historical task inventory. A task leaving
the queue does not prove completion. Do not fan out into all task histories.

### atm_workflow.py — bounded declared workflow changes

```sh
atm search --team "$team" --workflow-scope-kind sprint \
  --workflow-scope-id "$sprint" --workflow-stage "$stage" \
  --since "$since" --until "$until" --limit 100 --json
```

For a configured team's sprint changes in one request, omit scope-id and stage;
retain scope-kind and the time window, then join explicit sprint identities.
Continue only within the same selector/window:

```sh
atm search --team "$team" --workflow-scope-kind sprint \
  --workflow-scope-id "$sprint" --workflow-stage "$stage" \
  --since "$since" --until "$until" --limit 100 --cursor "$cursor" --json
```

No guessing template SHA/type. Untagged events remain a known coverage limitation.

### atm_report.py — one relevant report without marking it read

```sh
atm peek --team "$team" --as "$mailbox_agent" --message-id "$message_id" --json
```

Use the mailbox identity from the search hit under configured read authority.
Extract the reviewed revision, round, verdict and findings; malformed embedded
JSON returns a parse problem for targeted agent interpretation, not fabricated counts.

### herdr_agents.py — live agent observation

```sh
herdr agent list
```

The installed command has no advertised team/JSON selector. Reuse its single
machine snapshot across applicable repos, join explicit identities and validate
the response format before accepting an adapter. Never add an assumed `--json`.

### atm_members.py — fallback roster observation

```sh
atm members --team "$team" --json
```

Retain provider observation time. ATM data derived from Herdr is not independent
corroboration and does not become fresh simply because this request succeeded.

### gh_qa.py — targeted PR report fallback

```sh
gh pr view "$pr_number" --repo "$repo_slug" \
  --json number,headRefOid,body,comments,latestReviews
```

Invoke only for identified missing QA evidence, not every tick. Accept only an
explicit revision-addressed report. Verify nested-comment coverage in adapter
fixtures; do not claim complete historical QA from an unverified nested limit.

### scheduler_runs.py — recent execution receipts

```sh
hermes --profile "$profile" cron runs "$job_id" --limit 20
```

Help-verified, but the installed command advertises no JSON switch. A stable
machine-readable receipt binding remains to be verified before implementing
this adapter; human-formatted output must not silently become authoritative
structured state. Do not invent `--json` or substitute cron registration for runs.

## Live evidence and limits

The sequence was exercised against randlee/atm-core on September 12 local time
(September 13 UTC). A returned 22 PRs after the chosen cutoff and stack #1457;
B returned its nine members and check details. Both reported GraphQL cost 1,
with no top-level errors or additional pages. C succeeded in an identified
member worktree. This reduces requests and permits small normalized answers;
GraphQL cost is API cost, not an LLM-token measurement.

D found every local member head matched the remote observation, but the local
trunk for PR #1452 did not. gh-stack said needsRebase; exact current base/head
ancestry returned 0. Therefore the current-SHA answer supersedes that stale local
maintenance observation. This is a tested recovery case, not assumed equivalence.
Running stack view on the develop checkout returned exit 2 and explicit no-stack
context stderr; it did not erase the already identified remote stack.

An introspection request exceeding GitHub's field-use limit failed with
INTROSPECTION_LIMIT_EXCEEDED. Splitting the bounded schema checks succeeded.
This is a query-shape repair, not a reason to repeatedly retry the same request.

Stack lookup and local-view semantics were checked against
[gh-stack v0.1.0 client source](https://github.com/github/gh-stack/blob/v0.1.0/internal/github/github.go)
and [view source](https://github.com/github/gh-stack/blob/v0.1.0/cmd/view.go).
GraphQL fields and the two operations above were verified against the live API.
No adapter code was written and no rebase/branch modification was performed.

There are 13 named contracts including conditional REST membership fallback.
Required-check policy and scheduler machine-readable receipts remain unresolved.
Nested-pagination, rate-limit, permission-failure and multi-stack fixtures still
need execution before claiming full production compatibility; the contract above
specifies their required behavior without claiming they were all observed live.
