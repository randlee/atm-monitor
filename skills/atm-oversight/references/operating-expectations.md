# Operating expectations and required response

Rand has authorized continuous activity monitoring. Do not substitute a series
of user-initiated manual tests or repeatedly request schedule approval. A short
manual diagnostic may isolate a fault; only actual scheduled receipts prove
scheduled operation. Earlier Stage 1 capture-only instructions are historical.

| Expectation | Evidence to check | Required response to a gap |
|---|---|---|
| Activity cron runs continuously | Actual scheduler run/exit records and durable observation times | Inspect scheduler errors and execution environment; escalate to amon@atm-monitor with job, times, error, and next action |
| Qualified new planning/development wakes oversight once | Structured trigger evidence plus pending/handled handoff identity | Escalate missing qualification/wake or duplicate triggers; registration and raw collection alone do not meet this contract |
| Repo cron runs while any phase is open | Owned scheduler job, phase membership, latest scheduled successful run | Reuse/enable authorized monitoring; investigate failures and escalate rather than asking Rand for another manual test |
| Complete available task history | Running doctor/API and actual CLI selectors; complete result coverage | Investigate partial/failing sources and escalate; recheck current --help/source before calling a limit expected |
| Routine assignments/activity and sprint B/C/I are recorded | Evidence-backed current phase state and all planned sprint rows | Preserve unknown coverage and escalate missing recording/report integration |
| Agents wake only on notable events | Stable event/incident keys and prior handled state | Escalate excessive or unjustified wakes to maintainer; do not disable monitoring to hide them |
| Notable findings reach the proper owner | Actual message receipts, distinct from proposed routes | Follow the maintained route and escalate failed/unavailable delivery; “routed but not delivered” is not successful intervention |
| Immediate whole-phase report | Latest recorded evidence, every sprint, as-of/coverage | Return what is known immediately and identify missing fields; do not omit unseen/planned sprints |

A partial source is a defect/coverage gap to investigate, not an acceptable
steady state merely because it was already documented. On ATM 1.5.16/API 1.7,
`atm task events ID --all --team TEAM --as ACTOR --json` retrieves all events.
The default is the latest 200, not necessarily the first 200. A result at a
bound proves possible truncation; it does not by itself prove additional rows.
The collector uses --all on verified API 1.7+ and retains earlier compatibility.

Empty success logs do not prove scripts failed to run. Check snapshot times,
job receipts/exit codes, stderr and scheduler failure records. A permission
failure before script entry cannot appear in an application log opened later.
Moving a launcher alone does not prove its protected inputs or repositories
are accessible. Do not claim a different scheduler bypasses OS permissions.

For each detected monitoring gap, investigate enough to provide a concrete
incident: expected/observed behavior, source/job identity, time, bundle/API
version, failure evidence, impact, owner and next action. Escalate to
`amon@atm-monitor` without waiting for Rand to ask. Deduplicate repeated reports,
preserve unresolved state, and follow up on new evidence or an agreed deadline.
The maintainer owns master fixes and verified distribution. Project decisions
(e.g. an unmerged integration PR's disposition) follow their Rand escalation.

Do not claim the required autonomous loop exists just because this table does.
The current detector is still a candidate observer; qualification, durable
ownership/wake handoff and phase lifecycle projection remain implementation
gaps. Keep those as explicit maintainer-owned incidents until verified live.
