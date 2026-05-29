# Phase 216 Recovery/Refractory Decision Report

## Summary

**Verdict: no-change / resolved-by-197.** Phase 216 closes the stale Phase 196 queue-primary refractory-semantics thread without a new control-path change: Phase 197's shipped split-semantics arbitration stands, its replay tests are green, and the current Phase 213 baseline shows no live symptom under the captured load. No controller source, YAML config, systemd unit, script, test, RouterOS surface, or production service was changed in Phase 216.

## Requirement Coverage

| Requirement | Coverage note | Verdict | Evidence path | Downstream impact |
|---|---|---|---|---|
| RECOV-01 | The Phase 196 thread receives a concrete decision: **no-change / resolved-by-197**. Phase 197's tests are the semantic proof; Phase 213 shows no current symptom. | Covered | `.planning/phases/216-recovery-refractory-decision/216-EXIT-CRITERIA.md`, this report, `.planning/threads/phase-196-queue-primary-refractory-semantics-investigation.md` | Thread can be marked closed; no RECOV control follow-up is seeded. |
| RECOV-02 | No code design is approved in 216. Cascade safety is preserved by construction because no control code changes; any future follow-up must keep detection masked while keeping arbitration's queue-delay scalar live. | Covered / preserved | `tests/test_phase_197_replay.py:274`, `src/wanctl/wan_controller.py:2932-2939` | Future work must preserve both halves: no cascading CAKE/backlog reductions and live arbitration scalar. |
| RECOV-03 | **GATE/WAIVER:** satisfied because no tuning/change is approved (no-change). This is explicitly **not** a completed transient-recovery measurement and **not** a basis for future tuning. | Covered only for no-change | `RUN-20260527T222043Z/signal-sheet.json`, `scripts/phase213-classify.py:146-159` | Any future `green_required`, `step_up`, backlog suppression, or refractory change needs a real production transient/refractory artifact first. |

## Per-Exit-Criterion Findings

### D-02 — `backlog_suppressed_delta=14451` Is a Tooling Artifact

The Phase 213 runner-up flag does not carry verdict weight. The mechanism is fully explained by cross-WAN file merge plus max-min deltization over a cumulative lifetime counter:

- `scripts/phase213-classify.py:98` starts `_all_health_rows()`; `:106-108` merges all `health-*.ndjson` files in a test window.
- `scripts/phase213-classify.py:277-278` builds `vals = dl + ul` and reports `delta = max(vals) - min(vals)`.
- `src/wanctl/queue_controller.py:265` labels the underlying path `DETECT-02: Suppress green_streak while backlog is high`; `:274` increments `_backlog_suppressed_count` there, not on refractory entry.
- In `RUN-20260527T222043Z`, Spectrum's cumulative counter is flat at `14451` while ATT's is `0`; an `att/*` window ingesting Spectrum rows computes `14451 - 0 = 14451`.
- Target-WAN same-file movement is small (`20` to `516`) and represents GREEN-recovery backlog suppression, not refractory activity.

**Finding:** the 14451 flag is a cross-WAN merge artifact of a lifetime counter. It has zero weight toward the refractory verdict.

### D-03 — Phase 197 Tests Are the Semantic Proof

Focused verification for the relevant semantic proof passed:

```text
.venv/bin/pytest -o addopts='' tests/test_phase_197_replay.py tests/test_phase213_classify.py -q
21 passed in 1.02s
```

Relevant shipped surfaces:

- `src/wanctl/wan_controller.py:101-102` defines `queue_during_refractory` and `rtt_fallback_during_refractory`.
- `src/wanctl/wan_controller.py:2932-2939` splits detection-side masking from arbitration-side live-snapshot routing.
- `tests/test_phase_197_replay.py:211` asserts queue-primary during refractory with a valid snapshot.
- `tests/test_phase_197_replay.py:241` and `:253` assert RTT fallback when the snapshot is invalid.
- `tests/test_phase_197_replay.py:274` (`TestPhase197NoCascadeOnDetection`) guards RECOV-02 / Phase 160 cascade safety by asserting detection receives `cake_snapshot=None` during refractory.

**Finding:** Phase 197's code and replay tests are the proof for the refractory-active arbitration semantics used to close this thread.

### D-01 — Phase 213 Shows No Current Symptom Only

The Phase 213 baseline does not exercise a refractory window:

