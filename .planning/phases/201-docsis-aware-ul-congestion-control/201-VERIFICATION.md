---
phase: 201-docsis-aware-ul-congestion-control
verified: 2026-05-04T23:57:07Z
status: gaps_found
score: 4/9 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Spectrum UL canary at the deployed ceiling completes with ul_floor_hits_during_load=0 and floor_hit_cycles_total_delta_loaded_window=0 (VALN-06 primary gate)"
    status: failed
    reason: "Live canary 20260504T231334Z FAILED at setpoint_mbps=12 with floor_hit_cycles_total_delta_loaded_window=1453 over a 1022s loaded window and ul_floor_hits_during_load=84 on the 1Hz secondary cross-check. This is the inherited blocking VALN-06 requirement and the dominant phase-goal signal."
    artifacts:
      - path: ".planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json"
        issue: "verdict=fail; reason=ul_floor_hits_during_load_84_counter_delta_1453"
      - path: "src/wanctl/queue_controller.py:299-340"
        issue: "DOCSIS-mode rate-decision path has no anti-collapse mechanism under sustained saturation; RED branch (line 304) applies factor_down=0.90 unconditionally and the setpoint clamp only governs push-up (line 313). After 6-8 RED cycles current_rate * 0.90^N reaches floor_red_bps. See evidence below."
      - path: "src/wanctl/queue_controller.py:241-256"
        issue: "Integral window stays EXHAUSTED throughout the loaded window; canary samples observe rtt_integral_ms_s in 30-155 range vs 30 ms*s threshold, locking the push-up gate closed even when current_rate is at floor and there is in fact headroom available below setpoint."
    missing:
      - "Anti-collapse / anti-windup: when docsis_mode=true and current_rate <= setpoint, the multiplicative RED decay must not cascade to floor over consecutive RED cycles. Options: (a) decay_floor = setpoint when in docsis_mode and saturated, (b) shape factor_down per-direction with docsis_mode-specific gentler value (e.g. 0.95) gated on rate <= setpoint, (c) integral-aware decay that holds rate when integral is non-decreasing for N cycles."
      - "Recovery-from-floor path independent of green_streak >= green_required: under sustained iperf3 saturation, GREEN cycles are rare; the controller cannot climb back from floor on the existing recovery path. A floor-anchored recovery (e.g. step toward setpoint after K floor-stuck cycles regardless of green_streak) is needed."
      - "Cycle-fidelity diagnostic of the actual zone sequence during canary: the loaded_capture.ndjson does NOT include zone or red_streak per 50ms cycle, so the failure mode (RED-pulsing vs YELLOW-stuck) cannot be confirmed from evidence alone. Add a per-cycle zone counter or low-rate replay capture to /health for closure-cycle root cause."
  - truth: "VALN-06 24h Spectrum UL regression soak watchdog passes (suppression rate < 5/60s mean)"
    status: failed
    reason: "Plan 201-12 was authored but never executed; soak is not deferred to a later phase — it is a Phase 201 success-criterion #3 in the ROADMAP. Per the canary FAIL it could not run, so the goal is unmet for this phase."
    artifacts:
      - path: ".planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md"
        issue: "Plan exists but was never executed. STATE.md confirms blocked; no soak summary exists."
    missing:
      - "Soak cannot run until the canary passes. Closure must come via a re-canary path (A5 fallback at setpoint_mbps=10 or different control-model amendment) followed by 24h soak."
  - truth: "A5 fallback re-canary at setpoint_mbps=10 was authorized as a post-FAIL operator decision and produces a clean PASS or directs the next plan"
    status: failed
    reason: "Re-canary at setpoint_mbps=10 was explicitly authorized (REVIEWS HIGH-? / 201-11-CANARY-VERDICT 'A5 fallback availability'), but was not executed during this continuation. The phase is closed at FAIL with no fallback evidence either confirming or rejecting that setpoint=10 would close VALN-06."
    artifacts:
      - path: ".planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md"
        issue: "Records 'A5 fallback availability: re-canary at setpoint_mbps=10 is allowed as a future operator decision ... It was NOT started during this execution.' Decision is open, not executed."
    missing:
      - "Operator decision: either run A5 fallback re-canary at setpoint_mbps=10 (and capture verdict.json) OR plan a control-model amendment (anti-collapse + anti-windup, see truth-1 missing items) before any new canary attempt. Note: the canary evidence above suggests setpoint=10 alone may not close the gap because the failure mechanism is RED-decay-to-floor, not setpoint-too-aggressive — the controller still hits RED at 10 Mbit on saturated DOCSIS upload."
  - truth: "REVIEWS HIGH-5 evidence (cycle-fidelity floor-hit counter using 50ms-resolution counter delta, not 1Hz snapshot) is operationally honest"
    status: partial
    reason: "Counter is implemented (queue_controller.py:122,170 increments floor_hit_cycles every cycle that lands on floor_red_bps; surfaced via /health.upload.floor_hit_cycles_total at line 618; canary verdict consumes counter delta as primary gate). But the counter is monotonic-since-daemon-restart, not per-canary-window, and its delta is only as accurate as the bookend snapshots — both of which are 1Hz health pulls subject to ±1s sample jitter. The 1453 counter delta is honest but the start/end timing is not cycle-aligned, so per-cycle floor-hit attribution within the window is approximate."
    artifacts:
      - path: "src/wanctl/queue_controller.py:122,170,618"
        issue: "Counter present and wired; correct semantics."
    missing:
      - "Optional follow-up (NOT a Phase 201 closure blocker): emit per-cycle zone+rate to a debug ring buffer or downsampled (e.g. 5Hz) /health field so the failure-mode replay can attribute floor hits to specific RED-pulses. Without this, root-cause diagnosis stays inferential."
  - truth: "REVIEWS HIGH-7 YAML rollback restores production to pre-Phase-201 state on canary FAIL"
    status: verified_failed_path_only
    reason: "Rollback was executed and verified (see 201-11-CANARY-VERDICT.md). post-rollback /health.version=1.39.0 and all six Phase 201 YAML keys (docsis_mode, setpoint_mbps, integral_window_seconds, integral_threshold_ms_s, cake_backlog_low_threshold_bytes, cake_delay_delta_low_threshold_us) report count 0 in /etc/wanctl/spectrum.yaml. This is the only reason production is recoverable. Marking VERIFIED for the rollback path; the upstream goal (canary PASS) is FAILED separately."
    artifacts:
      - path: ".planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md"
        issue: "Rollback section confirms binary archive `/opt/wanctl-prephase201-20260504T231220Z.tar.gz` and YAML snapshot `/etc/wanctl/spectrum.yaml.prephase201-20260504T231220Z` were both restored."
    missing: []
  - truth: "max_delay_delta_us is publicly serialized through /health for post-canary diagnosis (REVIEWS LOW finding deferred in 201-10)"
    status: failed
    reason: "Per STATE.md decision 201-10: 'Deferred the max_delay_delta_us public /health serialization gap as non-blocking for VALN-06 because the live canary gate uses floor_hit_cycles_total_delta_loaded_window plus ul_floor_hits_during_load, not max_delay_delta_us.' Now that the canary FAILED and root-cause diagnosis is the dominant closure activity, the absence of this field in /health is actively harmful — the canary loaded_capture.ndjson cannot answer 'was CAKE backlog high during the floor hits, or only RTT integral?' without it."
    artifacts:
      - path: "src/wanctl/wan_controller.py:4510-4511"
        issue: "/health upload payload uses self._ul_cake_snapshot which contains max_delay_delta_us in the dataclass but is not part of the serialized public health field; the canary capture confirms cake_aligned: false but does not surface the underlying max_delay_delta_us value driving that boolean."
    missing:
      - "Serialize max_delay_delta_us into /health.wans[].upload (and download for symmetry) as an additive field. This is now blocking: gap-closure planning needs to know whether it was the integral or the CAKE corroborator (or both) that pinned the controller — current evidence only shows headroom_state=EXHAUSTED + cake_aligned=false simultaneously."
