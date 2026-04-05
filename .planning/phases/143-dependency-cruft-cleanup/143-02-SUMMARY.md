---
phase: 143-dependency-cruft-cleanup
plan: 02
subsystem: config
tags: [yaml, config-validation, dead-code, deprecated-params, check-config]

requires:
  - phase: 142-dead-code-removal
    provides: vulture dead code detection and whitelist infrastructure
provides:
  - Complete KNOWN_AUTORATE_PATHS set (~50 missing paths added)
  - Cleaned example files with current key names only
  - Verified deprecated translation correctness
  - Storage retention, fusion healing, owd_asymmetry, ping_source_ip documented in examples
affects: [143-dependency-cruft-cleanup, config-validation, check-config]

tech-stack:
  added: []
  patterns:
    - "KNOWN_*_PATHS grouped by source config loading function"
    - "Example files show current key names only, deprecated names removed"

key-files:
  created: []
  modified:
    - src/wanctl/check_config.py
    - configs/examples/cable.yaml.example
    - configs/examples/dsl.yaml.example
    - configs/examples/fiber.yaml.example
    - configs/examples/wan1.yaml.example
    - configs/examples/wan2.yaml.example
    - configs/examples/steering.yaml.example

key-decisions:
  - "Kept alpha_baseline/alpha_load in KNOWN_AUTORATE_PATHS (deprecated handler covers them, not unknown-key detector)"
  - "Converted alpha values per-file using actual values (not assuming uniform) -- dsl=0.015->3.3s, fiber=0.01->5.0s, wan1/wan2=0.02->2.5s"
  - "Removed steering ping_total (dead key never read by daemon code)"
  - "Did not modify deprecated translation code per D-08/D-13 constraints"

patterns-established:
  - "Config paths in KNOWN_*_PATHS sets grouped with source function comments"

requirements-completed: [DEAD-04]

duration: 44min
completed: 2026-04-05
---

# Phase 143 Plan 02: Config Key Cross-Reference Audit Summary

**Bidirectional config key audit: ~50 missing paths added to KNOWN_AUTORATE_PATHS, 6 example files cleaned of dead/deprecated keys, undocumented keys added as commented-out sections**

## Performance

- **Duration:** 44 min
- **Started:** 2026-04-05T19:09:46Z
- **Completed:** 2026-04-05T19:53:47Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added ~50 missing config paths to KNOWN_AUTORATE_PATHS covering signal_processing, irtt, reflector_quality, owd_asymmetry, fusion (with healing sub-keys), tuning (with bounds/oscillation_threshold), ping_source_ip, storage.retention sub-keys, and WANController init paths
- Cleaned all 6 example files: removed dead keys (irtt.packet_size, steering ping_total), renamed stale keys (duration_ms->duration_sec), replaced deprecated active keys (alpha_baseline->baseline_time_constant_sec, alpha_load->load_time_constant_sec with correct per-file math)
- Added undocumented keys as commented-out sections: owd_asymmetry, ping_source_ip, fusion.healing (5 sub-keys), storage.retention (4 sub-keys)
- Verified all deprecated translations are correct (D-08/D-11/D-13 compliance)

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify deprecated translations and extend KNOWN_*_PATHS** - `9e33125` (feat)
2. **Task 2: Clean example files** - `4fc79c6` (feat)

## Files Created/Modified

- `src/wanctl/check_config.py` - Added ~50 missing paths to KNOWN_AUTORATE_PATHS (56 insertions)
- `configs/examples/cable.yaml.example` - Cleaned dead keys, added undocumented sections
- `configs/examples/dsl.yaml.example` - Replaced alpha_baseline=0.015->baseline_time_constant_sec=3.3
- `configs/examples/fiber.yaml.example` - Replaced alpha_baseline=0.01->baseline_time_constant_sec=5.0
- `configs/examples/wan1.yaml.example` - Replaced alpha_baseline=0.02->baseline_time_constant_sec=2.5
- `configs/examples/wan2.yaml.example` - Replaced alpha_baseline=0.02->baseline_time_constant_sec=2.5
- `configs/examples/steering.yaml.example` - Removed dead ping_total key

## Decisions Made

- Kept alpha_baseline/alpha_load in KNOWN_AUTORATE_PATHS since the deprecated param handler covers them -- removing would cause false-positive "unknown key" warnings for users with old configs
- Converted alpha values using actual per-file values rather than assuming uniform defaults
- Removed steering ping_total (never read by SteeringConfig code, only appeared in example and KNOWN_STEERING_PATHS)
- Did not modify any deprecated translation code per D-08/D-13 constraints -- only verified correctness

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added signal_processing paths to KNOWN_AUTORATE_PATHS**
- **Found during:** Task 1 (KNOWN_AUTORATE_PATHS audit)
- **Issue:** Research identified ~37 missing paths but missed signal_processing (6 paths) and WANController init paths (warning_threshold_pct, suppression_alert_threshold)
- **Fix:** Added all signal_processing sub-keys and WANController init config paths
- **Files modified:** src/wanctl/check_config.py
- **Verification:** vulture passes, all tests pass
- **Committed in:** 9e33125

**2. [Rule 1 - Bug] Removed dead ping_total from steering example**
- **Found during:** Task 2 (steering example audit)
- **Issue:** steering.yaml.example contained timeouts.ping_total which is never read by SteeringConfig._load_timeouts()
- **Fix:** Removed the dead key from the example
- **Files modified:** configs/examples/steering.yaml.example
- **Committed in:** 4fc79c6

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both auto-fixes improve config accuracy. No scope creep.

## Issues Encountered

- Pre-existing test failure: test_production_steering_yaml_no_unknown_keys tries to open configs/steering.yaml which doesn't exist in worktrees. Not caused by this plan's changes (confirmed by testing on clean HEAD). Deselected during test runs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DEAD-04 config references portion complete
- KNOWN_AUTORATE_PATHS now comprehensive -- future config additions should update this set
- Example files are clean reference documents showing current key names only

## Self-Check: PASSED

- All 8 files verified present on disk
- Both task commits (9e33125, 4fc79c6) verified in git log

---
*Phase: 143-dependency-cruft-cleanup*
*Completed: 2026-04-05*
