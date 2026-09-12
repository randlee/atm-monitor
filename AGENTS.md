# Working in atm-monitor

Every change must directly support one of four outcomes: O1 phase/sprint table,
O2 assigned-but-idle alerts, O3 CI/merge-readiness alerts, O4 self-healing.
Read `skills/atm-oversight/references/requirements.md` and the operating
`skills/atm-oversight/SKILL.md`. README.md maps retained files to these outcomes.

State is immutable data only. Independent Python queries are named
`<target>_<query>.py`, under 100 source lines excluding blanks/comments, and
return discriminated unions of state data or actionable errors. Do not add
implementation while the associated state/query contract is still being planned.
Cron composes query results, persists state and decides from state changes.

Masters live in skills/. Test before distributing verified bundles. Keep local
ATM config, credentials, state and archives out of commits. Do not alter the ATM
database, maintained repositories or system permissions to repair monitoring.
Run the applicable suites in .github/workflows/tests.yml. Never bypass hooks.
