---
phase: 38-storage-foundation
plan: 02
subsystem: database
tags: [sqlite, downsampling, retention, metrics, time-series]

# Dependency graph
requires:
  - phase: 38-01
    provides: MetricsWriter, METRICS_SCHEMA, create_tables
provides:
  - Retention cleanup with batch processing
  - Downsampling logic (raw->1m->5m->1h)
  - Storage configuration schema and helpers
  - Complete storage module exports
affects: [39-data-recording, 40-query-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Batch processing for database operations (10000 rows/transaction)
    - MODE aggregation for state/boolean metrics, AVG for numeric
    - Timestamp alignment to bucket boundaries for downsampling

key-files:
  created:
    - src/wanctl/storage/retention.py
    - src/wanctl/storage/downsampler.py
    - tests/test_storage_retention.py
    - tests/test_storage_downsampler.py
  modified:
    - src/wanctl/storage/__init__.py
    - src/wanctl/config_base.py
    - tests/test_config_base.py

key-decisions:
  - "Batch deletion in 10000-row chunks to avoid blocking daemon"
  - "VACUUM only after 100000+ deletions (expensive operation)"
  - "MODE aggregation for state metrics, AVG for RTT/rate"
  - "Bucket alignment for predictable downsampling behavior"

patterns-established:
  - "Align timestamps to bucket boundaries for time-series aggregation"
  - "Use isolation_level=None for SQLite WAL mode compatibility"

# Metrics
duration: 8min
completed: 2026-01-25
---

# Phase 38 Plan 02: Downsampling & Retention Summary

**Retention cleanup with batch processing and downsampling (raw->1m->5m->1h) with configurable thresholds**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-25T19:06:05Z
- **Completed:** 2026-01-25T19:14:22Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Retention cleanup deletes data older than configurable retention period (default 7 days)
- Batch processing (10000 rows/transaction) prevents blocking daemon cycles
- Downsampling reduces granularity: raw->1m after 1h, 1m->5m after 1d, 5m->1h after 7d
- AVG aggregation for RTT/rate metrics, MODE for state/boolean metrics
- Storage configuration schema with validation (retention_days: 1-365, db_path)
- 54 new tests for retention, downsampling, and config

## Task Commits

1. **Task 1: Implement retention cleanup** - `4c29820` (feat)
2. **Task 2: Implement downsampling logic** - `203af14` (feat)
3. **Task 3: Add config integration and update exports** - `07eef2a` (feat)

## Files Created/Modified

- `src/wanctl/storage/retention.py` - Batch cleanup of expired metrics, conditional VACUUM
- `src/wanctl/storage/downsampler.py` - Time-series aggregation with configurable thresholds
- `src/wanctl/storage/__init__.py` - Updated exports for complete module API
- `src/wanctl/config_base.py` - STORAGE_SCHEMA and get_storage_config() helper
- `tests/test_storage_retention.py` - 19 tests for retention cleanup
- `tests/test_storage_downsampler.py` - 24 tests for downsampling
- `tests/test_config_base.py` - 11 tests for storage config

## Decisions Made

- **Batch size 10000:** Balance between throughput and lock duration at 50ms cycles
- **VACUUM threshold 100000:** Only reclaim space after significant cleanup
- **MODE for state metrics:** Most common value in bucket (averaging states meaningless)
- **Bucket alignment:** Timestamp alignment to boundaries for predictable aggregation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Bucket alignment:** Initial tests failed due to non-aligned timestamps crossing bucket boundaries. Fixed by using `align_to_bucket()` helper in tests to ensure predictable bucket counts.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Storage module complete: writer, schema, retention, downsampling
- Ready for Phase 39 (Data Recording) to integrate storage with autorate daemon
- Configuration schema available for daemon YAML integration

---
*Phase: 38-storage-foundation*
*Completed: 2026-01-25*
