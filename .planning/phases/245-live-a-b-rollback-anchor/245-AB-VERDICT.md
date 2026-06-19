# Phase 245 A/B Verdict

## Outcome

- outcome: `rollback_trigger`
- recommendation: `keep-icmplib`
- interpretation: keep Spectrum on `icmplib`; do not promote `fping` as the production default in Phase 245.
- production default flip remains deferred to Phase 246 (FLIP-01).
- final steering state: Snapshot-A config state (`measurement.backend: icmplib`) with Phase-245 code deployed; this is a config-only revert, NOT a code rollback to `ffaa8a0e`.

## Run Evidence

- run summary: `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-summary.json`
- raw JSONL: `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z.jsonl`
- verdict JSON: `.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.json`
- rollback proof: `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-rollback-proof.json`
- preflight flat-file anchor proof: `.planning/phases/245-live-a-b-rollback-anchor/evidence/preflight-anchor-file-compare-20260619T001252Z.json`

## Provenance

- thresholds path: `scripts/phase245-thresholds.json`
- thresholds blob SHA: `fa3e95c6b080ed772281a62c63ac7ec05897d4f5`
- prereg commit SHA: `67faf6d56081443376a3c39712452957f780d2ac`
- evaluated at: `2026-06-19T00:33:51.040150Z`

## Six AB-03 Gate Results

### rtt_agreement: `pass`

- delta_ms: `0.35999999999999943`
- median_fping_ms: `33.22`
- median_icmplib_ms: `33.58`
- threshold_ms: `3.0`

### cycle_budget_nonregression: `fail`

- avg_delta_pct: `-2.028397565922921`
- avg_threshold_pct: `20.0`
- fping_p99_ms: `112.4`
- p99_ceiling_ms: `10.0`
- p99_delta_pct: `-6.876553438276717`
- p99_threshold_pct: `20.0`

### loss_detection_nonregression: `pass`

- delta_pct: `0.0`
- fping_loss_rate_pct: `0.0`
- icmplib_loss_rate_pct: `0.0`
- threshold_pct: `1.0`

### min_backend_cycle_fraction: `pass`

- fping_fraction: `1.0`
- icmplib_fraction: `1.0`
- min_fraction: `1.0`
- threshold: `0.95`

### unexpected_restarts: `pass`

- baseline_nrestarts: `0`
- max_planned_restarts: `None`
- max_unexpected_restarts: `0`
- planned_restarts: `2`
- total_nrestarts: `2`
- unexpected_restarts: `0`

### steering_decision_stability: `pass`

- delta_pct: `0.0`
- fping_enable_pct: `0.0`
- icmplib_enable_pct: `0.0`
- threshold_pct: `5.0`

## Backend Samples

### fping

- cycle_avg_ms: `48.3`
- cycle_p99_ms: `112.4`
- loss_rate_pct: `0.0`
- median_rtt_ms: `33.22`
- steering_decisions: `{'disable': 1, 'enable': 0}`
- total_accepted_cycles: `479`
- wanctl_backend_cycles: `479`

### icmplib

- cycle_avg_ms: `49.3`
- cycle_p99_ms: `120.7`
- loss_rate_pct: `0.0`
- median_rtt_ms: `33.58`
- steering_decisions: `{'disable': 1, 'enable': 0}`
- total_accepted_cycles: `479`
- wanctl_backend_cycles: `479`

## Restart Accounting

- baseline_nrestarts: `0`
- planned_restarts: `2`
- total_nrestarts: `2`
- unexpected_restarts: `0`
- max_unexpected_restarts: `0`
- max_planned_restarts: `None`

## Rollback / Final State

- rollback type: `config-only icmplib revert under Phase-245 code`
- ATT control touched: `False`
- final health backend: `icmplib`
- final health producer: `wanctl-backend`
- final health source_ip: `10.10.110.223`

## Notes

- The live run used the corrected flat-rsync production layout proof because `cake-shaper:/opt/wanctl` is intentionally not a git checkout.
- The A/B was bounded to two 240-second windows to fit the operator execution window; it still produced intended-backend samples for both arms and kept ATT as control.
- The failing gate is the pre-registered absolute cycle p99 ceiling; RTT agreement, loss, backend-cycle fraction, unexpected restarts, and steering-decision stability all passed.
