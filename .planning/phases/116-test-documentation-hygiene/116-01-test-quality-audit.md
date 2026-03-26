# 116-01 Test Quality Audit

Date: 2026-03-26

## Methodology

- AST-based scan of 126 test files (3,888 test functions collected)
- Assertion patterns detected: `assert`, `pytest.raises`, `pytest.warns`, `pytest.fail`, `mock.assert_*`
- Over-mocked threshold: >4 `@patch` decorators per test function
- Tautological patterns: `assert True`, `assert x == x`, self-referential assertions

## Assertion-Free Tests

28 functions flagged by AST scan. After manual review:
- 6 are **fixtures** named `test_*` (false positives -- decorated with `@pytest.fixture`)
- 2 use `pytest.fail()` as assertion (not detected by initial AST pass)
- **20 genuine assertion-free tests** remaining

### False Positives (Fixtures Named test_*)

| File | Function | Lines | Disposition |
|------|----------|-------|-------------|
| `tests/test_metrics_reader.py` | `test_db_path` | 29-31 | Fixture, not a test |
| `tests/test_phase52_validation.py` | `test_db_path` | 25-27 | Fixture, not a test |
| `tests/test_storage_downsampler.py` | `test_db` | 20-25 | Fixture, not a test |
| `tests/test_storage_maintenance.py` | `test_db` | 16-21 | Fixture, not a test |
| `tests/test_storage_retention.py` | `test_db` | 20-25 | Fixture, not a test |
| `tests/test_storage_writer.py` | `test_db_path` | 23-25 | Fixture, not a test |

### Uses pytest.fail() (AST Missed)

| File | Function | Lines | Disposition |
|------|----------|-------|-------------|
| `tests/test_alert_engine.py` | `test_persistence_error_does_not_crash` | 236-253 | Has `pytest.fail()` -- not assertion-free |
| `tests/test_deployment_contracts.py` | `test_dependency_importable` | 198-206 | Has `pytest.fail()` -- not assertion-free |

### HIGH Risk -- Fix Required

| File | Test Function | Lines | Risk | Issue | Action |
|------|---------------|-------|------|-------|--------|
| `tests/test_autorate_continuous.py` | `test_profile_flag_accepted_by_argparse` | 380-400 | HIGH | Catches all exceptions silently; verifies nothing about --profile flag | fix |
| `tests/test_steering_daemon.py` | `test_profile_flag_accepted_by_argparse` | 4699-4720 | HIGH | Catches all exceptions silently; verifies nothing about --profile flag | fix |
| `tests/test_autorate_metrics_recording.py` | `test_no_error_when_storage_disabled` | 329-336 | HIGH | Tests dead code path (if None is not None); no assertion | fix |
| `tests/test_steering_confidence.py` | `test_recovery_in_degraded_state_dry_run` | 521-527 | HIGH | Runs 210 evaluate() cycles, never checks return value or state | fix |

### MEDIUM Risk -- Acceptable "Should Not Raise" Pattern

These tests verify robustness (function does not crash on edge-case input). The pattern is intentional: if the function raises, pytest reports a failure. Adding explicit assertions would strengthen them but they are not false-confidence tests.

| File | Test Function | Lines | Risk | Pattern | Action |
|------|---------------|-------|------|---------|--------|
| `tests/test_autorate_continuous.py` | `test_persist_reflector_events_no_writer` | 572-578 | MED | No-crash on None writer | acceptable |
| `tests/test_perf_profiler.py` | `test_clear_nonexistent_label` | 167-170 | MED | No-crash on missing key | acceptable |
| `tests/test_router_client.py` | `test_close_safe_when_no_clients_created` | 217-223 | MED | No-crash close() | acceptable |
| `tests/test_router_client.py` | `test_clear_router_password_no_attr` | 769-774 | MED | No-crash on missing attr | acceptable |
| `tests/test_routeros_rest.py` | `test_close_safe_when_no_session` | 981-986 | MED | No-crash close() on None session | acceptable |
| `tests/test_signal_processing_strategy.py` | `test_zero_time_gap_skipped` | 166-181 | MED | No-crash on duplicate timestamps | acceptable |
| `tests/test_state_manager.py` | `test_add_measurement_handles_missing_deque_keys` | 885-895 | MED | No-crash on missing keys | acceptable |
| `tests/test_state_manager.py` | `test_log_transition_handles_missing_transitions_key` | 962-971 | MED | No-crash on missing key | acceptable |
| `tests/test_systemd_utils.py` | `test_noop_when_sd_notify_none` (5 instances) | 39-118 | MED | No-crash when systemd unavailable | acceptable |
| `tests/test_tuning_config.py` | `test_idempotent` | 301-306 | MED | No-crash on double create_tables() | acceptable |
| `tests/test_tuning_wiring.py` | `test_tuning_exception_caught_and_logged` | 254-264 | MED | No-crash on bad tuning input | acceptable |
| `tests/test_webhook_integration.py` | `test_reload_webhook_url_no_webhook_delivery` | 631-649 | MED | No-crash on None webhook | acceptable |

