---
phase: quick-8
plan: 1
subsystem: alerting
tags: [bugfix, flapping, alert-engine, cooldown, dwell-filter, production]
key-files:
  modified:
    - src/wanctl/alert_engine.py
    - src/wanctl/autorate_continuous.py
    - tests/test_anomaly_alerts.py
decisions:
  - "rule_key is keyword-only parameter on fire() for backward compatibility"
  - "min_hold_sec=0 disables dwell filter (existing tests unchanged)"
  - "min_hold_sec defaults to 1.0s (20 cycles at 50ms) in production"
  - "_rule_key_map dict on AlertEngine maps alert_type to rule_key for get_active_cooldowns()"
metrics:
  duration: 460s
  completed: "2026-03-13T01:17:23Z"
  tasks_completed: 2
  tasks_total: 3
  tests_added: 12
  tests_modified: 5
  tests_total_passing: 2726
---

# Quick Task 8: Fix Flapping Alert Detection Cooldown Key and Dwell Filter Summary

**AlertEngine rule_key parameter for parent-rule cooldown lookup, plus dwell filter rejecting single-cycle zone blips**

## Performance

- **Duration:** 460s (~8 min)
- **Started:** 2026-03-13T01:09:43Z
- **Completed:** 2026-03-13T01:17:23Z
- **Tasks:** 2/3 (Task 3 is human-action checkpoint for production deployment)
- **Files modified:** 3

## Accomplishments

- AlertEngine.fire() now accepts `rule_key` kwarg so flapping_dl/flapping_ul alerts use congestion_flapping rule's cooldown_sec (600s not default 300s)
- Dwell filter prevents single-cycle zone blips from counting as transitions (must hold zone >= min_hold_cycles)
- min_hold_sec configurable per-rule (default 1.0s = 20 cycles at 50ms production interval)
- 12 new tests, 5 existing tests updated, all 2726 tests passing

## Task Commits

1. **Task 1: Fix cooldown key mismatch and add dwell filter (TDD RED)** - `d5c883a` (test)
2. **Task 1: Fix cooldown key mismatch and add dwell filter (TDD GREEN)** - `f6babcc` (feat)
3. **Task 2: Full test suite regression check** - no commit (verification only, 2726 passed)
4. **Task 3: Deploy to production** - CHECKPOINT (human-action)

## Files Modified

- `src/wanctl/alert_engine.py` - Added rule_key parameter to fire(), \_is_cooled_down(), \_rule_key_map for get_active_cooldowns()
- `src/wanctl/autorate_continuous.py` - Added \_dl_zone_hold/\_ul_zone_hold counters, dwell filter logic, rule_key="congestion_flapping" in fire() calls
- `tests/test_anomaly_alerts.py` - 12 new tests (TestFlappingCooldownKeyFix: 6, TestFlappingDwellFilter: 6), fixture updates

## Changes Detail

### Part A: AlertEngine rule_key parameter

- `fire()` accepts `rule_key: str | None = None` (keyword-only, backward compatible)
- When rule_key provided: uses it for per-rule enabled gate and cooldown config lookup
- Cooldown dict key remains `(alert_type, wan_name)` -- only the config rule lookup changes
- `_is_cooled_down()` accepts rule_key for correct cooldown_sec lookup
- `_rule_key_map` dict populated by fire() when rule_key is provided, used by get_active_cooldowns()

### Part B: Dwell filter

- `_dl_zone_hold` and `_ul_zone_hold` counters track how many cycles current zone has been held
- On zone change: only count as transition if departing zone held >= min_hold_cycles
- `min_hold_sec` read from congestion_flapping rule config (default 1.0s)
- `min_hold_cycles = max(1, int(min_hold_sec / CYCLE_INTERVAL_SECONDS))` (20 at 50ms)
- `min_hold_sec <= 0` disables filter entirely (min_hold_cycles = 0)

## Decisions Made

- rule_key is keyword-only (`*` separator) to prevent positional argument confusion
- min_hold_sec=0 disables dwell filter completely (used in existing test fixtures)
- Default min_hold_sec=1.0 chosen for production (20 cycles = 1 second of sustained zone)
- \_rule_key_map stored on engine instance rather than passed through every method

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] min_hold_sec=0 produced min_hold_cycles=1 instead of 0**

- **Found during:** Task 1 GREEN phase
- **Issue:** `max(1, int(0 / 0.05))` = 1, not 0. Existing tests with min_hold_sec=0 failed because hold=0 < 1.
- **Fix:** Added `if min_hold_sec <= 0: min_hold_cycles = 0` branch before max() calculation
- **Files modified:** src/wanctl/autorate_continuous.py
- **Commit:** f6babcc

**2. [Rule 1 - Bug] Three inline AlertEngine overrides in tests missing min_hold_sec: 0**

- **Found during:** Task 1 GREEN phase
- **Issue:** Tests that create inline AlertEngine for severity/threshold/window overrides didn't include min_hold_sec: 0
- **Fix:** Added "min_hold_sec": 0 to all three inline congestion_flapping rule dicts
- **Files modified:** tests/test_anomaly_alerts.py
- **Commit:** f6babcc

**3. [Rule 1 - Bug] TestFlappingDefaults using empty rules hit default min_hold_sec=1.0**

- **Found during:** Task 1 GREEN phase
- **Issue:** Tests with `rules={}` got default min_hold_sec=1.0, filtering all rapid transitions
- **Fix:** Changed to `rules={"congestion_flapping": {"min_hold_sec": 0}}` (preserves default threshold/window behavior)
- **Files modified:** tests/test_anomaly_alerts.py
- **Commit:** f6babcc

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All auto-fixes necessary for backward compatibility with existing tests. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## Pre-existing Lint Issues (Out of Scope)

- `tests/test_webhook_delivery.py` and `tests/test_webhook_integration.py` have 6 pre-existing ruff errors (unused imports, ambiguous variable names). Not caused by this task, not fixed.

## Next: Production Deployment (Task 3 Checkpoint)

Production deployment requires human action -- see checkpoint details below.

---

_Quick Task: 8_
_Completed: 2026-03-13 (Tasks 1-2 only, Task 3 awaiting deployment)_

## Self-Check: PASSED

- FOUND: src/wanctl/alert_engine.py
- FOUND: src/wanctl/autorate_continuous.py
- FOUND: tests/test_anomaly_alerts.py
- FOUND: 8-SUMMARY.md
- FOUND: commit d5c883a
- FOUND: commit f6babcc
