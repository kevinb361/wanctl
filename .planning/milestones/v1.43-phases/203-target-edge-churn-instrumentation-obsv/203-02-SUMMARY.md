---
phase: 203-target-edge-churn-instrumentation-obsv
plan: 02
subsystem: observability
tags: [soak-aggregator, pytest, ndjson, histogram, safe-07]

requires:
  - phase: 203-01-soak-capture-script-and-projection-test
    provides: locked v1.43 soak capture NDJSON row schema
provides:
  - Stdlib soak-summary aggregator for diagnostic_distribution.load_rtt_delta_us
  - Upload zone × cause load_rtt_delta_us attribution matrix
  - Deterministic synthetic NDJSON and golden summary fixtures
  - Replay coverage for aggregator math, v1.42 diagnostic compatibility, generator drift, zone axis, and cause attribution
affects: [phase-203, phase-204, calib-baseline, soak-harness]

tech-stack:
  added: []
  patterns:
    - deterministic fixture generator with byte-identical drift detection
    - stdlib-only histogram and percentile aggregation for soak analysis

key-files:
  created:
    - scripts/soak_summary_aggregate.py
    - tests/fixtures/_phase_203_generator.py
    - tests/fixtures/phase_203_synthetic_capture.ndjson
    - tests/fixtures/phase_203_synthetic_summary.json
    - tests/test_phase_203_replay.py
  modified: []

key-decisions:
  - "Used Option (b) for Phase 202 helper handling: duplicated/lifted compatible helper logic into the aggregator module while leaving tests/test_phase_202_replay.py unchanged to minimize regression risk."
  - "Kept aggregator scope to diagnostic_distribution and load_rtt_delta_us_by_zone_cause only; secondary-gate computation remains Phase 204/CALIB-03 territory."

patterns-established:
  - "Synthetic NDJSON fixtures are generated from tests/fixtures/_phase_203_generator.py and protected by byte-identical drift tests."
  - "Histogram JSON always carries buckets_us so downstream consumers can interpret historical summaries after defaults change."

requirements-completed: [OBSV-06, OBSV-07, SAFE-07]

duration: 4 min
completed: 2026-05-06
---

# Phase 203 Plan 02: Soak Summary Aggregator and Replay Summary

**Stdlib soak-summary aggregator now computes load RTT delta distributions and upload zone × cause histograms, backed by deterministic replay fixtures and v1.42 diagnostic regression coverage.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-06T22:45:30Z
- **Completed:** 2026-05-06T22:49:41Z
- **Tasks:** 4 completed (3 implementation/test commits, 1 verification-only task)
- **Files modified:** 5 plan files (+ planning metadata after summary)

## Accomplishments

- Created executable `scripts/soak_summary_aggregate.py` exposing `aggregate_soak`, `aggregate_load_rtt_delta`, `aggregate_by_zone_cause`, and `aggregate_v142_diagnostic_distribution`.
- Added deterministic 42-row synthetic fixture generation and checked in both `phase_203_synthetic_capture.ndjson` and byte-comparison golden `phase_203_synthetic_summary.json`.
- Added `tests/test_phase_203_replay.py` with coverage for aggregator math, v1.42 diagnostic compatibility, generator drift, upload-only zone axis, dual-attribution, null filtering, overflow bucketing, and first-row exclusion.
- Verified Phase 202 replay compatibility, SAFE-05 pin test, hot-path regression slice, phase-scoped slice, ruff, mypy, and SAFE-07 no-`src/wanctl` diff.

## Aggregator API

- `aggregate_soak(ndjson_path, buckets=None)` — reads NDJSON and returns the Phase 203 summary fragment with v1.42-compatible `diagnostic_distribution`, `diagnostic_distribution.load_rtt_delta_us`, `load_rtt_delta_us_by_zone_cause`, and `phase_203_metadata`.
- `aggregate_load_rtt_delta(rows, buckets=None)` — computes top-level p50/p95/p99/max, histogram, `samples_total`, and `samples_filtered_null` for rows containing `load_rtt_delta_us`.
- `aggregate_by_zone_cause(rows, buckets=None)` — computes 4-zone × 3-cause upload matrix using lifetime-counter deltas, first-row exclusion, null filtering, and dual-attribution.
- `aggregate_v142_diagnostic_distribution(rows)` — preserves unaffected v1.42 diagnostic-distribution fields for historical soak replay.

## Fixture Details

- **ROW_CATALOG count:** 42 rows.
- **Final `phase_203_metadata.buckets_us`:** `[0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000]`.
- **Per-cell sample counts:**
  - `GREEN`: dwell_hold=4, backlog_recovery=3, other=3
  - `YELLOW`: dwell_hold=4, backlog_recovery=4, other=3
  - `SOFT_RED`: dwell_hold=3, backlog_recovery=3, other=3
  - `RED`: dwell_hold=3, backlog_recovery=3, other=3

## v1.42 Regression Results

Computed values from the new aggregator against the v1.42 reference NDJSON matched the checked-in v1.42 summary within the plan tolerance:

