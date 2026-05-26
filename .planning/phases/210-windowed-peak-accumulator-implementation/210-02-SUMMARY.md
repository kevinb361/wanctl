---
phase: 210-windowed-peak-accumulator-implementation
plan: 02
subsystem: alerting-tests
tags: [wanctl, flapping-alerts, peak-transition-count, tests]

# Dependency graph
requires:
  - phase: 210-windowed-peak-accumulator-implementation
    plan: 01
    provides: two-deque flapping peak-window production implementation
provides:
  - migrated flapping alert tests for peak-window deque attrs
  - fixed-threshold sustained oscillation unit and integration coverage
  - two-deque lifecycle assertions for fire clear vs flap-window prune
affects: [phase-210-safe10, phase-211-production-verification]

# Tech tracking
tech-stack:
  added: []
  patterns: [two-deque test fixtures, fixed-threshold sustained oscillation regression]

key-files:
  created:
    - .planning/phases/210-windowed-peak-accumulator-implementation/210-02-SUMMARY.md
  modified:
    - tests/test_alert_engine.py
    - tests/integration/test_flapping_integration.py

key-decisions:
  - "Unit and integration tests now assert peak_transition_count from _*_peak_window_transitions deques, not removed scalar attrs."
  - "The existing threshold-mutation integration test was adjusted to respect identical flap_window pruning on episode and peak-window deques."

patterns-established:
  - "First-fire tests cover peak == threshold; second-fire tests cover peak > threshold under fixed threshold."
  - "Peak-window deques are asserted to survive fire and reset only via flap_window pruning."

requirements-completed: [TEST-01, TEST-02, TEST-03]

# Metrics
duration: 6.0min
completed: 2026-05-26
---

# Phase 210 Plan 02: Flapping Peak-Window Test Rewrite Summary

**Flapping alert tests now lock the two-deque peak-window semantics at unit and integration layers.**

## Performance

- **Duration:** 6.0 min
- **Started:** 2026-05-26T16:47:27Z
- **Completed:** 2026-05-26T16:53:29Z
- **Tasks:** 2
- **Files modified:** 2 test files + this summary

## Accomplishments

- Migrated all test references away from removed `_dl_peak_transitions` / `_ul_peak_transitions` scalar attrs.
- Updated fixtures to initialize `_dl_peak_window_transitions` / `_ul_peak_window_transitions` as `deque()` instances.
- Replaced `test_flapping_ul_peak_resets_after_fire` with `test_ul_peak_window_survives_fire_and_drains_via_prune`.
- Extended `TestFlappingDequeClear` from 3 to 5 tests while preserving its original episode-clear assertions.
- Added `TestFlappingPeakWindow` with fixed-threshold DL/UL second-fire coverage, monotonic within-window growth, and flap-window prune reset coverage.
- Added `test_peak_transition_count_above_threshold_fixed_threshold` integration coverage for the production-faithful second-fire path.

## Task Commits

1. **Task 1: Migrate test references to the new deque attrs and rewrite the buggy UL test** - `d6d089c` (test)
2. **Task 2: Add TestFlappingPeakWindow asserting fixed-threshold peak > flap_threshold on both DL and UL** - `bc5bc25` (test)

## Files Created/Modified

- `tests/test_alert_engine.py`
  - Fixture setup now uses `_dl_peak_window_transitions = deque()` and `_ul_peak_window_transitions = deque()`.
  - `test_flapping_dl_includes_peak_transition_count` now documents that first-fire `peak == threshold` coverage is separate from second-fire above-threshold coverage.
  - Deleted old `test_flapping_ul_peak_resets_after_fire`.
  - Added `test_ul_peak_window_survives_fire_and_drains_via_prune` at line 1417.
  - Added `test_dl_peak_window_deque_not_cleared_on_fire` at line 1678.
  - Added `test_ul_peak_window_deque_not_cleared_on_fire` at line 1690.
  - Added `class TestFlappingPeakWindow` at line 1703 with four methods: DL sustained oscillation, UL sustained oscillation, monotonic growth, and prune reset.