- `RUN-20260527T222043Z/signal-sheet.json` reports `pct_samples_refractory_active=0.0` for every refractory-semantics row.
- Research verified `arb_refractory_active=0` and `dl_refractory_remaining=0` in every captured health file.
- Recovery-input windows are 100% GREEN; no RED or SOFT_RED recovery episode exists in this evidence set.
- `scripts/phase213-classify.py:146-159` contains the WR-02 zero-lag conflation: `lag = float(green_after or 0)`, so `time_to_green_after_red_sec=0.0` means "no RED observed" here and is not positive recovery evidence.

**Finding:** Phase 213 supports the absence-of-current-symptom framing only. It is not future tuning evidence.

## Verdict

**No NEW change; Phase 197's shipped change stands and is validated by its own tests.** The Phase 196 thread is closed as **no-change / resolved-by-197** because:

1. The 213 `14451` backlog flag is a cross-WAN merge/cumulative-counter artifact.
2. Phase 197's replay tests cover the refractory arbitration behavior and pass.
3. Phase 213 shows no current live symptom under its passive baseline, while never exercising the refractory path.

Honest framing: **Phase 197's tests are the semantic proof; Phase 213 shows no current symptom.** This is not a claim that the passive baseline proved refractory-active behavior end-to-end.

## Downstream Constraints / Reopen Criteria

### Primary Reopen Trigger (D-04a)

Reopen this thread, or open a successor, if a natural production artifact shows:

```text
signal_arbitration.refractory_active == true
```

(`arb_refractory_active` in the Phase 213 projection) accompanied by any of:

- `active_primary_signal == "rtt"` during queue-primary load,
- measurable recovery lag after RED/SOFT_RED, e.g. `time_to_green_after_red_sec > 0` with `recovered:true`, or
- throughput collapse during the refractory window.

### Telemetry-Independent Fallback Trigger

Even if the refractory flag is absent or renamed, reopen on recurrence of the original Phase 196 symptom signature: a valid queue-delay signal is present (`cake_av_delay_delta_us` is non-null) while `active_primary_signal == "rtt"` under queue-primary download load.

### Cascade-Safety Carry-Forward (D-05)

Any future follow-up must keep refractory free of cascading CAKE/backlog reductions while keeping a valid queue-delay scalar live for queue-primary arbitration. Concretely: detection remains masked during refractory, and arbitration keeps access to the live queue-delay scalar.

### Steering-Drift Caveat (D-06)

Do not interpret v1.39-shaped steering threshold-name fields as v1.45 semantics. This decision relies on autorate `/health` and CAKE signal evidence, not steering threshold-name comparisons.

## Classifier-Hardening Note (Tooling Only)

Two classifier observations are recorded for future tooling hygiene only:

- `analyze_refractory()` merges per-WAN health files and deltizes cumulative counters (`scripts/phase213-classify.py:98`, `:277-278`).
- `analyze_download_recovery()` conflates no-event / no-recovery with zero lag (`scripts/phase213-classify.py:146-159`).

This note is **tooling**, not a control-path change. It does not satisfy, change, or affect any RECOV control-design requirement, and it is **not** the success-criterion-4 follow-up.

## Run Metadata

| Field | Value |
|---|---|
| Evidence run | `RUN-20260527T222043Z` |
| Signal sheet JSON | `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/signal-sheet.json` |
| Signal sheet Markdown | `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/signal-sheet.md` |
| Exit criteria artifact | `.planning/phases/216-recovery-refractory-decision/216-EXIT-CRITERIA.md` |
| Focused verification | `21 passed` |

## Evidence Index

- `.planning/phases/216-recovery-refractory-decision/216-EXIT-CRITERIA.md` — detailed EC1/EC2/EC3 confirmation.
- `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/signal-sheet.json` — Phase 213 bucket rows and thresholds.
- `scripts/phase213-classify.py:98,146-159,277-278` — merge behavior, WR-02 zero-lag behavior, refractory delta calculation.
- `src/wanctl/queue_controller.py:265,274` — backlog suppression counter source.
- `src/wanctl/wan_controller.py:101-102,2932-2939` — Phase 197 arbitration constants and split detection/arbitration implementation.
- `tests/test_phase_197_replay.py:211,241,253,274` — asserting replay tests, including the cascade-safety guard.
