# Phase 247: AB-03 Methodology Review

Phase 245 rollback_trigger root-cause analysis

Date: 2026-06-18

## Source Evidence

- Phase 245 AB verdict: git commit `7e6844a2`, path `.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.json`.
- Phase 245 AB run summary: git commit `7e6844a2`, path `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-summary.json`.
- Pre-committed thresholds: `scripts/phase245-thresholds.json` from commit `67faf6d5`, blob sha `fa3e95c6`.
- icmplib p99 source: `247-RESEARCH.md` "Critical Discovery" section and the Phase 245 run summary JSON, both describing the `autorate_cycle_total` window.
- Run duration: 479 cycles, approximately 24 minutes; this was shorter than `MIN_MINUTES=30` and far below `MIN_CYCLES=10000`.

Relevant threshold literals from `scripts/phase245-thresholds.json`:

- `CYCLE_P99_ABS_CEILING_MS=10.0`
- `ICMPLIB_REPRESENTATIVE_P99_MS=6.9`
- `ICMPLIB_REPRESENTATIVE_P99_TOL_MS=3.5`
- `ICMPLIB_REPRESENTATIVE_AVG_MS=2.85`
- `ICMPLIB_REPRESENTATIVE_AVG_TOL_MS=1.5`
- `CYCLE_AVG_REGRESSION_PCT=20.0`
- `CYCLE_P99_REGRESSION_PCT=20.0`
- `RTT_AGREEMENT_TOL_MS=3.0`
- `LOSS_DETECTION_MAX_DELTA_PCT=1.0`
- `MIN_WANCTL_BACKEND_CYCLE_FRACTION=0.95`
- `MAX_UNEXPECTED_RESTARTS=0`
- `STEERING_DECISION_STABILITY_MAX_DELTA_PCT=5.0`

## What cycle_p99_ms Measures

Phase 245 `cycle_p99_ms` was the daemon-level `autorate_cycle_total` timing exported through the health endpoint's `cycle_budget.cycle_time_ms.p99` field. It measured the total wanctl control-loop cycle time during the A/B windows: RTT polling, state handling, metrics, any RouterOS interaction, and other daemon work. It did not measure the fping burst subprocess runtime directly.

Phase 247's shadow capture will measure a separate quantity: `fping_background_cycle` through `FpingThread.get_profile_stats()`, plus per-burst `probe_cycle.elapsed_ms` records. Those records represent the fork+exec+parse time of fping probe bursts, with `count=5` and `period_ms=200`, normally on a 10s background cadence. The background fping burst does not run inside the 50ms autorate daemon loop.

This distinction is critical. The Phase 245 value `fping_p99_ms=112.4` is not the fping probe execution time. It is the daemon `autorate_cycle_total` p99 during the fping-backend window under production load. Phase 247's `probe_elapsed_p99_ms_full_window` will answer a different question: how long the fping background probe bursts themselves take across the shadow soak.

## AB-03 Gate-by-Gate Analysis

