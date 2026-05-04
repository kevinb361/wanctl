# Phase 201 Plan 01 Corpus Audit

## Summary

Phase 200 Attempt 3 capture exists at `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/loaded_capture.ndjson` with 885 non-empty NDJSON lines sampled at 1 Hz, and `verdict.json` reports `ul_floor_hits_during_load: 4`. This closes Open Question 1 by confirming which replay-critical fields are present and which are absent in the corpus shape.

## Field Presence Audit (Attempt 3 — 20260504T133207Z)

| Field needed for Phase 201 replay | Path in NDJSON | Present? |
|---|---|---|
| `load_rtt_ms` | `wans[0].load_rtt_ms` | YES |
| `baseline_rtt_ms` | `wans[0].baseline_rtt_ms` | YES |
| `upload.current_rate_mbps` | `wans[0].upload.current_rate_mbps` | YES |
| `upload.state` (zone label) | `wans[0].upload.state` | YES |
| `cake_signal.upload.backlog_bytes` | `wans[0].cake_signal.upload.backlog_bytes` | YES |
| `cake_signal.upload.cold_start` | `wans[0].cake_signal.upload.cold_start` | YES |
| `cake_signal.upload.max_delay_delta_us` | `wans[0].cake_signal.upload.max_delay_delta_us` | NO (CRITICAL GAP) |
| `cake_signal.upload.tins[].max_delay_delta_us` | per-tin | NO (only `peak_delay_us` and `backlog_bytes` per tin) |

## Replay Implications

- RTT-integral state-machine behavior is fully testable from Attempt 3 because `baseline_rtt_ms`, `load_rtt_ms`, upload state, and upload rate are present for the loaded window.
- The CAKE backlog arm of `_is_cake_aligned_for_pushup` is testable because `cake_signal.upload.backlog_bytes` and `cake_signal.upload.cold_start` are present.
- The `max_delay_delta_us` arm CANNOT be validated from Attempt 3 capture — replay tests for that arm MUST use synthetic traces. Plan 201-08 canary extension MUST add `max_delay_delta_us` to the capture shape.

## Spectrum Provisioned Upstream Rate (Open Question 2)

Estimated provisioned upstream rate is ~20 Mbit per Phase 200 RETRO and CONTEXT D-09. This audit does NOT independently verify against ISP-side billing data; the value is treated as `[ASSUMED A4]`. If operator confirms a materially different value (>10% delta), the canary preflight in Plan 201-08 MUST be re-run with adjusted `PHASE201_SETPOINT_MBPS`. Setpoint default 12 Mbit is 60% of 20; if actual is 22, defensible setpoint shifts to 13; if actual is 18, defensible setpoint shifts to 11.

## Sampling Rate Note

- Capture is 1 Hz; integral runs at 20 Hz (50ms cycle). Replay tests can validate integral state-machine logic but not 50ms timing fidelity. Acceptable per RESEARCH Assumption A10. Canary itself is the 20 Hz validator; soak is the 24h watchdog.

## Recommended canary extension for v1.42 corpus

- `scripts/phase200-saturation-canary.sh` `capture_health_ndjson` should be extended (Plan 201-08) to record `wans[].cake_signal.upload.max_delay_delta_us` at 1 Hz.