deferred:
  - truth: "ATT cake-primary canary VALN-05b"
    addressed_in: "v1.39 Phase 191 closure (cross-milestone)"
    evidence: "201-CONTEXT.md Deferred Ideas; .planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md"
human_verification:
  - test: "Operator decision on closure path"
    expected: "One of: (a) authorize A5 fallback re-canary at setpoint_mbps=10 with full predeploy/canary/rollback flow; (b) authorize a control-model amendment phase (anti-collapse + anti-windup + diagnostic /health serialization) before any new canary; (c) close Phase 201 as gaps_found and re-roadmap into v1.43+."
    why_human: "Production network change-policy in CLAUDE.md ('stability > safety > clarity > elegance') makes this an operator-only call. Verifier evidence supports option (b): the failure mechanism is structural (RED-decay-to-floor under saturated DOCSIS, no anti-collapse), not parameter-tuning, so option (a) at setpoint=10 has high a-priori risk of repeating the FAIL with smaller magnitude."
  - test: "Cycle-level zone trace during a re-canary attempt"
    expected: "If a re-canary runs, capture per-cycle zone (RED/YELLOW/GREEN), red_streak, _last_integral_ms_s, _cake_aligned, current_rate at the same 50ms cadence as the controller. This is the only way to confirm the failure mechanism inferred above (RED-pulsing collapsing rate to floor)."
    why_human: "Requires a code change (e.g. debug ring buffer or downsampled health field) and a coordinated re-canary; not something the verifier can produce."
