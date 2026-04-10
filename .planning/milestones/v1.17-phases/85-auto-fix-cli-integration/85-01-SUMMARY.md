---
phase: 85-auto-fix-cli-integration
plan: 01
subsystem: api
tags: [routeros, rest, cake, queue-type, lock-utils, snapshots]

# Dependency graph
requires:
  - phase: 84-cake-detection-optimizer-foundation
    provides: OPTIMAL_CAKE_DEFAULTS, OPTIMAL_WASH constants, get_queue_types(), check_cake_params()
provides:
  - set_queue_type_params() PATCH method on RouterOSREST
  - check_daemon_lock() safety gate for --fix mode
  - _save_snapshot() and _prune_snapshots() for rollback support
  - _extract_changes_for_direction() for deriving sub-optimal params
affects: [85-02-PLAN, auto-fix orchestrator, wanctl-check-cake --fix]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      GET-then-PATCH for queue type writes,
      lock PID liveness check,
      timestamped JSON snapshots,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/routeros_rest.py
    - src/wanctl/check_cake.py
    - tests/test_check_cake.py

key-decisions:
  - "set_queue_type_params uses inline GET+PATCH (not _find_resource_id cache) since queue types are write-once operations"
  - "Snapshots use json.dump (not atomic_write_json) since they are one-shot archival writes, not concurrent state"
  - "_extract_changes_for_direction returns (actual, expected) tuples for both display and PATCH payload derivation"
  - "datetime.UTC alias used instead of timezone.utc for Python 3.11+ modern style (ruff UP017)"

patterns-established:
  - "Queue type PATCH pattern: GET /queue/type?name=X to find .id, PATCH /queue/type/{id} with string params"
  - "Snapshot naming: {UTC_timestamp}_{wan_name}.json with chronological sort by filename"
  - "Lock check safety gate: glob /run/wanctl/*.lock, read PID, check liveness before destructive operations"

requirements-completed: [FIX-02, FIX-04, FIX-05]

# Metrics
duration: 13min
completed: 2026-03-13
---

# Phase 85 Plan 01: Fix Infrastructure Summary

**RouterOSREST queue type PATCH method, daemon lock safety gate, snapshot persistence, and change extraction helpers for CAKE auto-fix**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-13T18:37:19Z
- **Completed:** 2026-03-13T18:50:24Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- set_queue_type_params() on RouterOSREST: GET-then-PATCH to /rest/queue/type endpoint with string-enforced params
- check_daemon_lock() safety gate: prevents --fix when wanctl daemon is running (PID liveness check via lock_utils)
- \_save_snapshot() + \_prune_snapshots(): JSON snapshots to /var/lib/wanctl/snapshots/ with MAX_SNAPSHOTS=20 auto-prune
- \_extract_changes_for_direction(): derives sub-optimal params from OPTIMAL_CAKE_DEFAULTS/OPTIMAL_WASH constants without message parsing
- 17 new tests (6 for set_queue_type_params, 11 for lock/snapshot/extraction), 109 total in test_check_cake.py, 2882 unit tests passing

## Task Commits

Each task was committed atomically (TDD: red then green):

1. **Task 1: set_queue_type_params() PATCH method**
   - `a4e23d4` (test: failing tests for set_queue_type_params)
   - `c7d8a62` (feat: implement set_queue_type_params on RouterOSREST)
2. **Task 2: Daemon lock check, snapshot persistence, change extraction**
   - `401b06e` (test: failing tests for daemon lock, snapshots, change extraction)
   - `8e9ac17` (feat: implement daemon lock check, snapshots, and change extraction)

## Files Created/Modified

- `src/wanctl/routeros_rest.py` - Added set_queue_type_params() method after get_queue_types()
- `src/wanctl/check_cake.py` - Added check_daemon_lock(), \_save_snapshot(), \_prune_snapshots(), \_extract_changes_for_direction() with LOCK_DIR/SNAPSHOT_DIR/MAX_SNAPSHOTS constants
- `tests/test_check_cake.py` - Added TestSetQueueTypeParams, TestDaemonLock, TestSnapshot, TestExtractChanges classes

## Decisions Made

- set_queue_type_params uses inline GET+PATCH rather than \_find_resource_id cache, since queue type writes are infrequent one-shot operations (not hot-path like queue tree limit changes)
- Snapshots use simple json.dump rather than atomic_write_json since they are archival writes without concurrent access concerns
- \_extract_changes_for_direction returns dict[str, tuple[str, str]] with (actual, expected) tuples -- the expected value can be directly used as the PATCH payload value in Plan 02
- Used datetime.UTC alias (Python 3.11+) instead of timezone.utc per ruff UP017

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff UP017 linting violation**

- **Found during:** Task 2 (implementation)
- **Issue:** `timezone.utc` triggers ruff UP017 "Use datetime.UTC alias" in Python 3.11+ codebases
- **Fix:** Changed `from datetime import datetime, timezone` to `from datetime import UTC, datetime` and `datetime.now(timezone.utc)` to `datetime.now(UTC)`
- **Files modified:** src/wanctl/check_cake.py
- **Verification:** `ruff check src/wanctl/check_cake.py` passes, all tests pass
- **Committed in:** 8e9ac17 (amended into Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug/lint)
**Impact on plan:** Trivial lint fix, no scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All primitives ready for Plan 02's orchestrator (apply_fix(), restore_snapshot(), --fix CLI flag)
- set_queue_type_params() provides the write path; \_extract_changes_for_direction() provides the diff
- check_daemon_lock() provides the safety gate; \_save_snapshot() provides rollback support

## Self-Check: PASSED

- All 4 source/test files exist
- All 4 commits verified (a4e23d4, c7d8a62, 401b06e, 8e9ac17)
- All 5 new functions found in source
- 109 test_check_cake tests passing, 2882 total unit tests passing

---

_Phase: 85-auto-fix-cli-integration_
_Completed: 2026-03-13_
