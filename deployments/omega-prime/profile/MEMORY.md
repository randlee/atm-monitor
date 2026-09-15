The authoritative oversight instructions are in atm-oversight/SKILL.md.
Only four outcomes are in scope: phase/sprint table; assigned-but-idle alerts;
CI/merge-readiness alerts; self-healing. Use actual evidence and saved state.
Continuous monitoring is authorized. Recover failures and keep unrelated checks
running. Make fixes to masters in atm-monitor, verify and redistribute; preserve
deployment-local state and unrelated profile memory.
