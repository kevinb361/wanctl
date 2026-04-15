---
phase: 186-measurement-degradation-contract
plan: 03
subsystem: tests
tags: [measurement, health, contract, validation]
requires: [186-01, 186-02]
provides:
  - "Locked unit-level contract coverage for wan_health.measurement"
  - "Collected pytest IDs for all six legal state/stale combinations"
affects: [tests/test_health_check.py]
tech-stack:
  added: []
  patterns: [direct section-builder contract tests, explicit pytest param IDs]
key-files:
  created:
    - .planning/phases/186-measurement-degradation-contract/186-03-SUMMARY.md
  modified:
    - tests/test_health_check.py
key-decisions:
  - "Kept coverage at the unit level by calling _build_measurement_section directly."
  - "Used explicit pytest IDs so the six legal cross-product combinations are grep-verifiable."
patterns-established:
  - "Phase contract tests can pin legal state/stale combinations without adding duplicate HTTP round-trip coverage."
requirements-completed: []
duration: 20 min
completed: 2026-04-15
---

# Phase 186 Plan 03: Measurement Contract Test Summary

**Added focused unit-level regression coverage for the new measurement health contract**

## Outcome

- Added `TestMeasurementContract` to `tests/test_health_check.py`.
- Covered all six legal `state x stale` combinations with a single parametrized test using explicit pytest IDs.
- Added boundary coverage for `successful_count` across `0..3`, the exact stale threshold boundary, D-14 fallback behavior, D-16 malformed-input handling, and preservation of the original five measurement fields.

## Verification

- `.venv/bin/pytest tests/test_health_check.py --collect-only -q | rg 'test_contract_combination_'` returns exactly 6 collected IDs
- `.venv/bin/pytest tests/test_health_check.py -q` -> `149 passed`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` -> `438 passed`

## Covered Decisions

- D-01 / D-02 / D-03: `healthy`, `reduced`, `collapsed` state mapping and six legal cross-product combinations
- D-05 / D-14: stale threshold and default-to-stale fallback
- D-10 / D-11 / D-12: backwards-compatible preservation of existing measurement fields
- D-16: safe coercion of `successful_reflector_hosts=None` and missing `measurement`

## Deviations from Plan

None - plan executed exactly as written after the test-class placement fix captured in `186-02-SUMMARY.md`.

## Self-Check: PASSED

- Found `TestMeasurementContract` in `tests/test_health_check.py`
- Verified all six explicit combination IDs are collected
- Verified standalone and hot-path regression suites pass

---
*Phase: 186-measurement-degradation-contract*
*Completed: 2026-04-15*
