---
phase: 201-docsis-aware-ul-congestion-control
plan: 14
type: tdd
wave: 10
depends_on: [13]
files_modified:
  - src/wanctl/queue_controller.py
  - src/wanctl/autorate_config.py
  - src/wanctl/check_config_validators.py
  - src/wanctl/wan_controller.py
  - configs/spectrum.yaml
  - tests/test_queue_controller.py
  - CHANGELOG.md
  - docs/CONFIGURATION.md
autonomous: true
gap_closure: true
requirements: [VALN-06]
tags: [phase-201, gap-closure, control-model, floor-anchor, push-down-clamp, anti-windup, tdd, docsis-gated]

must_haves:
  truths:
    - "When docsis_mode=true AND current_rate <= setpoint_bps, RED multiplicative decay is FLOOR-ANCHORED — not unconditional factor_down. The 12 Mbit -> 6.37 Mbit -> floor cascade observed in canary 20260504T231334Z is structurally impossible."
    - "Setpoint clamp on the push-DOWN boundary: when docsis_mode=true and current_rate >= setpoint_bps and the rate would otherwise decay below setpoint, the clamp prevents collapse below setpoint UNLESS there is sustained-RED escalation (multi-cycle), in which case decay is gentler than factor_down=0.90."
    - "BLOCKER 1 invariant: when zone=RED and docsis_mode=true, new_rate <= current_rate ALWAYS — the floor-anchor formula MUST NOT raise the rate when current_rate is already below setpoint. Below setpoint, the controller falls through to the legacy asymmetric factor_down decay path (which enforce_rate_bounds clamps at floor_red_bps). This preserves the CLAUDE.md architectural spine: 'Rate decreases are immediate. Rate increases require sustained healthy cycles.'"
    - "Integral anti-windup: when docsis_mode=true and headroom_state has been EXHAUSTED for >= anti_windup_cycles AND current_rate is at floor, the integral window is reset OR halved so the recovery path is not gated on a stuck signal."
    - "Asymmetry preserved: rate decreases remain immediate on the FIRST RED cycle (no relaxation). The floor-anchor only applies to SUSTAINED RED at-or-above setpoint. Recovery still requires green_streak >= green_required (no relaxation of push-up gate)."
    - "All three changes are docsis_mode-gated: when docsis_mode=false, every code path returns the SAME value as before this plan (byte-identical legacy behavior). No link-type Python branching introduced — all gating is on `self._docsis_mode` (already YAML-driven)."
    - "Flash-wear protection preserved: last_applied_ul_rate dedup is upstream of QueueController (in WANController); this plan changes only QueueController.adjust() return values, so dedup semantics are unchanged."
    - "Replay against the 201-11 canary loaded_capture.ndjson zone sequence (or a CALIBRATED synthetic equivalent that demonstrates pre-fix cascade below floor) shows floor_hit_cycles=0 over a 1000-cycle RED-pulsing window at setpoint=12 Mbit post-fix."
  artifacts:
    - path: src/wanctl/queue_controller.py
      provides: "Floor-anchored RED decay (two-regime: at/above setpoint vs below setpoint) + push-down setpoint clamp + integral anti-windup, all docsis_mode-gated"
      contains: "_compute_red_rate_docsis"
    - path: tests/test_queue_controller.py
      provides: "TestDocsisModeFloorAnchor + TestDocsisModePushDownClamp + TestDocsisModeIntegralAntiWindup + TestDocsisModeReplayCanary11"
      contains: "TestDocsisModeFloorAnchor"
  key_links:
    - from: "src/wanctl/queue_controller.py:_compute_rate_3state RED branch"
      to: "self._docsis_mode + self._setpoint_bps + self.floor_red_bps"
      via: "if self._docsis_mode and self._setpoint_bps is not None and self.current_rate >= self._setpoint_bps and self.red_streak < self._sustained_red_cycles: floor-anchored decay; else fall through to legacy asymmetric factor_down"
      pattern: "_docsis_mode.*setpoint_bps.*current_rate"
    - from: "src/wanctl/queue_controller.py:_update_integral"
      to: "self._headroom_exhausted_streak counter (new)"
      via: "anti-windup reset when streak >= threshold and current_rate at floor"
      pattern: "_headroom_exhausted_streak"
---

<objective>
**Gap-closure Plan 2 of 4. PRIMARY DEFECT FIX.** This is the control-model amendment that closes the 1453-cycle floor-peg gap from canary 20260504T231334Z. Per VERIFICATION.md root-cause analysis (lines 140-188): the failure mechanism is `RED multiplicative decay drives current_rate to floor in 6-8 cycles` because (a) `factor_down=0.90` cascades unconditionally, (b) the existing setpoint clamp only governs push-up not push-down, and (c) the integral remains EXHAUSTED throughout the loaded window with no anti-windup. All three are inside `_compute_rate_3state` and `_update_integral`.

This plan implements the operator-confirmed closure direction (path b — control-model amendment, NOT setpoint=10 workaround). Three coordinated, docsis_mode-gated changes:

1. **Floor-anchored RED decay AT-OR-ABOVE setpoint.** When `docsis_mode=true` AND `current_rate >= setpoint_bps` AND `red_streak < sustained_red_cycles`, the RED branch must NOT cascade multiplicatively to floor. Apply a gentler step (subtract a small absolute step, e.g. `int(setpoint_bps * 0.02)` per cycle, clamped at setpoint as a soft floor) so the controller can hold near setpoint under sustained RED instead of collapsing.

   **BLOCKER 1 invariant (added in revision):** When `current_rate < setpoint_bps`, the floor-anchor MUST NOT engage — its `max(decayed, setpoint_bps)` formula would otherwise RAISE the rate, violating the CLAUDE.md architectural spine ("Rate decreases are immediate. Rate increases require sustained healthy cycles."). Below setpoint, fall through to the legacy `factor_down` decay path; `enforce_rate_bounds` already clamps at `floor_red_bps`. Approach (b) from plan-checker review: two-regime branching, preserves asymmetry on both sides.

