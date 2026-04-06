---
phase: 144-module-splitting
plan: 03
subsystem: infra
tags: [refactoring, module-extraction, python-imports, cli-tools]

# Dependency graph
requires: [144-01]
provides:
  - "check_config_validators.py with all autorate/steering validators (1,235 LOC)"
  - "check_cake_fix.py with fix infrastructure (342 LOC)"
  - "calibrate_measurements.py with measurement functions + CalibrationResult (467 LOC)"
  - "benchmark_compare.py with compare/history subcommands (333 LOC)"
  - "check_config.py reduced from 1,558 to 340 LOC"
  - "check_cake.py reduced from 1,423 to 1,114 LOC"
  - "calibrate.py reduced from 1,130 to 752 LOC"
  - "benchmark.py reduced from 1,010 to 723 LOC"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Local import in check_config.main() to avoid circular dependency (validators import CheckResult/Severity from check_config)"
    - "Local import in check_cake_fix.run_fix() and _extract_changes_for_direction() to avoid circular dependency (check_cake_fix <-> check_cake)"
    - "Self-contained calibrate_measurements.py duplicates Colors/print helpers to avoid circular dependency with calibrate.py"
    - "Self-contained benchmark_compare.py duplicates _GRADE_COLORS/_colorize to avoid circular dependency with benchmark.py"

key-files:
  created:
    - src/wanctl/check_config_validators.py
    - src/wanctl/check_cake_fix.py
    - src/wanctl/calibrate_measurements.py
    - src/wanctl/benchmark_compare.py
  modified:
    - src/wanctl/check_config.py
    - src/wanctl/check_cake.py
    - src/wanctl/calibrate.py
    - src/wanctl/benchmark.py
    - tests/test_check_config.py
    - tests/test_check_config_smoke.py
    - tests/test_check_cake.py
    - tests/test_calibrate.py
    - tests/test_benchmark.py

key-decisions:
  - "Used local import in check_config.main() for validator dispatchers to break circular dependency (validators need CheckResult/Severity from check_config)"
  - "Used local imports in check_cake_fix.py for check_cake functions (run_audit, check_daemon_lock, etc.) to break circular dependency"
  - "Duplicated Colors/print_* helpers in calibrate_measurements.py rather than creating circular import with calibrate.py -- 30 LOC cost for clean separation"
  - "Duplicated _GRADE_COLORS/_colorize in benchmark_compare.py rather than importing from benchmark.py -- 12 LOC cost for clean separation"
  - "Moved set_cake_limit to calibrate_measurements.py since binary_search_optimal_rate depends on it"

patterns-established:
  - "CLI tool modules keep main() and CLI-specific code, extract reusable logic to companion modules"
  - "calibrate.py re-imports measurement functions for backward compatibility and step-function namespace lookup"

requirements-completed: [CPLX-01]

# Metrics
duration: 103min
completed: 2026-04-06
---

# Phase 144 Plan 03: CLI Tool Module Splitting Summary

**Split 4 CLI tool modules (check_config, check_cake, calibrate, benchmark) into 8 focused modules, extracting validators, fix infrastructure, measurements, and comparison logic**

## Performance

- **Duration:** 103 min
- **Started:** 2026-04-06T00:12:45Z
- **Completed:** 2026-04-06T01:55:49Z
- **Tasks:** 3
- **Files modified:** 13 (4 new modules, 9 existing files updated)

## Accomplishments

- Extracted check_config validators (1,235 LOC) to check_config_validators.py
- Extracted check_cake fix infrastructure (342 LOC) to check_cake_fix.py
- Extracted calibrate measurements + CalibrationResult (467 LOC) to calibrate_measurements.py
- Extracted benchmark compare/history subcommands (333 LOC) to benchmark_compare.py
- All 4,176 tests pass with zero behavioral changes
- All 5 CLI entry points verified working (pyproject.toml unchanged)
- All 8 new modules (from Plans 01-03) import cleanly with no circular imports
- Ruff clean, vulture dead-code clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Split check_config.py and check_cake.py** - `25ec982` (feat)
2. **Task 2: Split calibrate.py and benchmark.py** - `cee0450` (feat)
3. **Task 3: Final LOC verification and phase gate** - `7d47028` (chore)

## Files Created/Modified

- `src/wanctl/check_config_validators.py` - All autorate/steering validators + KNOWN_*_PATHS registries + dispatcher functions
- `src/wanctl/check_cake_fix.py` - Snapshot management, diff display, interactive fix workflow, change extraction
- `src/wanctl/calibrate_measurements.py` - CalibrationResult, connectivity tests, RTT/throughput measurement, binary search
- `src/wanctl/benchmark_compare.py` - Delta computation, formatted comparison, history table display
- `src/wanctl/check_config.py` - Reduced to data model (Severity, CheckResult), type detection, output formatting, CLI
- `src/wanctl/check_cake.py` - Reduced to audit checks, config extraction, orchestrator, client creation, CLI
- `src/wanctl/calibrate.py` - Reduced to constants, UI helpers, config generation, wizard steps, CLI
- `src/wanctl/benchmark.py` - Reduced to grade computation, BenchmarkResult, storage, flent parsing, CLI
- `tests/test_check_config.py` - Updated imports to reference check_config_validators
- `tests/test_check_config_smoke.py` - Updated KNOWN_AUTORATE_PATHS import source
- `tests/test_check_cake.py` - Updated fix function imports and mock patch targets to check_cake_fix
- `tests/test_calibrate.py` - Updated measurement imports and mock patch targets to calibrate_measurements
- `tests/test_benchmark.py` - Updated compare/history imports to benchmark_compare

## LOC Distribution After Phase 144

