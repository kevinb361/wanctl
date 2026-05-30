# Phase 216 Exit Criteria Confirmation

**Phase:** 216 — recovery/refractory decision  
**Plan:** 216-01  
**Date:** 2026-05-29  
**Verdict:** **no-change / resolved-by-197**

This is a planning-artifact confirmation only. No control-path code, YAML config, systemd unit, script, test, RouterOS surface, or production service was edited.

## Verification Command

```text
.venv/bin/pytest -o addopts='' tests/test_phase_197_replay.py tests/test_phase213_classify.py -q
```

Result:

```text
21 passed in 1.02s
```

## EC1 / D-02 — Backlog Suppression Flag Is a Cross-WAN Merge Artifact

**Finding:** The Phase 213 `backlog_suppressed_delta=14451` refractory-semantics flag is a **cross-WAN MERGE artifact** over a cumulative lifetime counter. It carries **ZERO weight** toward the Phase 216 verdict.

Evidence and mechanism:

- `scripts/phase213-classify.py:98` starts `_all_health_rows()`, and `:106-108` loads every `health-*.ndjson` file in each test directory. That means a test window can include both `health-spectrum.ndjson` and `health-att.ndjson` rows.
- `scripts/phase213-classify.py:277-278` computes `vals = cake_dl_backlog_suppressed_count + cake_ul_backlog_suppressed_count` for each merged row, then reports `delta = max(vals) - min(vals)`.
- The counter source is not refractory entry. `src/wanctl/queue_controller.py:265` marks `DETECT-02: Suppress green_streak while backlog is high`, and `:274` increments `_backlog_suppressed_count += 1` in that GREEN-recovery suppression path.
- In `RUN-20260527T222043Z`, Spectrum's lifetime counter sits flat at `14451` while ATT's is `0`; an `att/*` window that ingests Spectrum's file computes `14451 - 0 = 14451`.
- Genuine same-WAN counter movement is small (`20`, `390`, `448`, `516`) and represents normal backlog-suppressed GREEN recovery, not refractory activity.

Conclusion: the `14451` bucket flag is explained by cross-WAN file merge plus max-min deltization over a monotonic lifetime counter. It is not a per-event refractory distress signal.

## EC2 / D-03 — Phase 197 Replay Tests Are the Semantic Proof

**Finding:** Phase 197's replay tests are the semantic proof for the shipped refractory arbitration behavior. Phase 213 is not used as this proof.

Evidence:

- Focused verification passed: `21 passed` for `tests/test_phase_197_replay.py` and `tests/test_phase213_classify.py`.
- `src/wanctl/wan_controller.py:101-102` defines the refractory-specific reason constants: `queue_during_refractory` and `rtt_fallback_during_refractory`.
- `src/wanctl/wan_controller.py:2932-2939` splits `dl_cake_for_detection` from `dl_cake_for_arbitration`, masks detection to `None` during refractory, and keeps the arbitration snapshot live.
- `tests/test_phase_197_replay.py:211` asserts queue-primary remains active through the refractory window with a valid snapshot.
- `tests/test_phase_197_replay.py:241` and `:253` assert RTT fallback only when the refractory snapshot is `None` or `cold_start`.
- `tests/test_phase_197_replay.py:274` names `TestPhase197NoCascadeOnDetection`, the RECOV-02 / Phase 160 cascade-safety guard: detection receives `cake_snapshot=None` during refractory.

Conclusion: Phase 197's shipped code and replay tests cover the refractory-active arbitration branches required by the Phase 196 closeout.

## EC3 / D-01 — Phase 213 Shows No Current Symptom, Not Validated Correctness

**Finding:** Phase 213 shows **no current symptom under the captured baseline**, but it does not validate refractory correctness.

Evidence:

- `signal-sheet.json` reports `pct_samples_refractory_active: 0.0` for every refractory-semantics evidence row, and research confirmed `arb_refractory_active=0` plus `dl_refractory_remaining=0` in every captured file.
- Every recovery-input RRUL / `tcp_12down` window is 100% GREEN; no RED or SOFT_RED recovery was observed in those windows.
- `scripts/phase213-classify.py:146-159` contains the WR-02 zero-lag conflation: `green_after` remains `None` unless a confirmed GREEN recovery is seen, then `lag = float(green_after or 0)` logs `0.0` for no recovery information.
- Therefore `time_to_green_after_red_sec=0.0` means **"no RED observed"** for this evidence set, not instant recovery. In a different window with RED and no recovery, the same code could also log `0.0`.

Conclusion: Phase 213 supports only the absence-of-current-symptom framing. It is not a basis for future tuning.

## Derived Verdict

All three exit criteria pass:

1. D-02: the `14451` backlog flag is a merge/cumulative-counter artifact and carries zero verdict weight.
2. D-03: Phase 197's replay tests are green and cover the refractory arbitration semantics.
3. D-01: Phase 213 shows no current symptom under this baseline, while never exercising a refractory window.

**Verdict:** **no-change / resolved-by-197**.

**RECOV-03 scope note:** RECOV-03 is satisfied only in the no-change sense: no recovery/refractory tuning is approved in Phase 216, so no transient-congestion measurement is needed for this closeout. This is **not** evidence for future tuning.