| Gate | Threshold | Phase 245 fping | Phase 245 icmplib | Verdict | Diagnosis |
|------|-----------|-----------------|-------------------|---------|-----------|
| `rtt_agreement` | Δ < `RTT_AGREEMENT_TOL_MS=3.0ms` | median=33.22ms | median=33.58ms, Δ=0.36ms | PASS | Median RTT agreement was excellent; fping and icmplib saw the same network latency. |
| `cycle_budget_nonregression` (avg) | fping avg ≤ icmplib avg × 1.20 (`CYCLE_AVG_REGRESSION_PCT=20.0`) | 48.3ms | 49.3ms, delta=-2.03% | PASS | fping average daemon cycle timing was marginally better than icmplib. |
| `cycle_budget_nonregression` (p99 relative) | fping p99 ≤ icmplib p99 × 1.20 (`CYCLE_P99_REGRESSION_PCT=20.0`) | 112.4ms | 120.7ms, delta=-6.88% | PASS | fping p99 was 6.88% BETTER than icmplib; the relative regression gate clearly passed. |
| `cycle_budget_nonregression` (p99 absolute) | fping p99 < `CYCLE_P99_ABS_CEILING_MS=10.0ms` | 112.4ms | 120.7ms | **FAIL — SOLE FAILING GATE** | The 10.0ms ceiling was derived from idle/low-load `ICMPLIB_REPRESENTATIVE_P99_MS=6.9ms` plus `ICMPLIB_REPRESENTATIVE_P99_TOL_MS=3.5ms` (10.4ms, gate rounded to 10.0ms). The absolute ceiling did not represent loaded AB-03 daemon-cycle timing. Both backends exceeded it under production load. |
| `loss_detection_nonregression` | delta < `LOSS_DETECTION_MAX_DELTA_PCT=1.0%` | 0.0% loss | 0.0% loss | PASS | Both backends reported zero loss. |
| `min_backend_cycle_fraction` | ≥ `MIN_WANCTL_BACKEND_CYCLE_FRACTION=0.95` | 1.0 | 1.0 | PASS | Both backends ran 100% of accepted cycles. |
| `unexpected_restarts` | `MAX_UNEXPECTED_RESTARTS=0` | 0 unexpected restarts | 0 unexpected restarts | PASS | Planned restarts were excluded; no unexpected restarts occurred. |
| `steering_decision_stability` | delta < `STEERING_DECISION_STABILITY_MAX_DELTA_PCT=5.0%` | 0.0% enable pct | 0.0% enable pct | PASS | No steering enables occurred in either window. |

## Finding

**Root cause:** calibration mismatch — not fping inferiority. The Phase 245 `rollback_trigger` was caused by the absolute cycle p99 methodology/threshold, not by fping being slower than icmplib in the observed run.

The sole failing gate was `cycle_budget_nonregression`'s absolute p99 ceiling: `CYCLE_P99_ABS_CEILING_MS=10.0ms`. That ceiling came from an idle/low-load representative icmplib p99 (`ICMPLIB_REPRESENTATIVE_P99_MS=6.9ms`) plus tolerance (`ICMPLIB_REPRESENTATIVE_P99_TOL_MS=3.5ms`), yielding 10.4ms and rounded in the gate to 10.0ms. That calibration source did not represent the loaded AB-03 window.

Under the Phase 245 production-load window, both backend windows showed `autorate_cycle_total` p99 above 100ms. fping p99 was 112.4ms, while icmplib p99 was 120.7ms. If the same absolute ceiling had been evaluated on the icmplib window alone, icmplib would also have failed it. The comparative p99 regression test passed because `fping_p99 / icmplib_p99 - 1 = -6.88%`; fping was not the disqualifying factor.

The observed evidence shows the absolute p99 gate was miscalibrated for that production-load window. This document does not claim a universal "would fail at any run length" conclusion. It claims only what the evidence supports: for the observed production-load window, the idle-derived absolute ceiling did not match the loaded daemon-cycle timing distribution.

## Run Duration Note

Phase 245 ran for 479 cycles, approximately 24 minutes, versus the pre-registered `MIN_MINUTES=30` and `MIN_CYCLES=10000` targets. The min backend cycle fraction gate passed for the executed windows because both backends had 100% backend-cycle coverage for those accepted cycles.

The shorter-than-planned run should be recorded as a methodology limitation, but it does not change the calibration mismatch finding. The observed production-load window already showed both fping and icmplib exceeding the idle-derived absolute p99 ceiling by an order of magnitude, while the relative fping-vs-icmplib p99 comparison passed.

## Implication for Phase 248

Phase 248 should design AB-03 calibration around load-representative daemon timing, not an idle-only snapshot. Phase 247 shadow data will provide raw fping RTT and probe-cycle timing distributions, but it does not by itself prove a production default flip. It is evidence for the next methodology step: separating network RTT distribution, fping probe-cycle timing, and daemon `autorate_cycle_total` timing so each threshold uses the correct distribution.