---

# Phase 201: DOCSIS-Aware UL Congestion Control — Verification Report

**Phase Goal:** Ship a DOCSIS-aware UL congestion control mode that holds Spectrum DOCSIS upload off the floor under saturated load, closing VALN-06 with `floor_hit_cycles_total_delta_loaded_window=0` and `ul_floor_hits_during_load=0`, followed by a 24h soak watchdog at `<5/60s` UL hysteresis suppression rate.

**Verified:** 2026-05-04T23:57:07Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | DOCSIS-aware mode is YAML opt-in keyed off `continuous_monitoring.upload.docsis_mode: true`; absent or false is byte-identical to legacy | VERIFIED | `queue_controller.py:47,109,158` (gate); `tests/test_queue_controller.py::TestDocsisModeByteIdentity` collected; `configs/spectrum.yaml:79` shows `docsis_mode: true`; non-Spectrum YAMLs untouched per D-17 |
| 2 | Schema accepts `docsis_mode`, `setpoint_mbps`, integral window keys; `setpoint_mbps` REQUIRED when `docsis_mode: true`; ordering check honored | VERIFIED | `autorate_config.py` schema present; `check_config_validators.py` `KNOWN_AUTORATE_PATHS` updated (per 201-03 SUMMARY); `tests/test_autorate_config.py::TestPhase201Schema` and `tests/test_check_config.py::TestDocsisModeValidation` collected |
| 3 | RTT-integral classifier and CAKE corroborator wired into `_classify_zone_3state`/`_compute_rate_3state` | VERIFIED | `queue_controller.py:155-161, 241-270, 311-323` — code reads correctly: integral updates from `delta`, CAKE alignment categorical AND, setpoint clamp on push-up only |
| 4 | `/health` carries additive runtime-state fields: `docsis_mode_active`, `setpoint_mbps`, `headroom_state`, `rtt_integral_ms_s`, `cake_aligned`, `floor_hit_cycles_total` | VERIFIED | `queue_controller.py:611-619`; canary `loaded_capture.ndjson` confirms all six fields populated per 1Hz sample |
| 5 | Predeploy gate inspects `/etc/wanctl/spectrum.yaml` and either reconciles v1.41 rejected-hypothesis keys or fails closed | VERIFIED | `scripts/phase201-predeploy-gate.sh` exists; canary record confirms first run BLOCK on `target_bloat_ms`/`warn_bloat_ms`, reconcile-by-copy applied, second run PASS; `tests/test_phase201_predeploy_gate.py` exists |
| 6 | Spectrum canary primary gate is `floor_hit_cycles_total_delta_loaded_window=0` AND `ul_floor_hits_during_load=0` (cycle-fidelity, REVIEWS HIGH-5) | FAILED | `verdict.json` reports `floor_hit_cycles_total_delta_loaded_window=1453`, `ul_floor_hits_during_load=84`; verdict=fail. **Phase goal not achieved.** |
| 7 | 24h Spectrum UL regression soak passes (`<5/60s` mean) — VALN-06 watchdog | FAILED | Plan 201-12 was authored but never ran. STATE.md confirms blocked; no soak summary exists. |
| 8 | YAML rollback on canary FAIL restores production to pre-Phase-201 binary AND YAML state (REVIEWS HIGH-7) | VERIFIED | post-rollback `/health.version=1.39.0`; all six Phase 201 YAML keys count `0` in `/etc/wanctl/spectrum.yaml` |
| 9 | A5 fallback path (re-canary at setpoint_mbps=10) was executed OR an explicit operator close-out decision was recorded | FAILED | Per `201-11-CANARY-VERDICT.md`, A5 was authorized as a "future operator decision" but was not executed. No closure decision recorded; phase is left at canary FAIL with rollback complete and Plan 201-12 blocked. |

