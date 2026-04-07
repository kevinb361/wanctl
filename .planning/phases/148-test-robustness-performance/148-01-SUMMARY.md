---
phase: 148-test-robustness-performance
plan: 01
subsystem: tests
tags: [test-quality, brittleness, cross-module, ci]
dependency_graph:
  requires: [147-interface-decoupling]
  provides: [cross-module-patch-elimination, brittleness-ci-enforcement]
  affects: [tests, scripts, Makefile]
tech_stack:
  added: []
  patterns: [ast-based-code-analysis, public-api-testing]
key_files:
  created:
    - scripts/check_test_brittleness.py
    - tests/test_check_test_brittleness.py
  modified:
    - src/wanctl/check_cake_fix.py
    - src/wanctl/router_client.py
    - src/wanctl/autorate_continuous.py
    - tests/test_check_cake.py
    - tests/test_metrics.py
    - tests/test_router_behavioral.py
    - tests/test_fusion_healer.py
    - tests/test_autorate_entry_points.py
    - tests/test_autorate_continuous.py
    - tests/test_irtt_thread.py
    - tests/test_router_client.py
    - Makefile
decisions:
  - Promoted private functions to public API rather than mocking at higher level (simpler, preserves test intent)
  - Used AST analysis in brittleness checker to avoid false positives from string literals in test fixtures
  - Removed _check_connectivity_alerts patches in test_metrics.py (no-op for test scenario with non-None RTT)
  - Used actual SIGUSR1 signal in test_fusion_healer.py instead of mocking private event
metrics:
  duration: 20m
  completed: "2026-04-07T15:24:28Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 14
  files_created: 2
---

# Phase 148 Plan 01: Mock Retargeting & Brittleness CI Summary

Eliminated all 22 cross-module private patches in 6 test files by promoting 5 private functions to public APIs and removing unnecessary mocks, then added AST-based CI enforcement script preventing regression.

## Task Results

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Retarget 22 cross-module private patches | 9899393 | Promoted 5 functions to public, updated 11 files |
| 2 (TDD) | Create CI brittleness enforcement script | bd2098e, 334f4f5 | AST-based scanner, 7 tests, Makefile integration |

## Changes Made

### Task 1: Retarget Cross-Module Private Patches

**Source promotions (private -> public):**
- `check_cake_fix.py`: `_save_snapshot` -> `save_snapshot`, `_show_diff_table` -> `show_diff_table`, `_confirm_apply` -> `confirm_apply`
- `router_client.py`: `_create_transport_with_password` -> `create_transport_with_password`
- `autorate_continuous.py`: `_start_irtt_thread` -> `start_irtt_thread`

**Test retargeting strategies by file:**
- `test_check_cake.py` (8 patches): Updated to use promoted public function names
- `test_metrics.py` (5 patches): Removed `_check_connectivity_alerts` mocks entirely -- method is a no-op when `measured_rtt` is not None and controller is freshly constructed
- `test_router_behavioral.py` (1 patch): Updated to use promoted public function name
- `test_fusion_healer.py` (1 patch): Replaced `_reload_event` mock with actual SIGUSR1 signal via `os.kill(os.getpid(), signal.SIGUSR1)` using registered handler
- `test_autorate_entry_points.py` (1 patch): Updated to use promoted public function name
- `test_autorate_continuous.py` (1 patch): Replaced `patch.object(ssh, "_ensure_connected")` and `patch.object(ssh, "_client")` with direct instance attribute assignment + mock transport

**Additional files updated (Rule 3 - blocking):**
- `test_router_client.py`: 17 references to renamed `create_transport_with_password`
- `test_irtt_thread.py`: 6 references to renamed `start_irtt_thread`

### Task 2: CI Brittleness Enforcement Script

- Created `scripts/check_test_brittleness.py` with AST-based analysis
- Detects `patch("wanctl.MODULE._attr")` calls where MODULE differs from module under test
- AST parsing avoids false positives from patterns inside string literals
- conftest.py files exempt (shared fixtures)
- Threshold of 3 per file (D-12 safety valve), target is zero (D-11)
- Integrated into `make check-boundaries` target (runs via `make ci`)
- 7 test cases covering detection, same-module exclusion, thresholds, exemptions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated test_router_client.py and test_irtt_thread.py**
- **Found during:** Task 1
- **Issue:** Renaming `_create_transport_with_password` and `_start_irtt_thread` in source broke 23 references in same-module test files
- **Fix:** Updated all references to use the new public names
- **Files modified:** tests/test_router_client.py, tests/test_irtt_thread.py
- **Commit:** 9899393

**2. [Rule 1 - Bug] Switched from regex to AST analysis in brittleness checker**
- **Found during:** Task 2
- **Issue:** Regex-based detection matched `patch()` patterns inside string literals (test fixture content), causing false positives
- **Fix:** Rewrote `scan_file()` to use Python `ast` module, only detecting actual `patch()` function calls
- **Files modified:** scripts/check_test_brittleness.py
- **Commit:** 334f4f5

## Pre-existing Test Failures (Out of Scope)

- `TestTinDistribution::test_happy_path_all_tins_have_traffic`: `platform.py` decode error (Python 3.12 compat issue)
- `TestHealthEndpoint`: 4 tests fail due to `suppression_alert` key structure change from commit 4393064

## Decisions Made

1. **Promote vs mock-at-higher-level:** Chose to promote private functions to public API (remove underscore) rather than restructuring tests to mock at higher levels. This is simpler, preserves test intent, and the functions are genuinely useful at module boundaries.
2. **AST over regex for checker:** AST analysis costs ~30 lines more code but eliminates entire class of false positives. Worth the complexity for a CI enforcement tool.
3. **Remove _check_connectivity_alerts mocks:** Analyzed the method and confirmed it's a no-op when RTT is non-None and controller is freshly constructed. Removing the mock simplifies tests without changing behavior.
4. **Actual SIGUSR1 signal for fusion healer test:** Using `os.kill(os.getpid(), signal.SIGUSR1)` with registered handlers is more realistic than mocking the private event, and tests the actual signal flow.

## Self-Check: PASSED

- scripts/check_test_brittleness.py: FOUND
- tests/test_check_test_brittleness.py: FOUND
- Commit 9899393: FOUND
- Commit bd2098e: FOUND
- Commit 334f4f5: FOUND