## Tautological Tests

**Result: 0 tautological tests found.**

No tests assert on their own setup, `assert True`, or `assert x == x`. The test suite does not contain self-referential assertions.

## Over-Mocked Tests (Document Only)

Per D-02: over-mocked tests are lower risk and documented only, no fixes planned.

Threshold: >4 `@patch` decorators per test function.

| File | Test Function | Lines | Patch Count | Concern |
|------|---------------|-------|-------------|---------|
| `tests/test_benchmark.py` | `test_success_flow` | 888-913 | 5 | Patches subprocess, sleep, config, load, store |
| `tests/test_benchmark.py` | `test_json_output` | 968-994 | 5 | Same pattern as test_success_flow |
| `tests/test_benchmark.py` | `test_auto_store_called` | 1481-1513 | 7 | Patches full benchmark pipeline + store |
| `tests/test_benchmark.py` | `test_auto_store_failure_does_not_affect_exit` | 1522-1549 | 7 | Same as above, error path |
| `tests/test_benchmark.py` | `test_auto_store_stderr_message` | 1558-1589 | 7 | Same as above, stderr variant |
| `tests/test_benchmark.py` | `test_auto_store_with_wan_flag` | 1598-1626 | 7 | Same as above, WAN flag variant |
| `tests/test_benchmark.py` | `test_auto_store_with_label` | 1635-1665 | 7 | Same as above, label variant |
| `tests/test_benchmark.py` | `test_daemon_running_passed_to_store` | 1674-1701 | 7 | Same as above, daemon variant |
| `tests/test_calibrate.py` | `test_run_calibration_returns_result` | 1210-1230 | 6 | Patches calibration pipeline + store |

**Assessment:** All 9 over-mocked tests are in CLI tool test files (benchmark, calibrate) where subprocess, file I/O, and external services must be isolated. The high patch count is a consequence of testing CLI entry points that orchestrate many components. These tests still verify meaningful behavior (return codes, output format, error handling). No action needed.

## Previously Identified (Phase 112)

From `112-01-findings.md` pytest-deadfixtures scan (FSCAN-07):

| # | Fixture Name | Location | Description |
|---|-------------|----------|-------------|
| 1 | `sample_config_data` | `tests/conftest.py:22` | Sample configuration data for testing |
| 2 | `with_controller` | `tests/integration/conftest.py:41` | Get controller monitoring flag from CLI |
| 3 | `integration_output_dir` | `tests/integration/conftest.py:47` | Get integration test output directory |
| 4 | `memory_db` | `tests/test_alert_engine.py:16` | In-memory SQLite connection with tables |
| 5 | `mock_controller` | `tests/test_autorate_entry_points.py:113` | Mock ContinuousAutoRate controller |
| 6 | `controller` | `tests/test_autorate_error_recovery.py:61` | WANController with patched load_state |
| 7 | `sample_steering_response` | `tests/test_dashboard/conftest.py:45` | Steering health JSON schema dict |
| 8 | `sample_autorate_response` | `tests/test_dashboard/conftest.py:7` | Autorate health JSON schema dict |

**Note:** 6 fixtures named `test_*` found in this audit (see False Positives table above) are a related naming issue but are not orphaned -- they are actively used as fixtures.

## Summary

- **20 genuine assertion-free tests found** (4 HIGH risk to fix, 16 MEDIUM acceptable)
- **0 tautological tests found** (clean)
- **9 over-mocked tests found** (document only, all in CLI tool tests)
- **8 orphaned fixtures** from Phase 112 (previously cataloged)
- **6 fixtures named test_*** found (naming convention issue, not a test quality bug)
