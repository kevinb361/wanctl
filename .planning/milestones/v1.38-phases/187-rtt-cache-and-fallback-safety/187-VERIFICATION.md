---
phase: 187-rtt-cache-and-fallback-safety
verified: 2026-04-15T11:28:42Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Current-cycle status publication is locked by regression coverage, including zero-success publication and the first-cycle None sentinel"
  gaps_remaining: []
  regressions: []
---

# Phase 187: RTT Cache And Fallback Safety Verification Report

**Phase Goal:** Prevent zero-success RTT cycles from silently reusing stale cached RTT as healthy current input
**Verified:** 2026-04-15T11:28:42Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Every background RTT cycle publishes explicit current-cycle status while preserving `_cached` stale-prefer-none semantics. | ✓ VERIFIED | [src/wanctl/rtt_measurement.py](/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py:107) defines `RTTCycleStatus`; [src/wanctl/rtt_measurement.py](/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py:400) stores `_last_cycle_status`; [src/wanctl/rtt_measurement.py](/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py:458) publishes status before the unchanged cache branch. |
| 2 | `WANController.measure_rtt()` consumes current-cycle status so zero-success cycles reuse cached `rtt_ms` but publish current-cycle host truth. | ✓ VERIFIED | [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:924) reads `get_cycle_status()`; [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:945) switches to current-cycle host metadata when `successful_count == 0`; [tests/test_wan_controller.py](/home/kevin/projects/wanctl/tests/test_wan_controller.py:2762) locks the branch behavior. |
| 3 | Zero-success reuse keeps staleness honesty and does not alter the existing 5s hard cutoff or SAFE-02 fallback pipeline. | ✓ VERIFIED | [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:932) keeps the `age > 5.0` hard fail; [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:962) still passes `timestamp=snapshot.timestamp`; [tests/test_autorate_error_recovery.py](/home/kevin/projects/wanctl/tests/test_autorate_error_recovery.py:359) proves zero-success cached cycles do not enter ICMP fallback. |
| 4 | Regression coverage locks the consumer-side zero-success behavior across controller, health contract, and SAFE-02 non-regression. | ✓ VERIFIED | [tests/test_wan_controller.py](/home/kevin/projects/wanctl/tests/test_wan_controller.py:2782) verifies cached RTT reuse and host override; [tests/test_health_check.py](/home/kevin/projects/wanctl/tests/test_health_check.py:4232) verifies `state="collapsed"` and `successful_count=0`; [tests/test_autorate_error_recovery.py](/home/kevin/projects/wanctl/tests/test_autorate_error_recovery.py:359) verifies no fallback escalation. |
| 5 | Regression coverage locks the new producer-side current-cycle status publication contract itself. | ✓ VERIFIED | [tests/test_rtt_measurement.py](/home/kevin/projects/wanctl/tests/test_rtt_measurement.py:684) pins the first-cycle `None` sentinel; [tests/test_rtt_measurement.py](/home/kevin/projects/wanctl/tests/test_rtt_measurement.py:816) proves zero-success cycles publish status while preserving `_cached`; [tests/test_rtt_measurement.py](/home/kevin/projects/wanctl/tests/test_rtt_measurement.py:873) proves successful cycles publish current host metadata and agree with the cached snapshot. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/wanctl/rtt_measurement.py` | `RTTCycleStatus`, `_last_cycle_status`, `get_cycle_status()`, and publish site in `_run()` | ✓ VERIFIED | Artifact exists and is substantive. The status surface is wired into `_run()` and fed from real `successful_rtts` / `successful_hosts` output. |
| `src/wanctl/wan_controller.py` | `measure_rtt()` zero-success override branch consuming `get_cycle_status()` | ✓ VERIFIED | Artifact exists and is wired. The branch preserves cached RTT and snapshot timestamp while overriding current-cycle host publication. |
| `tests/test_wan_controller.py` | Consumer-side regression coverage for zero-success behavior | ✓ VERIFIED | `TestZeroSuccessCycle` is present and executable. |
| `tests/test_health_check.py` | Collapsed measurement witness for zero-success current cycles | ✓ VERIFIED | Directly exercises `_build_measurement_section()` with empty current successful hosts. |
| `tests/test_autorate_error_recovery.py` | SAFE-02 non-regression witness | ✓ VERIFIED | Directly verifies the cached zero-success path does not invoke fallback. |
| `tests/test_rtt_measurement.py` | Producer-side regression coverage for cycle-status publication | ✓ VERIFIED | Directly exercises `BackgroundRTTThread._run()` and `get_cycle_status()` without mocking the accessor. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `BackgroundRTTThread._run()` | `self._last_cycle_status` | Assignment before `if successful_rtts:` | ✓ WIRED | [src/wanctl/rtt_measurement.py](/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py:458) assigns `RTTCycleStatus(...)` before cache overwrite logic. |
| `BackgroundRTTThread.get_cycle_status()` | `self._last_cycle_status` | Direct field read | ✓ WIRED | [src/wanctl/rtt_measurement.py](/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py:411) returns the shared field directly. |
| `WANController.measure_rtt()` | `BackgroundRTTThread.get_cycle_status()` | Direct method call after `get_latest()` | ✓ WIRED | [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:924) reads `cycle_status` immediately after `snapshot`. |
| `WANController.measure_rtt()` zero-success branch | `_record_live_rtt_snapshot(timestamp=snapshot.timestamp)` | Snapshot timestamp retained on both branches | ✓ WIRED | [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:960) preserves `snapshot.timestamp`. |
| `tests/test_rtt_measurement.py::TestBackgroundRTTThread` | `BackgroundRTTThread.get_cycle_status()` | Direct assertions on constructed thread instances | ✓ WIRED | [tests/test_rtt_measurement.py](/home/kevin/projects/wanctl/tests/test_rtt_measurement.py:700), [tests/test_rtt_measurement.py](/home/kevin/projects/wanctl/tests/test_rtt_measurement.py:865), and [tests/test_rtt_measurement.py](/home/kevin/projects/wanctl/tests/test_rtt_measurement.py:909) call the real accessor. |
| `tests/test_health_check.py::test_zero_success_cycle_reports_collapsed` | `HealthCheckHandler._build_measurement_section()` | Direct call on constructed health data | ✓ WIRED | [tests/test_health_check.py](/home/kevin/projects/wanctl/tests/test_health_check.py:4242) exercises the health builder directly. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/wanctl/rtt_measurement.py` | `_last_cycle_status.successful_count`, `.active_hosts`, `.successful_hosts` | `_ping_with_persistent_pool(hosts)` result at [rtt_measurement.py](/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py:452) | Yes | ✓ FLOWING |
| `src/wanctl/wan_controller.py` | `active_hosts`, `successful_hosts`, `rtt_ms`, `timestamp` passed to `_record_live_rtt_snapshot()` | `get_latest()` + `get_cycle_status()` at [wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:923) | Yes | ✓ FLOWING |
| `tests/test_health_check.py` | `measurement["state"]`, `successful_count`, `stale` | Directly built from health payload inputs at [tests/test_health_check.py](/home/kevin/projects/wanctl/tests/test_health_check.py:4235) | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Producer contract: first-cycle sentinel and zero/success publication | `.venv/bin/pytest -o addopts='' tests/test_rtt_measurement.py::TestBackgroundRTTThread::test_cycle_status_is_none_before_first_cycle tests/test_rtt_measurement.py::TestBackgroundRTTThread::test_cycle_status_published_on_zero_success_preserves_cached tests/test_rtt_measurement.py::TestBackgroundRTTThread::test_cycle_status_published_on_successful_cycle -q` | `3 passed in 0.31s` | ✓ PASS |
| Consumer branch: zero-success cached-cycle handling | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py::TestZeroSuccessCycle -q` | `6 passed in 0.55s` | ✓ PASS |
| Health + SAFE-02 witnesses | `.venv/bin/pytest -o addopts='' tests/test_health_check.py::TestMeasurementContract::test_zero_success_cycle_reports_collapsed tests/test_autorate_error_recovery.py::TestMeasurementFailureRecovery::test_zero_success_cycle_does_not_invoke_icmp_failure_fallback -q` | `2 passed in 1.09s` | ✓ PASS |
| Full phase regression slice | `.venv/bin/pytest -o addopts='' tests/test_rtt_measurement.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_error_recovery.py -q` | `362 passed in 59.01s` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `MEAS-02` | `187-01`, `187-02`, `187-03`, `187-04` | A background RTT cycle with zero successful reflectors does not continue to present the last cached RTT as a healthy current measurement. | ✓ SATISFIED | Producer status is published at [src/wanctl/rtt_measurement.py](/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py:458); consumer publishes empty current `successful_hosts` at [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:945); producer and consumer regressions exist in [tests/test_rtt_measurement.py](/home/kevin/projects/wanctl/tests/test_rtt_measurement.py:816) and [tests/test_health_check.py](/home/kevin/projects/wanctl/tests/test_health_check.py:4232). |
| `SAFE-01` | `187-01`, `187-02` | When measurement quality degrades, controller behavior follows explicit bounded semantics instead of silently acting on stale RTT as if it were current. | ✓ SATISFIED | `measure_rtt()` reuses cached `rtt_ms` only inside the existing cutoff and publishes current-cycle collapse explicitly via host metadata at [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:945). |
| `SAFE-02` | `187-02`, `187-03` | Existing ICMP failure fallback and total-connectivity-loss handling remain intact for real outages and do not regress while adding measurement-degradation handling. | ✓ SATISFIED | The hard cutoff remains unchanged at [src/wanctl/wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:932); zero-success cached cycles are proven not to invoke fallback in [tests/test_autorate_error_recovery.py](/home/kevin/projects/wanctl/tests/test_autorate_error_recovery.py:359). |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| None | — | No phase-scoped blocker or warning anti-patterns found | ℹ️ Info | Grep hits were routine initializers and test fixtures, not user-visible stubs or disconnected code paths. |

### Gaps Summary

The prior gap is closed. Phase 187 now has both sides of the contract verified: `BackgroundRTTThread` publishes current-cycle status on every cycle without clobbering the stale-prefer-none cache, and `WANController.measure_rtt()` consumes that status to keep bounded controller behavior while no longer presenting zero-success cycles as healthy current measurements.

The regression floor is now complete for this phase. The targeted producer tests that were previously missing are present and passing, and the broader phase slice remains green.

---

_Verified: 2026-04-15T11:28:42Z_
_Verifier: Claude (gsd-verifier)_
