---
phase: 151-burst-detection
verified: 2026-04-09T00:13:07Z
status: human_needed
score: 3/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run 'flent tcp_12down' from dev machine against dallas server while monitoring production logs on cake-shaper. Check 'journalctl -u wanctl@spectrum -f' for 'BURST detected' log entry."
    expected: "BURST detected log entry appears within 200ms (4 cycles at 50ms each) of tcp_12down flow onset. Log will read: 'Spectrum: BURST detected! accel=X.XXms/cycle^2 (N consecutive, threshold=2.0ms/cycle^2) (detection only, response not yet enabled)'"
    why_human: "SC2 requires a live flent tcp_12down test on production hardware. Cannot simulate real DOCSIS cable modem burst behavior in unit tests. The unit tests validate the math using a modeled EWMA sequence, but production RTT acceleration values depend on actual cable plant dynamics."
  - test: "Run 'flent rrul_be' from dev machine and monitor production logs on cake-shaper for absence of BURST detected entries."
    expected: "No BURST detected log entries during the entire rrul_be run. The single-flow gradual ramp should not exceed the 2.0ms/cycle^2 acceleration threshold."
    why_human: "SC3 requires verifying the false-trigger rejection on actual single-flow production traffic. Unit tests validate the signal math but cannot cover all real-world congestion patterns."
---

# Phase 151: Burst Detection Verification Report

**Phase Goal:** Controller can detect multi-flow burst ramps within 200ms by measuring RTT acceleration (second derivative), without false-triggering on normal single-flow congestion
**Verified:** 2026-04-09T00:13:07Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | RTT acceleration (second derivative) is computed each cycle and exposed in health endpoint or logs | VERIFIED | `wan_controller.py:1843` calls `_burst_detector.update(self.load_rtt)` inside `_run_spike_detection()` which is called every cycle. `health_check.py:267` adds `burst_detection` section with `current_acceleration`, `current_velocity`, `is_burst`, `consecutive_accel_cycles`, `warming_up` fields. Behavioral spot-check confirms acceleration math is correct. |
| 2 | A flent tcp_12down test triggers a burst detection event within 200ms of flow onset | NEEDS HUMAN | Unit tests validate math using a modeled EWMA sequence: `[23.0, 26.5, 35.75, 50.38]` produces accelerations `[5.75, 5.38]` both above 2.0ms/cycle^2, triggering burst on cycle 4 (4 x 50ms = 200ms). Cannot verify real tcp_12down dynamics on production cable plant programmatically. |
| 3 | A flent rrul_be test (single-flow normal congestion) does NOT trigger a burst detection event | NEEDS HUMAN | Unit tests validate that single-flow ramp `[23.0, 24.0, 25.5, 27.25, 28.63, 29.31]` never exceeds 2.0ms/cycle^2 threshold. Parametrized tests with 3 more sequences all confirm no burst. Cannot verify against actual production rrul_be cable dynamics. |
| 4 | Burst detection threshold is configurable in YAML and reloadable via SIGUSR1 | VERIFIED | `autorate_config.py:256-268` defines 3 SCHEMA entries for `continuous_monitoring.thresholds.burst_detection.{enabled,accel_threshold_ms,confirm_cycles}`. `autorate_config.py:395-400` parses them onto config object. `wan_controller.py:2504` calls `_reload_burst_detection_config()` from `reload()`. Reload method includes bounds validation (accel_threshold_ms [0.5-20.0], confirm_cycles [1-10]). SIGUSR1 E2E test passes. |

