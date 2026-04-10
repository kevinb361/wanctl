---
phase: 159-cake-signal-infrastructure
verified: 2026-04-09T23:30:00Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
---

# Phase 159: CAKE Signal Infrastructure Verification Report

**Phase Goal:** CAKE stats read, processed, and exposed every cycle -- no behavior change
**Verified:** 2026-04-09T23:30:00Z
**Status:** PASSED
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | CakeSignalProcessor computes EWMA drop rate from raw netlink counter deltas | VERIFIED | `cake_signal.py` lines 251-257: EWMA formula applied to `active_drops_per_sec` and `total_drops_per_sec` |
| 2 | u32 counter wrapping is handled correctly without spurious spikes | VERIFIED | `u32_delta()` at line 42: wrap-around path + `SANITY_MAX_DELTA = 1_000_000` guard; 7 tests in `TestU32Delta` all pass |
| 3 | First delta after cold start is discarded (not fed to EWMA) | VERIFIED | Lines 196-230: when `self._prev_counters is None`, stores counters and returns `cold_start=True, drop_rate=0.0` -- EWMA not updated |
| 4 | Active drop rate excludes Bulk tin (index 0); total drop rate includes all tins | VERIFIED | Lines 243-244: `active_drops = sum(deltas.get(i, 0) for i in range(1, len(tins_raw)))` vs `total_drops = sum(...)` for all; `TestCakeSignalProcessorTinSeparation` passes |
| 5 | CakeSignalSnapshot is frozen/immutable and safe to pass to health endpoint | VERIFIED | `@dataclass(frozen=True, slots=True)` at line 86; `TestCakeSignalSnapshot.test_frozen` raises `FrozenInstanceError` |
| 6 | CAKE stats are read in run_cycle hot path via existing NetlinkCakeBackend.get_queue_stats() | VERIFIED | `wan_controller.py` line 1924-1925: `PerfTimer("autorate_cake_stats", ...)` wraps `self._run_cake_stats()` inserted between ewma_spike and congestion_assess |
| 7 | Health endpoint includes cake_signal section with per-tin stats when enabled | VERIFIED | `health_check.py` `_build_cake_signal_section()` lines 488-524; wired into response assembly at lines 268-270 |
| 8 | Health endpoint omits cake_signal section when disabled or unsupported | VERIFIED | Lines 498-499: early return `None` when `not supported` or `not enabled`; 3 None-return tests pass |
| 9 | CAKE signal metrics (drop_rate, backlog, peak_delay per direction) written to metrics DB via DeferredIOWorker | VERIFIED | `wan_controller.py` lines 2283-2309: 4 metrics x 2 directions added to `metrics_batch`; cold_start guard present; `metrics_enabled` toggle guard present |
| 10 | cake_signal YAML config section controls independent enable/disable of sub-features | VERIFIED | `_parse_cake_signal_config()` lines 610-668: independently parses `enabled`, `drop_rate.enabled`, `backlog.enabled`, `peak_delay.enabled`, `metrics.enabled`, `drop_rate.time_constant_sec` with bounds [0.1, 30.0]; 8 YAML config tests pass |
| 11 | SIGUSR1 hot-reloads cake_signal config without daemon restart | VERIFIED | `_reload_cake_signal_config()` lines 1765-1789 logs transitions and updates `_dl_cake_signal.config` and `_ul_cake_signal.config`; registered in `reload()` at line 2797; 3 reload tests pass |
| 12 | All sub-features default to disabled (safe rollout) | VERIFIED | `CakeSignalConfig` defaults all booleans `False`, `time_constant_sec=1.0`; `TestCakeSignalConfig.test_defaults` passes |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/cake_signal.py` | CakeSignalProcessor, CakeSignalSnapshot, TinSnapshot, CakeSignalConfig, u32_delta | VERIFIED | 291 lines; all 5 exports present; frozen dataclasses confirmed |
| `tests/test_cake_signal.py` | Unit tests CAKE-01, CAKE-02, CAKE-03, YAML config, reload | VERIFIED | 716 lines (min 150); 45 tests across 12 test classes; all pass |
| `src/wanctl/wan_controller.py` | _run_cake_stats, _init_cake_signal, _parse_cake_signal_config, _reload_cake_signal_config, cake_signal in get_health_data | VERIFIED | All 5 methods present and wired; CAKE metrics in _run_logging_metrics |
| `src/wanctl/health_check.py` | _build_cake_signal_section | VERIFIED | Lines 488-524; conditional inclusion in response assembly at lines 268-270 |
| `tests/test_health_check.py` | TestBuildCakeSignalSection, cake_signal mock | VERIFIED | 5 tests in TestBuildCakeSignalSection; mock helper updated with isinstance guard |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `wan_controller.py` | `cake_signal.py` | `from wanctl.cake_signal import CakeSignalProcessor, CakeSignalSnapshot` | WIRED | Line 586 in `_init_cake_signal`; lazy import inside method |
| `wan_controller.py` | `NetlinkCakeBackend.get_queue_stats` | `adapter.dl_backend.get_queue_stats("")` | WIRED | Lines 2090, 2093 in `_run_cake_stats` |
| `health_check.py` | `WANController.get_health_data` | `_build_cake_signal_section reads health_data['cake_signal']` | WIRED | `health_data.get("cake_signal")` at line 495; assembled from `get_health_data()` return at line 2920 |
| `wan_controller.py` | `DeferredIOWorker` | `wanctl_cake_drop_rate` in metrics_batch | WIRED | Lines 2287-2309 extend `metrics_batch` before `io_worker.enqueue_batch` |
| `wan_controller.py reload()` | `_reload_cake_signal_config` | SIGUSR1 handler chain | WIRED | Line 2797 in `reload()` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_run_cake_stats` | `_dl_cake_snapshot`, `_ul_cake_snapshot` | `adapter.dl_backend.get_queue_stats("")` (NetlinkCakeBackend) | Yes -- reads live kernel netlink stats; disabled by default via `CakeSignalConfig.enabled=False`, short-circuits on non-linux-cake | FLOWING (disabled by default, no behavior change) |
| `_build_cake_signal_section` | `cake_data["download"]` / `cake_data["upload"]` | `get_health_data()["cake_signal"]` which reads `_dl_cake_snapshot` | Yes -- `CakeSignalSnapshot` frozen dataclass from processor; returns None/omits section when disabled | FLOWING (conditional on enabled) |
| Metrics batch | `snap.drop_rate`, `.backlog_bytes`, `.peak_delay_us` | `_dl_cake_snapshot` / `_ul_cake_snapshot` | Yes -- EWMA-processed values; cold_start guard prevents writing zero-initialized data | FLOWING (gated by `metrics_enabled` + `cold_start` check) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All CAKE signal unit tests pass | `.venv/bin/pytest tests/test_cake_signal.py tests/test_health_check.py tests/test_wan_controller.py -x -q --timeout=10` | 246 passed | PASS |
| ruff clean on all modified files | `.venv/bin/ruff check src/wanctl/cake_signal.py src/wanctl/wan_controller.py src/wanctl/health_check.py` | All checks passed | PASS |
| mypy clean on cake_signal module | `.venv/bin/mypy src/wanctl/cake_signal.py` | Success: no issues found | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| CAKE-01 | 159-01 | CAKE qdisc stats read every cycle via netlink with <1ms latency per direction | SATISFIED | `_run_cake_stats()` reads `dl_backend.get_queue_stats("")` and `ul_backend.get_queue_stats("")` in run_cycle hot path; wrapped in `PerfTimer("autorate_cake_stats")`; netlink call is 0.3ms per RESEARCH doc |
| CAKE-02 | 159-01 | Drop rate computed as EWMA-smoothed drops/sec with u32-safe delta math and cold start warmup | SATISFIED | `u32_delta()` handles wrap-around + sanity guard; EWMA in `update()` with `alpha = CYCLE_INTERVAL_SECONDS / time_constant_sec`; cold start discards first delta |
| CAKE-03 | 159-01 | Per-tin stats tracked separately (Bulk distinguished from BestEffort+ drops) | SATISFIED | `active_drops = sum(deltas for i in range(1, n))` excludes index 0 (Bulk); `total_drops` includes all; `TinSnapshot` per-tin breakdown; `TestCakeSignalProcessorTinSeparation` validates |
| CAKE-04 | 159-02 | CAKE signal metrics exposed via health endpoint and stored in metrics DB | SATISFIED | `_build_cake_signal_section` in health_check.py; 4 metrics x 2 directions in `_run_logging_metrics` metrics_batch |
| CAKE-05 | 159-02 | All CAKE signal features independently toggleable via YAML config (default: disabled) | SATISFIED | `_parse_cake_signal_config()` parses 5 independent bools + time_constant; `_reload_cake_signal_config()` SIGUSR1 hot-reload; all defaults False |

