---
phase: 201-docsis-aware-ul-congestion-control
verified: 2026-05-06T14:35:00Z
status: gaps_found
score: 8/9 must-haves verified; D-14 suppression watchdog deferred to v1.43+ via operator Route B
overrides_applied: 0
closure_route: "Route B — defer to v1.43+. D-19 primary VALN-06 floor-hit gate PASSED; D-14 secondary suppression watchdog FAIL classified as metric_semantics_and_recalibration, NOT control_regression. Bounded RED decay + anti-windup (Plans 201-13/14) shipped and held under 24h saturation; the FAIL is on the YELLOW-edge dwell-hold code path (`_apply_dwell_logic` at queue_controller.py:348), not the bounded RED decay path (queue_controller.py:361-376). See `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md` for the recorded rationale."
re_verification:
  previous_status: gaps_found
  previous_score: "6/9 frontmatter / 4/9 inline (disagreed; both stale)"
  gaps_closed:
    - "Truth 6: VALN-06 canary primary gate — recanary 20260505T122513Z PASSED with primary_gate_value=0 and ul_floor_hits_during_load=0 (Plan 201-15)"
    - "Truth 9: A5 fallback OR explicit operator close-out decision — operator decision recorded 2026-05-06 as Route B (close gaps_found, defer D-14 to v1.43+)"
    - "Sub-truth: max_delay_delta_us serialization — Plan 201-13 added 8 additive /health diagnostic fields including max_delay_delta_us, zone_trace, red_streak, headroom_exhausted_streak, anti_windup_cycles, anti_windup_triggers, red_decay_step_pct, red_decay_delta_max_pct"
    - "Sub-truth: per-cycle zone trace — Plan 201-13 zone_trace bounded deque (maxlen=200) records every adjust() cycle"
    - "Sub-truth: control-model RED-decay-to-floor cascade — Plan 201-14 replaced multiplicative cascade with bounded-absolute decay clamp (queue_controller.py:361-376); cycle-table proof: cycles 1-5 step down 240k each, cycles 6-18 hold at 10.8M above 8M floor"
    - "Sub-truth: integral anti-windup — Plan 201-14 added cap-and-clamp anti-windup helper at queue_controller.py:290-320 with synchronous headroom_state recompute"
    - "Sub-truth: red-decay safety validators — Plan 201-14 added daemon (autorate_config.py:530-555) and offline (check_config_validators.py:576-654) validators that fail closed on unsafe step/clamp/floor ordering"
  gaps_remaining:
    - "Truth 7: D-14 secondary suppression watchdog FAIL @ 6.47/60s mean (vs <5.0). Classified by operator Route B as metric_semantics + recalibration, deferred to v1.43+."
  regressions: []
  closeout_recorded: 2026-05-06
  closeout_artifact: ".planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md"
  closeout_note: "Plan 201-17 closeout completed per operator Route B 2026-05-06; D-19 primary VALN-06 PASS shipped on v1.42.1, D-14 secondary deferred to v1.43+ as SEED-002..SEED-005. See 201-RETRO.md."
gaps:
  - truth: "VALN-06 24h Spectrum UL regression soak watchdog passes (D-14 secondary `<5/60s` mean)"
    status: failed
    classification: "metric_semantics_and_recalibration (NOT control_regression)"
    reason: "Plan 201-16 24h soak (run 20260505T132736Z, v1.42.1) reported D-19 primary floor-hit delta = 0 (PASS) but D-14 secondary `ul_hysteresis_suppression_rate_per_60s_mean = 6.466842364880155` against the inherited Phase 200 `<5/60s` threshold (FAIL). Codex re-aggregation confirmed the FAIL is on the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at queue_controller.py:348), unrelated to Plan 201-14's bounded RED decay fix at queue_controller.py:361-376. The published 6.47 mean is the mean of live-counter snapshots; `suppressions_per_min` at queue_controller.py:649,668 is a 60s-reset counter, not a true rate. The `<5/60s` threshold was inherited from Phase 200's qualitative '31/60s degraded → near-zero' framing and was never soak-calibrated against the post-Plan-201-14 control surface."
    artifacts:
      - path: ".planning/phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-summary.json"
        issue: "verdict=fail; reason=soak_gates_disagreement_primary_pass_secondary_fail; primary_gate.verdict=pass (delta=0); secondary_gate.verdict=fail (value=6.467 vs threshold=5.0)"
      - path: ".planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md"
        issue: "Operator-readable verdict preserving D-19 primary PASS and D-14 secondary FAIL together honestly."
    missing:
      - "Fix metric semantics first (v1.43+ Plan A): completed-window UL suppression counts + cause tags (dwell vs backlog) on /health, additive only, so future soaks can compute a true 60s rate instead of mean-of-counter-snapshots."
      - "Recalibrate D-14 (v1.43+ Plan B): re-derive a soak-calibrated threshold from completed-window counts on the post-Plan-201-14 baseline; the original `<5/60s` was qualitative and does not survive the post-fix control surface."
      - "Capture per-sample `load_rtt - baseline_rtt` distribution before any `target_bloat_ms` tune (v1.43+ Plan C) so the dwell churn root cause is data-driven."
      - "Conservative tuning candidates (`dwell_cycles: 5→4` or modest target_bloat_ms bump) ONLY after the three preceding items, with canary+soak+rollback gates (v1.43+ Plan D)."
