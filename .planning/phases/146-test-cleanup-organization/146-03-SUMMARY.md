---
phase: 146-test-cleanup-organization
plan: 03
subsystem: tests
tags: [test-organization, merge, redundancy-audit]
dependency_graph:
  requires: [146-01, 146-02]
  provides: [consolidated-test-files, reduced-file-count]
  affects: [tests/]
tech_stack:
  added: []
  patterns: [section-divider-merging, helper-rename-disambiguation]
key_files:
  created: []
  modified:
    - tests/test_fusion_healer.py
    - tests/test_queue_controller.py
    - tests/test_hysteresis_observability.py
    - tests/test_irtt_measurement.py
    - tests/test_irtt_thread.py
    - tests/test_alert_engine.py
    - tests/test_reflector_scorer.py
    - tests/test_asymmetry_analyzer.py
    - tests/test_webhook_delivery.py
    - tests/test_signal_processing.py
    - tests/test_check_config.py
    - tests/test_lock_utils.py
    - tests/test_retry_utils.py
    - tests/test_health_check.py
    - tests/test_history_cli.py
    - tests/test_metrics.py
    - tests/test_autorate_config.py
    - tests/test_config_base.py
    - tests/test_autorate_continuous.py
    - tests/test_check_cake.py
decisions:
  - Hysteresis config+reload merged into test_queue_controller.py (2549 lines) rather than test_wan_controller.py to balance file sizes
  - Hysteresis alert merged into test_hysteresis_observability.py (984 lines) rather than test_queue_controller.py to respect 3000-line cap
  - test_congestion_alerts.py kept separate (merging into test_alert_engine.py would exceed 3000 cap at 3371 lines)
  - Cross-cutting tests kept standalone per plan directive (daemon_interaction, failure_cascade, deployment_contracts, sigusr1_e2e)
  - Helper functions renamed with prefixes (_make_controller -> _make_reload_controller etc.) to avoid collisions in merged files
metrics:
  duration: 64min
  completed: "2026-04-06T15:52:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_deleted: 31
  files_modified: 20
  redundant_tests_removed: 1
---

# Phase 146 Plan 03: Feature Test Merge and Redundancy Audit Summary

Merged 31 feature-specific test files into their parent module test files and audited the 10 largest files for within-file redundancy. Reduced top-level test file count from 86 to 55 while maintaining all test coverage.

## Task 1: Merge feature-specific test files into parent module tests

### Merge Group Results

| Group | Source Files | Target File | Result Lines | Cap Check |
|-------|-------------|-------------|-------------|-----------|
| Fusion | 5 files (config, core, baseline, reload, integration) | test_fusion_healer.py | 2078 | OK |
| Hysteresis config/reload | 2 files | test_queue_controller.py | 2549 | OK |
| Hysteresis alert | 1 file | test_hysteresis_observability.py | 984 | OK |
| IRTT | 2 files (config, loss_alerts) | test_irtt_measurement.py + test_irtt_thread.py | 895 + 962 | OK |
| Alerting | 5 files (config, history, anomaly, connectivity, health) | test_alert_engine.py | 2753 | OK |
| Reflector/Asymmetry | 3 files (quality_config, health, persistence) | test_reflector_scorer.py + test_asymmetry_analyzer.py | 1119 + 830 | OK |
| Webhook | 1 file (integration) | test_webhook_delivery.py | 1340 | OK |
| Signal Processing | 2 files (config, strategy) | test_signal_processing.py | 1309 | OK |
| Small orphans | 10 files | Various parent modules | All under 3000 | OK |

### Files Deleted (31 total)

test_fusion_config.py, test_fusion_core.py, test_fusion_baseline.py, test_fusion_reload.py, test_fusion_healer_integration.py, test_hysteresis_config.py, test_hysteresis_reload.py, test_hysteresis_alert.py, test_irtt_config.py, test_irtt_loss_alerts.py, test_alerting_config.py, test_alert_history.py, test_anomaly_alerts.py, test_connectivity_alerts.py, test_health_alerting.py, test_reflector_quality_config.py, test_asymmetry_health.py, test_asymmetry_persistence.py, test_webhook_integration.py, test_signal_processing_config.py, test_signal_processing_strategy.py, test_check_config_smoke.py, test_config.py, test_config_edge_cases.py, test_lockfile.py, test_retry_utils_extended.py, test_health_check_history.py, test_history_tuning.py, test_hot_loop_retry_params.py, test_metrics_observability.py, test_metrics_reader.py

