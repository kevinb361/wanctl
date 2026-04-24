---
phase: 194-download-queue-primary-distress-classification
plan: 01
subsystem: controller
tags: [wan-controller, cake-signal, arbitration, health, metrics]
requires:
  - phase: 193-queue-signal-contract-and-arbitration-telemetry
    provides: Phase 193 CAKE queue-delay scalar and arbitration observability surfaces
provides:
  - DL primary-signal selector using valid CAKE queue delay snapshots
  - Per-cycle controller arbitration stash shared by health and metrics
  - Health renderer pass-through over controller-owned arbitration state
affects: [phase-194, phase-195, health, metrics, queue-primary]
tech-stack:
  added: []
  patterns:
    - WANController selector feeding existing QueueController.adjust_4state
    - Controller-owned arbitration state rendered by health_check.py
key-files:
  created:
    - .planning/phases/194-download-queue-primary-distress-classification/194-01-SUMMARY.md
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/health_check.py
    - tests/test_wan_controller.py
    - tests/test_health_check.py
key-decisions:
  - "Kept queue-primary selection in WANController and continued using QueueController.adjust_4state unchanged."
  - "Used the per-cycle WANController arbitration stash as the single source for /health and metric emission."
  - "Kept Phase 194 active_primary_signal limited to queue or rtt; none remains a forward-compatible metric encoding only."
patterns-established:
  - "DL queue primary maps max_delay_delta_us to baseline_rtt + delta_ms before the existing 4-state classifier."
  - "Health signal_arbitration renders controller-owned state with a MagicMock-safe legacy fallback."
requirements-completed: [ARB-01, SAFE-05]
duration: 8 min
completed: 2026-04-24
---

# Phase 194 Plan 01: Download Queue-Primary Distress Classification Summary

**DL classification now selects valid CAKE queue-delay as the primary scalar while preserving the existing classifier and upload path**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-24T12:22:26Z
- **Completed:** 2026-04-24T12:28:23Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `_select_dl_primary_scalar_ms()` with inline semantics for `queue_distress`, `green_stable`, reserved `rtt_veto`, and deliberate non-emission of `none`.
- Wired `_run_congestion_assessment()` so DL classification passes either the queue-derived virtual load RTT or the original `self.load_rtt` fallback into `download.adjust_4state()`.
- Stashed the per-cycle arbitration primary and reason on `WANController`, then reused that source for `wanctl_arbitration_active_primary` and `/health.signal_arbitration`.
- Rewrote `HealthCheckHandler._build_signal_arbitration_section()` as a thin renderer over controller health data with a legacy fallback for tests and older controller-shaped payloads.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: DL selector tests** - `b699a56` (test)
2. **Task 1 GREEN: DL selector implementation** - `025ef04` (feat)
3. **Task 2 RED: arbitration plumbing tests** - `c3c195c` (test)
4. **Task 2 GREEN: assessment, metrics, and health-data wiring** - `6955f40` (feat)
5. **Task 3 RED: health renderer tests** - `94ccdda` (test)
6. **Task 3 GREEN: health renderer implementation** - `5918097` (feat)

## Files Created/Modified

- `src/wanctl/wan_controller.py` - Added arbitration reason constants, DL selector, initial arbitration stash, assessment-seam wiring, stash-backed metric emission, and controller-owned `signal_arbitration` health data.
- `src/wanctl/health_check.py` - Replaced the Phase 193 hardcoded arbitration renderer with a pass-through over controller state plus cold-start-aware fallback.
- `tests/test_wan_controller.py` - Added 12 focused tests for selector behavior, arbitration metric emission, health-data payload shape, and label-anchored UL metrics no-touch proof.
- `tests/test_health_check.py` - Added 5 renderer tests for queue/rtt pass-through, fallback behavior, cold-start null semantics, and Phase 194 reason vocabulary.

## SAFE-05 Status

- **Textual identity:** Verified. `queue_controller.py` and `cake_signal.py` have zero diff lines against the required base. The UL call site and the four upload `wanctl_cake_*` metric lines also have zero matching diff lines.
- **Behavioral identity:** Verified for the RTT fallback by selector tests: the fallback returns `("rtt", self.load_rtt, "green_stable")` without recomputation or rounding.
- **End-to-end identity:** Deferred as planned to Plan 194-02's integrated fallback replay proof.

## Verification

- `.venv/bin/pytest tests/test_wan_controller.py tests/test_health_check.py -x -q` -> `321 passed`
- `.venv/bin/pytest tests/test_phase_193_replay.py -x -q` -> `7 passed`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` -> `513 passed`
- `git diff 95593568418a983436d1232f15c9c46f2747ac7d..HEAD -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py | wc -l` -> `0`
- `git diff -U0 95593568418a983436d1232f15c9c46f2747ac7d..HEAD -- src/wanctl/wan_controller.py | grep -E '^\\+' | grep -E 'self\\.upload\\.adjust\\(' | wc -l` -> `0`
- `git diff 95593568418a983436d1232f15c9c46f2747ac7d..HEAD -- src/wanctl/wan_controller.py | grep -E '^[+-].*"wanctl_cake_(drop_rate|total_drop_rate|backlog_bytes|peak_delay_us)".*self\\._upload_labels' | wc -l` -> `0`

## Decisions Made

- Kept all queue primary logic in `WANController`, not `QueueController`, so the state machine and thresholds remain untouched.
- Used `CakeSignalSnapshot.max_delay_delta_us` as the authoritative queue-delay scalar.
- Preserved the Phase 194 active primary vocabulary as `queue` or `rtt`; `none` remains reserved for later degraded-cycle work.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. Stub-pattern scan found only existing runtime/test `None`, empty-list, and empty-dict initialization patterns; no new placeholder UI/data stubs were introduced.

## Known Limitation

`/health` and metrics now share the same per-cycle stashed source of truth, eliminating source-of-truth drift. Temporal drift between async `/health` reads and the next metric emit cycle is not addressed in Phase 194 because there is no per-cycle timestamp or sequence-id field. This is accepted for Plan 194-01 and can be revisited if a future phase adds cycle sequencing.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 194-02 can build the integrated fallback and queue-primary replay proofs against the new selector seam and controller-owned arbitration state. No blockers were introduced.

## Self-Check: PASSED

- Created/modified files exist: `src/wanctl/wan_controller.py`, `src/wanctl/health_check.py`, `tests/test_wan_controller.py`, `tests/test_health_check.py`, and this summary.
- Task commits found: `b699a56`, `025ef04`, `c3c195c`, `6955f40`, `94ccdda`, `5918097`.

---
*Phase: 194-download-queue-primary-distress-classification*
*Completed: 2026-04-24*
