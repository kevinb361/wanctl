---
phase: 158-parameter-re-validation
plan: 01
status: complete
started: 2026-04-09T15:35:00-05:00
completed: 2026-04-09T16:42:00-05:00
commits: []
deviations:
  - "hard_red=60 skipped: threshold ordering violation with warn_bloat=75 winner (75 > 60)"
  - "hard_red=60 crash-loop triggered circuit breaker; required reset-failed before continuing"
  - "Only 2 valid hard_red candidates tested (80 vs 100) instead of 3"
key-files:
  created:
    - .planning/phases/158-parameter-re-validation/158-01-SUMMARY.md
  modified: []
---

## Summary

A/B tested three DL controller parameters on the post-v1.31 linux-cake system (netlink backend, deferred I/O, CAKE rtt=25ms, 50ms cycle). 24 valid RRUL runs completed across ~70 minutes.

## Individual A/B Test Results

### step_up_mbps (10 vs 15 vs 20) — 9 runs

| Value | Run | ICMP Median | ICMP p99 | DL Sum | UL Sum |
|-------|-----|-------------|----------|--------|--------|
| 10 | 1 | 42.3ms | 85.0ms | 614.8 | 20.1 |
| 10 | 2 | 40.8ms | 72.6ms | 650.5 | 14.3 |
| 10 | 3 | 43.1ms | 81.8ms | 587.6 | 10.8 |
| **10 avg** | | **42.1ms** | **79.8ms** | **617.6** | **15.1** |
| 15 | 1 | 42.4ms | 81.3ms | 607.6 | 10.3 |
| 15 | 2 | 43.4ms | 83.0ms | 586.6 | — |
| 15 | 3 | 43.8ms | 69.1ms | 599.2 | 24.7 |
| **15 avg** | | **43.2ms** | **77.8ms** | **597.8** | **17.5** |
| 20 | 1 | 41.5ms | 66.7ms | 623.9 | 10.3 |
| 20 | 2 | 44.8ms | 75.6ms | 642.9 | 18.6 |
| 20 | 3 | 43.9ms | 99.4ms | 596.4 | 11.4 |
| **20 avg** | | **43.4ms** | **80.6ms** | **621.1** | **13.4** |

**Winner: step_up_mbps=10 (keep current)**
All three within <5% noise margin on median. step=10 has lowest median (42.1ms). step=20 produced concerning p99 outlier (99.4ms). In v1.26 step=15 won (-32% median) but with REST transport; linux-cake's 2.5x less jitter means the controller recovers fast enough at step=10.

### warn_bloat_ms (60 vs 45 vs 75) — 9 runs

| Value | Run | ICMP Median | ICMP p99 | DL Sum | UL Sum |
|-------|-----|-------------|----------|--------|--------|
| 60 | 1 | 45.1ms | 77.7ms | 589.4 | 17.1 |
| 60 | 2 | 44.4ms | 87.0ms | 599.6 | 28.4 |
| 60 | 3 | 44.8ms | 93.2ms | 584.1 | 8.2 |
| **60 avg** | | **44.8ms** | **86.0ms** | **591.0** | **17.9** |
| 45 | 1 | 44.8ms | 94.2ms | 590.5 | 14.2 |
| 45 | 2 | 43.7ms | 74.3ms | 584.0 | 14.6 |
| 45 | 3 | 44.0ms | 95.1ms | 596.4 | 8.4 |
| **45 avg** | | **44.2ms** | **87.9ms** | **590.3** | **12.4** |
| 75 | 1 | 41.2ms | 85.0ms | 654.4 | 15.4 |
| 75 | 2 | 45.1ms | 79.5ms | 587.7 | 30.0 |
| 75 | 3 | 42.5ms | 72.0ms | 584.8 | 8.1 |
| **75 avg** | | **42.9ms** | **78.8ms** | **609.0** | **17.8** |

**Winner: warn_bloat_ms=75 (CHANGED from 60)**
75 wins on both median (-4.2%) AND p99 (-8.4%). With linux-cake + CAKE rtt=25ms, the controller reacts fast enough that 60ms was triggering YELLOW transitions on normal DOCSIS jitter. 75ms lets CAKE's AQM handle jitter naturally. In v1.26 (REST, CAKE rtt=40ms), warn=45 won — the shift to 75 reflects the fundamentally faster system.

### hard_red_bloat_ms (100 vs 60 vs 80) — 6 valid runs

| Value | Run | ICMP Median | ICMP p99 | DL Sum | UL Sum | Notes |
|-------|-----|-------------|----------|--------|--------|-------|
| 100 | 1 | 43.3ms | 78.4ms | 589.7 | 15.3 | |
| 100 | 2 | 42.8ms | 80.5ms | 598.6 | 10.8 | |
| 100 | 3 | 44.4ms | 89.9ms | 603.7 | 17.2 | |
| **100 avg** | | **43.5ms** | **82.9ms** | **597.3** | **14.4** | No RED |
| 60 | — | — | — | — | — | INVALID: warn_bloat(75) > hard_red(60) |
| 80 | 1 | 43.1ms | 79.7ms | 622.2 | 31.1 | |
| 80 | 2 | 46.0ms | 83.6ms | 580.7 | 18.1 | |
| 80 | 3 | 45.7ms | 81.4ms | 582.5 | 17.7 | |
| **80 avg** | | **44.9ms** | **81.6ms** | **595.1** | **22.3** | RED fired |

**Winner: hard_red_bloat_ms=100 (keep current)**
hard_red=60 invalid (below warn_bloat=75). hard_red=80 triggered RED state (disqualifying per criteria) and regressed median (+3.2%). Only 5ms gap between warn_bloat=75 and hard_red=80 is too tight for DOCSIS jitter. hard_red=100 gives 25ms SOFT_RED buffer.

## Individual Winners Summary

| Parameter | v1.26 Value | Current | Winner | Changed? |
|-----------|-------------|---------|--------|----------|
| step_up_mbps | 15 | 10 | 10 | No |
| warn_bloat_ms | 45 | 60 | **75** | **Yes** |
| hard_red_bloat_ms | 60 | 100 | 100 | No |

## Key Observations

1. **System has fundamentally shifted since v1.26.** Linux-cake + netlink + deferred I/O + CAKE rtt=25ms means the controller is ~2.5x faster. Parameters that won with REST transport (step=15, warn=45) no longer win.
2. **warn_bloat is the only parameter that changed.** Moved from 60→75, reflecting the faster system's ability to rely on CAKE's AQM for normal jitter.
3. **hard_red=60 caused a circuit breaker trip.** The plan didn't account for warn_bloat winning at 75, making hard_red=60 invalid. Circuit breaker required manual reset-failed.
4. **Confirmation pass (Plan 02) needed for warn_bloat change.** The v1.26 confirmation pass proved interaction effects matter.

## Environment

- Transport: linux-cake (netlink qdiscs)
- CAKE rtt: 25ms
- Cycle interval: 50ms (20Hz)
- Adaptive tuning: disabled for testing
- Flent: v2.1.1 from dev machine to dallas (104.200.21.31)
- 24 valid RRUL runs completed (3 invalid from hard_red=60 crash-loop)

## Self-Check: PASSED