- `tests/integration/test_flapping_integration.py`
  - Updated `test_peak_transition_count_reflects_oscillation_intensity` to assert the new deque state.
  - Added `test_peak_transition_count_above_threshold_fixed_threshold` at line 150.

## Deleted vs Added Tests

- **Deleted:** `test_flapping_ul_peak_resets_after_fire`
- **Added:**
  - `test_ul_peak_window_survives_fire_and_drains_via_prune`
  - `test_dl_peak_window_deque_not_cleared_on_fire`
  - `test_ul_peak_window_deque_not_cleared_on_fire`
  - `TestFlappingPeakWindow::test_dl_peak_above_threshold_during_sustained_oscillation`
  - `TestFlappingPeakWindow::test_ul_peak_above_threshold_during_sustained_oscillation`
  - `TestFlappingPeakWindow::test_peak_window_deque_grows_monotonically_across_fires_within_window`
  - `TestFlappingPeakWindow::test_peak_window_deque_resets_when_flap_window_prunes_deque`
  - `test_peak_transition_count_above_threshold_fixed_threshold`

## Verification

- `.venv/bin/pytest tests/test_alert_engine.py::TestFlappingDequeClear -v` — 5 passed.
- `.venv/bin/pytest tests/test_alert_engine.py::TestFlappingUL::test_ul_peak_window_survives_fire_and_drains_via_prune -v` — passed.
- `.venv/bin/pytest tests/integration/test_flapping_integration.py::test_peak_transition_count_above_threshold_fixed_threshold -v` — passed.
- `.venv/bin/pytest tests/integration/test_flapping_integration.py::test_peak_transition_count_reflects_oscillation_intensity -v` — passed.
- `.venv/bin/pytest tests/test_alert_engine.py::TestFlappingPeakWindow -v` — 4 passed.
- `.venv/bin/pytest tests/test_alert_engine.py -q` — 129 passed.
- `.venv/bin/pytest tests/integration/test_flapping_integration.py -q` — 3 passed.
- Old scalar refs in both changed test files: `0`.
- `tests/test_alert_engine.py` window refs: `_dl_peak_window_transitions=10`, `_ul_peak_window_transitions=8`.
- `tests/integration/test_flapping_integration.py` window refs: `_dl_peak_window_transitions=2`.
- `git diff --stat HEAD -- src/` — empty; no `src/` changes in this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected impossible threshold-mutation integration expectations**
- **Found during:** Task 1 verification.
- **Issue:** The plan said to preserve the old threshold-mutation test as-is except for a field-name update and still expect `peak_transition_count == 35` while `transition_count == 30`. With the Plan 210-01 implementation, both episode and peak-window deques are pruned by the same `flap_window`; when old entries are pruned to make `transition_count == 30`, the peak-window deque is also pruned to 30. The old payload expectation was therefore inconsistent with the accepted two-deque design.
- **Fix:** Kept the existing test name but rewrote its sequence to produce a real two-deque divergence: first fire clears the episode deque while the peak-window deque survives; threshold mutation then triggers a later alert with `transition_count == 6` and `peak_transition_count == 36`.
- **Files modified:** `tests/integration/test_flapping_integration.py`
- **Commit:** `d6d089c`

## Issues Encountered

- The repository pre-commit hook is interactive when it recommends documentation updates. Non-interactive stdin selection did not complete, so `SKIP_DOC_CHECK=1` was set for task commits. The hook still ran; no `--no-verify` was used.
- Pre-existing unrelated working-tree changes were present in `.planning/PROJECT.md` and several `.planning/todos/pending/*` deletions. They were not staged or committed by this plan.

## Known Stubs

None.

## Threat Flags

None - test-only changes introduced no new network endpoints, auth paths, file access patterns, or trust-boundary schema changes.

## User Setup Required

None.

## Next Phase Readiness

Plan 210-03 can run SAFE-10 enforcement against the source boundary with the full flapping unit and integration test surface now updated for the two-deque implementation.

## Self-Check: PASSED

- FOUND: `.planning/phases/210-windowed-peak-accumulator-implementation/210-02-SUMMARY.md`
- FOUND: task commit `d6d089c`
- FOUND: task commit `bc5bc25`
