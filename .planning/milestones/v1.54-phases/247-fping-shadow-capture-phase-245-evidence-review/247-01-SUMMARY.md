---
phase: "247"
plan: "01"
status: complete
completed_at: "2026-06-19T11:00:00Z"
requirements:
  - PROF-02
key_files:
  created:
    - .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/247-METHODOLOGY-REVIEW.md
  modified: []
verification:
  - grep -c "calibration mismatch" .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/247-METHODOLOGY-REVIEW.md
  - grep -c "CYCLE_P99_ABS_CEILING_MS" .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/247-METHODOLOGY-REVIEW.md
  - grep -c "120.7" .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/247-METHODOLOGY-REVIEW.md
  - grep -ci "SOLE FAILING GATE" .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/247-METHODOLOGY-REVIEW.md
  - grep -ci "observed production-load window" .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/247-METHODOLOGY-REVIEW.md
---

# Plan 247-01 Summary — Methodology Review

## What changed

Created `247-METHODOLOGY-REVIEW.md`, the Phase 245 AB-03 root-cause analysis document for PROF-02.

The document records all eight gate rows required by the plan:

1. `rtt_agreement`
2. `cycle_budget_nonregression` avg
3. `cycle_budget_nonregression` p99 relative
4. `cycle_budget_nonregression` p99 absolute
5. `loss_detection_nonregression`
6. `min_backend_cycle_fraction`
7. `unexpected_restarts`
8. `steering_decision_stability`

## Findings

The document names the root cause as calibration mismatch, not fping inferiority. It records that the sole failing gate was the absolute daemon-cycle p99 ceiling (`CYCLE_P99_ABS_CEILING_MS=10.0ms`), derived from idle/low-load icmplib calibration.

It also records the critical comparative fact: icmplib p99 was 120.7ms while fping p99 was 112.4ms in the observed Phase 245 production-load window. The relative p99 gate therefore passed; fping was not worse than icmplib in that run.

The claim is intentionally scoped to the observed production-load window and does not overclaim a universal run-length conclusion.

## Verification

Executed grep-based checks:

- `calibration mismatch`: 2 matches
- `CYCLE_P99_ABS_CEILING_MS`: 3 matches
- `120.7`: 3 matches
- `SOLE FAILING GATE`: 2 case-insensitive matches
- `observed production-load window`: 2 case-insensitive matches

## Self-check: PASSED
