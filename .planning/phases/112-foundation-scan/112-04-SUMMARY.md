---
phase: 112-foundation-scan
plan: 04
subsystem: code-quality
tags: [vulture, dead-code, static-analysis, whitelist, false-positive]

# Dependency graph
requires:
  - phase: 112-01
    provides: "PITFALLS.md false positive patterns and project structure analysis"
provides:
  - ".vulture_whitelist.py -- reusable false positive whitelist for future scans"
  - "112-04-findings.md -- structured dead code inventory with categorized findings"
affects: [code-cleanup, dead-code-removal, future-refactoring]

# Tech tracking
tech-stack:
  added: [vulture-2.16]
  patterns: [vulture-whitelist-per-project, false-positive-validation-checklist]

key-files:
  created:
    - .vulture_whitelist.py
    - .planning/phases/112-foundation-scan/112-04-findings.md
  modified: []

key-decisions:
  - "Whitelist approach over per-line suppression: single .vulture_whitelist.py for project-wide false positive management"
  - "80% confidence as primary threshold per STACK.md; 60% for extended analysis only"
  - "Test-only functions classified as acceptable: 53 items with active test coverage kept"
  - "4 items classified as likely dead code pending transport validation before removal"

patterns-established:
  - "Vulture whitelist: .vulture_whitelist.py in project root for CI integration"
  - "Dead code categorization: likely-dead / needs-investigation / test-only"

requirements-completed: [FSCAN-03]

# Metrics
duration: 6min
completed: 2026-03-26
---

# Phase 112 Plan 04: Vulture Dead Code Inventory Summary

**Vulture 2.16 scan of 28,629 LOC identifying 0 true dead items at 80% confidence after whitelisting all 15 PITFALLS.md false positive patterns**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-26T18:07:17Z
- **Completed:** 2026-03-26T18:14:02Z
- **Tasks:** 1
- **Files created:** 2

## Accomplishments

- Ran vulture at 80% and 60% confidence across entire src/wanctl/ codebase
- Validated all 15 "Looks Dead But Isn't" patterns from PITFALLS.md against actual codebase
- Created reusable .vulture_whitelist.py covering 68 false positive entries across 10 categories
- Categorized 66 findings at 60% confidence: 4 likely dead, 9 needs investigation, 53 test-only
- All 8 CLI entry points and both transport modes (linux-cake, rest) checked for reachability
- Zero code removed per D-07 identification-only policy

## Task Commits

Each task was committed atomically:

1. **Task 1: Run vulture scan and validate findings against false positive patterns** - `7224a33` (feat)

## Files Created/Modified

- `.vulture_whitelist.py` - Project-wide vulture false positive whitelist (68 entries, 10 categories)
- `.planning/phases/112-foundation-scan/112-04-findings.md` - Structured dead code inventory with summary, false positive validation, likely dead code, needs investigation, test-only, and entry point coverage tables

## Decisions Made

- **Whitelist approach:** Used a single `.vulture_whitelist.py` in project root rather than per-file `# noqa` comments. This enables CI integration (`vulture src/wanctl/ .vulture_whitelist.py --min-confidence 80`) and centralized false positive management.
- **80% primary threshold:** At 80% confidence, all 13 findings were Python protocol false positives (context manager and signal handler parameters). Zero true dead code at this threshold.
- **Test-only classification:** 53 functions/methods that are only called from tests were classified as "acceptable" rather than "dead" because they are exported public API surface with active test coverage, validating correctness of utility code.
- **4 likely dead items identified:** `_create_transport()` (superseded), `SteeringLogger` class (no imports), `_ul_last_congested_zone` (orphaned attr), `_last_tuning_ts` (orphaned attr). Total ~270 lines pending transport validation before removal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed vulture into project venv**

- **Found during:** Task 1 (vulture scan)
- **Issue:** vulture was not installed in the project venv
- **Fix:** Ran `uv pip install vulture --python .venv/bin/python`
- **Files modified:** None (venv-only change)
- **Verification:** `vulture --version` returns 2.16
- **Committed in:** N/A (runtime dependency, not committed)

**2. [Rule 1 - Bug] Fixed vulture whitelist syntax for import statement**

- **Found during:** Task 1 (whitelist validation)
- **Issue:** `import wanctl.routeros_ssh` syntax in whitelist caused vulture to report unused import of `wanctl`
- **Fix:** Changed to bare name `routeros_ssh` which is the correct vulture whitelist syntax
- **Files modified:** .vulture_whitelist.py
- **Verification:** `vulture src/wanctl/ .vulture_whitelist.py --min-confidence 80` returns 0 findings
- **Committed in:** 7224a33 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for task completion. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## Known Stubs

None -- this plan produces analysis artifacts only, no production code changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `.vulture_whitelist.py` is ready for CI integration (e.g., `make dead-code-check`)
- Dead code inventory provides actionable input for future cleanup phases
- 4 likely dead items and 9 investigation items documented for prioritized removal in a dedicated cleanup milestone
- All 15 PITFALLS.md patterns validated -- future dead code scans can reference this inventory

## Self-Check: PASSED

- .vulture_whitelist.py: FOUND
- 112-04-findings.md: FOUND
- 112-04-SUMMARY.md: FOUND
- Commit 7224a33: FOUND
- Zero source modifications: VERIFIED
- Vulture with whitelist at 80%: 0 findings (exit code 0)

---

_Phase: 112-foundation-scan_
_Completed: 2026-03-26_