deferred:
  - truth: "ATT cake-primary canary VALN-05b"
    addressed_in: "v1.39 Phase 191 closure (cross-milestone)"
    evidence: "201-CONTEXT.md Deferred Ideas; .planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md"
  - truth: "D-14 secondary suppression watchdog recalibration"
    addressed_in: "v1.43+ (Route B operator decision 2026-05-06)"
    evidence: "Operator memory `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md`; codex re-aggregation classified D-14 FAIL as YELLOW-edge dwell churn (`_apply_dwell_logic`), not the RED-bounded-decay path (`_compute_rate_3state`); D-14 threshold inherited from Phase 200 qualitative framing, not soak-calibrated against post-201-14 surface."
human_verification:
  - test: "Plan 201-17 closeout authoring: refresh CONTEXT.md/ROADMAP.md to mark Phase 201 `gaps_found` with explicit baton-pass to v1.43, write 201-RETRO.md, and open the four v1.43 backlog items in priority order (semantics → recalibrate → distribution → tune)."
    expected: "Closeout artifacts committed; v1.43 milestone scoped with the four ordered work items from the operator decision memory."
    why_human: "Closeout planning shape is operator-authored; verifier can confirm artifacts exist after the planner produces them but cannot author the milestone-scoping decisions."
    resolved: 2026-05-06
    resolved_evidence: "Plan 201-17 executed; see closeout_recorded above and 201-RETRO.md."
---

# Phase 201: DOCSIS-Aware UL Congestion Control — Verification Report

**Phase Goal:** Ship a DOCSIS-aware UL congestion control mode that holds Spectrum DOCSIS upload off the floor under saturated load, closing VALN-06 with `floor_hit_cycles_total_delta_loaded_window=0` and `ul_floor_hits_during_load=0`, followed by a 24h soak watchdog at `<5/60s` UL hysteresis suppression rate.

**Verified:** 2026-05-06T14:35:00Z (refreshed; supersedes 2026-05-06T13:40:36Z and the original 2026-05-04T23:57:07Z verification)
**Status:** gaps_found
**Re-verification:** Yes — refreshed against shipped Plans 201-13/14/15/16
**Closure route:** Route B (operator decision 2026-05-06) — close `gaps_found`, defer D-14 watchdog to v1.43+ as metric_semantics + recalibration

---

## Closure Route — Read This First

Phase 201 closes as `gaps_found` per **Route B** (operator decision recorded 2026-05-06):

- **D-19 primary VALN-06 floor-hit gate: PASS.** Bounded RED decay + anti-windup (Plans 201-13/14) shipped on v1.42.1; canary `20260505T122513Z` and 24h soak `20260505T132736Z` both report `floor_hit_cycles_total_delta=0`. The original phase-goal control behavior is achieved.
- **D-14 secondary suppression watchdog: FAIL @ 6.47/min vs `<5.0`** — classified as **metric_semantics + threshold_recalibration**, **NOT** a control regression. The FAIL is on the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at `queue_controller.py:348`), unrelated to the bounded RED decay path (`_compute_rate_3state` at `queue_controller.py:361-376`) that Plan 201-14 fixed. Codex re-aggregation of `soak-capture.ndjson` confirmed `red_streak>0` in 0.023% of samples and YELLOW tails in 1.52%, with suppression correlating 0.72 with YELLOW samples and 0.01 with `max_delay_delta_us`.
- **Metric-semantics surprise (load-bearing for the deferral):** `suppressions_per_min` at `queue_controller.py:649,668` is a 60s-reset counter, not a true rate. The published 6.47 mean is the mean of live-counter snapshots; the completed-window peak mean is ~13.9/min (p95=41, max=124). The `<5/60s` threshold was inherited from Phase 200's qualitative "31/60s degraded → near-zero" framing and was never soak-calibrated against the post-Plan-201-14 control surface.
- **v1.43 baton:** four ordered work items (fix semantics → recalibrate → capture distribution → conservative tune), each with canary+soak+rollback gates. See operator memory `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md`.

