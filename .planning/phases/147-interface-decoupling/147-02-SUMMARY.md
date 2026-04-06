---
phase: 147-interface-decoupling
plan: 02
subsystem: core
tags: [facade-pattern, public-api, decoupling, cross-module-access]

# Dependency graph
requires:
  - 147-01
provides:
  - "WANController public facade API (reload, shutdown_threads, get_current_params, etc.)"
  - "Component public properties (sigma_threshold, window_size, min_score, cadence_sec, db_path)"
  - "Zero cross-module private access from autorate_continuous.py into WANController"
affects: [147-03, 147-04]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Public facade methods on WANController for orchestrator access", "Property-based encapsulation on component classes"]

key-files:
  created: []
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/signal_processing.py
    - src/wanctl/reflector_scorer.py
    - src/wanctl/irtt_thread.py
    - src/wanctl/storage/writer.py
    - src/wanctl/autorate_continuous.py
    - src/wanctl/health_check.py
    - scripts/check_private_access.py
    - tests/test_fusion_healer.py
    - tests/test_irtt_thread.py
    - tests/test_health_check.py
    - tests/test_metrics.py

key-decisions:
  - "Used Any type for pending_observation facade methods (matching existing untyped field)"
  - "Updated _apply_signal_param module-level function to use public properties (resize_window, sigma_threshold setter, min_score setter)"
  - "Also fixed health_check.py _cadence_sec cross-module access (Boundary 2 bonus)"

patterns-established:
  - "WANController PUBLIC FACADE API section with clearly marked boundary"
  - "Component PUBLIC FACADE API sections on SignalProcessor, ReflectorScorer, IRTTThread, MetricsWriter"

requirements-completed: [CPLX-03]

# Metrics
duration: 19min
completed: 2026-04-06
---

# Phase 147 Plan 02: WANController Facade + Orchestrator Decoupling Summary

**Public facade API on WANController (13 methods/properties) eliminating all 35+ cross-module private accesses from autorate_continuous.py, plus public properties on 4 component classes**

## Performance

- **Duration:** 19 min
- **Started:** 2026-04-06T19:18:41Z
- **Completed:** 2026-04-06T19:38:00Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Added 13 public facade methods/properties to WANController: reload(), shutdown_threads(), enable_profiling(), init_fusion_healer(), get/set/clear_pending_observation(), get_parameter_locks(), tuning_layer_index property, is_tuning_enabled property, get_current_params(), get_metrics_writer(), set_irtt_thread()
- Added public properties to 4 component classes: SignalProcessor (sigma_threshold, window_size, resize_window), ReflectorScorer (min_score), IRTTThread (cadence_sec), MetricsWriter (db_path, get_instance)
- Eliminated ALL cross-module private attribute accesses from autorate_continuous.py into WANController (~35 violations)
- Updated _apply_signal_param to use public properties instead of direct _attr access
- Updated health_check.py to use cadence_sec property (bonus Boundary 2 fix)
- Reduced allowlist from 73 to 44 entries (29 removed), violations from 109 to 68
- Updated 4 test files for cadence_sec property on MagicMock objects
- All 472 affected tests pass, boundary check passes with 0 new violations

## Task Commits

Each task was committed atomically:

1. **Task 1: Add public facade methods to WANController and component accessors** - `8646180` (feat)
2. **Task 2: Update autorate_continuous.py and fusion_healer.py to use public APIs** - `af7a878` (refactor)

## Files Created/Modified

- `src/wanctl/wan_controller.py` - 13 public facade methods/properties in PUBLIC FACADE API section, plus internal updates to use component properties
- `src/wanctl/signal_processing.py` - sigma_threshold property + setter, window_size property, resize_window() method
- `src/wanctl/reflector_scorer.py` - min_score property + setter
- `src/wanctl/irtt_thread.py` - cadence_sec property
- `src/wanctl/storage/writer.py` - db_path property, get_instance() classmethod
- `src/wanctl/autorate_continuous.py` - All wc._attr calls replaced with public method calls
- `src/wanctl/health_check.py` - _cadence_sec replaced with cadence_sec property
- `scripts/check_private_access.py` - 29 allowlist entries removed (21 Boundary 1, 1 Boundary 2, 7 Boundary 5)
- `tests/test_fusion_healer.py` - 14 _cadence_sec -> cadence_sec on MagicMock
- `tests/test_irtt_thread.py` - 3 _cadence_sec -> cadence_sec on MagicMock
- `tests/test_health_check.py` - 2 _cadence_sec -> cadence_sec on MagicMock
- `tests/test_metrics.py` - 3 _cadence_sec -> cadence_sec on MagicMock

## Decisions Made

- Used `Any` type annotation for get/set_pending_observation to match existing untyped `_pending_observation = None` field (pre-existing mypy gap, not introduced by this plan)
- Updated module-level `_apply_signal_param()` to use public properties (resize_window, sigma_threshold setter) even though it's in the same file as WANController -- consistent with facade pattern
- Fixed `_restore_tuning_params` to use `db_path` property and `_compute_fused_rtt` to use `cadence_sec` property within wan_controller.py itself (same-module but cross-class access)
- Fixed health_check.py `_cadence_sec` access as a bonus (Boundary 2 violation resolved ahead of Plan 03)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MagicMock cadence_sec property in 4 test files**
- **Found during:** Task 2 test verification
- **Issue:** Tests set `irtt_thread._cadence_sec = 10.0` on MagicMock objects; code now uses `cadence_sec` property, so MagicMock returned a MagicMock instead of float, causing TypeError in comparison
- **Fix:** Updated all 22 occurrences of `_cadence_sec` to `cadence_sec` on MagicMock objects across 4 test files
- **Files modified:** tests/test_fusion_healer.py, tests/test_irtt_thread.py, tests/test_health_check.py, tests/test_metrics.py
- **Commit:** af7a878

**2. [Rule 2 - Missing Critical] Fixed health_check.py cross-module _cadence_sec access**
- **Found during:** Task 2 grep audit for remaining _cadence_sec references
- **Issue:** health_check.py line 426 accessed `_irtt_thread._cadence_sec` (Boundary 2 violation), which would fail with the property change if not updated
- **Fix:** Changed to `_irtt_thread.cadence_sec` and removed allowlist entry
- **Files modified:** src/wanctl/health_check.py, scripts/check_private_access.py
- **Commit:** af7a878

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both necessary for correctness after property additions. health_check fix was a bonus Boundary 2 resolution.

## Issues Encountered

None.

## Next Phase Readiness

- WANController facade API established -- Plans 03 and 04 follow the same pattern for health_check.py (Boundary 2) and steering (Boundaries 3/4)
- Allowlist now at 44 entries (from 73), 68 violations (from 109)
- Remaining boundaries: health_check (19 violations), steering/health (12), steering/daemon (7), wan_controller internal (10), misc (1)

## Self-Check: PASSED

- All 12 modified files exist on disk
- Both commit hashes verified (8646180, af7a878)
- WANController facade methods confirmed (reload, get_current_params, shutdown_threads)
- Zero wc._ accesses in autorate_continuous.py confirmed
- Boundary check: 68 violations (68 allowlisted, 0 new) confirmed

---
*Phase: 147-interface-decoupling*
*Completed: 2026-04-06*
