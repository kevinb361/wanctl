---
phase: quick-7
plan: 1
subsystem: alerting
tags: [bugfix, flapping, alert-engine, production]
key-files:
  modified:
    - src/wanctl/autorate_continuous.py
    - tests/test_anomaly_alerts.py
decisions:
  - Single congestion_flapping rule key shared by DL and UL (matches YAML config pattern)
  - Deque clear after fire prevents accumulation-based re-fire
  - Default threshold 30 and window 120s tuned for 20Hz cycle rate
metrics:
  duration: 712s
  completed: "2026-03-12T20:44:50Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 5
  tests_modified: 6
  tests_total_passing: 2714
---

# Quick Task 7: Fix Flapping Alert Bugs Summary

Fixed three production bugs in \_check_flapping_alerts() that caused 74 false alerts in 3.2 hours -- rule name mismatch silently ignored config, deque not clearing caused re-fire every cooldown period, and defaults were too aggressive for 20Hz polling.

## Changes

### Bug 1: Rule name mismatch (config silently ignored)

- `_check_flapping_alerts` read from `flapping_dl`/`flapping_ul` rule keys
- YAML config uses single `congestion_flapping` rule (matching other alert patterns)
- Fixed: single `flap_rule = self.alert_engine._rules.get("congestion_flapping", {})` at method top
- Both DL and UL blocks now share the same config rule

### Bug 2: Deque not cleared after fire (re-fire every cooldown)

- After alert fired, transitions remained in deque
- Next cooldown expiry immediately re-fired (deque still >= threshold)
- Fixed: `self._dl_zone_transitions.clear()` and `self._ul_zone_transitions.clear()` after each fire()

### Bug 3: Defaults too aggressive for 20Hz

- Old defaults: threshold=6, window=60s (fires after 6 transitions in 60s)
- At 20Hz, 6 transitions can happen in under 1 second during normal congestion response
- Fixed: threshold=30, window=120s (sane for production)

## Test Updates

- Fixture `mock_flapping_controller` updated: single `congestion_flapping` rule replaces two separate keys
- 3 inline rule overrides updated to `congestion_flapping` key
- Existing tests updated to mock fire() during transition generation (deque clearing changes assertion timing)
- New `TestFlappingDequeClear` class: 3 tests (DL clear, UL clear, no re-fire after cooldown)
- New `TestFlappingDefaults` class: 2 tests (threshold=30, window=120s)

## Commits

| Hash    | Type | Description                                                      |
| ------- | ---- | ---------------------------------------------------------------- |
| ab6128b | test | Add failing tests for flapping alert bug fixes (RED)             |
| 1641769 | feat | Fix three flapping alert bugs in \_check_flapping_alerts (GREEN) |

## Verification

1. `pytest tests/test_anomaly_alerts.py -v` -- 22/22 passed
2. `ruff check` -- clean on both modified files
3. `pytest tests/ --ignore=tests/integration -x -q` -- 2714 passed, zero regressions
4. `grep congestion_flapping src/wanctl/autorate_continuous.py` -- confirms rule name fix
5. `grep .clear() src/wanctl/autorate_continuous.py | grep transition` -- confirms deque clearing
6. `grep 'flap_threshold.*30\|flap_window_sec.*120'` -- confirms raised defaults

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing tests for deque-clearing behavior**

- **Found during:** Task 1 GREEN phase
- **Issue:** Existing tests generated transitions with real fire(), then checked one more with mock fire(). After deque-clearing fix, deque was empty so threshold was never reached in the mocked call.
- **Fix:** Wrapped fire mock around the entire transition generation loop so the fire call is captured when threshold is first reached (before clear empties the deque).
- **Files modified:** tests/test_anomaly_alerts.py (5 test methods)
- **Commit:** 1641769

## Self-Check: PASSED

- FOUND: src/wanctl/autorate_continuous.py
- FOUND: tests/test_anomaly_alerts.py
- FOUND: 7-SUMMARY.md
- FOUND: commit ab6128b
- FOUND: commit 1641769
