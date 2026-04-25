---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
plan: 01
status: ready-for-spectrum-a-leg
created: 2026-04-24
requirements: [VALN-04, VALN-05, SAFE-05]
---

# Phase 196 Preflight Gates

phase_192_soak_status: pass

phase_191_att_closure_status: blocked

mode_gate_status: pass

mode_gate_evidence:

- Contract: `196-MODE-GATE.md` documents the reversible `cake_signal.enabled` gate and forbids protected controller, transport, router API, tuning, threshold, EWMA, dwell, deadband, burst-detection, and state-machine changes.
- Proof artifact: `soak/preflight/mode-gate-proof.json`
- Proof verdict: `pass`
- rtt-blend observation: `cake_signal_enabled=false`, `active_primary_signal=rtt`, `wanctl_arbitration_active_primary=2`, capture summary `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/preflight/preflight-20260425T044040Z-summary.json`
- cake-primary observation: `cake_signal_enabled=true`, `active_primary_signal=queue`, `wanctl_arbitration_active_primary=1`, capture summary `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/preflight/preflight-20260425T044045Z-summary.json`
- Restored mode: `cake-primary`
- Operator confirmations: restart window acceptable and no concurrent Spectrum experiment running.

safe_05_status: pass

decision: ready-for-spectrum-a-leg

## Evidence

Phase 192 dependency status is `pass` for Phase 196 preflight purposes because `192-VERIFICATION.md` records the Phase 192 deployment and its pre/post live 24-hour capture window as passed for the required D-08/OPER-02 categories. The Phase 192 artifact also states that no additional soak wait is required by that verification artifact.

Phase 191 ATT closure remains `blocked`. `STATE.md` records repeated ATT restored-config rerun failures against the old RRUL download comparator, and `192-PRECONDITION-WAIVER.md` explicitly says the waiver does not close Phase 191. Therefore the ATT canary remains blocked while Phase 191 is blocked, but this does not block the Spectrum A-leg preflight decision.

The Spectrum mode gate is `pass` because `mode-gate-proof.json` records the documented gate name, an operator-approved restart window, no concurrent Spectrum experiment, `rtt-blend` as RTT primary with metric encoding `2`, `cake-primary` as queue primary with metric encoding `1`, and `restored_mode: cake-primary`.

SAFE-05 is `pass` for this plan because the protected controller/control files have no Phase 196 diff:

- `src/wanctl/queue_controller.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/fusion_healer.py`
- `src/wanctl/wan_controller.py`

The go/no-go rule is strict: `decision: ready-for-spectrum-a-leg` is allowed only when `phase_192_soak_status: pass`, `mode_gate_status: pass`, and `safe_05_status: pass` are all present. Those Spectrum prerequisites are now present, so later Spectrum A-leg soak plans may start after their own operator gates. ATT canary plans must still wait for Phase 191 closure.

## Verification Output

```text
$ grep -E "phase_192_soak_status:|phase_191_att_closure_status:|mode_gate_status:|safe_05_status:|decision:" .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md
phase_192_soak_status: pass
phase_191_att_closure_status: blocked
mode_gate_status: pass
safe_05_status: pass
decision: ready-for-spectrum-a-leg

$ grep -n "mode_gate_status:" .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md
15:mode_gate_status: pass

$ grep -n "decision:" .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md
29:decision: ready-for-spectrum-a-leg

$ git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py
exit 0
```
