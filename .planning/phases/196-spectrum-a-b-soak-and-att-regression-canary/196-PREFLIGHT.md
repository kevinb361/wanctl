---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
plan: 01
status: blocked
created: 2026-04-24
requirements: [VALN-04, VALN-05, SAFE-05]
---

# Phase 196 Preflight Gates

phase_192_soak_status: pass

phase_191_att_closure_status: blocked

mode_gate_status: blocked

mode_gate_evidence:

- Search command:
  `rg -n "rtt-blend|cake-primary|queue_primary|queue-primary|arbitration.*mode|primary_signal|feature_gate|active_primary" configs src deploy scripts .planning/phases/193-* .planning/phases/194-* .planning/phases/195-*`
- Found: controller-owned `active_primary_signal` and `wanctl_arbitration_active_primary` observability/metrics surfaces, plus queue-primary selector tests and planning references.
- Not found: any documented YAML key, CLI option, environment variable, systemd override, or script mode that can reversibly force Spectrum to run as `rtt-blend` for the A leg and `cake-primary` for the B leg.
- Rejected as a gate: changing backend transport or disabling CAKE signal support by editing production config. That would be a transport/config mutation, not a documented Phase 196 mode gate.

safe_05_status: pass

decision: blocked-do-not-start-soak

## Evidence

Phase 192 dependency status is `pass` for Phase 196 preflight purposes because `192-VERIFICATION.md` records the Phase 192 deployment and its pre/post live 24-hour capture window as passed for the required D-08/OPER-02 categories. The Phase 192 artifact also states that no additional soak wait is required by that verification artifact.

Phase 191 ATT closure remains `blocked`. `STATE.md` records repeated ATT restored-config rerun failures against the old RRUL download comparator, and `192-PRECONDITION-WAIVER.md` explicitly says the waiver does not close Phase 191. Therefore the ATT canary remains blocked while Phase 191 is blocked.

SAFE-05 is `pass` for this plan because the protected controller/control files have no Phase 196 diff:

- `src/wanctl/queue_controller.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/fusion_healer.py`
- `src/wanctl/wan_controller.py`

The go/no-go rule is strict: `decision: ready-for-spectrum-a-leg` is allowed only when `phase_192_soak_status: pass`, `mode_gate_status: pass`, and `safe_05_status: pass` are all present. Because `mode_gate_status: blocked`, later soak plans must not start.

## Verification Output

```text
$ grep -E "phase_192_soak_status:|phase_191_att_closure_status:|mode_gate_status:|safe_05_status:|decision:" .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md
phase_192_soak_status: pass
phase_191_att_closure_status: blocked
mode_gate_status: blocked
safe_05_status: pass
decision: blocked-do-not-start-soak

$ grep -n "mode_gate_status:" .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md
15:mode_gate_status: blocked

$ grep -n "decision:" .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md
27:decision: blocked-do-not-start-soak

$ git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py
exit 0
```
