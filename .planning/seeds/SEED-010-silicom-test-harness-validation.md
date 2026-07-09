---
id: SEED-010
status: resolved
planted: 2026-07-06
planted_during: v1.60 closeout — silicom test harness complete
trigger_when: silicom bypass tooling needs validation OR before relying on it in production
scope: Small
priority: 3
prerequisites: []
---

# SEED-010: Silicom test harness validation

## Why This Matters

7 test scenarios + orchestrator deployed (SEED-006 Phase B), but never executed in production. The harness is operator-invoked only (safe), but untested means unproven.

## Scope

- Run each scenario in a controlled window
- Verify bypass/restore behavior matches expectations
- Document results in TRACEABILITY.md or a test report
