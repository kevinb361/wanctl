# Phase 248: fping p99 Distribution Analysis + Profiling Verdict

Date: 2026-06-19

Requirements: PROF-03, PROF-04

## Verdict

**Decision: fping is switch-eligible for an operator-gated controlled canary.**

This is not a blind production default flip. It is a clearance decision: the Phase 245 rollback should no longer block a carefully scoped fping canary because the rollback was caused by an invalid absolute cycle-p99 gate, not by demonstrated fping inferiority.

## Evidence sources

- Phase 245 A/B summary values preserved in `.planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-shadow-summary.json`.
- Phase 247 methodology review: `.planning/phases/247-fping-shadow-capture-phase-245-evidence-review/247-METHODOLOGY-REVIEW.md`.
- Phase 247 shadow soak summary: `.planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-shadow-summary.json`.
- Threshold file: `scripts/phase245-thresholds.json`.

## Phase 245 A/B comparison

Phase 245 produced the only same-window fping-vs-icmplib comparison in the current evidence set.

| Metric | fping | icmplib | Interpretation |
|---|---:|---:|---|
| Median RTT | 33.22 ms | 33.58 ms | fping was 0.36 ms lower; both were within the 3.0 ms RTT agreement tolerance. |
| Loss rate | 0.0% | 0.0% | No loss regression. |
| Backend cycle fraction | 1.0 | 1.0 | Both backends covered all accepted cycles. |
| Steering enable pct | 0.0% | 0.0% | No steering-decision instability. |
| Daemon cycle avg | 48.3 ms | 49.3 ms | fping was slightly lower. |
| Daemon cycle p99 | 112.4 ms | 120.7 ms | fping was 6.88% better by the relative p99 comparison. |

The Phase 245 `rollback_trigger` came from the old absolute ceiling:

- `CYCLE_P99_ABS_CEILING_MS = 10.0`
- fping daemon cycle p99 = 112.4 ms
- icmplib daemon cycle p99 = 120.7 ms

That ceiling was derived from idle/low-load representative icmplib timing and did not represent the loaded A/B window. Both backends exceeded it by an order of magnitude. Therefore, the old 10ms absolute p99 gate is not valid evidence that fping is worse than icmplib.

## Phase 247 fping shadow distribution

Phase 247 captured fping in read-only shadow mode on cake-shaper using the active external cake-autorate Spectrum reflector set.

| Metric | Value |
|---|---:|
| Duration | 6.964 h |
| Probe cycles | 2299 |
| Successful cycles | 2299 |
| Success rate | 100.0% |
| All-loss cycles | 0 |
| Inferred/drop cycles | 0 |
| Final stats records | 1 |

Full-window RTT distribution, computed from `probe_cycle.rtt_ms` records:

| RTT metric | Value |
|---|---:|
| min | 18.05 ms |
| median | 21.8 ms |
| avg | 22.91 ms |
| p95 | 29.55 ms |
| p99 | 38.15 ms |
| max | 101.75 ms |

Full-window fping probe elapsed distribution, computed from `probe_cycle.elapsed_ms` records, not rolling `probe_stats.p99_ms`:

| Probe elapsed metric | Value |
|---|---:|
| min | 884.95 ms |
| median | 893.49 ms |
| avg | 897.04 ms |
| p95 | 913.97 ms |
| p99 | 946.65 ms |
| max | 1074.00 ms |

The probe elapsed distribution is expected to be near 900 ms because the shadow script uses `count=5` and `period_ms=200` across the reflector set. It runs on a 10s background cadence and must not be treated as inline 50ms control-loop time.

## PROF-03 finding

PROF-03 asks for a comparable p99 RTT distribution for fping vs icmplib over a representative Spectrum production window.

The available evidence has two parts:

1. Phase 245 same-window fping-vs-icmplib median RTT comparison showed excellent agreement: 33.22 ms vs 33.58 ms.
2. Phase 247 fping full-window shadow distribution showed stable fping behavior over 6.964h: median 21.8 ms, p99 38.15 ms, no all-loss cycles, and no inferred drops.

There is no current same-window live icmplib stream on cake-shaper because Spectrum is running external cake-autorate with a state bridge, while native `wanctl@spectrum.service` is inactive. The Phase 248 decision therefore uses Phase 245 as the same-window comparator and Phase 247 as the cleaner fping stability distribution. This is sufficient for canary eligibility, not for a blind default flip.

## PROF-04 decision

fping is ready for a future default-flip attempt only through an operator-gated controlled canary.

Required canary properties:

1. Config-only canary unless a separate approved plan says otherwise.
2. No controller-path code changes; SAFE-18 must remain zero-diff for protected files.
3. No RouterOS/MikroTik mutations as part of the backend canary.
4. Do not reuse `CYCLE_P99_ABS_CEILING_MS=10.0` as a hard rollback gate.
5. Use relative/nonregression daemon-cycle checks when a valid same-window comparator exists.
6. Track median/p95/p99 RTT, loss/all-loss, inferred drops, unexpected restarts, backend-cycle coverage, and steering-decision stability.
7. Define an explicit rollback path back to icmplib before starting.
8. Require operator approval immediately before any production default change.

## Final decision statement

The old Phase 245 rollback should be considered a methodology failure of the absolute p99 ceiling, not a fping quality failure. Phase 247 shadow data is clean enough to proceed. The next fping action should be a controlled canary/default-flip attempt with updated gates, not more passive shadow soaking.

**Verdict: switch-eligible for controlled canary; not yet flipped by this phase.**
