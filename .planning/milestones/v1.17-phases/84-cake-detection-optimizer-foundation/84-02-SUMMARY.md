---
phase: 84-cake-detection-optimizer-foundation
plan: 02
subsystem: networking
tags: [cake, routeros, qdisc, param-detection, check-tool]

# Dependency graph
requires:
  - phase: 84-01
    provides: "get_queue_types(), OPTIMAL_CAKE_DEFAULTS, OPTIMAL_WASH, _extract_cake_optimization()"
provides:
  - "check_cake_params() for link-independent CAKE param detection with WARNING severity"
  - "check_link_params() for link-dependent overhead/rtt detection with ERROR severity"
  - "run_audit() pipeline step 3.5 wiring queue type checks after queue tree audit"
  - "KNOWN_AUTORATE_PATHS updated with cake_optimization paths"
affects: [85-auto-fix-cli]

# Tech tracking
tech-stack:
  added: []
  patterns: ["direction-dependent param checking (upload vs download optimal values)", "diff format 'current -> recommended' with rationale in suggestion field"]

key-files:
  created: []
  modified:
    - src/wanctl/check_cake.py
    - src/wanctl/check_config.py
    - tests/test_check_cake.py

key-decisions:
  - "INFO-level results mapped to Severity.PASS since Severity enum has no INFO variant (consistent with max-limit informational PASS pattern)"
  - "Rationale strings stored in module-level _RATIONALE dict for maintainability"
  - "_skippable_categories() helper extracts skip-list logic to avoid duplication between env var and connectivity failure paths"
  - "Step 3.5 re-fetches queue stats rather than modifying check_queue_tree() return signature -- simpler, avoids breaking existing interface"

patterns-established:
  - "Param check pattern: compare router value against constant dict, PASS for match, WARNING/ERROR for mismatch with diff format"
  - "Direction-dependent categories: 'CAKE Params (download)' / 'CAKE Params (upload)' for per-direction output grouping"
  - "Short param names in messages: strip 'cake-' prefix for display readability"

requirements-completed: [CAKE-01, CAKE-03, CAKE-04, CAKE-05]

# Metrics
duration: 56min
completed: 2026-03-13
---

# Phase 84 Plan 02: CAKE Parameter Detection Summary

**check_cake_params() and check_link_params() functions detecting sub-optimal CAKE queue type parameters with severity, diff format, and rationale -- wired into run_audit() pipeline**

## Performance

- **Duration:** 56 min
- **Started:** 2026-03-13T11:05:45Z
- **Completed:** 2026-03-13T12:02:12Z
- **Tasks:** 2 (Task 1: TDD RED+GREEN, Task 2: integration)
- **Files modified:** 3

## Accomplishments
- Implemented `check_cake_params()` comparing 5 link-independent params (flowmode, diffserv, nat, ack-filter, wash) against optimal defaults with direction-dependent wash handling
- Implemented `check_link_params()` comparing overhead and rtt against cake_optimization YAML config values with string coercion for int-to-string comparison
- Wired both functions into run_audit() pipeline as step 3.5 (after queue tree, before mangle), with queue type data fetched via get_queue_types()
- Updated KNOWN_AUTORATE_PATHS with cake_optimization paths to prevent spurious "unknown key" warnings
- 26 new tests (12 + 7 + 6 + 1), all passing; 2,867 total tests passing, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests** - `0ea1f89` (test)
2. **Task 1 (GREEN): Implementation** - `9e1e3a1` (feat)
3. **Task 2: Pipeline integration** - `b38493b` (feat)

_TDD task 1: test commit followed by implementation commit_

## Files Created/Modified
- `src/wanctl/check_cake.py` - Added check_cake_params(), check_link_params(), _RATIONALE dict, _skippable_categories(), and run_audit() step 3.5
- `src/wanctl/check_config.py` - Added cake_optimization, cake_optimization.overhead, cake_optimization.rtt to KNOWN_AUTORATE_PATHS
- `tests/test_check_cake.py` - Added TestCheckCakeParams (12 tests), TestCheckLinkParams (7 tests), TestRunAuditCakeParams (6 tests), TestKnownPaths (1 test); updated 4 existing CLI/exit-code tests for new mock call patterns

## Decisions Made
- Used Severity.PASS for "no cake_optimization config" INFO message since Severity enum only has PASS/WARN/ERROR -- consistent with max-limit informational PASS pattern from v1.16
- Stored rationale strings in module-level _RATIONALE dict rather than inline strings for maintainability
- Step 3.5 re-fetches queue stats via client.get_queue_stats() rather than modifying check_queue_tree() return type -- simpler approach that avoids breaking the existing interface contract
- Extracted _skippable_categories() to eliminate duplication between env var skip and connectivity skip paths

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing tests for new pipeline mock requirements**
- **Found during:** Task 2
- **Issue:** 4 existing tests (test_main_clean_config_returns_0, test_main_json_output_is_valid_json, test_main_type_override, test_exit_code_0_all_pass) used side_effect lists with only 2 get_queue_stats entries, but step 3.5 makes 2 additional calls
- **Fix:** Added 2 more get_queue_stats entries and get_queue_types mock to each affected test
- **Files modified:** tests/test_check_cake.py
- **Verification:** All 92 test_check_cake tests pass; full suite 2,867 tests pass
- **Committed in:** b38493b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix in tests)
**Impact on plan:** Test fix was necessary for correctness after pipeline extension. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CAKE detection feature complete: all 5 CAKE-XX requirements satisfied
- Plan 03 (if any) or Phase 85 (Auto-Fix CLI) can build on check_cake_params() and check_link_params() results to implement fix commands
- No blockers

---
*Phase: 84-cake-detection-optimizer-foundation*
*Completed: 2026-03-13*
