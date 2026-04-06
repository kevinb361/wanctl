---
phase: 146-test-cleanup-organization
plan: 02
subsystem: testing
tags: [pytest, test-organization, directory-structure]

# Dependency graph
requires:
  - phase: 146-test-cleanup-organization
    provides: "Phase context and D-01/D-02/D-03 directory restructuring decisions"
provides:
  - "tests/storage/ subdirectory with 6 test files and shared conftest.py"
  - "tests/tuning/ subdirectory with 16 test files and minimal conftest.py"
  - "tests/dashboard/ directory (renamed from test_dashboard) with 10 test files"
affects: [146-test-cleanup-organization]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Mirrored test directory structure: tests/{subpackage}/ matches src/wanctl/{subpackage}/"]

key-files:
  created:
    - tests/storage/__init__.py
    - tests/storage/conftest.py
    - tests/tuning/__init__.py
    - tests/tuning/conftest.py
  modified:
    - tests/storage/test_storage_downsampler.py
    - tests/storage/test_storage_retention.py
    - tests/storage/test_storage_maintenance.py

key-decisions:
  - "Extracted shared test_db fixture to storage conftest.py (used by 3 files), kept writer-specific reset_singleton local"
  - "Kept tuning conftest.py minimal -- tuning tests rely on root conftest mock_autorate_config per D-10"
  - "Removed unused pytest imports from 3 storage files after fixture extraction"

patterns-established:
  - "Shared fixtures extracted to subpackage conftest.py when 3+ files use identical pattern"
  - "Module-specific fixtures remain local to their test file"

requirements-completed: [TEST-04]

# Metrics
duration: 72min
completed: 2026-04-06
---

# Phase 146 Plan 02: Storage/Tuning/Dashboard Test Directory Restructuring Summary

**Moved 6 storage + 16 tuning test files into mirrored subdirectories and renamed test_dashboard to dashboard, with shared fixture extraction**

## Performance

- **Duration:** 72 min
- **Started:** 2026-04-06T13:20:24Z
- **Completed:** 2026-04-06T14:32:06Z
- **Tasks:** 2
- **Files modified:** 38

## Accomplishments
- Moved 6 storage test files to tests/storage/ with extracted test_db and reset_metrics_singleton shared fixtures
- Moved 16 tuning test files to tests/tuning/ with minimal conftest (tuning tests inherit root conftest fixtures)
- Renamed tests/test_dashboard/ to tests/dashboard/ preserving all 10 test files, conftest.py, and __init__.py
- All 583 tests in moved directories pass (1 pre-existing flaky dashboard test excluded)
- Removed 3 duplicate test_db fixture definitions and 3 unused pytest imports

## Task Commits

Each task was committed atomically:

1. **Task 1: Move storage test files into tests/storage/ subdirectory** - `6b8ed07` (refactor)
2. **Task 2a: Move tuning test files into tests/tuning/** - `61c7c81` (refactor)
3. **Task 2b: Rename tests/test_dashboard to tests/dashboard** - `bff98a7` (refactor)

## Files Created/Modified
- `tests/storage/__init__.py` - Package marker for pytest discovery
- `tests/storage/conftest.py` - Shared test_db and reset_metrics_singleton fixtures
- `tests/storage/test_storage_writer.py` - Moved from tests/ root
- `tests/storage/test_storage_downsampler.py` - Moved, removed duplicate test_db fixture and unused import
- `tests/storage/test_storage_retention.py` - Moved, removed duplicate test_db fixture and unused import
- `tests/storage/test_storage_schema.py` - Moved from tests/ root
- `tests/storage/test_storage_maintenance.py` - Moved, removed duplicate test_db fixture and unused import
- `tests/storage/test_config_snapshot.py` - Moved from tests/ root
- `tests/tuning/__init__.py` - Package marker for pytest discovery
- `tests/tuning/conftest.py` - Minimal docstring (tuning tests use root conftest fixtures)
- `tests/tuning/test_tuning_*.py` - 12 files moved from tests/ root
- `tests/tuning/test_advanced_tuning_strategies.py` - Moved from tests/ root
- `tests/tuning/test_response_tuning_strategies.py` - Moved from tests/ root
- `tests/tuning/test_response_tuning_wiring.py` - Moved from tests/ root
- `tests/tuning/test_congestion_threshold_strategy.py` - Moved from tests/ root
- `tests/dashboard/` - Renamed from tests/test_dashboard/ (10 test files + conftest + __init__)

## Decisions Made
- Extracted test_db fixture to storage conftest.py since 3 files (downsampler, retention, maintenance) had identical definitions
- Kept reset_metrics_singleton in conftest.py for broader reuse, but left reset_singleton local to writer (different name, no conflict)
- Did not extract _make_tuning_config helper to tuning conftest.py because the 4 copies have different bounds dictionaries
- mock_autorate_config remains in root conftest.py per D-10 (inherited by all subdirectories via pytest)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused pytest imports after fixture extraction**
- **Found during:** Task 1 (storage file moves)
- **Issue:** After removing duplicate @pytest.fixture definitions from 3 storage files, the `import pytest` became unused (ruff F401)
- **Fix:** Removed unused `import pytest` from test_storage_downsampler.py, test_storage_retention.py, test_storage_maintenance.py
- **Files modified:** tests/storage/test_storage_downsampler.py, tests/storage/test_storage_retention.py, tests/storage/test_storage_maintenance.py
- **Verification:** ruff check passes with no errors
- **Committed in:** 6b8ed07 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - cleanup of unused imports caused by fixture extraction)
**Impact on plan:** Minimal. Standard cleanup following fixture deduplication.

## Issues Encountered
- Pre-existing flaky test: `tests/dashboard/test_layout.py::TestHysteresis::test_rapid_resize_does_not_switch_immediately` fails intermittently due to timing sensitivity. File is identical to base commit -- not caused by rename. Out of scope per deviation rules.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Storage, tuning, and dashboard test directories fully restructured
- Combined with Plan 01 (autorate/config/steering), all subpackage-scoped tests now live in mirrored directories
- Ready for Plan 03 (fixture consolidation and cleanup)

## Self-Check: PASSED

All created files verified present. All commit hashes verified in git log. Old file locations confirmed removed.

---
*Phase: 146-test-cleanup-organization*
*Completed: 2026-04-06*
