---
phase: 159-cake-signal-infrastructure
plan: 01
subsystem: cake-signal
tags: [cake, signal-processing, ewma, netlink, tdd]
dependency_graph:
  requires: []
  provides: [CakeSignalProcessor, CakeSignalSnapshot, TinSnapshot, CakeSignalConfig, u32_delta]
  affects: [wan_controller.py, health_endpoint]
tech_stack:
  added: []
  patterns: [frozen-dataclass-snapshot, u32-counter-wrapping, ewma-smoothing, per-tin-separation]
key_files:
  created:
    - src/wanctl/cake_signal.py
    - tests/test_cake_signal.py
  modified:
    - src/wanctl/wan_controller.py
decisions:
  - "EWMA alpha = cycle_interval / time_constant (same pattern as signal_processing.py)"
  - "Bulk tin (index 0) excluded from active drop_rate but included in total_drop_rate"
  - "Cold start discards first delta to prevent spurious spike from cumulative counters"
  - "CakeSignalConfig defaults all disabled -- safe rollout, Phase 160 enables"
metrics:
  duration: 6m
  completed: 2026-04-09
  tasks_completed: 2
  tasks_total: 2
  tests_added: 29
  files_created: 2
  files_modified: 1
---

# Phase 159 Plan 01: CAKE Signal Processor Module Summary

CakeSignalProcessor computes EWMA drop rates from raw CAKE netlink counter deltas with u32 wrapping, per-tin separation (Bulk excluded from active rate), and frozen immutable snapshots wired into WANController.run_cycle hot path.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | CakeSignalProcessor module (TDD) | 27e700b | src/wanctl/cake_signal.py, tests/test_cake_signal.py |
| 2 | Wire into WANController run_cycle | ca8f6a6 | src/wanctl/wan_controller.py |

## Implementation Details

### Task 1: CakeSignalProcessor Module (TDD)

Created `src/wanctl/cake_signal.py` (291 lines) with:

- **u32_delta()**: Handles normal forward, wrap-around at 0xFFFFFFFF, and sanity guard (>1M delta = artifact, returns 0)
- **TinSnapshot**: Frozen dataclass with per-tin stats (name, dropped_packets, drop_delta, backlog_bytes, peak_delay_us, ecn_marked_packets)
- **CakeSignalSnapshot**: Frozen dataclass with EWMA drop_rate (BestEffort+Video+Voice), total_drop_rate (all tins), backlog_bytes, peak_delay_us, tins tuple, cold_start flag
- **CakeSignalConfig**: Frozen dataclass with enabled, drop_rate_enabled, backlog_enabled, peak_delay_enabled, metrics_enabled, time_constant_sec (all disabled by default)
- **CakeSignalProcessor**: Stateful processor with EWMA smoothing, config property setter for SIGUSR1 reload, None-safe update()

TDD flow: RED (29 tests fail, module missing) -> GREEN (all 29 pass) -> verify (ruff + mypy clean).

### Task 2: WANController Wiring

Modified `src/wanctl/wan_controller.py` (+48 lines):

- **_init_cake_signal()**: Creates DL/UL CakeSignalProcessor instances, detects LinuxCakeAdapter via isinstance
- **_run_cake_stats()**: Reads get_queue_stats() from dl_backend/ul_backend, updates processors. Short-circuits if not supported
- **PerfTimer**: autorate_cake_stats added between ewma_spike and congestion_assess in run_cycle
- **_record_profiling**: cake_stats_ms parameter added to signature and timings dict
- **get_health_data()**: cake_signal section with enabled, supported, download/upload snapshots

No behavior change: CAKE signal defaults to disabled, _run_cake_stats returns immediately for non-linux-cake transports.

## Test Results

- 29 new cake_signal tests: all passing
- 90 existing wan_controller tests: all passing (no regressions)
- ruff: clean on both files
- mypy: clean on cake_signal.py

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None. All data paths are fully wired (disabled by default via CakeSignalConfig).

## Threat Mitigations Applied

- T-159-01 (Tampering/u32_delta): Sanity guard returns 0 for delta > 1,000,000
- T-159-02 (Tampering/update): None check on raw_stats, .get() for all dict access, len check on tins list

## Self-Check: PASSED

- [x] src/wanctl/cake_signal.py exists (291 lines)
- [x] tests/test_cake_signal.py exists (434 lines, >150 minimum)
- [x] src/wanctl/wan_controller.py modified with all 5 changes
- [x] Commit 27e700b verified
- [x] Commit ca8f6a6 verified
- [x] 119 tests pass (29 + 90)
- [x] ruff clean
- [x] mypy clean
