---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
plan: 04
created: 2026-04-24
gate: att-canary
---

# ATT Canary Gate

phase_191_status: blocked
decision: blocked-do-not-run-att-canary

## Decision

ATT canary blocked by Phase 191.

Phase 191 closure remains blocked, so Phase 196 must not switch ATT mode, run
ATT flent, or record an ATT cake-primary throughput verdict. The ATT canary can
only move to `decision: run-att-canary` after Phase 191 closure is recorded in
the Phase 191/191.1 evidence and `STATE.md` no longer carries the Phase 191
closure blocker.

## Evidence Used

| Evidence | Result |
| --- | --- |
| `.planning/STATE.md` | Contains `Phase 191 closure remains blocked` with restored-config rerun FAIL history through `2026-04-24`. |
| `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md` | Records `phase_191_att_closure_status: blocked`. |
| `.planning/phases/191-netlink-apply-timing-stabilization/191-VERIFICATION.md` | Records `VALN-02 verdict: FAIL` and states Phase 191 remains open. |
| `.planning/phases/191.1-att-config-drift-resolution-and-phase-191-closure/191.1-rerun-results.json` | Latest restored-config rerun has ATT RRUL `70.95 Mbps`, below the old `74.38 Mbps` lower bound. |
| `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-PRECONDITION-WAIVER.md` | Waiver lets Phase 192 proceed only; it does not close Phase 191. |

## Actions Explicitly Not Taken

- No ATT `cake-primary` mode switch.
- No `scripts/phase196-soak-capture.sh att-canary` capture.
- No `scripts/phase191-flent-capture.sh --wan att` load run.
- No `att-canary-summary.json` or `att-mode-proof.json`, because the gate did
  not authorize the canary.

## Verification Output

```text
$ grep -E "phase_191_status:|decision:" .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-canary-gate.md
phase_191_status: blocked
decision: blocked-do-not-run-att-canary
```