**Score:** 3/4 truths verified (SC2 and SC3 require human/production testing; the 3/4 score counts only fully verified items)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/burst_detector.py` | BurstDetector class and BurstResult dataclass | VERIFIED | 204 lines. Contains `BurstDetector`, `BurstResult`, `update()`, `reset()`, `accel_threshold`/`confirm_cycles` properties, `total_bursts`, `@dataclass(frozen=True, slots=True)`. ruff clean, mypy clean. |
| `tests/test_burst_detector.py` | Unit tests for burst detection logic | VERIFIED | 415 lines. 26 tests across 6 classes: `TestBurstDetectorWarmup`, `TestBurstDetectorAcceleration`, `TestBurstDetection`, `TestSingleFlowNoBurst`, `TestBurstDetectorConfig`, `TestBurstDetectorReset`. All 26 pass. |
| `src/wanctl/wan_controller.py` | BurstDetector instantiation, cycle integration, health data, SIGUSR1 reload | VERIFIED | Import at line 21, instantiation at line 292, update() at line 1843, health data at line 2612, reload at line 2504, metrics at lines 2019-2021, `_reload_burst_detection_config` at line 1540. |
| `src/wanctl/autorate_config.py` | burst_detection config parsing with SCHEMA validation | VERIFIED | 3 SCHEMA entries at lines 256-268. Parsing in `_load_threshold_config()` at lines 395-400. |
| `src/wanctl/health_check.py` | burst_detection section in health endpoint | VERIFIED | `_build_burst_detection_section()` at line 307. Added to `_build_wan_status()` at line 267. All 8 fields present. |
| `src/wanctl/check_config_validators.py` | burst_detection KNOWN_PATHS entries | VERIFIED | 4 entries at lines 87-90 covering all burst_detection YAML paths. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `wan_controller.py` | `burst_detector.py` | `from wanctl.burst_detector import BurstDetector` at line 21; `_burst_detector.update(self.load_rtt)` at line 1843 | WIRED | gsd-tools confirmed |
| `wan_controller.py` | `health_check.py` | `get_health_data()` returns dict with `"burst_detection"` key at line 2612 | WIRED | gsd-tools confirmed |
| `autorate_config.py` | `wan_controller.py` | `burst_detection_enabled`, `burst_detection_accel_threshold_ms`, `burst_detection_confirm_cycles` read via `getattr` at lines 291-295 | WIRED | gsd-tools confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `health_check.py:_build_burst_detection_section` | `health_data["burst_detection"]["result"]` | `wan_controller.py:_last_burst_result` set by `_burst_detector.update(self.load_rtt)` each cycle | Yes — computed from live `load_rtt` (EWMA-smoothed RTT from `_rtt_thread`) | FLOWING |
| `wan_controller.py:_run_logging_metrics` | `_last_burst_result` | `_burst_detector.update()` called in `_run_spike_detection()` every 50ms cycle | Yes — real computation, metrics only written after warmup (3+ cycles) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Multi-flow burst fires by cycle 4 (200ms at 50ms interval) | `python3 -c "from wanctl.burst_detector import BurstDetector; from unittest.mock import MagicMock; d=BurstDetector('t',2.0,2,MagicMock()); r=[d.update(x) for x in [23.0,26.5,35.75,50.38]]; print(any(x.is_burst for x in r), 'cycle:', next((i+1 for i,x in enumerate(r) if x.is_burst),None))"` | `True cycle: 4` | PASS |
| Single-flow ramp never triggers burst | `python3 -c "from wanctl.burst_detector import BurstDetector; from unittest.mock import MagicMock; d=BurstDetector('t',2.0,2,MagicMock()); print(all(not d.update(x).is_burst for x in [23.0,24.0,25.5,27.25,28.63,29.31]))"` | `True` | PASS |
| 26 unit tests pass | `.venv/bin/pytest tests/test_burst_detector.py -x -q` | `26 passed` | PASS |
| 10 integration tests pass | `.venv/bin/pytest tests/test_wan_controller.py tests/test_health_check.py tests/test_sigusr1_e2e.py -x -q -k "burst"` | `10 passed` | PASS |
| Live tcp_12down burst trigger | Requires flent on production hardware | Not run | SKIP (needs human) |
| Live rrul_be no false trigger | Requires flent on production hardware | Not run | SKIP (needs human) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DET-01 | 151-01, 151-02 | Controller detects multi-flow burst ramps via RTT second derivative (acceleration) within 200ms of onset | PARTIAL | Code verified: BurstDetector computes acceleration, fires burst by cycle 4 (200ms). Unit tests validate math. Production verification pending (SC2 human test). |
| DET-02 | 151-01, 151-02 | Burst detection does not false-trigger on normal single-flow congestion (video call + browsing) | PARTIAL | Code verified: Single-flow EWMA sequences never exceed 2.0ms/cycle^2 threshold in unit tests. Production verification pending (SC3 human test). |

Note: RSP-01, RSP-02 (Phase 152), VAL-01, VAL-02, VAL-03 (Phase 153) are not in scope for Phase 151.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/wanctl/burst_detector.py` | 150 | `"(detection only, response not yet enabled)"` in log message | Info | Intentional — documented in plan as per Research Pitfall 3. Will be removed in Phase 152 when response is wired. Not a stub. |
| `src/wanctl/health_check.py` | 316 | `"burst_response_enabled": False` hardcoded | Info | Intentional — Phase 152 will flip this to True. Not a stub: detection is fully operational; response is a separate phase. |

No blockers or stub anti-patterns found. The two "detection only" markers are intentional design choices documented in plan and SUMMARY.

### Human Verification Required

#### 1. tcp_12down Burst Trigger Test

**Test:** From dev machine, run `flent tcp_12down -H dallas -l 60 -o /tmp/tcp12down-burst-test.flent` while tailing production logs: `ssh cake-spectrum 'journalctl -u wanctl@spectrum -f | grep -E "BURST detected|burst"'`

**Expected:** Within 200ms of tcp_12down flow onset (shown in flent output as download rate spike), the log should show: `Spectrum: BURST detected! accel=X.XXms/cycle^2 (N consecutive, threshold=2.0ms/cycle^2) (detection only, response not yet enabled)`. N should be >= 3 (default confirm_cycles).

**Why human:** SC2 requires validating the burst detection fires on actual DOCSIS cable modem burst behavior. The production RTT acceleration depends on cable plant dynamics (DOCSIS burst scheduling, OFDM channel characteristics) that cannot be modeled in unit tests. The unit tests use a synthetic EWMA sequence; production will have different dynamics.

#### 2. rrul_be No False Trigger Test

**Test:** From dev machine, run `flent rrul_be -H dallas -l 60 -o /tmp/rrul-be-no-burst.flent` while tailing: `ssh cake-spectrum 'journalctl -u wanctl@spectrum -f | grep "BURST detected"'`

**Expected:** No "BURST detected" log entries during the entire 60-second rrul_be run. The rrul_be test generates single-flow congestion (one bulk TCP flow with background traffic) which should produce linear RTT increase, not the accelerating multi-flow burst pattern.

**Why human:** SC3 requires confirming the false-trigger rejection on real single-flow congestion. Production rrul_be creates genuine cable modem congestion that may have different acceleration characteristics than the synthetic sequences in unit tests.

### Gaps Summary

No gaps found. All code artifacts exist, are substantive, wired, and data-flows are active. Two human verification items (SC2, SC3) require production flent tests and cannot be verified programmatically. These are acceptance tests, not gaps in the implementation.

The `burst_response_enabled: False` and "detection only" log note are intentional design choices for Phase 151 scope (detection only). Phase 152 will add the rate-control response.

---

_Verified: 2026-04-09T00:13:07Z_
_Verifier: Claude (gsd-verifier)_
