---
phase: 195-rtt-confidence-demotion-and-fusion-healer-containment
verified: 2026-04-24T17:36:35Z
status: human_needed
score: 10/13 must-haves verified
overrides_applied: 0
human_verification:
  - test: "SC-1 production rtt_confidence observation"
    expected: "On a cake_signal-supported WAN, /health signal_arbitration.rtt_confidence and SQLite wanctl_rtt_confidence show non-null floats in [0.0, 1.0] across a 1-hour production window and track ICMP/UDP plus queue-direction agreement."
    why_human: "The repository verifies renderer and metric wiring, but no 1-hour production health/SQLite capture is present in this phase artifact."
  - test: "SC-2 production low-confidence RTT spike trace"
    expected: "During a queue-GREEN RTT spike with rtt_confidence < 0.6, control_decision_reason is not rtt_veto and DL zone transitions do not escalate from the RTT path."
    why_human: "Automated unit and replay coverage prove the branch behavior, but no operator production trace for this scenario is present."
  - test: "SC-3 production single-path flip trace"
    expected: "During a single-path ICMP/IRTT flip with queue GREEN for at least 6 cycles, control_decision_reason never shows healer_bypass and fusion bypass remains inactive."
    why_human: "Automated replay coverage proves the branch behavior, but no production trace for this scenario is present."
---

# Phase 195: RTT Confidence Demotion and Fusion-Healer Containment Verification Report

**Phase Goal:** Introduce `rtt_confidence`, gate DL RTT override behind confidence plus direction agreement, contain fusion-healer bypass behind 6 aligned distress cycles, prevent single-path bypasses, and avoid magnitude-ratio/state-machine/timing/threshold/rate-compute changes.
**Verified:** 2026-04-24T17:36:35Z
**Status:** human_needed
**Re-verification:** No - previous `195-VERIFICATION.md` existed, but had no structured `gaps:` section.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | SC-1 production `rtt_confidence` is observed in `/health` and SQLite over a 1-hour cake-signal window | ? HUMAN | Code and tests verify pass-through/gated metric wiring, but no 1-hour production artifact is present. |
| 2 | SC-2 production low-confidence queue-GREEN RTT spike does not emit `rtt_veto` | ? HUMAN | Automated branch coverage passes; no operator production trace is present. |
| 3 | SC-3 production single-path flip does not enter `healer_bypass` | ? HUMAN | Automated replay passes; no operator production trace is present. |
| 4 | SC-4 Spectrum 2026-04-23 replay avoids phantom RTT bloat and healer bypass | VERIFIED | `tests/test_phase_195_replay.py:537` and `:566`; replay lineage passed `48 passed, 6 skipped`. |
| 5 | Controller derives `rtt_confidence` in `[0.0, 1.0]` from ICMP/UDP agreement and queue/RTT direction | VERIFIED | `_derive_rtt_confidence` at `src/wanctl/wan_controller.py:2642`; tests at `tests/test_wan_controller.py:3249`. |
| 6 | `rtt_confidence` is `None` when no valid queue snapshot exists | VERIFIED | `_run_congestion_assessment` sets `None` at `src/wanctl/wan_controller.py:2747`; focused tests passed. |
| 7 | `/health` and SQLite metric paths surface live confidence without sentinel rows | VERIFIED | `get_health_data` at `src/wanctl/wan_controller.py:4155`, metric append at `:3079`, renderer pass-through at `src/wanctl/health_check.py:781`. |
| 8 | Queue-primary distress remains authoritative | VERIFIED | Selector returns queue distress before veto at `src/wanctl/wan_controller.py:2694`; tests cover queue-distress authority. |
| 9 | RTT veto fires only for queue-GREEN, confidence `>= 0.6`, agreeing non-unknown directions, and RTT YELLOW+ | VERIFIED | Gate at `src/wanctl/wan_controller.py:2697-2706`; `TestPhase195RttVetoGate` passed. |
| 10 | Fusion bypass enters only after 6 aligned queue+RTT distress cycles | VERIFIED | Streak/gate at `src/wanctl/wan_controller.py:2772-2799`; `TestPhase195HealerBypass` and replay tests passed. |
| 11 | Single-path flips never bypass | VERIFIED | `tests/test_phase_195_replay.py:537`; `tests/test_wan_controller.py:3060`; replay and focused slices passed. |
| 12 | No queue-us/RTT-ms magnitude ratio, and UL/state-machine/timing/threshold/rate-compute contracts hold | VERIFIED | Source guards found no `absolute_disagreement` or queue/RTT ratio; no diff in `queue_controller.py`, `cake_signal.py`, or `fusion_healer.py`; full slice passed. |
| 13 | Post-review WR-01 stale fusion fallback expectation is fixed | VERIFIED | Commit `14b0343`; `tests/test_fusion_healer.py:831` asserts filtered RTT without bypass; `109 passed`. |