**Future readers: do not interpret the D-14 FAIL as a regression in bounded RED decay.** The two code paths are independent and the saturation evidence (D-19 PASS over 24h) is the load-bearing proof of the original phase-goal fix.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | DOCSIS-aware mode is YAML opt-in keyed off `continuous_monitoring.upload.docsis_mode: true`; absent or false is byte-identical to legacy | VERIFIED | `queue_controller.py:47,109,111-138` (gate + initialized-but-unused defaults); `tests/test_queue_controller.py::TestDocsisModeByteIdentity` collected; `configs/spectrum.yaml` shows `docsis_mode: true`; non-Spectrum YAMLs untouched per D-17. Plan 201-14 SAFE-05 byte-identity slice: 13 passed. |
| 2 | Schema accepts `docsis_mode`, `setpoint_mbps`, integral window keys, AND Plan 201-14 red-decay/anti-windup keys; `setpoint_mbps` REQUIRED when `docsis_mode: true`; cross-field validators fail closed on unsafe ordering | VERIFIED | `autorate_config.py:196,236-246,437-454,511-555` (all keys + validators); `check_config_validators.py:73-81,330-331,499-654` (mirrored offline validation); `tests/test_autorate_config.py::TestPhase201Schema` and `tests/test_check_config.py::TestDocsisModeValidation` collected; Plan 201-14 added 12 validator tests covering boundary semantics including 1/3 floating-point at-equality rejection. |
| 3 | RTT-integral classifier, CAKE corroborator, **bounded-absolute RED decay clamp**, and **integral anti-windup** are wired into `_classify_zone_3state`/`_compute_rate_3state` | VERIFIED | `queue_controller.py:155-180` (zone classification + zone_trace + max_delay_delta_us snapshot retention); `queue_controller.py:241-270` (integral); `queue_controller.py:290-320` (anti-windup helper); `queue_controller.py:361-376` (**bounded-absolute RED decay** under DOCSIS — replaces the original multiplicative cascade-to-floor identified as the root defect in the original verification); `queue_controller.py:381-386` (setpoint clamp on push-up only, byte-identical to legacy when `docsis_mode=false`). Plan 201-14 cycle-table test `TestDocsisModeReplayCanary11::test_red_burst_18_cycles_explicit_table` proves cycles 1-5 step down 240k each from 12M to 10.8M, cycles 6-18 hold at 10.8M above the 8M floor → `floor_hit_cycles=0` over the 18-cycle window. |
| 4 | `/health` carries the original 6 additive runtime-state fields PLUS Plan 201-13's 8 diagnostic fields (`max_delay_delta_us`, `red_streak`, `zone_trace`, `headroom_exhausted_streak`, `anti_windup_cycles`, `anti_windup_triggers`, `red_decay_step_pct`, `red_decay_delta_max_pct`); `sustained_red_cycles` deliberately absent per Plan 201-14 rev 4 | VERIFIED | `queue_controller.py:692-710` (get_health_data); `health_check.py:339-360` (passthrough into `/health.wans[].upload`); recanary `loaded_capture.ndjson` 20260505T122513Z first row contains all 14 fields; soak `soak-capture.ndjson` 20260505T132736Z 84117 rows confirm field stability over 24h. `grep sustained_red_cycles src/wanctl/queue_controller.py src/wanctl/health_check.py` returns no matches. |
| 5 | Predeploy gate inspects `/etc/wanctl/spectrum.yaml` and either reconciles v1.41 rejected-hypothesis keys or fails closed | VERIFIED | `scripts/phase201-predeploy-gate.sh` exists; recanary `201-15-CANARY-VERDICT.md` confirms first run BLOCK on `target_bloat_ms`/`warn_bloat_ms`, reconcile-by-copy applied, second run PASS; `tests/test_phase201_predeploy_gate.py` exists. The two-snapshot rollback strategy (Snapshot A rollback-clean, Snapshot B post-gate candidate) was validated end-to-end on the recanary path. |
| 6 | Spectrum canary primary gate is `floor_hit_cycles_total_delta_loaded_window=0` AND `ul_floor_hits_during_load=0` (cycle-fidelity, REVIEWS HIGH-5; VALN-06 primary) | VERIFIED | **Recanary `20260505T122513Z` PASSED** (Plan 201-15): `verdict.json` reports `verdict=pass`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`, `floor_hit_cycles_total_delta_loaded_window=0`, 1022s loaded window, pre/post baseline RTT 21.83/22.19 ms. **Phase goal D-19 primary achieved.** Supersedes the failed canary `20260504T231334Z` from the original verification. |
| 7 | 24h Spectrum UL regression soak passes (`<5/60s` D-14 secondary watchdog) | FAILED | Plan 201-16 24h soak `20260505T132736Z` against v1.42.1: D-19 primary `floor_hit_cycles_total_delta_soak_window=0` (PASS, operator-approved gate tightening per `201-16-OPERATOR-APPROVAL-D19.md`), D-14 secondary `ul_hysteresis_suppression_rate_per_60s_mean=6.467` against `<5.0` threshold (FAIL). Anti-windup trigger delta=0 over 24h (no anti-windup activations needed). Operator Route B 2026-05-06 classifies this as metric_semantics + recalibration, deferred to v1.43+. See "Closure Route" above. |
| 8 | YAML rollback on canary FAIL restores production to pre-Phase-201 binary AND YAML state (REVIEWS HIGH-7) | VERIFIED | Original canary FAIL path validated rollback (post-rollback `/health.version=1.39.0`; all six Phase 201 YAML keys count `0`). Recanary PASS path did not require rollback but the two-snapshot evidence (`Snapshot A` rollback-clean count=0, `Snapshot B` post-gate count=5) confirms the rollback target remains correct and uncontaminated. |
| 9 | A5 fallback path executed OR explicit operator close-out decision recorded | VERIFIED | **Operator Route B decision recorded 2026-05-06** in `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md`: close Phase 201 as `gaps_found`, ship Plans 201-13/14/15 (D-19 primary VALN-06 PASS), defer D-14 watchdog to v1.43+ as metric_semantics + recalibration. Codex second-opinion (saved at `/tmp/codex-201-prompt.md` / `/tmp/codex-201-response.log` 2026-05-06) recommended Route B; operator (Kevin) selected. |

**Score:** 8/9 truths verified (1 failed, 0 uncertain). The single failed truth is Truth 7, classified by operator Route B as metric_semantics + recalibration deferred to v1.43+, NOT a control regression.

The phase-goal control behavior (truths 1-6, 8) is achieved on shipped v1.42.1 production. The single remaining FAIL is on a code path independent of the phase-goal fix; deferral to v1.43+ is the recorded operator closure shape.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/queue_controller.py` | DOCSIS-mode internals: integral, CAKE corroborator, setpoint clamp, floor-hit counter, **bounded-absolute RED decay**, **anti-windup**, **zone trace**, **diagnostic /health fields** | EXISTS, SUBSTANTIVE, WIRED | All wired. The control-model defect identified in the original verification (multiplicative RED decay cascading to floor) was fixed by Plan 201-14 with a bounded-absolute clamp at lines 361-376; integral anti-windup at lines 290-320; zone trace and max-delay snapshot retention at 178-181. |
| `src/wanctl/wan_controller.py` | Constructor wiring + presence flags + INFO log + 5-6 additive /health fields + Plan 201-14 red-decay/anti-windup constructor wiring | EXISTS, SUBSTANTIVE, WIRED | Wired per 201-05 + 201-14 SUMMARYs; recanary capture confirms /health fields live including the 8 Plan 201-13 diagnostic fields. |
| `src/wanctl/autorate_config.py` | Schema for `docsis_mode`, `setpoint_mbps`, integral window keys, **red-decay/anti-windup keys**, ordering check, and Plan 201-14 cross-field validators | EXISTS, SUBSTANTIVE, WIRED | All keys parse, validate, and fail closed on unsafe combinations (lines 511-555). |
| `src/wanctl/check_config_validators.py` | KNOWN_AUTORATE_PATHS registers Phase 201 keys (SAFE-06) + offline mirror of red-decay safety validation | EXISTS, SUBSTANTIVE, WIRED | Recanary predeploy gate first run BLOCK on rejected v1.41 keys confirms registry-driven rejection works; offline validator mirror at lines 576-654. |
| `src/wanctl/health_check.py` | Passthrough of QueueController diagnostic fields into `/health.wans[].upload` | EXISTS, SUBSTANTIVE, WIRED | Plan 201-13 added 8 diagnostic fields with JSON-safe defaults (lines 339-360); Plan 201-14 mypy clean. |
| `configs/spectrum.yaml` | docsis_mode=true, setpoint_mbps=12, integral window keys, **red_decay_step_pct=0.02, red_decay_delta_max_pct=0.10, anti_windup_cycles=60** | EXISTS, SUBSTANTIVE | All Phase 201 keys present at expected values; Plan 201-14 added rev-4 red-decay defaults and anti-windup cycles. |
| `scripts/phase200-saturation-canary.sh` | D-12 preflight extension + counter-delta primary gate (HIGH-5) + fail-closed env enforcement (HIGH-6) | EXISTS, SUBSTANTIVE, WIRED | Recanary `verdict.json` shape confirms primary gate is counter delta and PASS path with delta=0. |
| `scripts/phase201-predeploy-gate.sh` | Fail-closed reconcile-or-block on rejected v1.41 keys before deploy | EXISTS, SUBSTANTIVE, WIRED | Recanary confirms first-run BLOCK + manual reconcile + second-run PASS path. |
| `canary/20260505T122513Z/verdict.json` | verdict=pass with both floor-hit gates at 0 | EXISTS, PASS | verdict=pass; primary_gate_value=0; ul_floor_hits_during_load=0. **Phase-goal D-19 primary VALN-06 closure evidence.** |
| `canary/20260505T122513Z/loaded_capture.ndjson` | 1022s loaded window with all 14 /health diagnostic fields | EXISTS, SUBSTANTIVE | First row confirmed to contain max_delay_delta_us, red_streak, zone_trace, anti_windup_cycles, anti_windup_triggers, headroom_exhausted_streak, red_decay_step_pct, red_decay_delta_max_pct. |
| `soak/20260505T132736Z/soak-summary.json` | 24h soak verdict with primary + secondary gates | EXISTS, MIXED | D-19 primary PASS (delta=0); D-14 secondary FAIL (6.467 vs <5.0). Overall verdict=fail per plan-defined gate-AND semantics. Operator Route B defers D-14 to v1.43+. |
| `soak/20260505T132736Z/soak-capture.ndjson` | 24h NDJSON capture (~86k rows expected) | EXISTS, SUBSTANTIVE | 84117 rows; sample coverage ratio 0.974 (above the 0.95 warning threshold); diagnostic distributions captured for RTT integral, CAKE delay delta, red streak, headroom. |
| `201-16-OPERATOR-APPROVAL-D19.md` | D-19 stricter primary soak gate operator approval, dated, captured BEFORE soak start | EXISTS | Approved 2026-05-05T13:15:37+00:00; references recanary PASS as justification. |
| `201-15-CANARY-VERDICT.md` | Operator-readable recanary PASS verdict + two-snapshot timeline + active knob proof | EXISTS, SUBSTANTIVE | All seven sections present; build identity binds to git SHA `311c9a4` and v1.42.1. |
| `201-16-SOAK-VERDICT.md` | Operator-readable soak verdict preserving D-19 PASS and D-14 FAIL together honestly | EXISTS, SUBSTANTIVE | Honest gate-disagreement preservation per codex NEW-HIGH-3 / LOW-CODEX-5. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `wan_controller.py` upload cycle | `queue_controller.adjust(..., cake_snapshot=ul_cake)` | direct call | WIRED | CAKE snapshot reaches DOCSIS-mode integral + corroborator + max-delay-delta-snapshot retention (Plan 201-13) |
| `queue_controller.adjust` | `floor_hit_cycles` increment | `queue_controller.py` `if new_rate == self.floor_red_bps: self.floor_hit_cycles += 1` | WIRED | Counter increments per cycle that lands on floor; recanary delta=0 over 1022s loaded window proves the bounded RED decay clamp at line 367-375 holds rate above floor. |
| `queue_controller._compute_rate_3state` (RED branch) | bounded-absolute decay + clamp-hold | `queue_controller.py:361-376` | WIRED | Plan 201-14 cycle-table test proves cycles 1-5 step down 240k each, cycles 6-18 hold at clamp 10.8M above 8M floor. **Replaces the multiplicative-cascade defect identified in original verification.** |
| `queue_controller._apply_anti_windup_if_needed` | integral cap + synchronous headroom recompute | `queue_controller.py:290-320` | WIRED | Anti-windup trigger counter exposed via /health; soak shows trigger delta=0 over 24h (no activations needed under bounded-decay regime). |
| `queue_controller.get_health_data` | `/health.wans[].upload.{14 diagnostic fields}` | `health_check.py:339-360` | WIRED | Recanary capture confirms all 14 fields populated; soak capture confirms 24h stability. |
| canary script | counter-delta primary verdict | `verdict.json.primary_gate=floor_hit_cycles_total_delta_loaded_window` | WIRED | Recanary verdict.json confirms cycle-fidelity gate at PASS (value=0). |
| Predeploy gate | `deploy.sh` exit propagation | `\|\| gate_rc=$?` pattern | WIRED | Recanary confirms gate exit propagates correctly through Snapshot A → BLOCK → reconcile → PASS → Snapshot B → deploy. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Bounded-decay cycle-table proof | `TestDocsisModeReplayCanary11::test_red_burst_18_cycles_explicit_table` | cycles 1-5 = 11.76M/11.52M/11.28M/11.04M/10.80M; cycles 6-18 = 10.80M (hold); floor_hit_cycles=0 across the window | PASS (Plan 201-14) |
| Anti-windup property suite | `tests/test_queue_controller.py` Plan 201-14 anti-windup tests | 20 passed | PASS |
| Red-decay validator boundary suite | `tests/test_autorate_config.py` + `tests/test_check_config.py` Plan 201-14 validator classes | 12 passed | PASS |
| SAFE-05 legacy byte-identity | Plan 201-14 SAFE-05 slice | 13 passed | PASS |
| Hot-path regression slice | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py tests/test_check_config.py -q` | 833 passed (Plan 201-14 verification) | PASS |
| `sustained_red_cycles` deliberately absent | `grep -n sustained_red_cycles src/wanctl/queue_controller.py src/wanctl/health_check.py` | no matches | PASS (intentional per Plan 201-13 / 201-14 rev-4 coordination) |
| Recanary verdict.json valid JSON with PASS verdict | `jq '.verdict' canary/20260505T122513Z/verdict.json` | `"pass"` | PASS |
| Live /health reports DOCSIS-mode active during recanary | Plan 201-15 spot-check | docsis_mode_active=true, setpoint_mbps=12.0, anti_windup_cycles=60, red_decay_step_pct=0.02, red_decay_delta_max_pct=0.10 | PASS |
| 24h soak floor-hit delta | `jq '.primary_gate.delta' soak/20260505T132736Z/soak-summary.json` | `0` | PASS |
| 24h soak suppression mean | `jq '.secondary_gate.value' soak/20260505T132736Z/soak-summary.json` | `6.466842364880155` (vs threshold 5.0) | FAIL — deferred to v1.43+ via operator Route B |

---

## Floor-Pegging Root Cause — RESOLVED

The original verification identified the dominant defect as multiplicative RED decay cascading current_rate from setpoint to floor in 6-8 cycles whenever the CMTS upstream queue refilled. Plan 201-14 replaced that path with a **bounded-absolute decay clamp** under DOCSIS mode:

**Before (multiplicative cascade):**
```python
if self.red_streak >= 1:
    self._yellow_decay_streak = 0
    return int(self.current_rate * self.factor_down)  # 0.90^N cascades to floor
