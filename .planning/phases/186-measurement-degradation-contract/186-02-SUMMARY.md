---
phase: 186-measurement-degradation-contract
plan: 02
subsystem: health
tags: [measurement, health, implementation, contract]
requires: [186-01]
provides:
  - "Machine-readable measurement contract fields on wan_health[wan].measurement"
  - "Controller-provided cadence_sec threaded through the measurement health payload"
affects: [src/wanctl/wan_controller.py, src/wanctl/health_check.py, wan_health.measurement]
tech-stack:
  added: []
  patterns: [additive health payload contract, cadence-derived staleness]
key-files:
  created:
    - .planning/phases/186-measurement-degradation-contract/186-02-SUMMARY.md
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/health_check.py
key-decisions:
  - "Kept cadence sourcing in wan_controller via self._cycle_interval_ms / 1000.0 instead of widening BackgroundRTTThread."
  - "Augmented only _build_measurement_section; _build_reflector_section remained unchanged."
patterns-established:
  - "Measurement health now exposes state, successful_count, and stale without redefining existing fields."
requirements-completed: []
duration: 35 min
completed: 2026-04-15
---

# Phase 186 Plan 02: Measurement Contract Implementation Summary

**Implemented the additive `/health` measurement contract while preserving existing field semantics and controller behavior**

## Outcome

- Added `cadence_sec` to `health_data["measurement"]` in `wan_controller.py`, sourced from the existing controller cadence expression and guarded so non-positive cadence reports as `None`.
- Expanded `_build_measurement_section()` in `health_check.py` to return the existing five fields unchanged plus `state`, `successful_count`, and `stale`.
- Preserved the scope boundary from the plan: no changes to `src/wanctl/rtt_measurement.py`, no new YAML tunables, and no edits to `_build_reflector_section()`.

## Verification

- `.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/health_check.py` -> `Success: no issues found in 2 source files`
- `.venv/bin/pytest tests/test_wan_controller.py -q` -> `102 passed`
- `.venv/bin/pytest tests/test_health_check.py -q` -> `149 passed`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` -> `438 passed`

## Contract Surface

- `successful_count == 3` -> `state="healthy"`
- `successful_count == 2` -> `state="reduced"`
- `successful_count <= 1` -> `state="collapsed"`
- `stale = True` when `staleness_sec` is missing, cadence is missing, or cadence is non-positive
- Otherwise `stale = staleness_sec > 3 * cadence_sec`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repositioned the new contract test class after the IRTT test class**
- **Found during:** cross-suite pytest execution after implementing the contract
- **Issue:** The first insertion point for `TestMeasurementContract` split the existing `TestIRTTHealth` class, causing downstream IRTT tests to be collected under the wrong class and fail fixture lookup.
- **Fix:** Moved `TestMeasurementContract` to the end of `tests/test_health_check.py` so the pre-existing class structure stays intact.
- **Files modified:** `tests/test_health_check.py`
- **Verification:** `tests/test_health_check.py -q` and the hot-path regression slice both pass.

## Issues Encountered

- `.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/health_check.py tests/test_health_check.py` remains non-zero because `src/wanctl/wan_controller.py` already contains pre-existing `B009/B010` findings in an unrelated parameter-update helper near lines `118-150`.
- I did not widen Phase 186 to rewrite that helper because the plan and repo instructions both require conservative, targeted changes.

## Self-Check: PASSED

- Found `src/wanctl/wan_controller.py` `cadence_sec` threading at the measurement build site
- Found `src/wanctl/health_check.py` additive `state`, `successful_count`, and `stale` fields
- Verified the targeted runtime and regression tests pass

---
*Phase: 186-measurement-degradation-contract*
*Completed: 2026-04-15*