| Module | Before | After | Delta | Notes |
|--------|--------|-------|-------|-------|
| autorate_continuous.py | 5,218 | 1,095 | -4,123 | Plans 01-02 |
| wan_controller.py | - | 2,579 | +2,579 | Plan 02 |
| autorate_config.py | - | 1,200 | +1,200 | Plan 01 |
| queue_controller.py | - | 347 | +347 | Plan 01 |
| routeros_interface.py | - | 50 | +50 | Plan 01 |
| check_config.py | 1,558 | 340 | -1,218 | Plan 03 |
| check_config_validators.py | - | 1,235 | +1,235 | Plan 03 |
| check_cake.py | 1,423 | 1,114 | -309 | Plan 03 |
| check_cake_fix.py | - | 342 | +342 | Plan 03 |
| calibrate.py | 1,130 | 752 | -378 | Plan 03 |
| calibrate_measurements.py | - | 467 | +467 | Plan 03 |
| benchmark.py | 1,010 | 723 | -287 | Plan 03 |
| benchmark_compare.py | - | 333 | +333 | Plan 03 |

**Known Phase 145 targets (exceed 500 LOC):**
- `wan_controller.py` (2,579) -- WANController is a single class, method extraction scope
- `autorate_config.py` (1,200) -- Config class with extensive YAML loading
- `check_config_validators.py` (1,235) -- 13 validator functions, each small and independent
- `check_cake.py` (1,114) -- Tightly coupled audit check functions
- `autorate_continuous.py` (1,095) -- main() is 650 LOC orchestrator
- `calibrate.py` (752) -- Wizard step functions tightly coupled to UI
- `benchmark.py` (723) -- Grade display + flent parsing + CLI

## Decisions Made

- **Circular dependency strategy:** Used local imports in check_config.main() and check_cake_fix functions rather than creating intermediate shared modules. This keeps the module count manageable while breaking import cycles.
- **Duplication over coupling:** Duplicated Colors/print helpers (30 LOC) in calibrate_measurements.py and _GRADE_COLORS/_colorize (12 LOC) in benchmark_compare.py to avoid circular imports. The cost is trivial compared to the complexity of shared helper modules.
- **Mock patch retargeting:** Tests that call functions directly needed patches on the new module. Tests that call step-helper functions (which re-import) needed patches on the original module's namespace.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Circular import between check_config and check_config_validators**
- **Found during:** Task 1
- **Issue:** check_config_validators imports CheckResult/Severity from check_config, and check_config imports dispatchers from check_config_validators at top level
- **Fix:** Moved check_config's import of validators into main() as a local import
- **Files modified:** src/wanctl/check_config.py
- **Committed in:** 25ec982

**2. [Rule 1 - Bug] Circular import between calibrate and calibrate_measurements**
- **Found during:** Task 2
- **Issue:** calibrate_measurements importing Colors/print helpers from calibrate creates circular dependency
- **Fix:** Duplicated Colors class and print helper functions in calibrate_measurements.py (self-contained module)
- **Files modified:** src/wanctl/calibrate_measurements.py
- **Committed in:** cee0450

**3. [Rule 1 - Bug] Mock patch targets needed retargeting for step-helper vs direct function tests**
- **Found during:** Task 2
- **Issue:** Step-helper tests in test_calibrate.py patch functions in calibrate's namespace (re-imported), while direct tests patch in calibrate_measurements' namespace. Bulk replacement broke step-helper tests.
- **Fix:** Selectively fixed step-helper test patches back to wanctl.calibrate.* while keeping direct test patches as wanctl.calibrate_measurements.*
- **Files modified:** tests/test_calibrate.py
- **Committed in:** cee0450

**4. [Rule 1 - Bug] Import sorting violation in check_cake.py**
- **Found during:** Task 1
- **Issue:** check_cake_fix import was placed before check_config imports, violating ruff isort rules
- **Fix:** Ran ruff --fix to auto-sort imports
- **Files modified:** src/wanctl/check_cake.py
- **Committed in:** 25ec982

**5. [Rule 1 - Bug] Unused imports in benchmark.py and calibrate.py after extraction**
- **Found during:** Task 2
- **Issue:** tabulate, query_benchmarks, re, statistics, subprocess, dataclass, Any imports no longer needed after function extraction
- **Fix:** Removed unused imports from residual modules
- **Files modified:** src/wanctl/benchmark.py, src/wanctl/calibrate.py
- **Committed in:** cee0450

**6. [Rule 1 - Bug] Missing argparse import in benchmark_compare.py**
- **Found during:** Task 2
- **Issue:** run_compare and run_history use argparse.Namespace type annotation but argparse wasn't imported
- **Fix:** Added argparse import
- **Files modified:** src/wanctl/benchmark_compare.py
- **Committed in:** cee0450

---

**Total deviations:** 6 auto-fixed (6x Rule 1 - bugs from relocated code references and circular imports)
**Impact on plan:** All fixes necessary for correctness. Circular import resolution was the primary challenge. No scope creep.

## Issues Encountered

- Pre-existing test failure: `test_production_steering_yaml_no_unknown_keys` fails due to missing `configs/steering.yaml` file -- not caused by this plan.
- Pre-existing flaky test: `test_max_delay_caps_backoff` timing-sensitive assertion -- not caused by this plan.
- Pre-existing mypy errors: 25 errors in 5 files (3 moved to check_cake_fix.py from check_cake.py) -- 0 new errors introduced.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

- All 4 new module files exist with correct class/function definitions
- All 3 task commits found in git history
- All 8 new modules importable without error
- All 5 CLI entry points verified
- 4,176 tests pass (2 pre-existing deselections)
- Vulture dead code check passes
- Ruff lint check passes

---
*Phase: 144-module-splitting*
*Completed: 2026-04-06*