| Field | New Aggregator | v1.42 Reference | Drift |
|-------|----------------|-----------------|-------|
| `rtt_integral_ms_s.mean` | 5.144822 | 5.144822223807321 | <0.000001 abs |
| `rtt_integral_ms_s.max` | 270.569 | 270.569 | 0 |
| `max_delay_delta_us.mean` | 810.337637 | 810.3376368629409 | <0.000001 abs |
| `max_delay_delta_us.max` | 161281 | 161281 | 0 |
| `red_streak.mean` | 0.005873 | 0.005872772447899949 | <0.000001 abs |
| `red_streak.max` | 101 | 101 | 0 |
| `headroom_exhausted_samples` | 469 | 469 | 0 |
| `total_samples` | 84117 | 84117 | 0 |

## Task Commits

Each implementation/test task was committed atomically:

1. **Task 1: Create soak summary aggregator** — `a5e53cb` (feat)
2. **Task 2: Create deterministic generator and fixtures** — `2f19ab2` (test)
3. **Task 3: Create Phase 203 replay tests** — `8d75a58` (test)
4. **Task 4: Hot-path + compatibility + SAFE-07 verification** — verification-only; no file changes to commit separately.

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `scripts/soak_summary_aggregate.py` — Stdlib CLI/module for soak-summary diagnostic aggregation and upload zone × cause matrix math.
- `tests/fixtures/_phase_203_generator.py` — Deterministic generator for the synthetic Phase 203 capture fixture.
- `tests/fixtures/phase_203_synthetic_capture.ndjson` — Checked-in synthetic capture with 42 rows covering all matrix cells and edge cases.
- `tests/fixtures/phase_203_synthetic_summary.json` — Golden expected summary generated from the synthetic capture.
- `tests/test_phase_203_replay.py` — Replay and compatibility tests for OBSV-06/OBSV-07 aggregator side.

## Verification

- Task 1 import/ruff check — passed.
- Task 2 fixture generation, summary bootstrap, samples_filtered_null=3, all-zone matrix presence, golden diff — passed.
- `.venv/bin/pytest tests/test_phase_203_replay.py -v` — 12 passed in 1.86s.
- `.venv/bin/pytest tests/test_phase_202_replay.py -v` — 9 passed in 0.54s.
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — 667 passed in 40.05s.
- `.venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts"` — 1 passed, 24 deselected in 0.28s.
- `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` — 56 passed in 3.01s.
- `.venv/bin/ruff check scripts/soak_summary_aggregate.py tests/fixtures/_phase_203_generator.py tests/test_phase_203_replay.py` — passed.
- `.venv/bin/ruff format --check scripts/soak_summary_aggregate.py tests/fixtures/_phase_203_generator.py tests/test_phase_203_replay.py` — passed.
- `.venv/bin/mypy scripts/soak_summary_aggregate.py` — passed.
- `git diff b72b463 -- src/wanctl/ | wc -l` — `0`.

## Decisions Made

- Chose Option (b) for Phase 202 helper handling: the aggregator module contains compatible `aggregate_completed_windows` and `_percentile` helpers, while `tests/test_phase_202_replay.py` remains unchanged. This avoids unnecessary churn in the Phase 202 replay canary.
- Kept the aggregator diagnostic-only. No secondary-gate successor computation was promoted here; that remains Phase 204/CALIB-03 territory as planned.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed histogram overflow bucket assignment**
- **Found during:** Task 3 (Phase 203 replay tests)
- **Issue:** The initial histogram implementation placed values greater than the final bucket boundary into the last bounded bucket instead of the overflow cell. `test_histogram_contains_overflow_bin` caught the 350000 µs synthetic row with overflow count 0.
- **Fix:** Updated `histogram()` to route `value >= buckets[-1]` to the overflow cell and regenerated the golden summary fixture.
- **Files modified:** `scripts/soak_summary_aggregate.py`, `tests/fixtures/phase_203_synthetic_summary.json`, `tests/test_phase_203_replay.py`
- **Verification:** `.venv/bin/pytest tests/test_phase_203_replay.py -v` passed with 12 tests.
- **Committed in:** `8d75a58` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** Correctness fix only; no scope expansion and no production code touched.

## Known Stubs

None. The aggregator and fixtures are fully wired; operator-facing docs remain assigned to Plan 203-03.

## Threat Flags

None. This plan added an offline local-file CLI and test fixtures only; no network endpoint, auth path, daemon behavior, file trust boundary beyond the planned NDJSON path, or `src/wanctl/` surface was introduced.

## Issues Encountered

- Repository pre-commit documentation hook recommended docs for the new script/test helpers. Plan 203-03 owns the soak harness documentation, so task commits used the hook's supported `SKIP_DOC_CHECK=1` path while still running hooks; no `--no-verify` was used.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 203-03. The aggregator API, fixture oracle, default bucket scheme, v1.42 compatibility behavior, and SAFE-07 verification results are all available for documentation and phase closeout.

## Self-Check: PASSED

- Found `scripts/soak_summary_aggregate.py`.
- Found `tests/fixtures/_phase_203_generator.py`.
- Found `tests/fixtures/phase_203_synthetic_capture.ndjson`.
- Found `tests/fixtures/phase_203_synthetic_summary.json`.
- Found `tests/test_phase_203_replay.py`.
- Found this summary file.
- Found task commit `a5e53cb`.
- Found task commit `2f19ab2`.
- Found task commit `8d75a58`.

---
*Phase: 203-target-edge-churn-instrumentation-obsv*
*Completed: 2026-05-06*