```

**After (Plan 201-14, queue_controller.py:361-376):**
```python
if self.red_streak >= 1:
    self._yellow_decay_streak = 0
    if self._docsis_mode and self._setpoint_bps is not None:
        delta_max_bps = max(1, int(self._setpoint_bps * self._red_decay_delta_max_pct))
        clamp_bps = self._setpoint_bps - delta_max_bps
        if self.current_rate >= clamp_bps:
            # Bounded-absolute decay until clamp, then HOLD above floor.
            step_bps = max(1, int(self._setpoint_bps * self._red_decay_step_pct))
            return max(int(self.current_rate - step_bps), clamp_bps)
    return int(self.current_rate * self.factor_down)  # legacy preserved
```

With Spectrum's `setpoint_mbps=12`, `red_decay_step_pct=0.02`, `red_decay_delta_max_pct=0.10`:
- step_bps = 240,000 (240k)
- clamp_bps = 10,800,000 (10.8M, comfortably above 8M floor)
- cycles 1-5 step from 12M to 10.8M; cycles 6-18 hold at 10.8M

The validator at `autorate_config.py:546-555` and `check_config_validators.py:625-654` fails closed when `setpoint_mbps * (1 - red_decay_delta_max_pct) <= floor_mbps` (with floating-point tolerance), so the at-clamp hold is **safe by construction** — production cannot start with a configuration that would cascade to floor.

Integral anti-windup at `queue_controller.py:290-320` provides the recovery-from-stuck-EXHAUSTED path:
- when headroom has been EXHAUSTED for ≥ `anti_windup_cycles` (default 60),
- cap the integral window to `threshold - 1.0`,
- recompute `headroom_state` synchronously,
- increment a counter exposed via `/health`,
- rate-limit the log so it does not flood.

24h soak evidence: anti-windup trigger delta=0 — bounded decay alone was sufficient under saturated load and anti-windup never had to engage.

**Live evidence the fix held:**
- Recanary `20260505T122513Z`: 0 floor-hit cycles in 1022s loaded window (vs 1453 in the original FAILED canary)
- 24h soak `20260505T132736Z`: 0 floor-hit cycles across 84117 captured samples (~86400s)
- Diagnostic distributions: `red_streak.mean=0.006`, `red_streak.max=101`, `headroom_exhausted_samples=469/84117` (0.56%) — RED is rare and bounded when it does fire

The phase-goal control behavior is achieved.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| VALN-06 D-19 primary (canary + soak floor-hit) | ROADMAP Phase 201 SC#2-#4; REQUIREMENTS.md; `201-16-OPERATOR-APPROVAL-D19.md` | Spectrum UL saturation gate canary `floor_hit_cycles_total_delta=0` AND 24h soak `floor_hit_cycles_total_delta_soak_window=0` | SATISFIED | Recanary PASS + 24h soak primary PASS — both at zero |
| VALN-06 D-14 secondary (suppression watchdog) | ROADMAP Phase 201 SC#3 | 24h soak `ul_hysteresis_suppression_rate_per_60s_mean < 5.0` | DEFERRED to v1.43+ | Soak FAIL @ 6.467; operator Route B classifies as metric_semantics + recalibration on YELLOW-edge dwell-hold path, independent of bounded RED decay fix |
| VALN-06 schema portion | ROADMAP Phase 201 SC#1 | Schema accepts new keys, `setpoint_mbps` required when `docsis_mode=true`, byte-identical legacy fallback, Plan 201-14 cross-field validators | SATISFIED | Plan 201-03 + 201-14 SUMMARYs; tests collect; recanary deploy validated YAML loads |
| VALN-06 predeploy gate | ROADMAP Phase 201 SC#4 | Predeploy gate inspects /etc/wanctl/spectrum.yaml and reconciles or fails closed | SATISFIED | Plan 201-07 SUMMARY; recanary confirms first-run BLOCK + reconcile + second-run PASS path |
| VALN-06 docs | ROADMAP Phase 201 SC#5 | CHANGELOG.md and docs/CONFIGURATION.md migration note | SATISFIED | Plan 201-06 SUMMARY (D-12/DOCS-03 applied); Plan 201-14 documented rev-4 invariant wording and restart-required validator semantics |

VALN-06 closes on the D-19 primary gate (the dominant phase-goal proof); the D-14 secondary gate is the one remaining open item, deferred to v1.43+ via operator Route B.

---

## REVIEWS HIGH-Item Coverage (Refreshed)

All seven original HIGH items resolved at the artifact level. The original verification noted HIGH-5 and HIGH-7 were load-bearing during the canary FAIL; the recanary PASS path additionally validates:

- **HIGH-5 (cycle-fidelity counter)** continues to be the load-bearing gate; recanary delta=0 and 24h soak delta=0 prove the counter is the right contract.
- **HIGH-7 (binary + YAML rollback)** validated end-to-end via two-snapshot strategy on the recanary; PASS path skipped rollback execution but Snapshot A / Snapshot B verification is recorded.
- **MEDIUM-CODEX-3 (active-knob proof)** Plan 201-13 added live attribute echoes for `red_decay_step_pct` and `red_decay_delta_max_pct` so the recanary could prove constructor wiring without grepping YAML text.
- **HIGH-CODEX-1 / HIGH-CODEX-2 (rev-4 invariant)** Plan 201-14 implemented the codex-amended bounded-absolute decay with the rev-4 invariant comment in code (`queue_controller.py:368-373`).
- **NEW-HIGH-1 (two-snapshot rollback)** Plan 201-15 captured Snapshot A rollback-clean (count=0) before any reconcile and Snapshot B post-gate (count=5) only as deploy evidence.
- **NEW-HIGH-2 / NEW-HIGH-3 (verbatim soak script + $rows-bound jq)** Plan 201-16 implemented both; `soak-summary.json.secondary_gate.computation` documents the $rows-binding fix.
- **LOW-CODEX-5 (D-19 approval as distinct artifact)** `201-16-OPERATOR-APPROVAL-D19.md` exists as a separate artifact, not silently written into the verdict file.

---

## Pre-Deploy / Config-Schema Behavior

The recanary record again shows the predeploy gate first run BLOCKED on `target_bloat_ms` and `warn_bloat_ms` keys. Reconciliation by copy applied; second run PASS. This is **NOT a Phase 201 gap** — it is the SAFE-06 unknown-key warning + Phase 201 fail-closed gate together preventing production from running with stale/rejected config. Surface this as a SAFE-06 success.

---

## Anti-Patterns Found

None of the standard stub anti-patterns. Code is substantive, tests are not skip-stubs, /health is wired through real fields with the Plan 201-13 diagnostic extension, and the bounded-decay control logic is guarded by Plan 201-14 fail-closed validators.

The original verification's diagnostic gap (`max_delay_delta_us` not serialized; no per-cycle zone trace) is closed by Plan 201-13. The original control-model defect (multiplicative RED decay cascading to floor) is closed by Plan 201-14.

---

## Human Verification Required

See `human_verification` block in frontmatter. The original two items have been resolved:

1. ~~Operator decision on closure path~~ — **resolved 2026-05-06 as Route B (close `gaps_found`, defer D-14 to v1.43+)**.
2. ~~Cycle-level zone trace during a re-canary attempt~~ — **resolved by Plan 201-13** which added a 200-element bounded zone-trace deque to `/health.wans[].upload.zone_trace`; the recanary loaded capture and 24h soak capture both contain it.

One remaining item:

### 1. Plan 201-17 closeout authored — resolved 2026-05-06

**Test:** Author Plan 201-17 (gap closure) to refresh `CONTEXT.md`/`ROADMAP.md` marking Phase 201 `gaps_found` with explicit baton-pass to v1.43, write `201-RETRO.md`, and open the four v1.43 backlog items in priority order:

1. Fix metric semantics first: completed-window UL suppression counts + cause tags (dwell vs backlog) on `/health`, additive only.
2. Recalibrate D-14 against completed-window counts and a clean post-201-14 baseline soak.
3. Capture per-sample `load_rtt - baseline_rtt` distribution before any `target_bloat_ms` tune.
4. Conservative tuning candidates (`dwell_cycles: 5→4` or modest `target_bloat_ms` bump) only after items 1-3, with canary+soak+rollback gates.

**Expected:** Closeout artifacts committed; v1.43 milestone scoped with the four ordered work items.

**Why human:** Closeout planning shape is operator-authored; verifier can confirm artifacts exist after the planner produces them but cannot author the milestone-scoping decisions.

---

## Gaps Summary

The phase **delivered the artifacts AND achieved the dominant phase-goal control behavior**. Plan 201-13 added the `/health` diagnostic surface (8 additive fields including the previously-deferred `max_delay_delta_us`). Plan 201-14 replaced the multiplicative RED decay cascade-to-floor with a bounded-absolute decay clamp proven safe by construction via fail-closed validators. Plan 201-15 deployed v1.42.1 and the recanary `20260505T122513Z` PASSED with both floor-hit gates at zero. Plan 201-16 ran a 24h soak; the operator-approved D-19 primary floor-hit gate held at zero across 84117 samples.

The single remaining open item is the D-14 secondary suppression watchdog at 6.47/min vs `<5.0`. This is **not a control regression** — codex re-aggregation localized the FAIL to the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at `queue_controller.py:348`), independent of the RED-bounded-decay fix at `queue_controller.py:361-376`. The `<5/60s` threshold itself was inherited from Phase 200's qualitative framing and was never soak-calibrated against the post-Plan-201-14 control surface, and the underlying counter (`suppressions_per_min` at `queue_controller.py:649,668`) is a 60s-reset counter rather than a true rate, making the "mean of suppressions_per_min snapshots" framing semantically slippery. Operator Route B closes Phase 201 as `gaps_found` and defers the D-14 work to v1.43+ as ordered metric_semantics → recalibration → distribution → tuning items.

**Suggested closure direction (for `/gsd-plan-phase 201 --gaps`):** Plan 201-17 closeout — refresh `CONTEXT.md`/`ROADMAP.md`, write `201-RETRO.md`, and open the four v1.43 backlog items in priority order.

---

## 2026-05-06 Re-Verification Refresh — Promotions and Score Reconciliation

This refresh supersedes the previous verification dated 2026-05-06T13:40:36Z (whose frontmatter score `6/9` disagreed with the inline table `4/9` because the document had been edited piecemeal). Every truth row was re-walked against the live code and shipped evidence files.

**Promotions since the original 2026-05-04T23:57:07Z verification:**

| # | Original Status | New Status | Driver |
|---|----|----|----|
| 1 | VERIFIED | VERIFIED | unchanged |
| 2 | VERIFIED | VERIFIED | scope expanded by Plan 201-14 (red-decay/anti-windup keys + cross-field validators); still verified |
| 3 | VERIFIED | VERIFIED | scope expanded by Plan 201-14 (bounded-absolute RED decay + anti-windup helper); still verified, now also covers the original control-model defect |
| 4 | VERIFIED | VERIFIED | scope expanded by Plan 201-13 (8 additive diagnostic fields including `max_delay_delta_us`, `zone_trace`); still verified |
| 5 | VERIFIED | VERIFIED | unchanged; recanary re-validated end-to-end |
| 6 | **FAILED** | **VERIFIED** | Plan 201-15 recanary `20260505T122513Z` PASS (`primary_gate_value=0`, `ul_floor_hits_during_load=0`) |
| 7 | FAILED (never ran) | **FAILED (D-14 only)** | Plan 201-16 24h soak ran; D-19 primary PASS, D-14 secondary FAIL @ 6.467; deferred to v1.43+ via operator Route B |
| 8 | VERIFIED | VERIFIED | recanary two-snapshot strategy re-validated rollback target integrity |
| 9 | FAILED | **VERIFIED** | operator Route B decision recorded 2026-05-06 (close `gaps_found`, defer D-14 to v1.43+) |

**Sub-truths (originally listed in `gaps[*].missing` of the previous frontmatter) closed by Plans 201-13/14:**
- max_delay_delta_us /health serialization → Plan 201-13 ✓
- per-cycle zone trace → Plan 201-13 (zone_trace deque) ✓
- anti-collapse on RED branch → Plan 201-14 (bounded-absolute decay clamp) ✓
- integral anti-windup → Plan 201-14 (cap-and-clamp helper) ✓
- recovery from floor independent of green_streak → Plan 201-14 (bounded decay holds at clamp above floor; floor never reached) ✓

**Net score:** **8/9** (was disputed `6/9` frontmatter / `4/9` inline; both stale). Single remaining FAIL is Truth 7 D-14, classified by operator as metric_semantics + recalibration deferred to v1.43+.

---

_Verified: 2026-05-06T14:35:00Z (refresh; supersedes 2026-05-06T13:40:36Z)_
_Verifier: Claude (gsd-verifier)_
