---
phase: 146-test-cleanup-organization
plan: 01
subsystem: testing
tags: [pytest, test-organization, refactoring, helpers]

# Dependency graph
requires: []
provides:
  - tests/steering/ subdirectory with 9 steering test files and steering conftest.py
  - tests/backends/ subdirectory with 4 backend test files and backends conftest.py
  - tests/helpers.py shared factory functions (find_free_port, make_host_result)
  - mock_steering_config fixture relocated to tests/steering/conftest.py
affects: [146-02, 146-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Subpackage conftest.py for domain-specific fixtures"
    - "Shared test factory functions in tests/helpers.py (not conftest)"
    - "Test file names mirror source module names (test_linux_cake.py -> linux_cake.py)"

key-files:
  created:
    - tests/helpers.py
    - tests/steering/__init__.py
    - tests/steering/conftest.py
    - tests/backends/__init__.py
    - tests/backends/conftest.py
  modified:
    - tests/conftest.py

key-decisions:
  - "make_host_result in helpers.py includes full attribute set (min_rtt, avg_rtt, max_rtt, packets_sent, packets_received, jitter) for compatibility with test_rtt_measurement.py consumers"
  - "Pre-existing C901 lint error in tests/integration/framework/report_generator.py left out of scope per deviation rules"

patterns-established:
  - "Subpackage test directories: tests/{subpackage}/ mirrors src/wanctl/{subpackage}/"
  - "Domain fixtures in subpackage conftest.py, shared utilities in tests/helpers.py"

requirements-completed: [TEST-04]

# Metrics
duration: 64min
completed: 2026-04-06
---

# Phase 146 Plan 01: Test Restructuring Infrastructure Summary

**Deleted 18 stale phase tests, extracted shared helpers, moved 9 steering and 4 backends test files into mirrored subdirectories with dedicated conftest.py files**

## Performance

- **Duration:** 64 min
- **Started:** 2026-04-06T13:20:16Z
- **Completed:** 2026-04-06T14:24:01Z
- **Tasks:** 3
- **Files modified:** 29

## Accomplishments
- Deleted stale test_phase52_validation.py and test_phase53_code_cleanup.py (18 tests removed, all covered by later phases)
- Created tests/helpers.py with deduplicated find_free_port (7 copies) and make_host_result (1 copy)
- Moved 9 steering test files to tests/steering/ with mock_steering_config fixture relocated from root conftest.py
- Moved 4 backends test files to tests/backends/ with renames to mirror source module names
- Kept test_routeros_rest.py and test_routeros_ssh.py at top level (they test top-level modules, not backends/)
- All 4160 tests collected, 514 steering + 177 backends verified passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Baseline snapshot + stale file removal + create helpers.py** - `48e288a` (refactor)
2. **Task 2: Move steering test files into tests/steering/ subdirectory** - `44c6365` (refactor)
3. **Task 3: Move backends test files into tests/backends/ subdirectory** - `ac10d4f` (refactor)

## Files Created/Modified
- `tests/helpers.py` - Shared factory functions (find_free_port, make_host_result)
- `tests/steering/__init__.py` - Package marker for pytest discovery
- `tests/steering/conftest.py` - Steering fixtures (mock_steering_config moved from root)
- `tests/backends/__init__.py` - Package marker for pytest discovery
- `tests/backends/conftest.py` - Backends fixtures (minimal, no shared fixtures needed)
- `tests/conftest.py` - Removed mock_steering_config, updated comment block
- `tests/test_health_check.py` - Replaced inline find_free_port with import
- `tests/test_steering_health.py` - Replaced inline find_free_port with import
- `tests/test_health_alerting.py` - Replaced inline find_free_port with import
- `tests/test_health_check_history.py` - Replaced inline find_free_port with import
- `tests/test_asymmetry_health.py` - Replaced inline find_free_port with import
- `tests/test_metrics.py` - Replaced inline find_free_port with import
- `tests/test_hysteresis_observability.py` - Replaced inline find_free_port with import
- `tests/test_rtt_measurement.py` - Replaced inline make_host_result with import
- 9 steering test files moved to tests/steering/
- 4 backends test files moved to tests/backends/ (2 renamed to mirror source modules)

## Decisions Made
- make_host_result includes all attributes from the original test_rtt_measurement.py version (min_rtt, avg_rtt, max_rtt, packets_sent, packets_received, jitter) rather than the simplified version from the plan, to maintain compatibility
- Pre-existing C901 lint violation in tests/integration/framework/report_generator.py (_write_markdown complexity 17 > 15) left out of scope -- confirmed present before plan changes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added .venv symlink to .gitignore**
- **Found during:** Task 1
- **Issue:** Worktree agent needed symlink to main project .venv; generated .venv entry showed as untracked
- **Fix:** Added .venv to .gitignore
- **Files modified:** .gitignore
- **Verification:** git status clean
- **Committed in:** 48e288a (Task 1 commit)

**2. [Rule 1 - Bug] Fixed import sort ordering after adding tests.helpers import**
- **Found during:** Task 1
- **Issue:** ruff I001 import sort violation in test_hysteresis_observability.py after adding `from tests.helpers import find_free_port`
- **Fix:** Ran `ruff check --select I001 --fix tests/`
- **Files modified:** tests/test_hysteresis_observability.py
- **Verification:** ruff check passes
- **Committed in:** 48e288a (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Minor fixes necessary for clean commits. No scope creep.

## Issues Encountered
- Full test suite with coverage too slow to run in worktree environment with concurrent agents (4160 tests). Verified affected test groups individually (309 + 514 + 177 tests). Test collection count verified at 4160 (correct: 4178 baseline - 18 stale = 4160).
- Pre-existing C901 lint violation prevents `make ci` from passing, but this is not caused by plan changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- tests/steering/ and tests/backends/ directories established with conftest.py files
- tests/helpers.py available for additional shared utilities
- Ready for 146-02 (remaining test file moves) and 146-03 (further test organization)

## Self-Check: PASSED

All created files exist. All commits verified. All moved files in correct locations.
All removed files confirmed absent. routeros test files correctly at top level.

---
*Phase: 146-test-cleanup-organization*
*Completed: 2026-04-06*