2. **Push-down setpoint clamp.** Inherent in the floor-anchor formula above: when `current_rate >= setpoint_bps` and the small-step decay would fall below setpoint, the `max(..., setpoint_bps)` clamps to setpoint. This makes setpoint a soft floor for short RED bursts (the mechanism that pegged the canary) and only allows below-setpoint decay under multi-cycle sustained RED escalation (the original safety intent).

3. **Integral anti-windup.** Track `_headroom_exhausted_streak`. When `docsis_mode=true` AND streak >= `anti_windup_cycles` (default 60 = 3s @ 50ms) AND `current_rate == floor_red_bps`, halve the integral window so a single GREEN cycle isn't fighting a 30-155 ms·s buildup. Mirrors the asymmetric-recovery rule the controller already uses. Anti-windup engagement surfaces via a `/health.wans[0].upload.anti_windup_triggers` counter (Plan 201-13 owns the field; this plan owns the counter increment).

**TDD because:** the I/O is fully specifiable. Test inputs: zone sequence, current_rate, headroom_state, setpoint_bps, factor_down, floor_red_bps. Expected outputs: new_rate. The 201-11 canary capture is itself a regression corpus — feed a CALIBRATED RED-pulsing pattern (bursts long enough to demonstrate pre-fix cascade below floor) through the controller and assert floor_hit_cycles=0 post-fix.

**Asymmetry preservation:** the existing `factor_down=0.90` immediate-on-first-RED behavior is preserved when `current_rate > setpoint_bps` (above setpoint, multiplicative decay above the soft-floor threshold) AND when `current_rate < setpoint_bps` (below setpoint, the controller is already in the headroom regime — multiplicative decay continues, clamped at floor_red_bps by enforce_rate_bounds). The new behavior ONLY engages AT-OR-ABOVE setpoint with red_streak < sustained_red_cycles.

**No link-type branching:** every new code path is gated on `self._docsis_mode` and the YAML keys `setpoint_mbps`, `sustained_red_cycles`, `anti_windup_cycles`. Non-docsis_mode deployments are byte-identical (CLAUDE.md NON-NEGOTIABLE). The new YAML keys go through the existing `KNOWN_AUTORATE_PATHS` registry and have safe defaults so they're optional.

**Output:** ~30-50 lines of new code in queue_controller.py, 4 new test classes in test_queue_controller.py, two new YAML keys (`sustained_red_cycles`, `anti_windup_cycles`) registered in autorate_config.py + check_config_validators.py, configs/spectrum.yaml updated with explicit values, CHANGELOG.md and docs/CONFIGURATION.md updated.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json
@src/wanctl/queue_controller.py
@configs/spectrum.yaml
@./CLAUDE.md
</context>

<interfaces>
<!-- Existing patterns to mirror VERBATIM. -->

`_compute_rate_3state(zone)` (queue_controller.py:299-340) — current shape:
```python
def _compute_rate_3state(self, zone: str) -> int:
    if self.red_streak >= 1:
        self._yellow_decay_streak = 0
        return int(self.current_rate * self.factor_down)  # <-- DEFECT SITE: unconditional multiplicative decay
    if self.green_streak >= self.green_required:
        ...  # push-up clamp (already correct)
    if zone == "YELLOW":
        ...  # YELLOW decay (already correct)
    self._yellow_decay_streak = 0
    return self.current_rate
```

`_update_integral(delta_ms)` (queue_controller.py:241-256) — current shape:
```python
def _update_integral(self, delta_ms: float) -> tuple[float, str]:
    self._integral_window.append(max(0.0, float(delta_ms)))
    integral_ms_s = sum(self._integral_window) * 0.05
    self._last_integral_ms_s = integral_ms_s
    if len(self._integral_window) < (self._integral_window.maxlen or 0):
        return integral_ms_s, "EXHAUSTED"
    if integral_ms_s <= self._integral_threshold_ms_s:
        return integral_ms_s, "AVAILABLE"
    return integral_ms_s, "EXHAUSTED"
```

YAML key registration: `src/wanctl/check_config_validators.py:KNOWN_AUTORATE_PATHS` — every new key MUST be added, otherwise SAFE-06 unknown-key warning fires (CONTEXT.md D-06).

YAML schema: `src/wanctl/autorate_config.py` — D-08 keeps these as restart-required (NOT live-tunable via SIGUSR1).

Constructor pattern: keyword-only with safe default = no behavior change. See queue_controller.py:47-52 (existing Phase 201 keys all follow this).

Per-key explicit-presence flag pattern (Phase 200 D-03): `wan_controller.py:_setpoint_mbps_explicit` (line 471). Mirror for the new keys (`_sustained_red_cycles_explicit`, `_anti_windup_cycles_explicit`) — but note that since the new keys have safe defaults that preserve existing Phase 201 behavior even when present, the explicit flag is for telemetry only, not gating.

DOCSIS-mode gate idiom: `if self._docsis_mode and self._setpoint_bps is not None:` (used 3 times already in queue_controller.py at lines 125, 311, 317). Mirror exactly.
</interfaces>

