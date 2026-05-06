---
phase: 202-ul-suppression-metric-semantics-metric
plan: 02
subsystem: testing
tags: [replay, metrics, suppression-counters, completed-window, oracle]

requires:
  - phase: 202-01-counter-accounting-and-health-schema
    provides: QueueController per-cause suppression counters and reset_window completed-window snapshots
provides:
  - METRIC-03 replay oracle test for completed-window suppression aggregation
  - Offline aggregate_completed_windows helper pinning reset-boundary semantics
  - Synthetic QueueController reset_window snapshot tests for per-cause counters
affects: [phase-202, phase-204, metric-semantics, d14-successor-calibration]

tech-stack:
  added: []
  patterns: [offline-ndjson-column-reduction, observable-reset-boundary-oracle, synthetic-counter-snapshot-test]

key-files:
  created:
    - tests/test_phase_202_replay.py
  modified: []

key-decisions:
  - "Pinned METRIC-03 against observable reset-boundary windows from the v1.42 soak fixture: 1,331 windows, mean 13.8903/min, p95 41, max 124."
  - "Kept the NDJSON oracle as offline column reduction only; QueueController is instantiated only for the synthetic reset_window snapshot tests."
  - "Corrected the planned 1,400-1,500 window-count self-check because nominal elapsed windows include zero-suppression windows with no decreasing edge in suppressions_per_min."

patterns-established:
  - "aggregate_completed_windows treats a strict counter decrease as the only observable completed-window boundary."
  - "Replay oracle tests can pin historical soak math without invoking the controller over the corpus."

requirements-completed: [METRIC-03]

duration: 2min
completed: 2026-05-06
---

# Phase 202 Plan 02: Replay Fixture Completed-Window Oracle Summary

**METRIC-03 replay oracle pinning the v1.42 suppression completed-window distribution with synthetic reset_window snapshot coverage.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-06T21:03:23Z
- **Completed:** 2026-05-06T21:05:28Z
- **Tasks:** 3 completed
- **Files modified:** 1 test file + this summary/state metadata

## Accomplishments

- Created `tests/test_phase_202_replay.py` with three test classes covering the helper, the v1.42 soak oracle, and synthetic QueueController snapshot semantics.
- Added `aggregate_completed_windows()` for reset-boundary reduction of `suppressions_per_min` snapshots.
- Mechanically verified the codex oracle against `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson`:
  - Samples read: `84,117`
  - Observable completed suppression windows: `1,331`
  - Mean: `13.890308039068369/min` (matches `~13.9` within tolerance)
  - p95: `41.0`
  - Max: `124`
- Added synthetic-trace tests proving `_record_suppression()` snapshots into `_last_completed_window_total` / `_last_completed_window_by_cause` on `reset_window()` while lifetime counters remain monotonic.
- Preserved SAFE-07 for this plan: no `src/` files were modified.

## Task Commits

Each task was committed atomically where file changes existed:

1. **Task 1: Completed-window helper + v1.42 oracle test** — `8b8c52b` (test)
2. **Task 2: Synthetic reset_window snapshot tests** — `a75d70e` (test)
3. **Task 3: Verification-only hot-path regression + SAFE-07 source diff** — no source/doc commit; verification produced no file changes.

## Files Created/Modified

- `tests/test_phase_202_replay.py` — Offline completed-window aggregation helper, codex oracle test, and synthetic QueueController reset snapshot tests.

## Verification

- PASS: `.venv/bin/pytest tests/test_phase_202_replay.py::TestAggregateCompletedWindows tests/test_phase_202_replay.py::TestCompletedWindowOracle -v` — 7 passed.
- PASS: `.venv/bin/pytest tests/test_phase_202_replay.py::TestRecordSuppressionSyntheticTrace -v` — 2 passed.
- PASS: `.venv/bin/pytest tests/test_phase_202_replay.py -v` — 9 passed.
- PASS: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — 667 passed.
- PASS: `git diff main -- src/wanctl/ | wc -l` — `0`.

## Decisions Made

- Used strict reset-boundary detection (`snapshots[i] < snapshots[i - 1]`) for the oracle helper, matching the locked algorithm.
- Used a small in-file NumPy-default linear percentile implementation to avoid adding an import dependency for one p95 assertion.
- Treated `suppression-stats.json::window_count=1439` as a nominal elapsed-window count, not the observable reset-window count for the nonzero completed-window distribution.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected planned window-count self-check**
- **Found during:** Task 1 (Completed-window helper + v1.42 oracle test)
- **Issue:** The planned assertion expected `len(window_counts)` between 1,400 and 1,500 based on `suppression-stats.json::window_count=1439`, but the locked reset detector observes only 1,331 decreasing edges. Zero-suppression nominal windows do not create a visible decrease in the `suppressions_per_min` snapshot sequence.
- **Fix:** Pinned the observable reset-window count to `1331` while leaving the codex oracle assertions unchanged (`mean≈13.9`, `p95=41`, `max=124`).
- **Files modified:** `tests/test_phase_202_replay.py`
- **Verification:** Targeted oracle test passed and computed `mean=13.890308039068369`, `p95=41.0`, `max=124`.
- **Committed in:** `8b8c52b`

---

**Total deviations:** 1 auto-fixed (Rule 1).
**Impact on plan:** The oracle math is stronger, not weaker: the distribution values match exactly, and the corrected count documents the observable reset-boundary population rather than conflating it with elapsed nominal windows.

## Issues Encountered

- The repository pre-commit hook is interactive for documentation recommendations. In this non-interactive executor, commits used `SKIP_DOC_CHECK=1` so the hook ran and reported its checks without hanging; no `--no-verify` was used.

## TDD Gate Compliance

- The two `tdd="true"` tasks were test-materialization tasks over an already-landed Plan 202-01 implementation and an in-test helper. They produced test commits, not separate RED/GREEN production-code commits.
- Task 2 tests passed immediately because Plan 202-01 had already implemented the snapshot machinery this plan verifies.

## Known Stubs

None.

## Threat Flags

None.

## Auth Gates

None.

## User Setup Required

None - no external service configuration required.

## GSD State/Roadmap Update Limitation

This phase lives under `.planning/milestones/v1.43-phases/`, while the current GSD SDK phase index expects `.planning/phases/`. STATE.md, ROADMAP.md, and REQUIREMENTS.md were updated manually rather than through standard phase-dir handlers.

## Next Phase Readiness

- METRIC-03 is mechanically pinned and ready for Plan 202-03 SAFE-05 v1.43 occurrence pins.
- Plan 202-03 should preserve the corrected distinction between nominal elapsed soak windows and observable reset-boundary completed suppression windows.

## Self-Check: PASSED

- FOUND: `.planning/milestones/v1.43-phases/202-ul-suppression-metric-semantics-metric/202-02-SUMMARY.md`
- FOUND: `tests/test_phase_202_replay.py`
- FOUND commits: `8b8c52b`, `a75d70e`
- Verified plan-level replay tests, hot-path regression slice, and SAFE-07 source diff check passed.

---
*Phase: 202-ul-suppression-metric-semantics-metric*
*Completed: 2026-05-06*
