---
phase: 147-interface-decoupling
plan: 01
subsystem: infra
tags: [typing-protocol, ast, ci-enforcement, structural-subtyping]

# Dependency graph
requires: []
provides:
  - "interfaces.py with 4 Protocol definitions (HealthDataProvider, Reloadable, TunableController, ThreadManager)"
  - "AST-based boundary check script detecting cross-module private attribute access"
  - "make check-boundaries CI target preventing regression"
affects: [147-02, 147-03, 147-04]

# Tech tracking
tech-stack:
  added: []
  patterns: ["typing.Protocol for module boundary interfaces", "AST-based CI enforcement with allowlist"]

key-files:
  created:
    - src/wanctl/interfaces.py
    - scripts/check_private_access.py
    - tests/test_boundary_check.py
  modified:
    - Makefile
    - vulture_whitelist.py

key-decisions:
  - "All 4 Protocols use @runtime_checkable (matches existing webhook_delivery.py pattern)"
  - "Allowlist uses (file_stem, attr_name) tuples for precise violation tracking"
  - "73 unique allowlist entries covering 109 total violations across 6 coupling boundaries"

patterns-established:
  - "Protocol definitions in interfaces.py with stdlib-only imports and from __future__ import annotations"
  - "AST-based boundary enforcement via check_file() with allowlist-based regression detection"

requirements-completed: [CPLX-03]

# Metrics
duration: 8min
completed: 2026-04-06
---

# Phase 147 Plan 01: Interface Foundation Summary

**4 runtime-checkable Protocol definitions in interfaces.py plus AST boundary check script with 109-violation allowlist and CI integration**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-06T19:07:00Z
- **Completed:** 2026-04-06T19:15:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created interfaces.py with HealthDataProvider, Reloadable, TunableController, ThreadManager protocols
- Built AST-based check_private_access.py that detects cross-module private attribute access
- Catalogued all 109 violations (73 unique file/attr pairs) across 6 coupling boundaries
- Integrated into CI via make check-boundaries (added to make ci recipe)
- 8 tests covering detection, exclusion rules, exit codes, and summary output

## Task Commits

Each task was committed atomically:

1. **Task 1: Create interfaces.py with Protocol definitions** - `c60fd67` (feat)
2. **Task 2: Create AST-based boundary check script with CI integration**
   - RED: `c7f367c` (test -- failing tests)
   - GREEN: `b4e02db` (feat -- script, Makefile, vulture whitelist)
   - Lint fix: `b1ed059` (fix -- import ordering)

## Files Created/Modified
- `src/wanctl/interfaces.py` - 4 Protocol definitions for module boundary interfaces
- `scripts/check_private_access.py` - AST-based cross-module private access detector with allowlist
- `tests/test_boundary_check.py` - 8 tests for the boundary check script
- `Makefile` - Added check-boundaries target, included in ci recipe
- `vulture_whitelist.py` - Added interfaces.py Protocol classes and methods

## Decisions Made
- Used @runtime_checkable on all protocols (consistent with existing AlertFormatter pattern in webhook_delivery.py)
- AST-based approach over grep for accuracy (correctly handles self._, cls._, __dunder__, chained access)
- Allowlist keyed on (file_stem, attr_name) tuples rather than full path for portability
- Script returns exit code 0 when all violations are allowlisted, exit code 1 on any new violation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed import ordering in interfaces.py**
- **Found during:** Post-task CI verification
- **Issue:** ruff I001 flagged unsorted import block (blank line between `__future__` and `typing` imports)
- **Fix:** Ran `ruff check --fix` to reorder imports
- **Files modified:** src/wanctl/interfaces.py
- **Verification:** `ruff check src/wanctl/interfaces.py` passes
- **Committed in:** b1ed059

**2. [Rule 2 - Missing Critical] Added vulture whitelist entries for interfaces.py**
- **Found during:** Task 2 CI verification
- **Issue:** vulture flagged all 4 Protocol classes and their methods as unused (they're structural typing definitions with no runtime callers yet)
- **Fix:** Added whitelist entries for all Protocol classes and methods
- **Files modified:** vulture_whitelist.py
- **Verification:** `vulture src/wanctl/ vulture_whitelist.py` clean for interfaces.py
- **Committed in:** b4e02db (part of Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both necessary for CI compliance. No scope creep.

## Issues Encountered
- Worktree `.venv` symlink needed for `make check-boundaries` to work (the Makefile uses relative `.venv/bin/python` paths like all other targets)
- Pre-existing lint failures in tests/integration/ and tests/test_fusion_healer_integration.py unrelated to this plan's changes

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- interfaces.py ready for Plans 02-04 to add implementations (WANController.get_health_data(), .reload(), etc.)
- Boundary check script ready for allowlist entries to be removed as Plans 02-04 eliminate violations
- Current count: 109 violations in allowlist across 73 unique (file, attr) pairs

---
*Phase: 147-interface-decoupling*
*Completed: 2026-04-06*