**Score:** 10/13 truths verified; 3 require production human verification.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/wanctl/wan_controller.py` | Confidence helpers, RTT veto, healer streak gate, health/metric wiring | VERIFIED | Constants/helpers/stashes, selector, gate, and metrics are present and wired. |
| `src/wanctl/health_check.py` | `signal_arbitration.rtt_confidence` pass-through renderer | VERIFIED | Renderer returns `arb.get("rtt_confidence")`; docstring reflects live Phase 195 source. |
| `tests/test_wan_controller.py` | Unit coverage for confidence, veto, healer bypass, UL guards | VERIFIED | Focused slice passed `64 passed, 306 deselected`. |
| `tests/test_health_check.py` | Renderer pass-through for `0.0`, `0.5`, `1.0`, `None` | VERIFIED | `test_phase195_renderer_passes_rtt_confidence_through` at line 4488. |
| `tests/test_phase_195_replay.py` | Replay harness for ARB-02, ARB-03, SAFE-05, Spectrum event | VERIFIED | Manual check verified `SPECTRUM_2026_04_23_TRACE`; gsd-tools' mixed-case pattern check was a false negative. |
| `tests/test_phase_194_replay.py` | Superseded Phase 194 negative `rtt_veto` assertion | VERIFIED | Test is retained and skipped with explicit Phase 195 pointer at line 516. |
| `tests/test_fusion_healer.py` | Updated WR-01 fallback expectation | VERIFIED | Large ICMP/IRTT disagreement now asserts no bypass activation. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `_run_congestion_assessment` | `_last_rtt_confidence`, directions, and previous raw deltas | Raw queue/RTT deltas captured before selector | VERIFIED | Lines `2728-2756` compute and stash current-cycle confidence before arbitration. |
| `_select_dl_primary_scalar_ms` | `ARBITRATION_REASON_RTT_VETO` | Confidence, direction agreement, RTT YELLOW+ gate | VERIFIED | Lines `2697-2706`; queue distress returns first. |
| `_run_congestion_assessment` | Fusion bypass state | `_healer_aligned_streak >= 6` | VERIFIED | Lines `2772-2799`; sets `queue_rtt_aligned_distress` and `healer_bypass`. |
| `_compute_fused_rtt` | Phase 195 bypass driver | Fusion math records offset only | VERIFIED | Lines `1718-1720`; source has no `absolute_disagreement` literal. |
| `WANController.get_health_data` | `/health.signal_arbitration.rtt_confidence` | `getattr(self, "_last_rtt_confidence", None)` | VERIFIED | Line `4155`; `health_check.py` passes it through unchanged. |
| `_run_logging_metrics` | `wanctl_rtt_confidence` row | `_append_rtt_confidence_metric` only when non-None | VERIFIED | Lines `3028`, `3079-3088`; tests cover emit and skip. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `wan_controller.py` | `_last_rtt_confidence` | Raw queue delta, raw RTT delta, `_irtt_correlation`, `_derive_rtt_confidence` | Yes | FLOWING |
| `health_check.py` | `signal_arbitration.rtt_confidence` | `WANController.get_health_data()` | Yes | FLOWING |
| SQLite metrics path | `wanctl_rtt_confidence` | `_append_rtt_confidence_metric` gated on non-None confidence | Yes | FLOWING |
| Fusion bypass fields | `_fusion_bypass_active`, `_fusion_bypass_reason` | 6-cycle aligned distress gate | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 195 focused controller/health behavior | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py tests/test_health_check.py -q -k "rtt_confidence or arbitration or signal_arbitration or healer_bypass or phase195"` | `64 passed, 306 deselected` | PASS |
| Replay lineage | `.venv/bin/pytest -o addopts='' tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py -q` | `48 passed, 6 skipped` | PASS |
| Post-review fusion fallback test | `.venv/bin/pytest -o addopts='' tests/test_fusion_healer.py -q` | `109 passed` | PASS |
| Full hot-path plus fusion slice | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py tests/test_fusion_healer.py -q` | `719 passed, 6 skipped` | PASS |
| Lint | `.venv/bin/ruff check ...` | `All checks passed!` | PASS |
| Type check | `.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/health_check.py` | `Success: no issues found in 2 source files` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| ARB-02 | `195-02`, `195-03` | RTT only overrides queue-GREEN through confidence and direction agreement | SATISFIED IN CODE | Selector gate and tests verify all branches; production trace remains human verification. |
| ARB-03 | `195-02`, `195-03` | Healer bypass only after 6 aligned queue+RTT distress cycles; single-path flips never bypass; no magnitude ratio | SATISFIED IN CODE | Streak gate, no literal `absolute_disagreement`, no ratio matches, replay coverage. |
| SAFE-05 | `195-01`, `195-02`, `195-03` | No state-machine, EWMA, dwell, deadband, burst, threshold, or rate-compute changes | SATISFIED | Source guards clean; no changes in `queue_controller.py`, `cake_signal.py`, or `fusion_healer.py`; full tests pass. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `src/wanctl/wan_controller.py` | 3097 | `return {}` | Info | Existing fallback for unavailable Linux CAKE write timings; not a Phase 195 stub and not user-visible. |

### Human Verification Required

### 1. SC-1 Production Confidence Observation

**Test:** Run a cake-signal-supported WAN for at least 1 hour and capture `/health` plus SQLite metric rows for `wanctl_rtt_confidence`.
**Expected:** `rtt_confidence` is a non-null float in `[0.0, 1.0]` on valid queue-snapshot cycles and tracks protocol/direction agreement.
**Why human:** Requires a production window and operator access to live health/SQLite data.

### 2. SC-2 Low-Confidence RTT Spike Trace

**Test:** Capture or replay against production telemetry where queue remains GREEN while RTT spikes and `rtt_confidence < 0.6`.
**Expected:** `control_decision_reason != "rtt_veto"` and DL zone transitions do not escalate due to RTT in that window.
**Why human:** Automated tests prove the branch, but the roadmap asks for an operator-verifiable traced scenario.

### 3. SC-3 Single-Path Flip Trace

**Test:** Capture a single-path ICMP/IRTT flip with queue GREEN for at least 6 cycles.
**Expected:** `control_decision_reason` never shows `healer_bypass`; fusion bypass remains inactive.
**Why human:** Automated replay proves the branch, but no production trace artifact is present.

### Gaps Summary

No implementation gaps were found. The phase goal is achieved in the codebase and covered by automated tests, including the post-review `tests/test_fusion_healer.py` expectation update. Status is `human_needed` only because roadmap success criteria 1-3 require production/operator evidence that is not present in this phase directory.

---

_Verified: 2026-04-24T17:36:35Z_
_Verifier: Codex (gsd-verifier)_
