---
phase: 192
type: operator-waiver
created_at: 2026-04-24T13:30:00Z
applies_to:
  - 192-03 Task 3 phase-191-closure precondition
source_artifacts:
  - .planning/phases/191.1-att-config-drift-resolution-and-phase-191-closure/191.1-rerun-results.json
  - /home/kevin/flent-results/phase191.1/p191_1_rerun_20260424/att/20260424-082025/manifest.txt
  - /home/kevin/flent-results/phase191.1/p191_1_rerun_20260424/spectrum/20260424-082356/manifest.txt
verdict: proceed-with-guardrails
---

# Phase 192 Precondition Waiver

Phase 191 remains open. This waiver does not mark Phase 191 or Phase 191.1
closed, and it does not rewrite `VALN-02 verdict: FAIL`.

The operator authorizes Phase 192 to proceed despite the Phase 191 closure
precondition because repeated restored-config reruns now point to live-path
variance around the old ATT RRUL throughput comparator rather than a clear
Phase 192 safety blocker.

## Current Evidence

Latest rerun: `2026-04-24`, label `p191_1_rerun_20260424`.

| Check | Current | Baseline | Read |
| --- | ---: | ---: | --- |
| ATT RRUL down | `70.95 Mbps` | `78.29 Mbps` | Fails old `>=74.38 Mbps` lower bound |
| ATT RRUL up | `14.40 Mbps` | `10.80 Mbps` | Healthy |
| ATT RRUL ping p99 | `48.62 ms` | `74.42 ms` | Improved |
| ATT tcp_12down down | `72.95 Mbps` | `74.00 Mbps` | Within 5% |
| ATT VoIP one-way p99 | `28.02 ms` | `29.79 ms` | Improved |
| Spectrum RRUL down | `343.83 Mbps` | `288.41 Mbps` | Healthy throughput |
| Spectrum RRUL ping p99 | `653.68 ms` | `75.11 ms` | Confounded latency |

Interpretation: the restored ATT config no longer shows a broad regression
across tcp_12down or VoIP, but the old RRUL download comparator still fails.
The matching Spectrum discriminator has strong throughput and poor latency,
so the run is not a clean Phase 191 closure sample.

## Guardrails

- Phase 192 may proceed only for its additive observability/log hygiene work:
  `download.hysteresis.dwell_bypassed_count`, blackout-aware scorer behavior
  already planned in Phase 192, and the portable soak capture tool.
- No Phase 191 closure status changes are implied.
- No control thresholds, timing constants, state machines, or shaping logic are
  waived by this document.
- Phase 192 deployment must run canary checks before any soak clock starts.
- Phase 192 version closeout remains gated on explicit post-deploy observation
  and 24-hour soak evidence.
- If canary or soak shows service instability, stop Phase 192 closeout and
  return to the Phase 191/191.1 blocker.
