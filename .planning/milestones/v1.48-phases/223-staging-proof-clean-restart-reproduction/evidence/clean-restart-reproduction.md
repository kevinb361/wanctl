# PROOF-02 Clean-Restart Reproduction

## Pre-State Seed

### steering_pre_state

| field | value |
|---|---|
| current_state | `"SPECTRUM_DEGRADED"` |
| good_count | `0` |
| baseline_rtt | `25.0` |
| history_rtt | `[25, 25, 25, 25, 25]` |
| history_delta | `[0.5, 0.5, 0.5, 0.5, 0.5]` |
| rtt_delta_ewma | `0.5` |
| queue_ewma | `0.0` |
| congestion_state | `"GREEN"` |
| cake_read_failures | `0` |

### autorate_state_by_cycle

```json
{
  "default": {
    "ewma": {
      "baseline_rtt": 25.0
    },
    "congestion": {
      "dl_state": "GREEN",
      "ul_state": "GREEN"
    }
  }
}
```

## Initial Rule State

- `pre_steering_rule_state`: `True`
- `cycle_1_effective_steering_state`: `True`

## Per-Cycle Observations

| cycle | current_state | effective_steering_state | enable_steering_called | disable_steering_called | baseline_rtt | RTT delta |
|---:|---|---|---|---|---:|---:|
| 0 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 1 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 2 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 3 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 4 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 5 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 6 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 7 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 8 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 9 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 10 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 11 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 12 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 13 | SPECTRUM_DEGRADED | True | False | False | 25.0 | 0.5 |
| 14 | SPECTRUM_GOOD | False | False | True | 25.0 | 0.5 |
| 15 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 16 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 17 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 18 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 19 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 20 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 21 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 22 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 23 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 24 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 25 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 26 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 27 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 28 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 29 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 30 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 31 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 32 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 33 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |
| 34 | SPECTRUM_GOOD | False | False | False | 25.0 | 0.5 |

## Outcome Verdict

- **§5 outcome:** `reproduced-bug`
- **Rationale:** effective_steering remained true during recovery-window cycles [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13] from pre-enabled boot rule; this violates the binary-on/off + autorate-baseline-authoritative spine contract because persisted DEGRADED kept traffic effectively steered before fresh GOOD-consistent measurements recovered the daemon at cycle 14.
- **Proposed fix scope:** `src/wanctl/steering/daemon.py` startup/state-load path; revalidate persisted DEGRADED against fresh measurement before leaving RouterOS steering effectively enabled, while preserving autorate baseline authority.
- **Fix status:** fix DID NOT land in this plan and is held against Phase 224 pre-canary or a follow-up phase.
- **Phase 224 Block Recommendation:** Phase 224 BLOCKED on this outcome unless fix lands or operator accepts the risk.

## Folded-Todo Closure

Closure note for `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md`: PROOF-02 recorded the clean-restart outcome above, with structured JSON evidence and this report. The todo is resolved by Phase 223 annotation, not deletion.
