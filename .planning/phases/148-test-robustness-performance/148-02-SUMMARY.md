---
phase: 148-test-robustness-performance
plan: 02
subsystem: tests
tags: [mock-retargeting, public-api, test-robustness, cross-module-patches]
dependency_graph:
  requires: [147-interface-decoupling]
  provides: [cross-module-private-patch-elimination]
  affects: [tests/test_metrics.py, tests/test_check_cake.py, tests/test_router_behavioral.py, tests/test_fusion_healer.py, tests/test_autorate_entry_points.py, tests/test_autorate_continuous.py, src/wanctl/check_cake_fix.py]
tech_stack:
  added: []
  patterns: [public-api-mocking, signal-raise-for-test, session-request-mock]
key_files:
  created: []
  modified:
    - tests/test_metrics.py
    - tests/test_check_cake.py
    - tests/test_router_behavioral.py
    - tests/test_fusion_healer.py
    - tests/test_autorate_entry_points.py
    - tests/test_autorate_continuous.py
    - src/wanctl/check_cake_fix.py
decisions:
  - "Removed _check_connectivity_alerts patches entirely -- method is no-op with default controller state (no mock replacement needed)"
  - "Promoted _save_snapshot, _confirm_apply, _show_diff_table to public in check_cake_fix.py -- already de-facto public (called cross-module)"
  - "Replaced client._request patches with client._session.request -- same args, public Session API"
  - "Used register_signal_handlers + raise_signal for fusion healer SIGUSR1 test -- exercises real signal path"
  - "Used IRTTMeasurement.is_available=False mock instead of _start_irtt_thread patch -- natural short-circuit"
  - "Used paramiko.SSHClient mock at module level instead of ssh._ensure_connected/_client patches"
metrics:
  duration: 17m
  completed: 2026-04-08
  tasks_completed: 2
  tasks_total: 2
  files_modified: 7
---

# Phase 148 Plan 02: Cross-Module Private Patch Retargeting Summary

Retargeted 22 cross-module private patches across 6 test files to use public APIs, function promotion, and standard library mocks.

## Task Results

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Retarget test_metrics.py and test_check_cake.py (18 patches) | 94fe5c5 | Removed 5 _check_connectivity_alerts patches; promoted 3 check_cake_fix functions to public; replaced 10 client._request with client._session.request |
| 2 | Retarget 4 remaining patches across 4 files | e227ab2 | Mock RouterOSREST/SSH constructors; use raise_signal for SIGUSR1; mock IRTTMeasurement; mock paramiko.SSHClient |

## Approach Details

### test_metrics.py (5 patches removed)
The `_check_connectivity_alerts` patches were suppressing a method that is a no-op when called with a non-None measured_rtt and default controller state (`_connectivity_offline_start = None`). Simply removing the patches lets the method execute harmlessly. No replacement mock needed.

### test_check_cake.py (18 patches retargeted)
- **8 check_cake_fix._ patches**: Promoted `_save_snapshot`, `_confirm_apply`, `_show_diff_table` to public API in `src/wanctl/check_cake_fix.py`. These were already called cross-module and are de-facto public. Updated all patch strings and direct imports.
- **10 client._request patches**: Replaced with `client._session.request` mocks. The `_request` method is a thin wrapper around `session.request` with SSL warning suppression. Same call signature, public standard library API.

### test_router_behavioral.py (1 patch retargeted)
Replaced `_create_transport_with_password` patch with mocks on `wanctl.routeros_rest.RouterOSREST` and `wanctl.routeros_ssh.RouterOSSSH.from_config` constructors.

### test_fusion_healer.py (1 patch retargeted)
Replaced `signal_utils._reload_event` patch with `register_signal_handlers()` + `sig.raise_signal(sig.SIGUSR1)`. This exercises the real signal path and verifies via public `is_reload_requested()` and `reset_reload_state()`.

### test_autorate_entry_points.py (1 patch retargeted)
Replaced `_start_irtt_thread` patch with `IRTTMeasurement` mock returning `is_available=False`. The function naturally returns None when IRTT is unavailable.

### test_autorate_continuous.py (1 patch retargeted)
Replaced `ssh._ensure_connected` + `ssh._client` patches with `paramiko.SSHClient` mock at module level. The mock client's `exec_command` raises the expected error.

## Verification Results

- All 6 modified test files: 410 passed, 18 failed, 33 errors (identical to main repo baseline -- all failures/errors are pre-existing)
- Test collection count: 4195 tests (unchanged)
- Zero `_check_connectivity_alerts` in test_metrics.py
- Zero `check_cake_fix._` private patches in test_check_cake.py
- Zero `_create_transport_with_password` in test_router_behavioral.py
- Zero `signal_utils._reload_event` in test_fusion_healer.py
- Zero `_start_irtt_thread` in test_autorate_entry_points.py
- Zero `ssh._ensure_connected`/`ssh._client` in test_autorate_continuous.py

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Pre-existing Issues (out of scope)

- test_metrics.py: 5 ERRORs + 1 FAIL in TestSignalQualityInRunCycle/TestIRTTInRunCycle/TestWANControllerIRTTWriteTs (MagicMock RateLimiter incompatibility)
- test_check_cake.py: 2 FAILs in TestTinDistribution (Python 3.12 platform.py decode error)
- test_autorate_continuous.py: 28 ERRORs in TestMeasureRTTReflectorScoring (fixture setup) + 16 FAILs (various pre-existing)

## Self-Check: PASSED

- All 8 files exist (7 modified + 1 SUMMARY)
- Commit 94fe5c5: found (Task 1)
- Commit e227ab2: found (Task 2)
- Public functions verified: save_snapshot, confirm_apply, show_diff_table
