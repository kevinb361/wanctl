---
phase: 143-dependency-cruft-cleanup
plan: 03
subsystem: docs
tags: [docstrings, config-schema, dead-references, documentation-sync]

requires:
  - phase: 143-dependency-cruft-cleanup
    plan: 02
    provides: cleaned example files and config key audit findings
provides:
  - Corrected stale docstrings in priority source modules
  - Synced CONFIG_SCHEMA.md with all config key audit findings
  - Cleaned docs/*.md references to deprecated parameters
affects: [documentation, config-schema]

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - src/wanctl/router_command_utils.py
    - src/wanctl/backends/base.py
    - docs/CONFIG_SCHEMA.md
    - docs/ARCHITECTURE.md
    - docs/CONFIGURATION.md

key-decisions:
  - "Left alpha_baseline/alpha_load references in historical docs (INTERVAL_TESTING_*.md, FASTER_RESPONSE_INTERVAL.md, CALIBRATION.md, PRODUCTION_INTERVAL.md) -- these are version history, not current guidance"
  - "Updated ARCHITECTURE.md and CONFIGURATION.md alpha references since they describe current config keys, not history"
  - "Added storage.retention_days to deprecated parameters table rather than removing the old storage section entirely"

requirements-completed: [DEAD-04]

duration: 31min
completed: 2026-04-05
---

# Phase 143 Plan 03: Docstring Audit and CONFIG_SCHEMA.md Sync Summary

**Corrected stale docstrings (is_ok/is_err, wrong path), synced CONFIG_SCHEMA.md with 5 new/updated sections (storage.retention, owd_asymmetry, fusion.healing, ping_source_ip, deprecated table), and fixed alpha_baseline/alpha_load references in ARCHITECTURE.md and CONFIGURATION.md**

## Performance

- **Duration:** 31 min
- **Started:** 2026-04-05T19:57:34Z
- **Completed:** 2026-04-05T20:29:28Z
- **Tasks:** 2/2
- **Files modified:** 5

## Accomplishments

- Fixed stale docstring examples in router_command_utils.py: `is_ok()`/`is_err()` replaced with `.success` (methods never existed on CommandResult)
- Fixed wrong module path in backends/base.py: `cake/backends/` corrected to `wanctl/backends/`
- Added `storage.retention` sub-section to CONFIG_SCHEMA.md with 4 sub-keys (raw_age_seconds, aggregate_1m_age_seconds, aggregate_5m_age_seconds, prometheus_compensated)
- Added `owd_asymmetry` section to CONFIG_SCHEMA.md with ratio_threshold documentation
- Added `fusion.healing` sub-section to CONFIG_SCHEMA.md with 5 parameters (suspend/recover thresholds, windows, grace period)
- Added `ping_source_ip` documentation to CONFIG_SCHEMA.md
- Added `storage.retention_days` to deprecated parameters table
- Updated ARCHITECTURE.md: replaced `alpha_baseline`/`alpha_load` references with `baseline_time_constant_sec`/`load_time_constant_sec`
- Updated CONFIGURATION.md: replaced all alpha references with time constant equivalents in both prose and YAML examples
- Verified 4,177 tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit and fix stale docstrings in priority modules** - `0cd3d64` (fix)
2. **Task 2: Sync CONFIG_SCHEMA.md and fix stale docs references** - `0de5777` (feat)

## Files Created/Modified

- `src/wanctl/router_command_utils.py` - Fixed is_ok()/is_err() docstring examples to use .success
- `src/wanctl/backends/base.py` - Fixed wrong path cake/backends/ -> wanctl/backends/
- `docs/CONFIG_SCHEMA.md` - Added storage.retention, owd_asymmetry, fusion.healing, ping_source_ip; updated deprecated table
- `docs/ARCHITECTURE.md` - Updated alpha_baseline/alpha_load to time constant references
- `docs/CONFIGURATION.md` - Updated alpha references in prose, fiber example, DSL example, and YAML blocks

## Decisions Made

- Left alpha_baseline/alpha_load references in historical testing docs (INTERVAL_TESTING_*.md, FASTER_RESPONSE_INTERVAL.md, CALIBRATION.md, PRODUCTION_INTERVAL.md) as they document version history
- Updated ARCHITECTURE.md and CONFIGURATION.md since they present alpha values as current guidance
- Added retention_days to deprecated table rather than removing old storage docs entirely

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed wrong module path in backends/base.py**
- **Found during:** Task 1 (backends/ docstring audit)
- **Issue:** Module docstring referenced `cake/backends/` which was a legacy path; correct path is `wanctl/backends/`
- **Fix:** Updated the path reference
- **Files modified:** src/wanctl/backends/base.py
- **Commit:** 0cd3d64

**2. [Rule 2 - Missing Critical] Updated alpha references in ARCHITECTURE.md and CONFIGURATION.md**
- **Found during:** Task 2 (docs/*.md scan for stale references)
- **Issue:** ARCHITECTURE.md and CONFIGURATION.md described alpha_baseline/alpha_load as current config parameters, but these were deprecated in favor of time constants
- **Fix:** Updated references to baseline_time_constant_sec/load_time_constant_sec with correct typical values
- **Files modified:** docs/ARCHITECTURE.md, docs/CONFIGURATION.md
- **Commit:** 0de5777

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes improve documentation accuracy. No scope creep.

## Issues Encountered

- Pre-existing test failure: test_production_steering_yaml_no_unknown_keys tries to open configs/steering.yaml which doesn't exist in worktrees. Not caused by this plan's changes. Deselected during test runs.

## User Setup Required

None - documentation-only changes.

## Next Phase Readiness

- DEAD-04 (docstring/comment/doc staleness) complete across all 3 plans
- CONFIG_SCHEMA.md now documents all sections present in cleaned example files
- Historical testing docs (INTERVAL_TESTING_*.md etc.) left with alpha references as version history

## Self-Check: PASSED

- All 5 modified files verified present on disk
- Both task commits (0cd3d64, 0de5777) verified in git log

---
*Phase: 143-dependency-cruft-cleanup*
*Completed: 2026-04-05*
