# Monitoring workflow

Working brief from Rand's requirements discussion, September 9, 2026.
This captures intended behavior; polling intervals, intervention thresholds,
model selection, and installation details are not yet specified.

## Intended operation

1. Cron polls Herdr regularly on the local computer and detects agent activity.
2. Monitoring associates discovered agents with ATM team membership and work.
   Tagged `dev-task`, `fix-task`, `qa-task`, and `qa-report` messages provide
   focused queries for assignments and reports. Worktree paths are present in
   task assignments and the project plan, linking activity to sprint work.
3. Work is organized into phases containing multiple sprints. Each sprint has
   a separate worktree and branch. When activity establishes that a phase has
   started, monitoring tracks its sprints, CI, and stacked PR maintenance.
4. Small, reliable scripts do the collection and routine checks. Cron owns
   ongoing execution. An inexpensive model, preferably local, performs a
   small amount of reasoning and escalates issues through ATM or Telegram.
5. Rand can ask the oversight agent for a report through Telegram. The report
   uses the existing omega-prime sprint table described below.
6. Monitoring retains current state and a history of work so reports can answer
   both what is running now and what work was done. Start with JSON in a
   temporary folder for a couple of teams, move to SQLite for 5–10 teams on
   one computer, and later use a server database for multiple computers.
   The eventual target is about 30 teams; multiple-computer implementation
   is deferred. See [improvement-plan.md](improvement-plan.md) for the layers,
   test requirements, and rollout sequence.

## Scheduled checks and on-demand investigation

Notification routing is defined in [notification-policy.md](notification-policy.md).
CI failure/conflict goes to team-lead; confirmed stack-rule/order violations
go to the team and Rand on Telegram; serious problems escalate to Rand.
Healthy operation is recorded locally and reported to Rand only on request.

Cron's routine inputs are the ATM task event log, ATM team roster status,
Herdr agent status, and git log. CI and `gh stack view --json` remain scheduled
checks as established earlier. Targeted tag queries for `dev-task`, `fix-task`,
`qa-task`, and `qa-report` are also routine structured lookups: scripts can
retrieve those records and extract worktree and other declared fields for
discovery and reporting. This does not require LLM interpretation of the
surrounding conversation.

Message-history mining scripts are primarily tools for the oversight LLM.
The LLM calls them when a finding or operator request needs explanation,
retrieves relevant exchanges, and reasons about an appropriate intervention.
For example, a sprint that has reached eight rounds of QA needs investigation
of the conversation: which findings recur, what fixes were attempted, what
reviewers rejected, and what decisions or misunderstandings are preventing
closure. The round count alone does not explain the cause or prescribe a fix.

Mining tools should retrieve evidence by team, agent, task, sprint, and time
window where supported. Results should preserve message IDs, timestamps,
sender/recipient, and conversation order, with bounded pages and an explicit
indication that more history exists. The LLM can expand the investigation
without every cron tick paying the cost of retrieving that history.

Scheduled findings should carry identifiers and relevant event/commit times
so the LLM can start a focused investigation. If structured sources cannot
resolve an agent's work, report the missing association for investigation;
do not silently turn the scheduled check into unrestricted message mining.

## Report contract from the existing skill

Source:
`/Users/randlee/Documents/github/hendrix/omega-prime/skills/phase-oversight/sprint-report/SKILL.md`.

The report has five columns: `Sprint | DEV | QA | CI | FND`.
Sprint identifiers link to PRs when available. FND presents
blocking:important:minor counts. The skill defines status markers for queued,
in-progress, completed, blocked, failing CI, and merge readiness.

Preserve that compact presentation for the requested report. Stack diagnostics
and actionable findings can accompany the table without changing its columns.
Report requests use the same collected state as scheduled monitoring and may
retrieve additional evidence on demand, including QA reports and findings.
The table renderer is deterministic; additional evidence retains its source
and timestamp, and the model should not invent table status.

## Design implications to carry into implementation

- Discovery starts from observed activity. Merely finding an old phase plan
  or an idle agent is not evidence that a new phase started.
- Once discovered, a phase remains tracked through quiet periods, agent exits,
  monitoring restarts, and handoffs. Retirement needs phase completion or
  another recorded disposition, not lack of live agent activity.
- Agent process status, task state, sprint development completion, QA verdict,
  CI result, and phase completion are different facts. Preserve their sources
  and timestamps instead of collapsing them into one inferred status.
- Resolve identity using machine/session/workspace context, team membership,
  and repository evidence. A bare agent name or pane ID is not a global key.
  Retain unresolved or ambiguous associations for investigation.
- Use worktree paths from task assignments and the project plan to associate
  work with its phase, sprint, branch, and PR. Preserve the source record for
  each association. Herdr's process directory can supply discovery context
  even when it is the repository root rather than the assigned worktree.
- Current state supports fast reports; timestamped observations and transitions
  support history. Include machine identity from the start so future records
  from another computer do not collide. Storage technology can remain a
  separate decision from the scripts' output contract.
- Record observation time separately from source event time. The first time
  monitoring sees a running phase is not necessarily when that phase started.
- Reports expose when data was last collected and any unavailable sources.
  A model failure must not erase state or turn failed collection into all-clear.
- Retain prior interventions and their outcomes across cron invocations.
  Acknowledgment and resolution are separate; consult ATM's existing reminder
  and lead-notification events when deciding whether to intervene again.
- Every cron invocation is bounded. Follow-up deadlines are evaluated on later
  invocations rather than by sleeping inside a monitoring process.

## Discovery evidence

Read-only `herdr agent list` returned a JSON envelope with agents under
`result.agents`. At inspection it contained nine agents, seven associated with
atm-core paths. Fields included `name`, `agent`, `agent_status`, `cwd`,
`foreground_cwd`, `workspace_id`, `pane_id`, `terminal_id`, `revision`, and
`state_change_seq`. Sample statuses were `working`, `idle`, and `done`.
These Herdr values need to be preserved as process observations; `done` does
not establish completion of an ATM task or sprint.

The inspected phase AZ plan enumerates sprint IDs, branches, authoritative
sprint documents, and dependencies. Sprint frontmatter includes phase/sprint,
branch, integration branch, and status. The develop copy still describes
sprints as planned despite live work/PR evidence observed during the survey.
Plan discovery therefore provides structure; current status needs live evidence
and awareness of which branch/version supplied each document.

See [query-survey.md](query-survey.md) for verified ATM and stack commands,
observed tracking gaps, and differences between installed and planned APIs.