<tdd_cycle>
This plan is pure RED→GREEN→REFACTOR. The test file is the spec. Write failing tests first (RED commit), then implement (GREEN commit), then clean up only if needed (REFACTOR commit).

**Replay corpus (BLOCKER 3 fix — calibrated cascade arithmetic):** the canary 201-11 loaded_capture.ndjson saw 1453 floor cycles in 1022s of loaded window at 50ms cadence (≈7% of cycles AT floor, sustained), with 1Hz secondary observing 84 floor samples (avg dwell ≥0.5s per excursion). Reproducing this as a unit-test corpus requires RED bursts long enough that the pre-fix `factor_down=0.90` decay cascades BELOW floor=8M from setpoint=12M:

```
Pre-fix arithmetic (must demonstrate cascade BELOW floor):
  RED_BURST_CYCLES = 18
  12_000_000 * (0.9 ** 18) = 1_801_135 bps  ≈ 1.80 Mbit
  1.80 Mbit < floor_red_bps = 8_000_000  →  sustained floor residence

Post-fix arithmetic (must NOT cascade — floor-anchor at setpoint, plus below-setpoint
factor_down clamped at floor_red_bps by enforce_rate_bounds):
  Cycle 1 (red_streak=1 < 8, current_rate=12_000_000 == setpoint):
    step = max(1, int(12_000_000 * 0.02)) = 240_000
    new_rate = max(12_000_000 - 240_000, 12_000_000) = 12_000_000  (clamped to setpoint)
  Cycles 2-7 (red_streak < 8, current_rate stays at setpoint): same → holds at 12_000_000
  Cycle 8 (red_streak == sustained_red_cycles=8, fall through to factor_down):
    new_rate = int(12_000_000 * 0.9) = 10_800_000  (still above floor)
  Cycle 9 (red_streak=9, current_rate=10_800_000 < setpoint, fall through to factor_down):
    new_rate = int(10_800_000 * 0.9) = 9_720_000
  Continued: descent reaches floor only after another ~2-3 cycles, at which point
  enforce_rate_bounds clamps. floor_hit_cycles delta is bounded — but the synthetic
  test corpus relaxes RED before that depth (RED_BURST_CYCLES=18, GREEN recovery follows),
  so floor_hit_cycles_total_delta == 0 over the post-fix run.
```

The `TestDocsisModeReplayCanary11` test class (Task 1) MUST use bursts of this calibrated length, not the original 5-cycle bursts. The original 5-cycle synthetic pattern (`12 * 0.9^5 = 7.08 Mbit`) does NOT cascade below floor=8M and therefore does not exercise the 201-11 failure mode. Pre-fix arithmetic comments must accompany the test constants.
</tdd_cycle>

<feature>
  <name>Floor-anchored RED decay at-or-above setpoint (docsis_mode-gated, two-regime)</name>
  <files>src/wanctl/queue_controller.py, tests/test_queue_controller.py</files>
  <behavior>
    Two-regime RED-branch behavior under `docsis_mode=true`:

    REGIME A — current_rate >= setpoint_bps AND red_streak < sustained_red_cycles:
      - Floor-anchored: new_rate = max(int(self.current_rate - max(1, int(self._setpoint_bps * 0.02))), self._setpoint_bps)
      - i.e. take a tiny step (240_000 bps for setpoint=12M) but clamp at setpoint as a soft floor.
      - INVARIANT: new_rate <= current_rate (small_step subtraction shrinks; max(..., setpoint_bps) cannot exceed current_rate because current_rate >= setpoint_bps).

    REGIME B — current_rate < setpoint_bps (any red_streak) OR red_streak >= sustained_red_cycles:
      - Fall through to legacy asymmetric decay: new_rate = int(self.current_rate * self.factor_down)
      - enforce_rate_bounds (called downstream in adjust()) clamps at floor_red_bps.
      - INVARIANT: new_rate <= current_rate (factor_down=0.9 < 1.0 always shrinks).

    REGIME C — docsis_mode=false (any state):
      - new_rate = int(self.current_rate * self.factor_down) — BYTE-IDENTICAL to current behavior.

    Combined invariant (BLOCKER 1): when zone=RED, new_rate <= current_rate ALWAYS in every regime. The floor-anchor never raises the rate; this is verified by an explicit regression test.
  </behavior>
  <implementation>
    1. Add YAML key `sustained_red_cycles: int = 8` to QueueController.__init__ (keyword-only, default 8). Register in KNOWN_AUTORATE_PATHS as `continuous_monitoring.upload.sustained_red_cycles`. Add to autorate_config.py schema.
    2. Add to configs/spectrum.yaml: `sustained_red_cycles: 8` under `continuous_monitoring.upload:` (with comment explaining the 8-cycle = 400ms threshold).
    3. Refactor RED branch in `_compute_rate_3state` using approach (b) from plan-checker review — two-regime branching that preserves the asymmetric model in BOTH the at-or-above-setpoint regime and the below-setpoint regime:
       ```python
       if self.red_streak >= 1:
           self._yellow_decay_streak = 0
           if (
               self._docsis_mode
               and self._setpoint_bps is not None
               and self.current_rate >= self._setpoint_bps
               and self.red_streak < self._sustained_red_cycles
           ):
               # REGIME A: floor-anchored decay AT-OR-ABOVE setpoint.
               # Tiny step, clamped at setpoint as soft floor.
               # Prevents 12->6.37 cascade observed in canary 20260504T231334Z.
               # BLOCKER 1 invariant: current_rate >= setpoint_bps guarantees
               # max(current_rate - step, setpoint_bps) <= current_rate.
               step = max(1, int(self._setpoint_bps * 0.02))
               return max(int(self.current_rate - step), self._setpoint_bps)
           # REGIME B (current_rate < setpoint_bps OR red_streak >= sustained_red_cycles)
           # AND REGIME C (docsis_mode=false): legacy asymmetric decay.
           # enforce_rate_bounds clamps at floor_red_bps downstream.
           return int(self.current_rate * self.factor_down)
       ```

    Note the changed condition: `self.current_rate >= self._setpoint_bps` (BLOCKER 1 fix; was `<=` in the prior revision). The semantics are: floor-anchor engages when the controller is AT-OR-ABOVE setpoint and RED has not been sustained long enough to escalate to factor_down. Below setpoint, the controller is already in the headroom regime where multiplicative decay is the correct response (and floor_red_bps is the safety net).
  </implementation>
