---
phase: 200-per-direction-rtt-bloat-thresholds
plan: 12
subsystem: config-validation
tags: [safe-06, valn-06, check-config, upload-thresholds, wr-01, tdd]

# Dependency graph
requires:
  - phase: 200-per-direction-rtt-bloat-thresholds
    provides: Per-direction upload threshold loading and daemon-side strict target/warn rejection
provides:
  - wanctl-check-config cross-field ERROR parity for upload target/warn threshold ordering
  - Regression tests for valid, inverted, equal, absent, partial fallback, and non-numeric upload thresholds
  - Closure of 200-REVIEW.md WR-01 preflight/daemon validation drift
affects: [phase-200, safe-06, valn-06, wanctl-check-config, config-preflight]

# Tech tracking
tech-stack:
  added: []
  patterns: [cross-field validator parity, upload-specific global fallback, TDD RED/GREEN]

key-files:
  created:
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-12-SUMMARY.md
  modified:
    - src/wanctl/check_config_validators.py
    - tests/test_check_config.py

key-decisions:
  - "The CLI preflight emits the upload-specific threshold row only when at least one upload-side threshold key is present, avoiding duplicate reports for global-only configs."
  - "The CLI ERROR message carries the daemon's existing strict ordering rejection shape with values, plus the WR-01 audit phrase required for operator/search parity."

patterns-established:
  - "Upload-specific preflight checks should fall back to global thresholds exactly like Config resolution, but only report the upload row when the upload namespace participates."
  - "Review gap-closure tests should live in the actual check-config test module (`tests/test_check_config.py`) when the planned filename is stale."

requirements-completed: [SAFE-06]
requirements-addressed: [VALN-06]

# Metrics
duration: 3min
completed: 2026-05-04T01:17:56Z
---

# Phase 200 Plan 12: Upload Threshold Preflight Parity Summary

**wanctl-check-config now fails closed on upload-specific target/warn threshold inversion using the same strict ordering contract as daemon config load.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-04T01:15:09Z
- **Completed:** 2026-05-04T01:17:56Z
- **Tasks:** 1/1 TDD task
- **Files modified:** 3 (2 code/test files plus this summary)

## Accomplishments

- Added `_validate_upload_threshold_ordering()` and wired it into `validate_cross_fields()` immediately after global threshold ordering.
- Added 6 regression tests covering valid explicit ordering, inverted ordering, equal values, absent upload keys, partial upload/global fallback, and non-numeric values.
- Restored SAFE-06 preflight/daemon parity for WR-01: upload `target_bloat_ms >= warn_bloat_ms` now yields a `Severity.ERROR` row from `wanctl-check-config` before daemon startup.
- Confirmed the new ERROR text includes the daemon's existing strict ordering shape (`target_bloat_ms (...) must be less than warn_bloat_ms (...)`) and the operator-facing WR-01 phrase `upload target_bloat_ms must be less than upload warn_bloat_ms`.

## Task Commits

TDD produced atomic RED and GREEN commits:

1. **RED: Add failing upload threshold validator coverage** - `88788db` (test)
2. **GREEN: Validate upload threshold ordering in preflight** - `6660930` (feat)

**Plan metadata:** pending final metadata commit.

## Files Created/Modified

- `src/wanctl/check_config_validators.py` - Adds the upload-specific cross-field validator, global fallback behavior, non-numeric ERROR row, and `validate_cross_fields()` integration.
- `tests/test_check_config.py` - Adds `TestUploadThresholdOrdering` with 6 WR-01 regression tests. The plan referenced `tests/test_check_config_validators.py`, but the repository's actual check-config test module is `tests/test_check_config.py`.
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-12-SUMMARY.md` - This execution summary.

## Decisions Made

- Emitted no upload-threshold row for global-only configs so the existing `_validate_threshold_ordering()` result remains the single authoritative global threshold report.
- Kept partial upload configs fail-closed by falling back the missing side to `continuous_monitoring.thresholds.*`, matching `Config._load_threshold_config()` resolution.
- Treated the stale planned test filename as a task-local blocking mismatch and placed tests in the existing `tests/test_check_config.py` module instead of creating a duplicate validator test file.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used the actual check-config test module**
- **Found during:** Task 1 read-first setup
- **Issue:** The plan named `tests/test_check_config_validators.py`, but that file does not exist in this repository; the existing validator tests are in `tests/test_check_config.py`.
- **Fix:** Added `TestUploadThresholdOrdering` to `tests/test_check_config.py` alongside the existing `TestCrossField` validator coverage.
- **Files modified:** `tests/test_check_config.py`
- **Verification:** `.venv/bin/pytest -o addopts='' tests/test_check_config.py::TestUploadThresholdOrdering -q` failed in RED and passed in GREEN.
- **Committed in:** `88788db`

---

**Total deviations:** 1 auto-fixed (1 blocking issue).
**Impact on plan:** The deviation corrected a stale path only; validator behavior, requirements, and verification scope stayed unchanged.

## Issues Encountered

- The repository documentation hook prompts on newly added functions/classes. Commits used `SKIP_DOC_CHECK=1` without `--no-verify`, matching prior Phase 200 noninteractive executor practice while still running hooks.

## Verification

- RED gate: `.venv/bin/pytest -o addopts='' tests/test_check_config.py::TestUploadThresholdOrdering -q` failed before implementation with 5 failing tests and 1 absent-row pass.
- GREEN targeted class: `.venv/bin/pytest -o addopts='' tests/test_check_config.py::TestUploadThresholdOrdering -q` → `6 passed`.
- Full check-config tests: `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q` → `112 passed in 0.69s`.
- Plan-level verification: `grep -n "_validate_upload_threshold_ordering" src/wanctl/check_config_validators.py` shows both call and definition; targeted upload class passed; hot-path slice passed.
- Hot-path regression slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `578 passed in 39.88s`.
- Static checks: `.venv/bin/ruff check src/wanctl/check_config_validators.py tests/test_check_config.py` → pass; `.venv/bin/mypy src/wanctl/check_config_validators.py` → pass.

## TDD Gate Compliance

- RED commit present: `88788db test(200-12): add failing upload threshold validator coverage`.
- GREEN commit present after RED: `6660930 feat(200-12): validate upload threshold ordering in preflight`.
- Refactor commit: not needed; no behavior-neutral cleanup was required after GREEN.

## Known Stubs

None.

## Threat Flags

None. This plan tightens existing offline config preflight validation and introduces no new network endpoint, auth path, file-access pattern, or schema trust boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WR-01 is closed; Plan 200-13 can proceed with the remaining review gap backlog.
- Future verifier should treat `continuous_monitoring.upload.target_bloat_ms >= warn_bloat_ms` as rejected by both `wanctl-check-config` and daemon config load.

## Self-Check: PASSED

- Found `src/wanctl/check_config_validators.py`.
- Found `tests/test_check_config.py`.
- Found `200-12-SUMMARY.md`.
- Found RED task commit `88788db`.
- Found GREEN task commit `6660930`.

---
*Phase: 200-per-direction-rtt-bloat-thresholds*
*Completed: 2026-05-04T01:17:56Z*
