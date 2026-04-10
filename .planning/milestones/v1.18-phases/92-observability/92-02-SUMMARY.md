---
phase: 92-observability
plan: 02
subsystem: storage
tags: [sqlite, metrics, signal-quality, irtt, deduplication, observability]

# Dependency graph
requires:
  - phase: 89-signal-processing
    provides: "SignalResult dataclass with jitter_ms, variance_ms2, confidence, total_outliers"
  - phase: 90-irtt-integration
    provides: "IRTTResult dataclass with rtt_mean_ms, ipdv_mean_ms, send_loss, receive_loss, timestamp"
provides:
  - "8 new STORED_METRICS entries for signal quality and IRTT"
  - "Signal quality metrics persisted to SQLite every 50ms cycle"
  - "IRTT metrics persisted to SQLite only on new measurements with timestamp dedup"
  - "_last_irtt_write_ts tracking for IRTT write deduplication"
affects: [92-01-health-endpoints, metrics-api, dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Timestamp-based deduplication for infrequent metric sources"
    - "Conditional metrics_batch.extend() for optional metric groups"

key-files:
  created:
    - tests/test_metrics_observability.py
  modified:
    - src/wanctl/storage/schema.py
    - src/wanctl/autorate_continuous.py
    - tests/test_storage_schema.py

key-decisions:
  - "Signal quality metrics written every cycle (same cadence as existing RTT metrics)"
  - "IRTT metrics deduplicated via monotonic timestamp comparison, not wall clock"
  - "outlier_count cast to float for SQLite REAL column consistency"

patterns-established:
  - "Conditional batch extension: if source is not None, extend metrics_batch before single write_metrics_batch call"
  - "Timestamp dedup: compare _last_write_ts to source.timestamp, update after extend"

requirements-completed: [OBSV-03, OBSV-04]

# Metrics
duration: 24min
completed: 2026-03-17
---

# Phase 92 Plan 02: Metrics Persistence Summary

**Signal quality and IRTT metrics persisted to SQLite with timestamp-based IRTT deduplication preventing 200x row bloat at 20Hz**

## Performance

- **Duration:** 24 min
- **Started:** 2026-03-17T11:24:56Z
- **Completed:** 2026-03-17T11:49:23Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- 18 total STORED_METRICS entries (10 existing + 4 signal quality + 4 IRTT)
- Signal quality (jitter, variance, confidence, outlier_count) written every 50ms cycle when available
- IRTT (rtt, ipdv, loss_up, loss_down) written only on new measurements (~every 10s) via timestamp dedup
- 17 new tests covering unit batch logic, deduplication, and run_cycle integration

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 8 STORED_METRICS entries** - `4b961a3` (feat)
2. **Task 2: Extend run_cycle() metrics batch (TDD)** - `61b7d8c` (test: RED), `452ec61` (feat: GREEN)

## Files Created/Modified

- `src/wanctl/storage/schema.py` - 8 new Prometheus-compatible metric definitions
- `src/wanctl/autorate_continuous.py` - \_last_irtt_write_ts init + metrics batch extensions in run_cycle()
- `tests/test_metrics_observability.py` - 17 tests: signal quality, IRTT dedup, run_cycle integration
- `tests/test_storage_schema.py` - Updated expected_keys for 18 total STORED_METRICS

## Decisions Made

- Signal quality metrics use full precision (no rounding) -- SQLite REAL handles float64
- IRTT dedup uses time.monotonic() timestamp from IRTTResult (not wall clock), matching IRTTThread cache design
- outlier_count (int) cast to float() for STORED_METRICS REAL column consistency
- Metrics batch extended in-place before single write_metrics_batch call (no extra DB transaction)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_storage_schema expected keys**

- **Found during:** Task 2 (GREEN phase, full test suite regression)
- **Issue:** test_stored_metrics_has_expected_keys expected 10 keys, now 18
- **Fix:** Added 8 new metric names to expected_keys set
- **Files modified:** tests/test_storage_schema.py
- **Verification:** All 22 schema tests pass
- **Committed in:** 452ec61 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test update necessary for correctness after schema change. No scope creep.

## Issues Encountered

- WANController constructor signature differs from plan's interface section (5 positional args, not config-only); tests adapted to match existing fixture pattern from test_wan_controller.py

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 8 metrics now queryable via existing /metrics/history API
- Health endpoint extension (92-01) can reference these metrics for signal quality and IRTT sections
- No new dependencies or configuration changes needed

## Self-Check: PASSED

- All 4 modified/created files exist
- All 3 commit hashes verified in git log
- STORED_METRICS: 18 entries (correct)
- 8 signal/irtt metrics in schema.py (correct)
- 8 signal/irtt metrics in autorate_continuous.py (correct)
- 3 \_last_irtt_write_ts references (init + compare + assign)

---

_Phase: 92-observability_
_Completed: 2026-03-17_
