---
phase: 204-d-14-successor-recalibration-calib
plan: 02
subsystem: soak-harness
tags: [calib-01, soak, distribution, safe-07, spectrum, cake-shaper]

requires:
  - phase: 204-01
    provides: v1.43.0 binary running on cake-shaper with METRIC-01 and OBSV-05 health fields live
  - phase: 203
    provides: soak capture harness and load_rtt_delta_us aggregation framework
provides:
  - aggregate_completed_window_distribution() for CALIB-01 completed-window suppression-count stats
  - CALIB-01 24h Spectrum baseline capture and soak-summary.json distribution
  - Plan 204-03 threshold-session input values: p99=82.0, dwell_hold_p99=70.25999999999999, backlog_recovery_p99=75.77
affects: [204-03-calib02-threshold-and-operator-approval, CALIB-01, CALIB-02, SAFE-07]

tech-stack:
  added: []
  patterns:
    - monotonic completed-window boundary detection via value-change deltas
    - fixture-driven soak-summary golden replay tests
    - documented operator acceptance for evidence-quality proxy deviation

key-files:
  created:
    - tests/test_phase_204_distribution.py
    - tests/fixtures/_phase_204_generator.py
    - tests/fixtures/phase_204_synthetic_capture.ndjson
    - tests/fixtures/phase_204_synthetic_summary.json
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/launch-notes.md
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-capture.ndjson
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-summary.json
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-acceptance.md
  modified:
    - scripts/soak_summary_aggregate.py
    - tests/fixtures/phase_203_synthetic_summary.json

key-decisions:
  - "Accepted CALIB-01 line count 84098 < 86000 as a documented deviation because the operator approved no extension and stronger quality checks passed: full 86400s wall-clock, zero parse errors, zero missing minute buckets, 97.335648% coverage, 1343 completed-window value changes, and floor-hit delta 0."
  - "Used the Spectrum-bound health endpoint http://10.10.110.223:9101/health for the soak harness, preserving the Plan 204-01 endpoint correction."
  - "Kept CALIB-01 aggregation in scripts/soak_summary_aggregate.py rather than a one-off script so Plan 204-03 consumes a versioned summary contract."

patterns-established:
  - "CALIB soak evidence may record a line-count proxy miss only with explicit operator acceptance and stronger contiguous-window quality evidence."
  - "Completed-window distribution stats include p99 and by_cause sub-dicts for the Plan 204-03 slice-vs-total decision."

requirements-completed: [CALIB-01]

duration: 24h wall clock plus ~35min active execution
completed: 2026-05-08
---

# Phase 204 Plan 02: CALIB-01 Baseline Soak and Distribution Summary

**CALIB-01 produced a 24h Spectrum completed-window suppression-count distribution with top-level p99 82.0 and per-cause p99 slices for Plan 204-03 threshold approval.**

## Performance

- **Duration:** 24h wall clock plus ~35min active execution
- **Started:** 2026-05-07T01:17:36Z
- **Soak window:** 2026-05-07T13:19:29+00:00 → 2026-05-08T13:19:28+00:00
- **Completed:** 2026-05-08T13:19:28Z
- **Tasks:** 3/3 completed
- **Files modified:** 10 plan-scoped files plus remote cake-shaper capture

## Accomplishments

- Added `aggregate_completed_window_distribution()` and a sibling monotonic boundary helper to `scripts/soak_summary_aggregate.py`.
- Added Phase 204 synthetic replay fixtures and tests covering golden output, explicit p99, by-cause accounting, meaningful window counts, and plateau de-duplication.
- Launched and completed CALIB-01 baseline soak on `cake-shaper` using `HEALTH_URL=http://10.10.110.223:9101/health`.
- Copied the 24h NDJSON capture locally and generated `soak-summary.json` with the new `suppressions_completed_window_count_distribution` block.
- Documented operator acceptance of the `84098 < 86000` line-count proxy miss based on stronger capture-quality evidence.

## CALIB_01_TS

`20260507T131911Z`

## Capture Quality

| Check | Result |
|------|--------|
| Line count | `84098` |
| Plan proxy | `>= 86000` |
| First sample | `2026-05-07T13:19:29+00:00` |
| Last sample | `2026-05-08T13:19:28+00:00` |
| Elapsed inclusive seconds | `86400` |
| Coverage vs elapsed seconds | `97.335648%` |
| Parse errors | `0` |
| Missing minute buckets | `0` |
| Completed-window value changes | `1343` |
| Floor-hit delta | `0` |

## Distribution Stats

Top-level `suppressions_completed_window_count_distribution`:

| Field | Value |
|-------|-------|
| mean | `14.63527653213752` |
| p50 | `8.0` |
| p95 | `55.0` |
| p99 | `82.0` |
| max | `119` |
| window_count | `669` |

By-cause sub-dict:

```json
{
  "backlog_recovery": {
    "max": 77,
    "mean": 25.322580645161292,
    "p50": 20.0,
    "p95": 58.849999999999994,
    "p99": 75.77,
    "window_count": 124
  },
  "dwell_hold": {
    "max": 119,
    "mean": 11.408888888888889,
    "p50": 6.0,
    "p95": 41.0,
    "p99": 70.25999999999999,
    "window_count": 675
  },
  "other": {
    "max": 0,
    "mean": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "p99": 0.0,
    "window_count": 0
  }
}
```