### Files Kept Separate (not merged)

- **test_congestion_alerts.py**: Merging would push test_alert_engine.py to ~3371 lines (over 3000 cap)
- **test_daemon_interaction.py**: Cross-cutting integration test between autorate and steering
- **test_failure_cascade.py**: Cross-cutting error propagation test
- **test_deployment_contracts.py**: Cross-cutting deployment validation
- **test_sigusr1_e2e.py**: Cross-cutting end-to-end signal handling
- **test_autorate_baseline_bounds.py**: Would push test_wan_controller.py over cap
- **test_autorate_entry_points.py**: 2059 lines, too large to merge into test_autorate_continuous.py
- **test_autorate_error_recovery.py**: 1090 lines, too large for safe merge
- **test_autorate_metrics_recording.py, test_autorate_telemetry.py**: Kept separate for clarity
- **test_router_behavioral.py**: No test_router_client.py target exists

## Task 2: Redundancy Audit of 10 Largest Test Files

### Files Audited

| File | Lines | Duplicate Bodies Found |
|------|-------|----------------------|
| test_check_cake.py | 2977 | 1 (removed) |
| test_health_check.py | 2919 | 0 |
| test_alert_engine.py | 2753 | 0 |
| test_queue_controller.py | 2549 | 0 |
| test_benchmark.py | 2284 | 0 |
| test_wan_controller.py | 2203 | 0 |
| test_fusion_healer.py | 2078 | 0 |
| test_autorate_entry_points.py | 2059 | 0 |
| test_metrics.py | 1846 | 0 |
| test_calibrate.py | 1628 | 0 |

### Redundancy Removed

**TestCLI.test_main_connectivity_error_returns_1** in test_check_cake.py: Exact duplicate of TestExitCodes.test_exit_code_1_errors (identical mock setup, assertion, and behavior). Kept the TestExitCodes version as the semantically appropriate location.

### Final Statistics

- **Top-level test files (tracked):** 55 (down from 86 before plan)
- **Subdirectory test files:** 46
- **Total tests collected:** 5,513
- **Subdirectories:** 5 (steering, backends, storage, tuning, dashboard)
- **No merged file exceeds 3000-line cap** (largest: test_check_cake.py at 2959)
- **1 redundant test removed** across 10 audited files

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing imports in merged files**
- **Found during:** Task 1 (all merge groups)
- **Issue:** When appending test bodies from source files, the source files' imports were stripped. Many source files had unique imports (datetime, deque, CYCLE_INTERVAL_SECONDS, LockFile, etc.) that weren't in the target.
- **Fix:** Added all missing imports to target files after each merge. Applied ruff --fix for import sorting.
- **Files modified:** All 19 merged target files

**2. [Rule 3 - Blocking] Helper function name collisions**
- **Found during:** Task 1 (Fusion, Hysteresis, Asymmetry merge groups)
- **Issue:** Multiple source files defined _make_controller() or _make_irtt_result() with different signatures.
- **Fix:** Renamed helpers with section-specific prefixes: _make_reload_controller, _make_baseline_controller, _make_health_irtt_result, etc.
- **Files modified:** test_fusion_healer.py, test_queue_controller.py, test_asymmetry_analyzer.py

**3. [Rule 3 - Blocking] Fixture name collisions**
- **Found during:** Task 1 (Alert Engine merge)
- **Issue:** default_rules and engine fixtures existed in both test_alert_engine.py and test_health_alerting.py.
- **Fix:** Renamed health_alerting fixtures: health_default_rules, health_engine, health_disabled_engine.
- **Files modified:** test_alert_engine.py

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | b6a7872 | Merge 31 feature-specific test files into parent module tests |
| 2 | 2b6a6a2 | Remove redundant test from test_check_cake.py |

## Self-Check: PASSED

- All 20 modified files exist
- All 31 deleted source files confirmed absent
- Both commits (b6a7872, 2b6a6a2) verified in git log
- 5 subdirectories (steering, backends, storage, tuning, dashboard) confirmed
- 1312 tests pass across all modified files (1 pre-existing failure in test_check_cake.py unrelated to our changes)
