---
phase: 53-code-cleanup
plan: 02
subsystem: transport
tags: [urllib3, ruff, ssl, warnings, imports]

# Dependency graph
requires:
  - phase: 52-operational-resilience
    provides: "SSL verify_ssl=True default in REST client"
provides:
  - "Session-scoped InsecureRequestWarning suppression (only when verify_ssl=False)"
  - "Zero ruff violations across entire src/"
affects: [routeros-rest, rtt-measurement]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conditional warning suppression in __init__ rather than module-level side effects"
    - "noqa: F401 for imports retained only for test patching"

key-files:
  created: []
  modified:
    - src/wanctl/routeros_rest.py
    - src/wanctl/rtt_measurement.py

key-decisions:
  - "Keep urllib3.disable_warnings in __init__ conditional on verify_ssl=False rather than per-request context manager -- urllib3 warnings are inherently global, but scoping the call to instantiation matches the semantic intent"
  - "Use noqa: F401 for subprocess import in rtt_measurement.py -- ruff supports inline noqa comments, removing need for bare expression workaround"

patterns-established:
  - "Warning suppression scoped to constructor, not module import"

requirements-completed: [CLEAN-05, CLEAN-06]

# Metrics
duration: 13min
completed: 2026-03-07
---

# Phase 53 Plan 02: Warning Suppression Scoping & Ruff Cleanup Summary

**Scoped InsecureRequestWarning suppression to REST client __init__ (verify_ssl=False only) and eliminated all 4 ruff violations in rtt_measurement.py**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-07T15:49:27Z
- **Completed:** 2026-03-07T16:02:30Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Removed process-global `disable_warnings` call from module-level import in routeros_rest.py
- InsecureRequestWarning suppression now only fires when a RouterOSREST client is instantiated with `verify_ssl=False`
- Fixed all 4 ruff violations in rtt_measurement.py (I001, B018, E402 x2) by removing bare subprocess expression and using proper noqa comment
- `ruff check src/` now reports zero violations across entire codebase

## Task Commits

Each task was committed atomically:

1. **Task 1: Scope InsecureRequestWarning and fix ruff violations** - `615c083` (fix)

## Files Created/Modified
- `src/wanctl/routeros_rest.py` - Moved disable_warnings from module level to __init__ conditional
- `src/wanctl/rtt_measurement.py` - Fixed import ordering, removed bare expression, added noqa: F401

## Decisions Made
- Kept `urllib3.disable_warnings(InsecureRequestWarning)` call (not `warnings.filterwarnings`) because it's the standard urllib3 API and matches existing codebase patterns
- The suppression is scoped to instantiation time rather than per-request because urllib3 warning state is inherently global -- the semantic improvement is that it only executes when verify_ssl=False is explicitly opted into
- Used `# noqa: F401` for subprocess import since ruff respects it natively, removing the need for the pyflakes bare-expression workaround

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 53 code cleanup complete (both plans done)
- Ready for Phase 54 (Codebase Audit)
- All 2037 tests passing

---
*Phase: 53-code-cleanup*
*Completed: 2026-03-07*
