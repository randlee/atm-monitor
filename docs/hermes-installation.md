# Hermes adapter for the monitoring pilot

Start with the harness-independent [installation and usage guide](installation.md).
That guide defines the two scheduled scripts, state paths, return codes, and
oversight responsibilities. This page only covers Hermes integration.

## Skill discovery

Merge this into the selected profile's existing `config.yaml`, preserving
other settings and entries:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/atm-monitor/skills
```

The standard named-profile config lives at
`~/.hermes/profiles/<name>/config.yaml`; use the actual profile home if relocated.
For Hendrix-managed profiles, update the managed configuration source and use
that profile's existing deployment process. Skills remain canonical in
atm-monitor. Do not copy only `SKILL.md`: the procedures need `scripts/` and
`docs/` in the full checkout.

External directories expose skills to Hermes and as slash commands; local
same-named skills take precedence. Check for stale copies. See the official
[skills documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills#external-skill-directories)
and [profile documentation](https://hermes-agent.nousresearch.com/docs/user-guide/profiles/).

Start a fresh session and verify that all three `atm-*` skills load from this
checkout. Use terminal/file tools to read `checkout/docs/` references outside
an individual skill directory; the skill-file reader is scoped to that directory.
The profile's terminal must reach the repos and local ATM/Herdr services.

## First agent test

Save the pilot instructions from the main guide in a local text file, replacing
the path placeholders. Then run:

```sh
hermes --profile <name> chat --skills atm-oversight --query-file /absolute/path/to/pilot-prompt.txt --oneshot
```

Use `/atm-oversight report status for atm-dev` for subsequent report requests,
or `/atm-investigate explain repeated QA rounds for <sprint>`. Supply the same
installation paths. An existing Telegram-connected profile can receive these
requests; test the actual request/reply separately from scheduled alerts.

## Hermes scheduling

The installed CLI was inspected on September 10, 2026:

- `--script ... --no-agent`: run a script with no LLM; empty stdout is silent.
- `--deliver local`: keep output local during the pilot.
- `--deliver bot-chat:<profile>`: deliver output to a local bot conversation
  that responds. Enabling this wakes an agent and needs the pilot instructions.
- `--monitor-script`: invokes an agent on an exact-byte output change. Do not
  feed it full snapshot JSON: timestamps and paths change on every tick.

Check `hermes cron create --help` on the deployment's runtime. The pasted
`notify: on_failure` / `delivery: ...` example is conceptual, not the verified
configuration syntax for this installation.

The official [script-only guide](https://hermes-agent.nousresearch.com/docs/guides/cron-script-only)
documents stdout/exit behavior. The
[cron reference](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)
also describes the `{"wakeAgent": false}` last-line JSON gate for agent jobs:
empty output alone does not suppress a normal agent-mode script job. Use the
no-agent capture setup below for the first pilot. If later using a pre-check
to wake the oversight model directly, explicitly emit that gate on exits 0/3,
and preserve the distinction between findings and script failures. Monitor-mode
hashing is documented in the upstream
[monitor source](https://github.com/NousResearch/hermes-agent/blob/main/cron/monitor.py).

Hermes scripts must reside under the selected profile's `scripts/` directory.
Place a small `.sh` launcher there that invokes the actual checkout by absolute
path; do not symlink outside that directory. The launcher must translate the
monitoring return codes for Hermes: codes 0 and 3 become silent success; code 1
becomes exit 0 with its JSON payload on stdout; code 2 remains a failure.
Without this translation Hermes treats a detected CI issue as a failed script.

For example, a phase-monitor launcher for a macOS/Linux host is:

```sh
#!/bin/sh
# Replace these installation paths. Do not add `set -e` before capturing status.
/absolute/path/to/python3 /absolute/path/to/atm-monitor/scripts/cron/monitor_phase.py \
  --config /absolute/path/to/monitor.json \
  --activity-dir /absolute/path/to/state/activity \
  --state-dir /absolute/path/to/state/phases
monitor_status=$?
case "$monitor_status" in
  0|1|3) exit 0 ;;
  *) exit "$monitor_status" ;;
esac
```

Create an analogous launcher for `detect_activity.py` using the activity
directory as its `--state-dir`. Omit `--json` in scheduled launchers so healthy
runs remain silent. For local capture, after placing the files:

```sh
hermes --profile <name> cron create '*/2 * * * *' --name atm-detect-activity --script atm-detect-activity.sh --no-agent --deliver local --failure-deliver local
hermes --profile <name> cron create '*/5 * * * *' --name atm-monitor-phase --script atm-monitor-phase.sh --no-agent --deliver local --failure-deliver local
```

`--failure-deliver local` suppresses failure delivery for this capture-only
pilot; inspect durable run failures with `hermes --profile <name> cron runs`.
Before unattended operation, connect a verified failure route as well as the
oversight route. An LLM must not run just because a healthy poll completed.
Do not simultaneously enable an ATM sender and Hermes delivery for the same
payload. Delivery integration still needs receipts, retry/deduplication, and
unresolved-incident follow-up; these launchers alone do not provide that worker.

## Verification

The installed Hermes runtime discovered and loaded all three skills with
`skills.external_dirs` in an isolated temporary Hermes home on September 10,
2026. CLI help confirmed the profile/chat/cron options described above. No live
profile, scheduler, gateway, or model session was changed by that smoke check.
The target profile's model, scheduler, and Telegram behavior remain pilot tests.