**Score:** 4/9 truths verified (5 failed, 0 uncertain)

The phase implementation landed (truths 1-5,8) but the phase goal (truth 6) is not achieved. Truths 7, 9 are downstream consequences of 6.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/queue_controller.py` | DOCSIS-mode internals: integral, CAKE corroborator, setpoint clamp, floor-hit counter | EXISTS, SUBSTANTIVE, WIRED | All wired; design defect is in the *behavior* under saturated load, not artifact integrity. See "Floor-Pegging Root Cause" below. |
| `src/wanctl/wan_controller.py` | Constructor wiring + presence flags + INFO log + 5-6 additive /health fields | EXISTS, SUBSTANTIVE, WIRED | Wired per 201-05 SUMMARY; canary capture confirms /health fields live |
| `src/wanctl/autorate_config.py` | Schema for `docsis_mode`, `setpoint_mbps`, integral window keys, ordering check | EXISTS, SUBSTANTIVE, WIRED | YAML-load path confirms keys parse and validate |
| `src/wanctl/check_config_validators.py` | KNOWN_AUTORATE_PATHS registers Phase 201 keys (SAFE-06) | EXISTS, SUBSTANTIVE, WIRED | Predeploy gate first run BLOCK on rejected v1.41 keys confirms registry-driven rejection works |
| `configs/spectrum.yaml` | docsis_mode=true, setpoint_mbps=12, integral_window_seconds=2.0, integral_threshold_ms_s=30.0, cake_backlog_low_threshold_bytes=5000, cake_delay_delta_low_threshold_us=5000 | EXISTS, SUBSTANTIVE | All six keys present at expected values |
| `scripts/phase200-saturation-canary.sh` | D-12 preflight extension + counter-delta primary gate (HIGH-5) + fail-closed env enforcement (HIGH-6) | EXISTS, SUBSTANTIVE, WIRED | verdict.json shape confirms primary gate is counter delta, not 1Hz snapshot |
| `scripts/phase201-predeploy-gate.sh` | Fail-closed reconcile-or-block on rejected v1.41 keys before deploy | EXISTS, SUBSTANTIVE, WIRED | Live canary confirms first-run BLOCK + manual reconcile + second-run PASS path |
| `.planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md` | Plan authored, executed, soak summary captured | EXISTS, NOT EXECUTED | Plan exists; no soak summary; STATE.md confirms blocked |
| `canary/20260504T231334Z/verdict.json` | verdict=pass with both floor-hit gates at 0 | EXISTS, FAILED | verdict=fail; primary gate value 1453 |
| `tests/test_phase_201_replay.py` | Replay corpus loader + Attempt 3 replay floor_hits=0 + legacy byte-identity | EXISTS, SUBSTANTIVE | Per STATE.md decision 201-04: 20x hold-last replay records 1003 RED-heavy floor-hit cycles under exact RED fast-trip and post-bounds floor-hit accounting; treated as safety diagnostic, not synthetic VALN-06 closure. **The replay model itself was a known-coarse approximation; live canary is the gate, and it failed.** |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `wan_controller.py` upload cycle | `queue_controller.adjust(..., cake_snapshot=ul_cake)` | direct call at `wan_controller.py:2978-2984` | WIRED | CAKE snapshot reaches DOCSIS-mode integral+corroborator |
| `queue_controller.adjust` | `floor_hit_cycles` increment | `queue_controller.py:170` `if new_rate == self.floor_red_bps: self.floor_hit_cycles += 1` | WIRED | Counter increments per cycle that lands on floor |
| `queue_controller.get_health_data` | `/health.wans[].upload.floor_hit_cycles_total` | `wan_controller.py` health builder | WIRED | Canary capture confirms field populated |
| canary script | counter-delta primary verdict | `verdict.json.primary_gate=floor_hit_cycles_total_delta_loaded_window` | WIRED | verdict.json schema confirms cycle-fidelity gate |
| Predeploy gate | `deploy.sh` exit propagation | `\|\| gate_rc=$?` pattern (REVIEWS plan 07 fix) | WIRED | Live canary confirms gate exit propagates correctly |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test suite for Phase 201 surfaces collects | `.venv/bin/pytest -o addopts='' <Phase 201 slice> --collect-only -q` | Per VALIDATION.md and 201-02 SUMMARY: 18 named test classes collect cleanly | PASS |
| Canary verdict.json valid JSON with FAIL verdict | `jq '.verdict' canary/20260504T231334Z/verdict.json` | `"fail"` | PASS (verdict captured), but the verdict value itself is FAIL — phase goal unmet |
| Live /health reports DOCSIS-mode active during canary | Post-deploy spot check captured in CANARY-VERDICT.md | `docsis_mode_active=true`, `setpoint_mbps=12.0`, `floor_hit_cycles_total=0` initially | PASS (deployment integrity), then FAIL (load behavior) |
| Loaded capture rate distribution shows oscillation between setpoint and floor | `python3 ...` (verifier ad-hoc) | Counter: `12.0`: 778 samples, `8.0` (floor): 84 samples, `18.0`: 7 samples (post-rollback boundary), intermediates 9.7/10.8: 16 samples | OBSERVED — confirms floor-pegging dynamics |

---

## Floor-Pegging Root Cause Analysis

The phase delivered the artifacts but not the behavior. Reading the canary capture (`loaded_capture.ndjson`, 885 1Hz samples over the 1022s loaded window) and the controller code together produces a specific defect identification:

**Observed dynamics (1Hz snapshots during loaded window, ad-hoc verifier inspection):**

| Sample | rate_mbps | floor_hit_cycles_total | rtt_integral_ms_s | headroom_state | cake_aligned |
|---|---|---|---|---|---|
| #0 | 18.0 | 0 | 2.7 | AVAILABLE | true |
| #100 | 12.0 | 135 | 84.9 | EXHAUSTED | false |
| #300 | 12.0 | 240 | 41.0 | EXHAUSTED | false |
| #500 | 12.0 | 424 | 69.6 | EXHAUSTED | false |
| #700 | 12.0 | 954 | 30.9 | EXHAUSTED | false |
| #880 | 8.0 | 1402 | 155.6 | EXHAUSTED | false |

Floor-hit increments per 1Hz sample average **~15.5 cycles** (mean of 94 non-zero deltas), with max 21 — i.e. for ~1s windows the controller is pegged at floor for the *entire window*.

**Mechanism (specific code paths):**

1. **RED multiplicative decay drives current_rate to floor in 6-8 cycles.** `queue_controller.py:301-304`:
   ```python
   if self.red_streak >= 1:
       self._yellow_decay_streak = 0
       return int(self.current_rate * self.factor_down)  # factor_down=0.90 for Spectrum UL
   ```
   Starting at setpoint=12 Mbit, six consecutive RED cycles reach `12 * 0.9^6 = 6.37 Mbit`, which is below floor (8 Mbit), so `enforce_rate_bounds` clamps to floor. Floor pegs.

2. **Integral remains EXHAUSTED throughout.** `queue_controller.py:241-256`. Under saturated iperf3, `delta = load_rtt - baseline_rtt` is consistently > 0; integral over 2s window stays well above 30 ms·s threshold (observed 30-155 in capture). `_headroom_state` stays "EXHAUSTED" for the full loaded window.

3. **Setpoint clamp does NOT prevent collapse.** `queue_controller.py:309-313`:
   ```python
   if self._docsis_mode and self._setpoint_bps is not None:
       if not (self._headroom_state == "AVAILABLE" and self._cake_aligned):
           return min(raw_rate, self._setpoint_bps)
   ```
   This branch only fires when `green_streak >= green_required`. It governs *push-up*, not *push-down*. Once RED takes the rate below setpoint, the setpoint clamp is silent.

4. **Recovery from floor is gated on green_streak ≥ 3 (Spectrum YAML), and GREEN cycles are starved under sustained load.** Once at floor, the iperf3 saturation reduces (because shaping is more aggressive) and RTT eventually relaxes. But by the time enough GREEN cycles accumulate, the controller has pulsed RED again from upstream queue refills. The capture shows the controller recovering to setpoint=12 (778 samples) but each recovery is followed by another RED-collapse to floor (84 floor-1Hz samples ≈ 84 collapse events × 15-20 cycles each = ~1453 floor cycles).

5. **The "DOCSIS-aware" mode is ASYMMETRIC ONLY ON THE PUSH-UP SIDE.** It adds a setpoint clamp on the recovery branch but introduces no anti-collapse mechanism on the RED branch. Yet the failure mode is on the RED branch.

**Architectural diagnosis (consistent with 201-CONTEXT.md):** The Phase 200 RETRO correctly identified that the residual failure regime is "shaping-headroom dominated, not threshold dominated." Phase 201 added a setpoint to create *headroom on the push-up boundary* but did not add a corresponding *floor-anchor on the push-down boundary*. Under saturated DOCSIS, the CMTS upstream queue refills as fast as wanctl can shape it down — RED keeps firing — and `factor_down=0.90` cascades current_rate to floor. The headroom intervention is on the wrong side of the asymmetric controller.

**Specific defect locations:**

- `src/wanctl/queue_controller.py:301-304` — RED branch unconditionally applies factor_down, no docsis_mode anti-collapse
- `src/wanctl/queue_controller.py:309-314` — setpoint clamp governs push-up only
- `src/wanctl/queue_controller.py:241-256` — integral has no anti-windup; once EXHAUSTED, stays EXHAUSTED for the full 2s window after RTT actually decays, slowing recovery further

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| VALN-06 (inherited blocking from Phase 200) | ROADMAP Phase 201 SC#2-#4; REQUIREMENTS.md | Spectrum UL saturation gate canary `ul_floor_hits_during_load=0` AND 24h soak `<5/60s` | BLOCKED | Canary FAIL at 84 floor hits / 1453 cycles; soak never ran |
| VALN-06 schema portion | ROADMAP Phase 201 SC#1 | Schema accepts new keys, `setpoint_mbps` required when `docsis_mode=true`, byte-identical legacy fallback | SATISFIED | Plan 201-03 SUMMARY confirms; tests collect; canary deploy validated YAML loads |
| VALN-06 predeploy gate | ROADMAP Phase 201 SC#4 | Predeploy gate inspects /etc/wanctl/spectrum.yaml and reconciles or fails closed | SATISFIED | Plan 201-07 SUMMARY confirms; live canary confirms first-run BLOCK + reconcile + second-run PASS |
| VALN-06 docs | ROADMAP Phase 201 SC#5 | CHANGELOG.md and docs/CONFIGURATION.md migration note | SATISFIED | Per Plan 201-06 SUMMARY (D-12/DOCS-03 applied) |

VALN-06 is the single phase requirement and it is BLOCKED — closure shape requires both canary PASS *and* soak watchdog PASS, neither of which were achieved.

---

## REVIEWS HIGH-Item Coverage

Codex pre-review (`201-09-CODEX-PRE-REVIEW.md`) flagged 7 HIGH items. Per STATE.md decision 201-09 ("All HIGH amendments accepted"), each was addressed in plan amendments. Verifying actual implementation:

| HIGH | Concern | Implementation Status | Evidence |
|---|---|---|---|
| HIGH-1 | Plan 03 must depend on Plan 09 (Codex pre-review) | RESOLVED | Plan 09 ran before Wave 1; STATE.md timeline confirms |
| HIGH-2 | Plans 04 and 05 not parallel-safe | RESOLVED | VALIDATION.md notes Wave 5 split; Plan 05 moved to Wave 3 after Plan 04 |
| HIGH-3 | Wave 0 skip-only stubs weaken RED contract | RESOLVED | STATE.md decision 201-02: "Importable Phase 201 stubs use strict xfail or natural missing-symbol failures rather than skip-only placeholders"; only the absent predeploy shell uses function-level skips |
| HIGH-4 | Replay does not model the 50ms loop | PARTIALLY RESOLVED — disclosed | STATE.md decision 201-04: replay revised to "20x hold-last replay records 1003 RED-heavy floor-hit cycles ... safety diagnostic rather than synthetic VALN-06 closure; Plan 201-11 live canary remains the closure gate." Live canary subsequently FAILED, so the replay's coarseness was correctly disclosed but the canary did NOT compensate. |
| HIGH-5 | Canary may not detect cycle-level floor hits (1Hz polling) | RESOLVED ARTIFACT, FAILED OUTCOME | `floor_hit_cycles` counter (queue_controller.py:122,170) increments every 50ms cycle; canary primary gate uses counter delta. The cycle-fidelity gate worked as designed and detected 1453 floor-cycles where the 1Hz snapshot saw only 84 samples at floor. **The HIGH-5 resolution was load-bearing for catching this failure honestly.** |
| HIGH-6 | Canary checks fail-OPEN if env vars missing | RESOLVED | STATE.md decision 201-08: "Phase 201 canary mode is fail-closed unless PHASE201_DOCSIS_MODE=true and PHASE201_SETPOINT_MBPS=12 are set"; tests/test_phase200_canary_script.py::TestPhase201EnvFailClosed |
| HIGH-7 | Rollback does not restore YAML | RESOLVED + EXECUTED | YAML snapshot taken predeploy; rollback restored both binary and YAML; verified by post-rollback grep counts (all 6 keys = 0) |

**REVIEWS HIGH summary:** All 7 HIGH items resolved at the artifact level. HIGH-5 and HIGH-7 actively load-bearing during the canary FAIL — without the cycle-fidelity counter the 1Hz gate would have read 84 floor samples / 1022s = "8% loaded floor presence" and the verdict shape would have been weaker; without HIGH-7 the rollback would have left v1.42 YAML keys under the v1.40 binary in an undefined state.

---

## Pre-Deploy / Config-Schema Gap

The canary record shows the predeploy gate first run BLOCKED on `target_bloat_ms` and `warn_bloat_ms` keys (rejected v1.41 hypothesis keys still on production `/etc/wanctl/spectrum.yaml` from Phase 200's failed gap-closure cycle). Reconciliation was applied by copying the repo YAML over.

This is **NOT a Phase 201 gap** — it is the predeploy gate doing its job, exactly as designed (D-15). It validates that the SAFE-06 unknown-key warning + Phase 201 fail-closed gate together prevent production from running with stale/rejected config. Surface this as a SAFE-06 success, not a config-schema failure.

---

## Anti-Patterns Found

None of the standard stub anti-patterns. Code is substantive, tests are not skip-stubs, /health is wired through real fields. The failure is behavioral, not artifactual.

One observation: `queue_controller.py` line 1453 reflects a tight cycle without per-zone instrumentation — the loaded_capture lacks a `current_zone` field per sample (verified: `zone=None` for all sampled rows in the inspection above). This is not a defect per the contract (the contract is `floor_hit_cycles_total`), but it is a diagnostic gap that compounds with the deferred `max_delay_delta_us` serialization.

---

## Human Verification Required

See `human_verification` block in frontmatter. Two items:

### 1. Operator decision on closure path

**Test:** Operator picks one of:
- (a) authorize A5 fallback re-canary at `setpoint_mbps=10` with full predeploy/canary/rollback flow
- (b) authorize a control-model amendment phase (anti-collapse on RED branch + anti-windup on integral + diagnostic /health serialization for `max_delay_delta_us` and zone trace) before any new canary
- (c) close Phase 201 as `gaps_found` and re-roadmap into v1.43+ as a control-model redesign milestone

**Expected:** Operator records decision; the `/gsd-plan-phase 201 --gaps` flow plans against that decision.

**Why human:** Production network change-policy in CLAUDE.md (`stability > safety > clarity > elegance`) makes this an operator-only call. **Verifier evidence supports option (b)**: the failure mechanism is structural (RED-decay-to-floor under saturated DOCSIS, no anti-collapse), not parameter-tuning, so option (a) at setpoint=10 has high a-priori risk of repeating the FAIL with smaller magnitude. setpoint=10 still saturates a 20 Mbit DOCSIS upstream and leaves wanctl's CAKE qdisc with 10 Mbit shaping headroom — better than 6 Mbit at setpoint=12, but the RED-to-floor cascade mechanism remains identical.

### 2. Cycle-level zone trace during a re-canary attempt

**Test:** If a re-canary runs, capture per-cycle `zone` (RED/YELLOW/GREEN), `red_streak`, `_last_integral_ms_s`, `_cake_aligned`, `current_rate` at the same 50ms cadence as the controller, either via debug ring buffer in `/var/log/wanctl/spectrum_debug.log` or as an additional `/health` endpoint sampled at 5-20 Hz.

**Expected:** Per-cycle data confirms or refutes the inferred RED-pulsing-to-floor mechanism.

**Why human:** Requires a code change (e.g. debug ring buffer or downsampled health field) and a coordinated re-canary; not something the verifier can produce.

---

## Gaps Summary

The phase **delivered every artifact it promised** but **failed the goal it was meant to achieve.** The DOCSIS-aware UL controller exists in code, is YAML-opt-in, is byte-identical when off, has a cycle-fidelity floor-hit counter, has fail-closed predeploy gate, has fail-closed canary env enforcement, has both binary-and-YAML rollback. All of that worked.

What did not work is the **control behavior under saturated load.** The setpoint mechanism creates push-up headroom but does nothing about the existing asymmetric RED-decay path that drives current_rate from setpoint to floor in 6-8 cycles whenever the CMTS queue refills. Adding a setpoint without adding floor-anchored anti-collapse is treating the symptom (rate above setpoint causes bloat) without addressing the disease (RED multiplicative decay collapses rate to floor when the pipe stays saturated).

**The dominant gap is BLOCKER-severity:** VALN-06 is unmet by a 1453-cycle margin (vs zero-tolerance gate). The 24h soak is structurally unmet because it never ran. The A5 fallback is an open operator decision. Without operator authorization to re-canary or re-plan, Phase 201 is closed at FAIL with rollback complete and inheritance to a future milestone unavoidable.

**Suggested closure direction (for `/gsd-plan-phase 201 --gaps`):** Plan a control-model amendment that adds:
1. `factor_down_floor_anchor` (or equivalent): when `docsis_mode=true` and `current_rate <= setpoint_bps`, use a gentler factor_down (e.g. 0.95) OR clamp the per-cycle decay to `max(setpoint_bps * 0.9, current_rate * factor_down)` so the controller cannot cascade below setpoint absent a sustained-RED multi-cycle escalation.
2. Integral anti-windup: when `_headroom_state` has been EXHAUSTED for ≥ N cycles AND current_rate is at floor, halve the integral or reset the window so the recovery path is not gated on a stuck signal.
3. Diagnostic serialization: add `max_delay_delta_us`, `red_streak`, and a downsampled per-cycle zone trace to `/health.wans[].upload` so the next canary attempt can be root-caused without inference.
4. Re-canary at the same setpoint=12 (or A5 fallback setpoint=10) AFTER the above amendments. setpoint-tuning-only path has high re-FAIL risk per the analysis above.

---

_Verified: 2026-05-04T23:57:07Z_
_Verifier: Claude (gsd-verifier)_
