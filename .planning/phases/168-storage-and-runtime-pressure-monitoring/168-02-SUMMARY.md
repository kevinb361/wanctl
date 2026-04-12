---
phase: 168-storage-and-runtime-pressure-monitoring
plan: 02
subsystem: observability
tags: [validation, production, health, metrics]

# Dependency graph
requires:
  - phase: 168-storage-and-runtime-pressure-monitoring
    plan: 01
    provides: bounded health and metrics pressure visibility for storage and runtime state
provides:
  - healthy-live validation of the new pressure signals
  - explicit operator decision on Phase 168 readiness
  - handoff to Phase 169 surface polish work
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Healthy-live validation should confirm new observability stays quiet and interpretable before later alerting or summary phases consume it"
    - "Metrics availability remains config-scoped; health must still carry the pressure signal when a metrics endpoint is not exposed"

key-files:
  created:
    - .planning/phases/168-storage-and-runtime-pressure-monitoring/168-02-SUMMARY.md
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
    - .planning/HANDOFF.json
    - .planning/WAITING.json

key-decisions:
  - "Approved outcome: ready with follow-up surface polish in Phase 169"
  - "Spectrum `/metrics` is sufficient to validate the new scrape-time gauges because ATT still relies on health-only visibility in its current live config shape"
  - "Phase 168 stops at bounded operator visibility; no alert-policy or dashboard redesign was pulled forward from later phases"

patterns-established:
  - "When metrics exposure differs by service, health remains the contract-of-record for bounded operator state"

requirements-completed: [OPER-01, OPER-02, OPER-03]

# Metrics
duration: 35min
completed: 2026-04-11
status: complete
---

# Phase 168 Plan 02 Summary

**Validated that the new storage and runtime pressure signals are healthy, readable, and low-noise on the live host.**

## Local Validation
- `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py -q`
- Result: `293 passed`
- `.venv/bin/mypy src/wanctl/runtime_pressure.py src/wanctl/metrics.py src/wanctl/health_check.py src/wanctl/wan_controller.py src/wanctl/steering/health.py src/wanctl/steering/daemon.py src/wanctl/autorate_continuous.py`
- Result: `Success: no issues found in 7 source files`
- `.venv/bin/ruff check src/wanctl/runtime_pressure.py src/wanctl/metrics.py src/wanctl/health_check.py src/wanctl/wan_controller.py src/wanctl/steering/health.py src/wanctl/steering/daemon.py src/wanctl/autorate_continuous.py tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py`
- Result: only the pre-existing `B009/B010` warnings in [wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py)

## Manual Gate Result
- **Decision:** `approved: ready with follow-up surface polish in Phase 169`
- Deployment target: `cake-shaper` (`wanctl@spectrum`, `wanctl@att`, `steering.service`)
- Deploy action: copied the touched observability modules to `/opt/wanctl/` and `/opt/wanctl/steering/`, then restarted all three services
- Live healthy-state checks after deploy:
  - `systemctl is-active wanctl@spectrum wanctl@att steering.service` -> `active active active`
  - warning journal over the restart window for all three services -> `No entries`
  - `http://10.10.110.223:9101/health` sampled twice -> `healthy`, `storage.status=ok`, `runtime.status=ok`, `storage.files.wal_bytes=67108864`, `runtime.rss_bytes≈77MB`
  - `http://10.10.110.227:9101/health` sampled twice -> `healthy`, `storage.status=ok`, `runtime.status=ok`, `storage.files.wal_bytes=67108864`, `runtime.rss_bytes≈77MB`
  - `http://127.0.0.1:9102/health` on the host -> `healthy`, `storage.status=ok`, `runtime.status=ok`, `storage.files.wal_bytes=67108864`, `runtime.rss_bytes≈69MB`
  - `http://10.10.110.223:9100/metrics` exposes `wanctl_process_resident_memory_bytes`, `wanctl_storage_db_bytes`, `wanctl_storage_wal_bytes`, and `wanctl_storage_total_bytes` with bounded values for `process="autorate"`
  - `http://10.10.110.227:9100/metrics` is still not exposed in the current live setup, so ATT validation remained health-only

## Notes
- The phase deliberately kept the payload incremental: existing `storage` counters were preserved and augmented with `files` plus `status`, while `runtime` was added as a separate section. That keeps later Phase 169 summary work free to improve presentation without rewriting the Phase 168 contract.
- ATT’s live config still does not expose a reachable `9100` metrics endpoint even though the new health fields are present and healthy. That is acceptable for Phase 168 because the requirement was bounded operator visibility, not universal metrics exposure; the surface consistency follow-up belongs in Phase 169.
