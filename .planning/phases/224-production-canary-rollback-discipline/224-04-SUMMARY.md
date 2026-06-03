---
phase: 224-production-canary-rollback-discipline
plan: 04
type: execute
status: complete
completed: 2026-06-03
requirements:
  - CANARY-02
  - CANARY-03
outcome: kept_aligned
observation_window_start: "2026-06-03T17:24:32Z"
observation_window_end: "2026-06-03T17:39:34Z"
observation_samples: 16
restart_reference_ts: "2026-06-03T12:35:38Z"
rollback_fired: false
---

# 224-04 Summary — Canary Observation + Verdict

## Outcome: KEPT_ALIGNED

Gate evaluator returned `kept_aligned` over a 16-sample, ~902-second observation window
(≥900s / ≥15 samples requirement met). All six gates pass; `rollback_trigger: None`;
`window_end_reached: true`. No rollback executed; `evidence/rollback/` is empty.

## Observation Window

- Window: `2026-06-03T17:24:32Z → 17:39:34Z` (16 samples @ 60s cadence).
- Every sample: `status=healthy`, `version=1.47.0`, steering `enabled=false` (SPECTRUM_GOOD).
- Spectrum code-fingerprint `(match=true, deployed==baseline)` on all 16 spine samples.
- Final sample: `rtt_source.last_measurement_age_sec=0.314` (≤5s), `decision.time_in_state_seconds` present.
- Samples: `evidence/observation/sample-01..16.{health,spine}.json`; bounds in `window-bounds.txt`.

## Gate Verdicts (`evidence/verdict.json`)

| Gate | Verdict | Basis |
|------|---------|-------|
| gate_version_alignment | pass | 1.47.0 + healthy |
| gate_rtt_source_fresh | pass | rtt age 0.314s ≤ 5s |
| gate_daemon_not_degraded | pass | healthy + time_in_state present |
| gate_spectrum_state_not_written_by_daemon | pass | code-fingerprint, deployed_sha256==baseline |
| gate_binary_on_off | pass | router rule-read (rule *313, disabled flag toggle) |
| gate_only_new_connections | pass | router rule-read (connection-state=new) |

## Spine Composition (auditable, not synthesized)

gate-eval treats a `null` spine match as `fail` (`_bool_gate(None)=="fail"`), which past the
restart window would falsely trigger rollback. The credentialless spine probe returns `null` for
`binary_on_off` / `only_new_connections` (no router creds in probe env). The verdict spine input
(`observation/sample-16.spine.composed.json`) therefore combines:
- `spectrum_state_not_written_by_daemon` — per-sample probe code-fingerprint (real, all 16 True).
- `binary_on_off` / `only_new_connections` — authoritative operator-authorized router rule-read
  (`leg-b-postalignment/spine-rule-proof.json`, rule `*313`), constant over the window because rule
  shape does not change absent a redeploy/reconfig (none occurred during observation).

Each injected field carries a `provenance` note; `composition_note` records the method. This is a
real-measurement composition, not a fabricated pass. Supporting continuity: the 4h soak
(`leg-b-postalignment/soak/`) ran 48 clean cycles including one live SPECTRUM_DEGRADED
activate→recover (cycle 17), exercising the on/off toggle under real congestion.

## Restart-Window Filtering (D-11/D-12)

`observation-start-ts` = restart_completed_ts `12:35:38Z`; final sample ~5h later, far outside the
15-cycle restart window. No restart-window symptom present; verdict reflects steady-state.

## Next

Plan 05 — SAFE-12 phase-boundary check (controller-path zero-diff vs v1.47) + `224-REPORT.md`
canary report citing snapshot anchor, gate verdicts, and the kept-aligned outcome.