</feature>

<feature>
  <name>Integral anti-windup (docsis_mode-gated)</name>
  <files>src/wanctl/queue_controller.py, tests/test_queue_controller.py</files>
  <behavior>
    Track `self._headroom_exhausted_streak: int` — incremented every cycle `_update_integral` returns "EXHAUSTED", reset to 0 every cycle it returns "AVAILABLE".

    When `docsis_mode=true` AND `_headroom_exhausted_streak >= anti_windup_cycles` (default 60 = 3s) AND `current_rate == floor_red_bps`:
      - Halve every entry in `self._integral_window` (so future samples have a fighting chance to drop below threshold).
      - Reset `self._headroom_exhausted_streak = 0` after the halve so we don't immediately re-trigger.
      - Increment `self._anti_windup_triggers` counter (exposed via Plan 201-13 /health diagnostic block — see WARNING 6 absorption: counter is preferable to log spam under sustained engagement).
      - Log at INFO once per trigger: `"[ANTI-WINDUP] %s integral halved after %d EXHAUSTED cycles at floor"` % (self.name, anti_windup_cycles).

    When `docsis_mode=false`: streak is still computed (cheap) but never triggers the halve (gated on docsis_mode).
  </behavior>
  <implementation>
    1. Add YAML key `anti_windup_cycles: int = 60` to QueueController.__init__ (keyword-only, default 60). Register in KNOWN_AUTORATE_PATHS. Add to autorate_config.py schema.
    2. Add to configs/spectrum.yaml: `anti_windup_cycles: 60` under `continuous_monitoring.upload:`.
    3. Init `self._headroom_exhausted_streak: int = 0` and `self._anti_windup_triggers: int = 0` alongside `self.floor_hit_cycles` in __init__.
    4. Modify `_update_integral` to bump/reset streak based on the returned state:
       ```python
       _, state = ...  # existing logic
       if state == "EXHAUSTED":
           self._headroom_exhausted_streak += 1
       else:
           self._headroom_exhausted_streak = 0
       ```
    5. Add an `_apply_anti_windup_if_needed()` helper called once per cycle from `adjust()` AFTER `_update_integral` and BEFORE `_classify_zone_3state`:
       ```python
       def _apply_anti_windup_if_needed(self) -> None:
           if not self._docsis_mode:
               return
           if self._headroom_exhausted_streak < self._anti_windup_cycles:
               return
           if self.current_rate != self.floor_red_bps:
               return
           # Halve all integral samples
           halved = [s * 0.5 for s in self._integral_window]
           self._integral_window.clear()
           for s in halved:
               self._integral_window.append(s)
           self._headroom_exhausted_streak = 0
           self._anti_windup_triggers += 1
           self._last_integral_ms_s = sum(self._integral_window) * 0.05
           self._logger.info(
               "[ANTI-WINDUP] %s integral halved after %d EXHAUSTED cycles at floor",
               self.name, self._anti_windup_cycles,
           )
       ```
  </implementation>