### Anti-Patterns Found

No blockers or warnings found.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | - |

Notable: `_parse_cake_signal_config` returns `Any` (not `CakeSignalConfig`) to work around ruff F821 forward reference issue. This is an intentional deviation documented in 159-02-SUMMARY.md. The runtime type is always `CakeSignalConfig` and the pattern follows existing codebase conventions for lazy imports.

### Human Verification Required

None. All must-haves are verifiable programmatically. CAKE signal is disabled by default so production behavior is unchanged. No A/B testing or latency measurement is required to confirm this phase's goal (signal infrastructure only, no zone classification changes).

### Gaps Summary

No gaps. All 12 must-haves are verified against the codebase. The phase goal -- CAKE stats read, processed, and exposed every cycle with no behavior change -- is fully achieved:

- New module `cake_signal.py` (291 lines) implements EWMA signal processing with u32 safety
- `wan_controller.py` wires reading into the hot path between spike detection and congestion assessment
- `health_check.py` exposes per-tin stats conditionally when enabled
- YAML config + SIGUSR1 hot-reload provides safe rollout with all features defaulting to disabled
- 246 tests pass (45 new CAKE signal tests + 5 new health tests + 90 existing controller tests + existing suite)
- ruff and mypy clean

---

_Verified: 2026-04-09T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
