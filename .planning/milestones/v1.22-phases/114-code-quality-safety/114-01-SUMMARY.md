---
phase: 114-code-quality-safety
plan: 01
subsystem: error-handling
tags: [exception-handling, logging, code-quality, audit]

requires:
  - phase: 112-foundation-scan
    provides: "Ruff rule expansion and baseline complexity data"
provides:
  - "Full triage of all 96 except Exception catches with dispositions"
  - "5 bug-swallowing catches fixed with logging"
affects: [114-02, 114-03]

tech-stack:
  added: []
  patterns: ["DEBUG-level logging for non-critical cleanup catch blocks"]

key-files:
  created:
    - ".planning/phases/114-code-quality-safety/114-01-exception-triage.md"
  modified:
    - "src/wanctl/router_client.py"
    - "src/wanctl/rtt_measurement.py"
    - "src/wanctl/benchmark.py"
    - "src/wanctl/calibrate.py"

key-decisions:
  - "UI widget catches (5) classified as acceptable safety nets -- logging would spam at 20Hz"
  - "Shutdown nosec B110 catches (3) accepted as intentional -- annotated best-effort cleanup"
  - "All fixes use DEBUG level to avoid noise in production logs"
  - "calibrate.py fix uses print_error() for consistency with CLI output pattern"

patterns-established:
  - "Exception catch classification: safety-net (logs), framework (decorator/context manager), cleanup-reraise, intentional-silent (nosec), bug-swallowing (needs fix)"
  - "Non-critical cleanup catches should log at DEBUG with exc_info=True"

requirements-completed: [CQUAL-01, CQUAL-02]

duration: 16min
completed: 2026-03-26
---

# Phase 114 Plan 01: Exception Handling Triage Summary

**Triaged all 96 except Exception catches: 88 safety nets, 5 bug-swallowing catches fixed with DEBUG logging**

## Performance

- **Duration:** 16 min
- **Started:** 2026-03-26T21:16:16Z
- **Completed:** 2026-03-26T21:32:16Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Complete triage of all 96 `except Exception` catches in codebase with documented dispositions
- 5 bug-swallowing catches identified and fixed with logging (no exception types narrowed)
- Exception count unchanged at 96 -- only logging added, no control flow changes
- All 3,760+ unit tests pass after changes

## Task Commits

Each task was committed atomically:

1. **Task 1: Triage all except Exception catches** - `0b4bf21` (docs)
2. **Task 2: Fix bug-swallowing exception catches** - `e0e3f21` (fix)

## Files Created/Modified

- `.planning/phases/114-code-quality-safety/114-01-exception-triage.md` - Full triage report with dispositions for all 96 catches
- `src/wanctl/router_client.py` - Added DEBUG logging to 2 silent close() catches in failover probe
- `src/wanctl/rtt_measurement.py` - Added DEBUG logging to concurrent ping future result catch
- `src/wanctl/benchmark.py` - Added DEBUG logging to icmplib fallback catch
- `src/wanctl/calibrate.py` - Added print_error() to SSH queue rate failure catch

## Decisions Made

- UI widget catches (sparkline_panel, cycle_gauge, history_browser) classified as acceptable safety nets -- they handle Textual TUI widget lifecycle where widgets may not be mounted, and logging at 20Hz would create noise
- Shutdown nosec B110 catches (3 in autorate_continuous.py, 1 in routeros_ssh.py) accepted as intentional -- already annotated with security audit comments
- All 5 fixes use DEBUG level with exc_info=True to capture tracebacks without polluting production WARNING/ERROR logs
- calibrate.py uses print_error() instead of logger.debug() for consistency with CLI output pattern used throughout that module

## Deviations from Plan

None - plan executed exactly as written. The plan anticipated ~96 catches needing triage and identified the likely files. The actual count of bug-swallowing catches (5) was lower than the implicit expectation, as most catches already had proper logging.

## Issues Encountered

- Dashboard test import failure (httpx not installed in venv) -- pre-existing, not related to changes
- Integration test flaky failure (p99 latency timing) -- pre-existing, not related to changes
- Deployment contract version spec mismatch -- pre-existing, not related to changes

## Known Stubs

None - all changes are complete logging additions with no placeholder data.

## Next Phase Readiness

- Exception handling audit complete, triage report available for reference
- Findings inform 114-02 (thread safety) and 114-03 (complexity/SIGUSR1) work
- No blockers for parallel plans

## Self-Check: PASSED

All artifacts verified:

- Triage file: FOUND
- Summary file: FOUND
- Task 1 commit (0b4bf21): FOUND
- Task 2 commit (e0e3f21): FOUND
- All 4 modified source files: FOUND

---

_Phase: 114-code-quality-safety_
_Completed: 2026-03-26_
