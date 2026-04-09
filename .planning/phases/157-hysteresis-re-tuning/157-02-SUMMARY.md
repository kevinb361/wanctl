---
phase: 157-hysteresis-re-tuning
plan: 02
subsystem: tuning
tags: [hysteresis, dwell, deadband, a-b-test, docsis, suppression]

# Dependency graph
requires: [157-01]
provides:
  - "Validated hysteresis parameters for post-v1.31 DOCSIS jitter profile"
  - "Raised suppression_alert_threshold from 20 to 60 (DOCSIS-appropriate)"
affects: []

# Tech tracking
tech-stack:
  added: []
  removed: []

key-files:
  created: []
  modified:
    - configs/spectrum.yaml

self-check:
  tests-pass: true
  verification: manual
  notes: "6 RRUL runs (3 baseline + 3 A/B), production measurement via health endpoint + journal logs"
---

# Summary: Phase 157 Plan 02 — Baseline Measurement & A/B Testing

## What Was Done

Deployed v1.31 to cake-shaper, measured post-v1.31 hysteresis suppression rate under RRUL load, A/B tested dwell_cycles 5 vs 7, and validated final parameter values.

## Baseline Measurement (dwell_cycles=5)

| Run | DL Suppressions | UL Suppressions | Total | ICMP Median | ICMP p99 | DL Sum | UL Sum |
|-----|-----------------|-----------------|-------|-------------|----------|--------|--------|
| 1 | 27 | 27 | 54 | 39.80ms | 92.73ms | 318 Mbps | 6.48 Mbps |
| 2 | 8 | 8 | 16 | 41.00ms | 68.87ms | 297 Mbps | 5.65 Mbps |
| 3 | 17 | 17 | 34 | 41.90ms | 76.93ms | 291 Mbps | 5.06 Mbps |
| **Average** | **17.3** | **17.3** | **34.7** | **40.9ms** | **79.5ms** | **302 Mbps** | **5.73 Mbps** |

Average 34.7/min exceeds 20/min threshold. Decision gate: > 30/min → A/B test dwell_cycles.

## A/B Test: dwell_cycles=7

| Run | DL Suppressions | UL Suppressions | Total | ICMP Median | ICMP p99 | DL Sum | UL Sum |
|-----|-----------------|-----------------|-------|-------------|----------|--------|--------|
| 1 | 42 | 42 | 84 | 39.20ms | 82.95ms | 330 Mbps | 7.42 Mbps |
| 2 | 26 | 26 | 52 | 38.90ms | 77.31ms | 323 Mbps | 6.83 Mbps |
| 3 | 31 | 31 | 62 | 40.55ms | 100.64ms | 312 Mbps | 6.36 Mbps |
| **Average** | **33.0** | **33.0** | **66.0** | **39.55ms** | **86.97ms** | **322 Mbps** | **6.87 Mbps** |

### Result: dwell_cycles=7 REJECTED

- Suppressions INCREASED from 34.7 to 66.0/min (+90%) — expected: longer dwell absorbs more transients, counting more suppressions
- ICMP p99 WORSENED from 79.5 to 87.0ms (+9.4%) — violates CRITICAL constraint
- ICMP median slightly better (40.9 → 39.6ms, -3.3%)
- Throughput slightly better (DL +6.6%, UL +19.9%)
- Per plan criteria: reject if p99 worsens → **REJECTED**

## Key Finding

The suppression rate is inherent DOCSIS cable jitter (bimodal MAP scheduling ~8ms intervals), NOT controller I/O overhead. Evidence:

1. Phases 154-156 removed ~5ms of controller jitter (netlink, deferred I/O) but suppressions INCREASED slightly (31 pre-v1.31 → 35 post-v1.31)
2. DL and UL suppressions are always exactly equal — same RTT measurement drives both
3. Increasing dwell_cycles INCREASES the suppression count (more events caught by longer window)
4. High run-to-run variance (16-84) is characteristic of DOCSIS MAP scheduling

## Decision: Raise Alert Threshold

Since the suppression rate is DOCSIS-inherent and not actionable:
- **dwell_cycles: 5** — confirmed (dwell=7 rejected due to p99 regression)
- **deadband_ms: 3.0** — confirmed (5.0 already rejected in v1.26 — traps in YELLOW)
- **suppression_alert_threshold: 20 → 60** — raised to accommodate DOCSIS jitter profile

The threshold of 60 provides headroom above the peak observed rate (54/min) while still alerting on genuinely abnormal suppression rates that would indicate a system problem.

## Commits

- configs/spectrum.yaml: suppression_alert_threshold raised from 20 to 60

## Deviations

- deadband_ms A/B test skipped: dwell_cycles=7 was rejected (p99 worse), and deadband_ms=5.0 was already rejected in v1.26. No further parameters to test.
- The suppression rate being DOCSIS-inherent was not predicted by the research (which assumed Phases 154-156 would reduce it). The correct fix is adjusting the alert threshold, not the hysteresis parameters.
