---
phase: 167-latency-and-burst-regression-alerts
plan: 01
subsystem: alerting
tags: [alerting, latency, burst, cooldowns]

# Dependency graph
requires:
  - phase: 166-burst-detection-and-multi-flow-ramp-control-for-tcp-12down-p
    provides: bounded burst health/metrics telemetry and validated burst control behavior
provides:
  - sustained latency-regression alerts on the existing AlertEngine path
  - repeated burst-churn alerts on the existing AlertEngine path
  - focused test coverage for severity and cooldown contracts
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Latency-regression alerting reuses bounded controller state instead of adding new persistence"
    - "Burst churn alerting uses short in-memory trigger windows plus AlertEngine cooldowns"

key-files:
  created:
    - .planning/phases/167-latency-and-burst-regression-alerts/167-01-SUMMARY.md
  modified:
    - src/wanctl/wan_controller.py
    - tests/test_alert_engine.py

key-decisions:
  - "Used existing GREEN and SOFT_RED RTT-delta thresholds as the warning/critical alert boundary instead of introducing another tuning surface"
  - "Marked latency-regression episodes active after the first matured alert attempt so cooldown suppression does not cause per-cycle re-fire attempts"
  - "Burst churn is keyed off confirmed burst-trigger count deltas, not raw RTT spikes, so low-signal candidate activity stays quiet"

patterns-established:
  - "Production alerts should be derived from bounded in-memory controller state first, not ad hoc flent runs or new raw-series tables"

requirements-completed: [ALRT-01, ALRT-02, ALRT-03]

# Metrics
duration: 45min
completed: 2026-04-11
status: complete
---

# Phase 167 Plan 01 Summary

**Added bounded latency-regression and burst-churn alerts to the existing autorate alert path without touching the control algorithm.**

## Accomplishments
- Extended [wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py) with a sustained `latency_regression` alert that keys off existing RTT-delta and zone state rather than adding new stored series.
- Added a `burst_churn_dl` alert that watches confirmed burst-trigger count deltas inside a short in-memory window and reuses AlertEngine cooldown suppression.
- Kept both rules on the existing AlertEngine path with stable detail payloads, explicit warning/critical boundaries, and no new SQLite writes.
- Added focused regression coverage in [test_alert_engine.py](/home/kevin/projects/wanctl/tests/test_alert_engine.py) for sustained warning/critical severity selection, healthy-state silence, and cooldown behavior.

## Verification
- `.venv/bin/pytest -o addopts='' tests/test_alert_engine.py -q`
- Result: `121 passed`
- `.venv/bin/pytest -o addopts='' tests/test_alert_engine.py tests/test_health_check.py -q`
- Result: `242 passed`
- `.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/alert_engine.py`
- Result: `Success: no issues found in 2 source files`
- `.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/alert_engine.py tests/test_alert_engine.py tests/test_health_check.py`
- Result: only the pre-existing `B009/B010` warnings in [wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py); no new lint failures from this alerting work.
