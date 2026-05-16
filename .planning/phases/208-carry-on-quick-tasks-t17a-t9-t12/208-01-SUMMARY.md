---
phase: 208-carry-on-quick-tasks-t17a-t9-t12
plan: 01
subsystem: tooling
tags: [soak-harness, watchdog, aggregator, pytest, schema-contract]

# Dependency graph
requires:
  - phase: 207-soak-harness-hardening-v1-43-closeout-routed
    provides: secondary_gate_legacy removed and CALIB-02 YAML promotion routed to NO
  - phase: 204-d-14-successor-recalibration-calib
    provides: completed-window watchdog constants and golden soak-summary fixtures
provides:
  - aggregate_watchdog() fail-closed guard for unknown gate_column/statistic
  - exact 10-key secondary_gate_completed_window schema assertions
  - deterministic aggregate_soak() round-trip and recursive legacy-absent proof
affects: [phase-208, phase-209, soak-harness, TOOL-01, CALIB-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - in-band fail-closed operator-tool validation
    - fixture-as-determinism-proxy with golden byte-equal schema anchor

key-files:
  created:
    - .planning/phases/208-carry-on-quick-tasks-t17a-t9-t12/208-01-SUMMARY.md
  modified:
    - scripts/soak_summary_aggregate.py
    - tests/test_phase_204_watchdog.py
    - CHANGELOG.md

key-decisions:
  - "TOOL-01 invalid watchdog config fails closed in-band instead of raising, preserving generated summary inspectability."
  - "Cross-version schema proof is split: deterministic fixture re-run here, byte-equal golden anchor in tests/test_phase_204_distribution.py."
  - "SAFE-09 boundary preserved: no src/wanctl/ changes."

patterns-established:
  - "Watchdog misconfiguration reports config_reason while retaining the same 10 output keys."
  - "Schema tests recursively walk output to prove secondary_gate_legacy remains absent at every depth."

requirements-completed: [TOOL-01]

# Metrics
duration: 4m15s
completed: 2026-05-16
---

# Phase 208 Plan 01: TOOL-01 Watchdog Aggregator Hardening Summary

**Completed-window watchdog aggregation now fails closed on misconfigured gate columns/statistics while preserving the v1.44 10-key schema contract.**

## Performance

- **Duration:** 4m15s
- **Started:** 2026-05-16T17:14:58Z
- **Completed:** 2026-05-16T17:19:13Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Closed the WR-01 false-pass hole in `aggregate_watchdog()` for unknown top-level `gate_column`, unknown `by_cause.<cause>`, and unsupported `statistic` values.
- Added explicit `EXPECTED_SECONDARY_GATE_KEYS` assertions covering fail-closed and valid paths for the exact 10-key `secondary_gate_completed_window` block contract.
- Added `TestSchemaRoundTripV143V144` to prove recursive `secondary_gate_legacy` absence and deterministic `aggregate_soak()` output from the post-HRDN-03 fixture.
- Preserved the existing golden fixture anchor: `tests/test_phase_204_distribution.py::test_aggregate_soak_matches_golden` remains byte-equal.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fail-closed cases to test_phase_204_watchdog.py (RED)** - `d29cb0d` (test)
2. **Task 2: Implement fail-closed guard in aggregate_watchdog() (GREEN)** - `8da071d` (fix)
3. **Task 3: Pin schema round-trip determinism + legacy-absent walker** - `7fb37e6` (test)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `scripts/soak_summary_aggregate.py` - Added known-statistic/top-level-gate constants and `config_reason` fail-closed handling in `aggregate_watchdog()`.
- `tests/test_phase_204_watchdog.py` - Added fail-closed TDD cases, 10-key block contract constant/assertions, deterministic round-trip test, and recursive legacy-absent walker.
- `CHANGELOG.md` - Documented TOOL-01 test coverage and fail-closed watchdog fix under v1.44 Unreleased.
- `.planning/phases/208-carry-on-quick-tasks-t17a-t9-t12/208-01-SUMMARY.md` - This execution summary.

## Verification

- `.venv/bin/pytest tests/test_phase_204_watchdog.py::TestWatchdogMath::test_unknown_gate_column_cause_fails_closed tests/test_phase_204_watchdog.py::TestWatchdogMath::test_unknown_top_level_gate_column_fails_closed tests/test_phase_204_watchdog.py::TestWatchdogMath::test_unsupported_statistic_fails_closed tests/test_phase_204_watchdog.py::TestWatchdogMath::test_valid_config_shape_regression -v`
  - RED result before implementation: 3 failed, 1 passed.
- `.venv/bin/pytest tests/test_phase_204_watchdog.py tests/test_phase_204_distribution.py tests/test_phase_204_replay.py -v`
  - GREEN result after implementation: 18 passed.
- `.venv/bin/pytest tests/test_phase_204_watchdog.py::TestSchemaRoundTripV143V144 tests/test_phase_204_distribution.py::test_aggregate_soak_matches_golden tests/test_phase_204_replay.py -v`
  - Schema result: 5 passed.
- `.venv/bin/pytest tests/test_phase_204_watchdog.py tests/test_phase_204_replay.py tests/test_phase_204_distribution.py -v`
  - Final result: 20 passed.
- `git diff -- src/wanctl/` returned empty.
- `git diff -- scripts/calib_02_threshold.json` returned empty.
- Non-comment scan of `scripts/soak_summary_aggregate.py` found no `secondary_gate_legacy` references.

## Decisions Made

- Invalid watchdog config uses in-band fail-closed output (`verdict="fail"`, `value=0.0`, non-null `reason`) rather than raising, matching D-02 and keeping summary artifacts inspectable.
- The cross-version schema claim stays evidence-split: new tests prove determinism and legacy absence; existing distribution golden test remains the byte-equal schema anchor.
- Changelog updates were included with task commits because repository pre-commit hooks require documentation freshness for new test classes/security-like terms.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The pre-commit documentation hook prompts interactively on new test classes/security-like terms. Instead of bypassing hooks, each relevant task commit included a tracked `CHANGELOG.md` update so hooks passed normally.

## Known Stubs

None.

## Threat Flags

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TOOL-01 is complete and ready for Phase 208 follow-on plans.
- Phase 209 can rely on `secondary_gate_completed_window` remaining top-level, 10-key shaped, and fail-closed for bad operator threshold config.

## Self-Check: PASSED

- Found created/modified files: `scripts/soak_summary_aggregate.py`, `tests/test_phase_204_watchdog.py`, `CHANGELOG.md`, and this summary.
- Found task commits in git history: `d29cb0d`, `8da071d`, `7fb37e6`.
- Final verification passed: 20/20 selected Phase 204 watchdog/replay/distribution tests.

---
*Phase: 208-carry-on-quick-tasks-t17a-t9-t12*
*Completed: 2026-05-16*
