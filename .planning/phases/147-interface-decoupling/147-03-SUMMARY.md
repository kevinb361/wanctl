---
phase: 147-interface-decoupling
plan: 03
title: "Health Check Decoupling"
subsystem: health-endpoint
tags: [decoupling, facade, health-check, interface]
dependency_graph:
  requires: [147-02]
  provides: [get_health_data-facade, health-check-public-api]
  affects: [health_check.py, wan_controller.py, queue_controller.py, alert_engine.py]
tech_stack:
  patterns: [facade-method, data-dict-compositor]
key_files:
  created: []
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/queue_controller.py
    - src/wanctl/alert_engine.py
    - src/wanctl/health_check.py
    - tests/test_health_check.py
    - scripts/check_private_access.py
decisions:
  - "Used side_effect (not return_value) for test mock helpers to support dynamic attr reads after fixture setup"
  - "Passed health_data dict through sub-builder methods instead of wan_controller object, minimizing signature changes"
  - "Kept wan_controller param in _build_tuning_section for config.tuning_config.bounds access (public attr)"
metrics:
  duration_minutes: 14
  completed: "2026-04-06T19:56:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 6
---

# Phase 147 Plan 03: Health Check Decoupling Summary

**One-liner:** Eliminated ~30 cross-module private attribute accesses from health_check.py via get_health_data() facade methods on WANController, QueueController, and AlertEngine.enabled property.

## What Was Done

### Task 1: Add get_health_data() facade methods (69af5bd)
- Added `WANController.get_health_data()` returning structured dict with keys: cycle_budget, signal_result, irtt, reflector, fusion, tuning, suppression_alert
- Added `QueueController.get_health_data()` returning hysteresis state dict (dwell_counter, transitions_suppressed, suppressions_per_min, window_start_epoch)
- Added `AlertEngine.enabled` property exposing `_enabled` read access
- All methods placed in `# PUBLIC FACADE API` sections
- Purely additive -- 190 existing tests passed unchanged

### Task 2: Update health_check.py to use public APIs (c4f745e)
- Replaced all ~30 cross-module private attribute accesses with facade calls
- `_build_wan_status()` now calls `wan_controller.get_health_data()` once and passes dict to all sub-builders
- `_build_rate_hysteresis_section()` now calls `qc.get_health_data()` for hysteresis state
- `_build_alerting_section()` now uses `ae.enabled` property instead of `ae._enabled`
- Eliminated all `getattr(wan_controller, "_private_attr", default)` patterns
- Removed 16 health_check entries from check_private_access.py allowlist
- Created `_configure_wan_health_data()` and `_configure_qc_health_data()` test helpers using `side_effect` for dynamic mock resolution
- All 107 health check tests pass, JSON output byte-identical

## Verification Results

- `pytest tests/test_health_check.py`: 107 passed
- `pytest tests/test_wan_controller.py tests/test_health_check.py`: 190 passed
- `grep -c 'wan_controller\._|qc\._|ae\._' src/wanctl/health_check.py`: 0
- `python scripts/check_private_access.py src/wanctl/`: 44 violations (44 allowlisted, 0 new)
- `mypy src/wanctl/health_check.py`: clean (no errors in health_check.py)

## Private Accesses Eliminated (16 allowlist entries)

| Attr | Source | Replaced By |
|------|--------|-------------|
| `_profiler` | WANController | `health_data["cycle_budget"]["profiler"]` |
| `_overrun_count` | WANController | `health_data["cycle_budget"]["overrun_count"]` |
| `_cycle_interval_ms` | WANController | `health_data["cycle_budget"]["cycle_interval_ms"]` |
| `_warning_threshold_pct` | WANController | `health_data["cycle_budget"]["warning_threshold_pct"]` |
| `_last_signal_result` | WANController | `health_data["signal_result"]` |
| `_irtt_thread` | WANController | `health_data["irtt"]["thread"]` |
| `_irtt_correlation` | WANController | `health_data["irtt"]["correlation"]` |
| `_last_asymmetry_result` | WANController | `health_data["irtt"]["last_asymmetry_result"]` |
| `_reflector_scorer` | WANController | `health_data["reflector"]["scorer"]` |
| `_fusion_enabled` | WANController | `health_data["fusion"]["enabled"]` |
| `_last_icmp_filtered_rtt` | WANController | `health_data["fusion"]["icmp_filtered_rtt"]` |
| `_last_fused_rtt` | WANController | `health_data["fusion"]["fused_rtt"]` |
| `_fusion_icmp_weight` | WANController | `health_data["fusion"]["icmp_weight"]` |
| `_fusion_healer` | WANController | `health_data["fusion"]["healer"]` |
| `_yellow_dwell` | QueueController | `qc_health["hysteresis"]["dwell_counter"]` |
| `_enabled` | AlertEngine | `ae.enabled` property |

Plus 5 additional getattr-based accesses eliminated: `_tuning_enabled`, `_tuning_state`, `_parameter_locks`, `_pending_observation`, `_suppression_alert_threshold`.

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 69af5bd | feat(147-03): add get_health_data() facade methods and enabled property |
| 2 | c4f745e | refactor(147-03): eliminate all cross-module private access from health_check.py |

## Self-Check: PASSED

All created/modified files exist. Both commits verified in git log.