## Task Commits

1. **Task 1 RED: Add failing distribution replay tests** — `ab5ddbd` (`test`)
2. **Task 1 GREEN: Implement completed-window distribution aggregation** — `1dabafe` (`feat`)
3. **Task 2: Launch CALIB-01 24h baseline soak** — `6d8874b` (`docs`)
4. **Task 3: Pull capture, aggregate, and commit distribution** — `1ed2d45` (`docs`)

## Files Created/Modified

- `scripts/soak_summary_aggregate.py` — added monotonic boundary helper and completed-window distribution aggregation.
- `tests/test_phase_204_distribution.py` — Phase 204 replay tests for CALIB-01 distribution math.
- `tests/fixtures/_phase_204_generator.py` — deterministic fixture generator for the synthetic CALIB-01 capture.
- `tests/fixtures/phase_204_synthetic_capture.ndjson` — synthetic capture with completed-window jumps and plateau rows.
- `tests/fixtures/phase_204_synthetic_summary.json` — golden summary for Phase 204 replay tests.
- `tests/fixtures/phase_203_synthetic_summary.json` — refreshed for the new top-level distribution key with existing synthetic fields.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/launch-notes.md` — launch evidence, pre-soak health snapshot, and timer details.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-capture.ndjson` — accepted 24h CALIB-01 raw capture.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-summary.json` — generated CALIB-01 distribution summary.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-acceptance.md` — documented acceptance of line-count proxy deviation.

## Decisions Made

- Accepted the completed CALIB-01 soak without extension despite `84098 < 86000`, per operator direction, because full wall-clock and minute-bucket coverage proved the baseline was contiguous and usable.
- Used `http://10.10.110.223:9101/health` for launch/capture, matching the Plan 204-01 correction that localhost is not the Spectrum health binding on this deployment.
- Preserved SAFE-07: no new `src/wanctl/**` changes were introduced by this plan.

## Deviations from Plan

### Auto-fixed Issues

None.

### Operator-Accepted Deviations

**1. Line-count proxy miss accepted without non-contiguous extension**
- **Found during:** Task 3 (Pull CALIB-01 capture, run aggregator, commit distribution)
- **Issue:** Final line count was `84098`, below the strict plan proxy `>= 86000`.
- **Disposition:** Operator explicitly accepted the completed soak and instructed not to extend. Stronger checks passed: contiguous 24h wall-clock window, zero parse errors, zero missing minute buckets, 97.335648% coverage, 1343 completed-window value changes, and floor-hit delta 0.
- **Files modified:** `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-acceptance.md`, this summary.
- **Verification:** Remote capture quality script, local line count, generated `soak-summary.json`, and jq distribution checks.
- **Committed in:** `1ed2d45`

---

**Total deviations:** 1 operator-accepted evidence-quality deviation.
**Impact on plan:** CALIB-01 remains suitable for Plan 204-03 because the distribution is based on a contiguous full-day capture with complete minute coverage and adequate completed-window transitions. No source/control-path behavior changed.

## Issues Encountered

- The plan text still referenced localhost for the soak launch. This execution used the Plan 204-01 endpoint correction (`http://10.10.110.223:9101/health`) and documented it in launch notes.

## Threat Flags

None. The plan exercised the existing cake-shaper SSH and local health-fetch trust boundaries already identified in the plan threat model; no new endpoint, auth path, file access pattern, or schema boundary was introduced.

## Known Stubs

None found in created/modified plan files.

## Auth Gates

None.

## Verification

- `.venv/bin/pytest tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py -v` → `26 passed`
- `bash scripts/check-safe07-source-diff.sh` → `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`
- Hot-path slice → `667 passed`
- `jq -e '.suppressions_completed_window_count_distribution.p99 != null and .suppressions_completed_window_count_distribution.window_count > 100' soak-summary.json` → `true`
- `jq -e '.suppressions_completed_window_count_distribution.by_cause.dwell_hold != null and .suppressions_completed_window_count_distribution.by_cause.backlog_recovery != null' soak-summary.json` → `true`

## TDD Gate Compliance

- RED commit present: `ab5ddbd` (`test(204-02): add failing distribution replay tests`)
- GREEN commit present after RED: `1dabafe` (`feat(204-02): add completed-window distribution aggregation`)
- Refactor commit: not needed.

## User Setup Required

None. The CALIB-01 baseline capture and summary are committed locally.

## Next Phase Readiness

Plan 204-03 is unblocked. Operator threshold session should use:

- Top-level p99: `82.0`
- Dwell-hold p99: `70.25999999999999`
- Backlog-recovery p99: `75.77`
- Top-level max: `119`
- Top-level window_count: `669`

## Self-Check: PASSED

- Verified key files exist: Task 1 tests/fixtures, `scripts/soak_summary_aggregate.py`, launch notes, local NDJSON capture, generated summary, acceptance artifact, and this summary.
- Verified task commits exist: `ab5ddbd`, `1dabafe`, `6d8874b`, `1ed2d45`.
- Verified SAFE-07 remained clean via `scripts/check-safe07-source-diff.sh`.

---
*Phase: 204-d-14-successor-recalibration-calib*
*Completed: 2026-05-08*