</feature>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (RED): Write failing tests for floor-anchor + push-down clamp + anti-windup + canary-11 calibrated replay + BLOCKER 1 regression</name>
  <read_first>
    - tests/test_queue_controller.py (TestDocsisModeIntegralClassifier, TestDocsisModeSetpointClamp, TestDocsisModeCakeCorroborator at lines 3517-3650 — fixture and helper patterns)
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json (1453 floor cycles over 1022s loaded window)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md (Floor-Pegging Root Cause Analysis section, lines 140-188)
    - src/wanctl/queue_controller.py (current _compute_rate_3state and _update_integral)
  </read_first>
  <files>tests/test_queue_controller.py</files>
  <action>
    Add four new test classes AFTER `TestDocsisModeCakeCorroborator`:

    **`TestDocsisModeFloorAnchor`** (covers floor-anchored RED decay):
      - test_red_decay_at_setpoint_holds: docsis_mode=true, setpoint_bps=12_000_000, current_rate=12_000_000 (== setpoint), simulate 7 consecutive RED cycles (red_streak goes 1..7, all below sustained_red_cycles=8), assert current_rate stays >= setpoint_bps after each cycle (clamped to setpoint as soft floor — the at-setpoint case of REGIME A).
      - test_red_decay_above_setpoint_takes_small_step: docsis_mode=true, setpoint_bps=12_000_000, current_rate=15_000_000 (above setpoint), red_streak=1, assert new_rate == 15_000_000 - 240_000 == 14_760_000 (REGIME A: small-step decay applied because current_rate >= setpoint).
      - test_red_decay_below_setpoint_legacy_path: docsis_mode=true, setpoint_bps=12_000_000, current_rate=10_000_000 (below setpoint), red_streak=1, assert new_rate == int(10_000_000 * factor_down) == 9_000_000 (REGIME B: falls through to legacy asymmetric decay; floor-anchor does NOT engage below setpoint — BLOCKER 1 fix).
      - test_red_decay_legacy_mode_unchanged: docsis_mode=false, current_rate=12_000_000, red_streak=1, assert new_rate == int(12_000_000 * factor_down) (REGIME C: BYTE-IDENTICAL legacy).
      - test_sustained_red_engages_factor_down: docsis_mode=true, setpoint_bps=12_000_000, current_rate=12_000_000, red_streak=8 (== sustained_red_cycles), assert new_rate == int(12_000_000 * factor_down) (REGIME B trigger via sustained-red threshold; original multiplicative decay re-engages).
      - test_floor_anchor_clamps_at_floor: docsis_mode=true, setpoint_bps=12_000_000, floor_red_bps=8_000_000, current_rate=8_500_000 (already below setpoint, near floor), red_streak=2, simulate adjust() flow including enforce_rate_bounds; assert new_rate >= floor_red_bps (no below-floor decay; REGIME B + enforce_rate_bounds clamp).

    **`TestDocsisModePushDownClamp`** (covers the push-down setpoint clamp explicitly + BLOCKER 1 regression):
      - test_first_red_cycle_at_setpoint_holds: docsis_mode=true, setpoint_bps=12_000_000, current_rate=12_000_000, red_streak=1, assert new_rate == 12_000_000 (small_step=240_000 brings it to 11_760_000 then clamps back UP to setpoint per max(decayed, setpoint)).
      - test_first_red_cycle_above_setpoint_decays_normally: docsis_mode=true, setpoint_bps=12_000_000, current_rate=15_000_000, red_streak=1, assert new_rate == 14_760_000 (REGIME A small-step, not factor_down).
      - **test_red_below_setpoint_does_not_increase_rate (BLOCKER 1 regression):** Reproduce the BLOCKER 1 trace from plan-checker review. Construct a QueueController with docsis_mode=true, setpoint_bps=12_000_000, floor_red_bps=8_000_000, current_rate=8_500_000 (just above floor, below setpoint), red_streak=2 (< sustained_red_cycles=8), zone=RED. Call `_compute_rate_3state("RED")`. Assert `new_rate <= 8_500_000` (must NOT increase to setpoint=12M). This test MUST FAIL against a buggy formula `max(current_rate - step, setpoint_bps)` and PASS against the corrected formula `current_rate >= setpoint_bps`-gated.

    **`TestDocsisModeIntegralAntiWindup`** (covers integral anti-windup):
      - test_headroom_exhausted_streak_increments: docsis_mode=true, feed 70 saturated samples (delta=50ms each), assert ctrl._headroom_exhausted_streak >= 60.
      - test_headroom_exhausted_streak_resets_on_available: docsis_mode=true, feed 30 saturated then 30 idle (delta=0), assert ctrl._headroom_exhausted_streak == 0 (or close to 0; reset on first AVAILABLE).
      - test_anti_windup_halves_integral_at_floor: docsis_mode=true, ctrl.current_rate = ctrl.floor_red_bps, feed enough saturated samples to fill integral_window with values >= 30 ms·s and accumulate streak >= 60. After calling adjust() once with cake_snapshot=None, assert that ctrl._last_integral_ms_s is approximately HALF of the pre-trigger value AND ctrl._anti_windup_triggers == 1.
      - test_anti_windup_does_not_fire_above_floor: docsis_mode=true, ctrl.current_rate = ctrl.floor_red_bps + 100_000, accumulate streak >= 60 EXHAUSTED, assert _last_integral_ms_s does NOT halve AND _anti_windup_triggers == 0.
      - test_anti_windup_legacy_mode_no_op: docsis_mode=false, accumulate any streak, assert no halve fires (integral unchanged) AND _anti_windup_triggers == 0.

    **`TestDocsisModeReplayCanary11`** (calibrated synthetic replay of the 201-11 RED-pulsing pattern — BLOCKER 3 fix):
      - test_red_pulse_cycle_does_not_floor_peg: docsis_mode=true, setpoint_bps=12_000_000, floor_red_bps=8_000_000, ceiling_bps=18_000_000. Simulate the calibrated canary pattern:
        ```python
        # BLOCKER 3 calibrated cascade arithmetic:
        # Pre-fix: 12_000_000 * (0.9 ** RED_BURST_CYCLES) = 1.80 Mbit
        # 1.80 Mbit < floor_red_bps = 8_000_000 -> sustained floor residence (PRE-FIX FAILURE MODE)
        # Post-fix: rate holds at setpoint during burst (REGIME A clamp); recovery before floor
        RED_BURST_CYCLES = 18    # demonstrably cascades pre-fix
        RECOVERY_CYCLES = 35     # > sustained-healthy threshold; ensures clean recovery
        ```
        Repeat (RED for 18 cycles, then YELLOW-to-GREEN for 35 cycles) for 1000 total cycles. Construct delta_ms per cycle that produces this zone sequence. Assert floor_hit_cycles == 0 over the entire 1000-cycle window POST-FIX. (Pre-fix, this test would FAIL with floor_hit_cycles > 0 because the 18-cycle RED bursts cascade below floor; post-fix, REGIME A holds at setpoint during the burst, then REGIME B engages briefly at red_streak >= 8 but recovery happens before floor.)
      - test_sustained_red_does_descend: same setup, but feed 50 consecutive RED cycles (no relaxation), assert current_rate descends below setpoint at red_streak >= sustained_red_cycles=8 (i.e. REGIME B engages); the fix does NOT prevent ALL descent, only short-burst cascades. Assert floor_hit_cycles may be > 0 in this purely-sustained-overload case (operator's safety intent for true overload preserved).

      Add a comment in the test class header showing the cascade arithmetic verbatim:
        ```python
        # Calibrated against canary 20260504T231334Z (1453 floor cycles in 1022s loaded window
        # ≈ 7% of cycles AT floor at 50ms cadence; 1Hz secondary saw 84 floor samples,
        # avg dwell ≥0.5s per excursion).
        # Pre-fix cascade arithmetic:
        #   12_000_000 * (0.9 ** 18) = 1_801_135 bps (1.80 Mbit) << floor_red_bps=8M
        # Post-fix arithmetic: REGIME A holds at setpoint=12M during burst;
        # REGIME B engages at red_streak >= sustained_red_cycles=8 if RED continues;
        # enforce_rate_bounds clamps at floor_red_bps in REGIME B.
        ```

    All tests must FAIL before Task 2 lands. This is the RED step of TDD. Run pytest and confirm failures, then commit with message `test(201-14): add failing tests for floor-anchor + anti-windup + calibrated canary-11 replay + BLOCKER 1 regression`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeFloorAnchor tests/test_queue_controller.py::TestDocsisModePushDownClamp tests/test_queue_controller.py::TestDocsisModeIntegralAntiWindup tests/test_queue_controller.py::TestDocsisModeReplayCanary11 -v 2>&1 | grep -E 'failed|FAILED' | wc -l | grep -qE '^[1-9][0-9]*$'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "class TestDocsisModeFloorAnchor:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModePushDownClamp:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModeIntegralAntiWindup:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModeReplayCanary11:" tests/test_queue_controller.py` == 1
    - `grep -q "test_red_below_setpoint_does_not_increase_rate" tests/test_queue_controller.py` (BLOCKER 1 regression test present)
    - `grep -q "RED_BURST_CYCLES = 18" tests/test_queue_controller.py` (BLOCKER 3 calibrated cascade burst sizing present)
    - Total test count across the four classes >= 15 (6+3+5+2 with BLOCKER 1 regression added)
    - At least 10 of the 15 tests FAIL when run against the pre-implementation queue_controller.py (RED step)
    - Existing test_queue_controller.py tests still PASS (no regression from test additions alone)
  </acceptance_criteria>
  <done>
    Four test classes exist, >= 15 tests total, majority fail because the implementation hasn't landed yet. Commit recorded.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (GREEN): Implement floor-anchor + push-down clamp + anti-windup with BLOCKER 1 corrected condition; register YAML keys</name>
  <read_first>
    - src/wanctl/queue_controller.py (Task 1 tests now exist and FAIL)
    - src/wanctl/autorate_config.py (lines 182-194, threshold ordering pattern)
    - src/wanctl/check_config_validators.py (lines 28-180, KNOWN_AUTORATE_PATHS registry)
    - src/wanctl/wan_controller.py:402-437 (UL QueueController constructor wiring; mirror per-key explicit-presence pattern)
    - configs/spectrum.yaml (lines 67-89, current Phase 201 block)
  </read_first>
  <files>src/wanctl/queue_controller.py, src/wanctl/autorate_config.py, src/wanctl/check_config_validators.py, src/wanctl/wan_controller.py, configs/spectrum.yaml</files>
  <action>
    Implement the three control-model changes. Goal: make all Task 1 tests PASS without breaking any existing test.

    1. **queue_controller.py** — add two keyword-only constructor params with safe defaults:
       ```python
       sustained_red_cycles: int = 8,
       anti_windup_cycles: int = 60,
       ```
       Store as `self._sustained_red_cycles` and `self._anti_windup_cycles`. Init `self._headroom_exhausted_streak: int = 0` and `self._anti_windup_triggers: int = 0` alongside `self.floor_hit_cycles`.

    2. **queue_controller.py:_update_integral** — at the end (before each return), update the streak. Two-line addition:
       ```python
       if state_returned == "EXHAUSTED":
           self._headroom_exhausted_streak += 1
       else:
           self._headroom_exhausted_streak = 0
       ```
       (Refactor the function so it computes `state` once, updates the streak, then returns.)

    3. **queue_controller.py:_compute_rate_3state RED branch** — replace the unconditional `return int(self.current_rate * self.factor_down)` with the BLOCKER 1-corrected variant (approach b: two-regime, gated on `>= setpoint_bps`):
       ```python
       if self.red_streak >= 1:
           self._yellow_decay_streak = 0
           if (
               self._docsis_mode
               and self._setpoint_bps is not None
               and self.current_rate >= self._setpoint_bps
               and self.red_streak < self._sustained_red_cycles
           ):
               # REGIME A: floor-anchored decay AT-OR-ABOVE setpoint.
               # BLOCKER 1 invariant: current_rate >= setpoint_bps guarantees
               # max(current_rate - step, setpoint_bps) <= current_rate (no rate increase).
               step = max(1, int(self._setpoint_bps * 0.02))
               return max(int(self.current_rate - step), self._setpoint_bps)
           # REGIME B (below setpoint OR sustained RED) AND REGIME C (legacy):
           # legacy asymmetric decay; enforce_rate_bounds clamps at floor_red_bps downstream.
           return int(self.current_rate * self.factor_down)
       ```

       **Verify the condition is `>=` not `<=`.** This is the BLOCKER 1 fix from plan-checker review. The prior plan had `<=`, which raised the rate from 8.5M to 12M on a single RED cycle below setpoint — violating CLAUDE.md spine.

    4. **queue_controller.py:_apply_anti_windup_if_needed** — add helper as specified in <feature> above. Call from `adjust()` AFTER the `_update_integral` line and BEFORE `_classify_zone_3state` (i.e. between current line 159 and current line 161). Wrap call in `if self._docsis_mode:` to skip the no-op early in legacy mode. Increment `self._anti_windup_triggers` counter inside the helper before logging.

    5. **WARNING 4 absorption — health diagnostic fields move to Plan 201-13.** This plan does NOT add `headroom_exhausted_streak`, `sustained_red_cycles`, `anti_windup_cycles`, or `anti_windup_triggers` to `get_health_data()`. Plan 201-13 owns the /health diagnostic surface and will add these four fields in its own task. This plan is responsible only for the controller-side counters; serialization is Plan 201-13's responsibility.

    6. **autorate_config.py** — add `sustained_red_cycles` and `anti_windup_cycles` to the upload schema. Both are int-only with safe defaults; they do NOT participate in the existing threshold ordering check. Add per-key explicit-presence flags following the Phase 200 D-03 / Phase 201 setpoint_mbps pattern.

    7. **check_config_validators.py** — add to `KNOWN_AUTORATE_PATHS`:
       ```python
       "continuous_monitoring.upload.sustained_red_cycles",
       "continuous_monitoring.upload.anti_windup_cycles",
       ```

    8. **wan_controller.py** — wire the two new config values into the upload QueueController constructor at lines 402-437:
       ```python
       sustained_red_cycles=int(getattr(config, "sustained_red_cycles", 8)),
       anti_windup_cycles=int(getattr(config, "anti_windup_cycles", 60)),
       ```
       Plus the explicit-presence flags `self._sustained_red_cycles_explicit` and `self._anti_windup_cycles_explicit` for telemetry symmetry (mirroring `_setpoint_mbps_explicit` at line 471).

    9. **configs/spectrum.yaml** — under `continuous_monitoring.upload:`, alongside the existing Phase 201 keys, add:
       ```yaml
           # Phase 201 gap-closure (control-model amendment, post-canary-fail 20260504T231334Z):
           # 8 cycles = 400ms; below this, RED decay is floor-anchored at setpoint
           # (prevents 12->6.37 multiplicative cascade). At/above 8, factor_down re-engages.
           sustained_red_cycles: 8
           # 60 cycles = 3s; halve integral when EXHAUSTED-at-floor that long.
           # Prevents the 30-155 ms*s windup observed in canary 20260504T231334Z from
           # locking the recovery gate closed for the entire load window.
           anti_windup_cycles: 60
       ```

    10. Run pytest. All 15+ Task 1 tests must now PASS, including the BLOCKER 1 regression test `test_red_below_setpoint_does_not_increase_rate`. Commit with message `feat(201-14): add docsis_mode floor-anchor (>=setpoint) + anti-windup + push-down clamp`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeFloorAnchor tests/test_queue_controller.py::TestDocsisModePushDownClamp tests/test_queue_controller.py::TestDocsisModeIntegralAntiWindup tests/test_queue_controller.py::TestDocsisModeReplayCanary11 -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModePushDownClamp::test_red_below_setpoint_does_not_increase_rate -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py -q</automated>
    <automated>.venv/bin/ruff check src/wanctl/queue_controller.py src/wanctl/autorate_config.py src/wanctl/check_config_validators.py src/wanctl/wan_controller.py</automated>
    <automated>.venv/bin/mypy src/wanctl/queue_controller.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "sustained_red_cycles: int = 8" src/wanctl/queue_controller.py`
    - `grep -q "anti_windup_cycles: int = 60" src/wanctl/queue_controller.py`
    - `grep -q "self._headroom_exhausted_streak" src/wanctl/queue_controller.py`
    - `grep -q "self._anti_windup_triggers" src/wanctl/queue_controller.py`
    - `grep -q "_apply_anti_windup_if_needed" src/wanctl/queue_controller.py`
    - **BLOCKER 1 fix verification:** `grep -E "self\.current_rate >= self\._setpoint_bps" src/wanctl/queue_controller.py` returns at least one hit AND `grep -E "self\.current_rate <= self\._setpoint_bps.*sustained_red_cycles" src/wanctl/queue_controller.py | grep -v '^#'` returns ZERO hits (the buggy `<=` formulation must NOT be present).
    - `grep -q "self.red_streak < self._sustained_red_cycles" src/wanctl/queue_controller.py`
    - `grep -q "continuous_monitoring.upload.sustained_red_cycles" src/wanctl/check_config_validators.py`
    - `grep -q "continuous_monitoring.upload.anti_windup_cycles" src/wanctl/check_config_validators.py`
    - `grep -q "sustained_red_cycles: 8" configs/spectrum.yaml`
    - `grep -q "anti_windup_cycles: 60" configs/spectrum.yaml`
    - All 4 new test classes pass: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeFloorAnchor tests/test_queue_controller.py::TestDocsisModePushDownClamp tests/test_queue_controller.py::TestDocsisModeIntegralAntiWindup tests/test_queue_controller.py::TestDocsisModeReplayCanary11 -v` exits 0
    - BLOCKER 1 regression specifically passes: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModePushDownClamp::test_red_below_setpoint_does_not_increase_rate -v` exits 0
    - Hot-path slice passes: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` exits 0
    - SAFE-05 byte-identical legacy regression: there exists at least one test that constructs a QueueController with `docsis_mode=False` and exercises RED-decay; it must still pass with the same output as before this plan. (Verify by running `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestAdjust3StateRateAdjustments -v` — it must exit 0 with the same test count as before.)
    - ruff and mypy clean on all modified files
  </acceptance_criteria>
  <done>
    All four new test classes pass including the BLOCKER 1 regression; existing tests continue to pass; ruff/mypy clean. The RED→GREEN transition is complete. Commit recorded.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3 (REFACTOR): Lint, document, and verify SAFE-05 byte-identity</name>
  <read_first>
    - src/wanctl/queue_controller.py (post-Task-2 state)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md (D-17 portable controller architecture; SAFE-05 byte-identity)
    - CHANGELOG.md
  </read_first>
  <files>src/wanctl/queue_controller.py, CHANGELOG.md, docs/CONFIGURATION.md</files>
  <action>
    1. **Inline comments.** Add a docstring to `_apply_anti_windup_if_needed` referencing the canary 20260504T231334Z evidence (1453 floor cycles, 30-155 ms·s integral range observed) and the VERIFICATION.md root-cause section. Add a comment block above the new RED-branch docsis path explaining the 12->6.37 cascade it prevents AND the BLOCKER 1 invariant (current_rate >= setpoint_bps gate prevents the rate-increase regression).

    2. **CHANGELOG.md** — under the v1.42 section (or create one if absent), add:
       ```markdown
       ### Fixed
       - **Phase 201 gap-closure:** DOCSIS-aware UL mode no longer cascades current_rate from setpoint to floor under sustained RED. Adds floor-anchored decay AT-OR-ABOVE setpoint (REGIME A), legacy multiplicative decay below setpoint (REGIME B; clamped at floor_red_bps), and integral anti-windup, all gated on `continuous_monitoring.upload.docsis_mode: true`. Non-DOCSIS deployments are byte-identical (CLAUDE.md NON-NEGOTIABLE). Closes the 1453-floor-cycle margin from canary 20260504T231334Z.
       ```

    3. **docs/CONFIGURATION.md** — add documentation for the two new YAML keys (`sustained_red_cycles`, `anti_windup_cycles`) under the Phase 201 section. Match the existing migration-note pattern (D-08 restart-required).

    4. **SAFE-05 verification.** Run the legacy regression slice:
       ```
       .venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestAdjust3StateRateAdjustments tests/test_queue_controller.py::TestStateTransitionSequences -v
       ```
       These tests must still all pass with exactly the same test count as pre-Task-2. Document the count in the commit message.

    5. Final commit: `refactor(201-14): doc + CHANGELOG + SAFE-05 byte-identity verified`. (Skip if no real refactor was needed; the lint/doc work alone justifies a commit.)
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q</automated>
    <automated>grep -q "Phase 201 gap-closure" CHANGELOG.md</automated>
    <automated>grep -q "sustained_red_cycles" docs/CONFIGURATION.md</automated>
    <automated>grep -q "anti_windup_cycles" docs/CONFIGURATION.md</automated>
    <automated>.venv/bin/ruff format --check src/wanctl/queue_controller.py</automated>
  </verify>
  <acceptance_criteria>
    - All test_queue_controller.py tests pass
    - `grep -q "canary 20260504T231334Z" src/wanctl/queue_controller.py` (root-cause traceability inline)
    - CHANGELOG.md and docs/CONFIGURATION.md updated
    - ruff format check passes
  </acceptance_criteria>
  <done>
    The control-model amendment is documented, linted, and SAFE-05 byte-identity is verified by the legacy test slice.
  </done>
</task>

</tasks>

<verification>
Full hot-path slice + Phase 201 surfaces:
```
.venv/bin/pytest -o addopts='' \
  tests/test_cake_signal.py \
  tests/test_queue_controller.py \
  tests/test_wan_controller.py \
  tests/test_health_check.py \
  tests/test_autorate_config.py \
  tests/test_check_config.py \
  -q
```
Must exit 0.

Static checks:
```
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/wanctl/
```
</verification>

<success_criteria>
- Three control-model changes implemented and tested with corrected BLOCKER 1 condition (`current_rate >= setpoint_bps`, not `<=`)
- All 15+ new tests in 4 new test classes pass, including the BLOCKER 1 regression `test_red_below_setpoint_does_not_increase_rate`
- BLOCKER 3: Replay corpus uses calibrated 18-cycle RED bursts that demonstrably cascade pre-fix (12 * 0.9^18 = 1.80 Mbit << floor=8M) and hold post-fix
- Existing test count unchanged or grown (no test deletions)
- Hot-path slice passes with no regression
- ruff and mypy clean
- configs/spectrum.yaml has explicit values for both new keys
- KNOWN_AUTORATE_PATHS registers both new keys (SAFE-06 compliance)
- CHANGELOG and docs/CONFIGURATION.md updated
- SAFE-05 byte-identity preserved (legacy mode tests unchanged)
- WARNING 4 absorbed: /health diagnostic fields (`headroom_exhausted_streak`, `sustained_red_cycles`, `anti_windup_cycles`, `anti_windup_triggers`) are NOT added in this plan; they are owned by Plan 201-13.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md` per the standard template. Include: list of behaviors changed, list of YAML keys added, exact line ranges of the three control-model edits, replay-test outcome (floor_hit_cycles=0 over 1000-cycle synthetic window with 18-cycle RED bursts), BLOCKER 1 regression test outcome, SAFE-05 byte-identity confirmation.
</output>
</content>
</invoke>