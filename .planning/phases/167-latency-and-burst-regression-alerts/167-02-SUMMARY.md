---
phase: 167-latency-and-burst-regression-alerts
plan: 02
subsystem: alerting
tags: [alerting, validation, production, health]

# Dependency graph
requires:
  - phase: 167-latency-and-burst-regression-alerts
    plan: 01
    provides: latency-regression and burst-churn alert rules on the AlertEngine path
provides:
  - healthy-state silence validation for the new rules
  - production sanity check against live /health and /metrics surfaces
  - explicit phase-close decision for alert readiness
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Manual alert sanity gates should confirm healthy-state silence on the live host after deploy"
    - "Alert readiness can be approved from bounded operator surfaces when local tests already cover degraded severity branches"

key-files:
  created:
    - .planning/phases/167-latency-and-burst-regression-alerts/167-02-SUMMARY.md
  modified:
    - src/wanctl/wan_controller.py
    - tests/test_alert_engine.py

key-decisions:
  - "Approved outcome: alert rules ready"
  - "Production currently uses alerting defaults for the new rule names because the live YAMLs only set enabled/webhook_url"
  - "The manual sanity gate relied on healthy-state silence in /health and existing burst metrics rather than trying to force a degraded condition on production"

patterns-established:
  - "Healthy production state must stay quiet after deploy before new alert rules can be considered ready"

requirements-completed: [ALRT-01, ALRT-02, ALRT-03]

# Metrics
duration: 30min
completed: 2026-04-11
status: complete
---

# Phase 167 Plan 02 Summary

**Validated that the new alert rules stay quiet on the live autorate service and are ready for production use.**

## Local Validation
- `.venv/bin/pytest -o addopts='' tests/test_alert_engine.py tests/test_health_check.py -q`
- Result: `242 passed`
- `.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/alert_engine.py`
- Result: `Success: no issues found in 2 source files`
- `.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/alert_engine.py tests/test_alert_engine.py tests/test_health_check.py`
- Result: only the pre-existing `B009/B010` warnings in [wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py)

## Manual Gate Result
- **Decision:** `approved: alert rules ready`
- Deployment target: `cake-shaper` (`wanctl@spectrum`, `wanctl@att`)
- Deploy action: copied [wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py) to `/opt/wanctl/wan_controller.py` and restarted both autorate services
- Live sanity checks after deploy:
  - `systemctl is-active wanctl@spectrum` -> `active`
  - `systemctl is-active wanctl@att` -> `active`
  - `http://10.10.110.223:9101/health` -> `healthy`
  - warning journal for `wanctl@spectrum` / `wanctl@att` over the restart window -> `No entries`
  - `/health.alerting.fire_count` stayed `0` across two post-restart samples
  - `/health.alerting.active_cooldowns` stayed empty across two post-restart samples
  - `cake_signal.burst.active` stayed `false` and `trigger_count` stayed `0`
  - `/metrics` continued to expose bounded burst telemetry, with `wanctl_burst_active{wan="spectrum",direction="download"} 0.0`

## Notes
- Live Spectrum and ATT configs already have `alerting.enabled: true`, but they do not define per-rule overrides for the new `latency_regression` and `burst_churn_dl` rule names yet. The rules therefore run with AlertEngine defaults, which is acceptable for this phase and leaves explicit threshold policy work to later v1.34 phases.
- The sanity gate deliberately did not force a degraded production condition. Severity boundaries and cooldown behavior were validated locally by the new focused tests; the production gate only had to prove healthy-state silence and operator-readable surfaces.
