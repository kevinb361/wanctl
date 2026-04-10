---
phase: 88-signal-processing-core
plan: 01
subsystem: signal-processing
tags: [hampel, ewma, jitter, variance, confidence, outlier-detection, stdlib]

# Dependency graph
requires: []
provides:
  - "SignalProcessor class: Hampel outlier filter, jitter EWMA, variance EWMA, confidence scoring"
  - "SignalResult frozen dataclass: 10-field per-cycle signal quality metadata"
affects: [88-02-PLAN, phase-92-observability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      hampel-filter,
      mad-based-outlier-detection,
      ewma-time-constant,
      frozen-dataclass-slots,
    ]

key-files:
  created:
    - src/wanctl/signal_processing.py
    - tests/test_signal_processing.py
  modified: []

key-decisions:
  - "Warm-up period is window_size cycles (7 at 50ms = 350ms) -- check happens before append"
  - "MAD=0 guard skips outlier detection when window values are identical (correct Hampel behavior)"
  - "Jitter and variance both computed from raw RTT, not filtered -- reflects true network quality"
  - "Confidence formula 1/(1 + var/baseline^2) with baseline<=0 guard returning 1.0"

patterns-established:
  - "SignalProcessor per-WAN instance pattern: config dict with defaults, logger, wan_name"
  - "Parallel deque tracking: _window (raw RTT values) + _outlier_window (bool) for rate calculation"
  - "EWMA zero-init pattern: first sample initializes directly, subsequent samples blend"

requirements-completed: [SIGP-01, SIGP-02, SIGP-03, SIGP-04, SIGP-05]

# Metrics
duration: 16min
completed: 2026-03-16
---

# Phase 88 Plan 01: Signal Processing Core Algorithms Summary

**Hampel outlier filter with MAD-based detection, EWMA jitter/variance tracking, and confidence scoring -- all stdlib-only Python**

## Performance

- **Duration:** 16 min
- **Started:** 2026-03-16T18:33:17Z
- **Completed:** 2026-03-16T18:49:39Z
- **Tasks:** 2 (TDD: RED + GREEN/REFACTOR)
- **Files created:** 2

## Accomplishments

- SignalProcessor class with Hampel filter, jitter EWMA, variance EWMA, and confidence scoring
- SignalResult frozen dataclass with 10 fields including total_outliers and consecutive_outliers
- 32 unit tests covering all SIGP-01 through SIGP-05 behaviors
- Zero third-party dependencies (stdlib only: statistics, collections, dataclasses, logging, typing)
- Full test suite green (3101 tests, zero regressions), ruff clean, mypy clean

## Task Commits

Each task was committed atomically:

1. **Task 1: RED -- Write failing tests for SignalProcessor** - `6748f92` (test)
2. **Task 2: GREEN + REFACTOR -- Implement SignalProcessor** - `a7d82d7` (feat)

_TDD: Task 1 created 32 failing tests (ImportError), Task 2 implemented + refined tests to match correct algorithmic behavior._

## Files Created/Modified

- `src/wanctl/signal_processing.py` - SignalProcessor class and SignalResult dataclass (264 lines)
- `tests/test_signal_processing.py` - 32 unit tests across 8 test classes (420 lines)

## Decisions Made

- Warm-up check uses `len(window) < window_size` before append -- 7 warm-up cycles for window_size=7 (not 6)
- MAD=0 guard is correct Hampel behavior: identical window values have zero dispersion, so no outlier threshold can be computed
- Tests use varying RTT values (~25ms +/- 0.5ms) for Hampel tests requiring outlier detection, identical values for MAD=0 guard test
- `from typing import Any` added for mypy-clean config dict typing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test expectations corrected for Hampel MAD=0 behavior**

- **Found during:** Task 2 (GREEN phase)
- **Issue:** Plan specified identical 25.0ms window values for outlier tests, but identical values produce MAD=0 which correctly skips detection. Plan's test descriptions used "~25ms" implying variance.
- **Fix:** Updated Hampel detection tests to use varying values [24.5, 25.0, 25.5, 24.8, 25.2, 24.9, 25.1] for non-zero MAD. Kept identical-value tests for MAD=0 guard test.
- **Files modified:** tests/test_signal_processing.py
- **Verification:** All 32 tests pass
- **Committed in:** a7d82d7 (Task 2 commit)

**2. [Rule 1 - Bug] Warm-up period count aligned with implementation**

- **Found during:** Task 2 (GREEN phase)
- **Issue:** Plan spec said "first 6 calls warming_up=True" but implementation checks window length before append, so 7 calls are warming up. Plan's implementation formula (`len < window_size`) and test spec ("first window_size-1 calls") were inconsistent.
- **Fix:** Updated warm-up tests to expect 7 warm-up calls (matching the `len < window_size` formula from the plan's implementation section).
- **Files modified:** tests/test_signal_processing.py
- **Verification:** All warm-up tests pass correctly
- **Committed in:** a7d82d7 (Task 2 commit)

**3. [Rule 1 - Bug] Stdlib import check scoped to import lines only**

- **Found during:** Task 2 (GREEN phase)
- **Issue:** TestStdlibOnly checked for "numpy" string in entire module source, but module docstring mentions "no numpy" -- false positive.
- **Fix:** Changed test to extract only `import`/`from` lines before checking for forbidden packages.
- **Files modified:** tests/test_signal_processing.py
- **Verification:** Test correctly passes (no third-party imports in actual import statements)
- **Committed in:** a7d82d7 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 test refinements, Rule 1)
**Impact on plan:** All fixes necessary for correctness. Tests now accurately verify the algorithmic behavior. No scope creep.

## Issues Encountered

None beyond the test corrections documented in deviations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SignalProcessor ready for integration into WANController (Plan 02)
- Config loading, daemon wiring, and integration tests are the next step
- Module is standalone with zero external dependencies -- clean import boundary

## Self-Check: PASSED

- [x] src/wanctl/signal_processing.py exists
- [x] tests/test_signal_processing.py exists
- [x] 88-01-SUMMARY.md exists
- [x] Commit 6748f92 (RED) exists
- [x] Commit a7d82d7 (GREEN+REFACTOR) exists

---

_Phase: 88-signal-processing-core_
_Completed: 2026-03-16_
