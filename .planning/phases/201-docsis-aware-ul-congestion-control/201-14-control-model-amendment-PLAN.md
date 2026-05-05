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
revision: 3  # Iteration 3 — incorporates Codex cross-AI HIGH-CODEX-1, HIGH-CODEX-2, MEDIUM-CODEX-1, MEDIUM-CODEX-2 from 201-REVIEWS.md
requirements: [VALN-06]
tags: [phase-201, gap-closure, control-model, bounded-absolute-decay, anti-windup, tdd, docsis-gated, codex-revised]

must_haves:
  truths:
    - "When docsis_mode=true AND zone=RED AND current_rate >= (setpoint_bps - delta_max_bps), RED decay is BOUNDED-ABSOLUTE — subtract a fixed step per cycle, clamp at (setpoint_bps - delta_max_bps). No multiplicative cascade. The 12 Mbit -> floor cascade observed in canary 20260504T231334Z is structurally impossible across the canary's 18-cycle longest RED burst."
    - "When current_rate < (setpoint_bps - delta_max_bps) OR docsis_mode=false: legacy multiplicative `factor_down` decay engages and enforce_rate_bounds clamps at floor_red_bps. This preserves CLAUDE.md spine ('rate decreases immediate') in BOTH regimes — bounded-absolute decay also decreases rate, just by a smaller fixed amount."
    - "BLOCKER 1 invariant (preserved from prior revision): when zone=RED and docsis_mode=true, new_rate <= current_rate ALWAYS, in EVERY regime. Bounded-absolute decay cannot raise rate (max(rate-step, clamp) <= rate when rate >= clamp). Verified by a property test sampling thousands of (rate, red_streak, setpoint) tuples."
    - "Cycle-1 through cycle-18 expected post-fix rates are explicitly tabled and asserted in the replay test. floor_hit_cycles == 0 across the entire 18-cycle RED burst. cycle-by-cycle assertion (not just end-state) catches any regression in the math."
    - "Integral anti-windup: when docsis_mode=true AND _headroom_exhausted_streak >= anti_windup_cycles AND current_rate == floor_red_bps, the integral window is CAPPED-AND-CLAMPED to a value strictly BELOW threshold (not merely halved) AND _headroom_state is recomputed IMMEDIATELY (not deferred to next cycle) so recovery is not gated on a stuck signal. Logging is RATE-LIMITED: at most one INFO log per anti_windup_cycles trigger interval; the queryable counter `anti_windup_triggers` is the primary observability surface."
    - "Asymmetry preserved: rate decreases on every RED cycle (no holding at setpoint, no first-RED-no-decrease exception). Recovery still requires green_streak >= green_required (no relaxation of push-up gate). HIGH-CODEX-2 closed by Option B (bounded-absolute decay always decreases)."
    - "All control-model changes are docsis_mode-gated: when docsis_mode=false, every code path returns the SAME value as before this plan (byte-identical legacy 3-state UL behavior). No link-type Python branching — gating is on `self._docsis_mode` (already YAML-driven)."
    - "Flash-wear protection preserved: last_applied_ul_rate dedup is upstream of QueueController (in WANController); this plan changes only QueueController.adjust() return values, so dedup semantics are unchanged."
    - "Existing tests at tests/test_queue_controller.py:3574 (test_red_decay_takes_rate_below_setpoint) and :3640 (test_red_immediate_decay_regardless_of_integral_state) are EXPLICITLY UPDATED with revised expectations and recorded rationale; not silently broken."
  artifacts:
    - path: src/wanctl/queue_controller.py
      provides: "Bounded-absolute RED decay (two-regime: in-setpoint-band vs below-band) + integral anti-windup with immediate headroom recompute, all docsis_mode-gated"
      contains: "_compute_rate_3state"
    - path: tests/test_queue_controller.py
      provides: "TestDocsisModeBoundedAbsoluteDecay + TestDocsisModeIntegralAntiWindup + TestDocsisModeReplayCanary11 + TestDocsisModeRedNonIncreaseProperty + UPDATED TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint + UPDATED TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state"
      contains: "TestDocsisModeBoundedAbsoluteDecay"
  key_links:
    - from: "src/wanctl/queue_controller.py:_compute_rate_3state RED branch"
      to: "self._docsis_mode + self._setpoint_bps + self._red_decay_step_pct + self._red_decay_delta_max_pct"
      via: "if docsis_mode and current_rate >= (setpoint - delta_max): new_rate = max(current_rate - step, setpoint - delta_max); else: legacy factor_down"
      pattern: "_red_decay_delta_max_pct|_red_decay_step_pct"
    - from: "src/wanctl/queue_controller.py:_apply_anti_windup_if_needed"
      to: "self._integral_window + self._headroom_state recompute"
      via: "cap-and-clamp integral to (threshold - 1.0) and recompute headroom_state synchronously"
      pattern: "_apply_anti_windup_if_needed"
---

<objective>
**Gap-closure Plan 2 of 4. PRIMARY DEFECT FIX. Revision 3 — Codex cross-AI BLOCKER closure.**

This is the control-model amendment that closes the 1453-cycle floor-peg gap from canary 20260504T231334Z. Per 201-REVIEWS.md HIGH-CODEX-1: the **prior revision's algorithm did not pass its own 18-cycle replay** — at cycle 8 it fell through to `factor_down=0.90` and cascaded `12M → 10.8M → 9.72M → 8.748M → floor=8M` by cycle 11, producing 7+ floor hits across cycles 11-18. The local plan-checker missed this; codex caught it. This revision adopts **Option B** from the codex review: replace the fall-through-to-factor_down threshold with a **bounded-absolute decay** that decreases rate by a fixed delta per cycle and clamps at `setpoint - delta_max`, so RED bursts of any length within the canary corpus stay strictly above floor.

**Algorithm (Option B — bounded absolute decay):**

```
REGIME A (in-band, docsis-gated):
  IF docsis_mode AND zone == RED AND current_rate >= (setpoint - delta_max):
      step      = max(1, int(setpoint * red_decay_step_pct))      # default 2% of setpoint
      delta_max = max(1, int(setpoint * red_decay_delta_max_pct)) # default 10% of setpoint
      clamp     = setpoint - delta_max
      new_rate  = max(int(current_rate - step), clamp)

REGIME B (out-of-band sustained overload):
  ELIF current_rate < (setpoint - delta_max) OR docsis_mode=false:
      new_rate = int(current_rate * factor_down)   # legacy multiplicative
      # enforce_rate_bounds clamps at floor_red_bps downstream
```

**Cycle 1-18 expected post-fix rate table (setpoint=12M, step=240_000, delta_max=1_200_000, clamp=10_800_000):**

| Cycle | red_streak | rate (entering) | Regime | new_rate (exiting) | floor_hit? |
|-------|------------|-----------------|--------|---------------------|------------|
| 1     | 1          | 12,000,000      | A      | 11,760,000          | no         |
| 2     | 2          | 11,760,000      | A      | 11,520,000          | no         |
| 3     | 3          | 11,520,000      | A      | 11,280,000          | no         |
| 4     | 4          | 11,280,000      | A      | 11,040,000          | no         |
| 5     | 5          | 11,040,000      | A      | 10,800,000          | no         |
| 6     | 6          | 10,800,000      | A      | 10,800,000 (clamp)  | no         |
| 7-18  | 7-18       | 10,800,000      | A      | 10,800,000 (clamp)  | no         |

**Result:** floor_hit_cycles = 0 across all 18 cycles. The cycle-8 fall-through bug from the prior revision is **structurally eliminated** because Regime A's gate (`current_rate >= clamp = 10.8M`) holds for the entire burst. There is no `sustained_red_cycles` threshold; the regime stays engaged as long as the controller is within `delta_max` of setpoint, which is the entire RED burst duration in the canary corpus. Sustained overload that pushes rate below the clamp (i.e., something is fundamentally wrong) falls through to legacy `factor_down`, which `enforce_rate_bounds` then anchors at `floor_red_bps`.

**HIGH-CODEX-2 closure (asymmetric-response honesty):** Option B's bounded-absolute decay decreases rate by `step` (= 240,000 bps for setpoint=12M) on the very first RED cycle. The CLAUDE.md "rate decreases immediate" invariant IS preserved — bounded-absolute decay also decreases, just by a smaller fixed amount. There is no first-RED-at-setpoint exception under Option B. The prior revision's `max(decayed, setpoint)` formula (which DID violate the invariant) is removed entirely.

**MEDIUM-CODEX-1 closure:** The two existing tests that asserted the old multiplicative-decay behavior at setpoint are explicitly updated, not silently broken:

- `tests/test_queue_controller.py:3574` (`TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint`): updated to assert `12,000,000 - 240,000 == 11,760,000` (new bounded-absolute step) instead of the prior `< 12,000,000` weak inequality. Renamed to `test_red_decay_at_setpoint_bounded_step`.
- `tests/test_queue_controller.py:3640` (`TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state`): updated to assert `rate == 11_760_000` (Option B step) instead of `int(12_000_000 * factor_down) == 10_800_000` (old multiplicative). Renamed to `test_red_immediate_bounded_decay_under_docsis_mode`. Rationale comment cites the canary 20260504T231334Z root cause.

**MEDIUM-CODEX-2 closure (anti-windup strengthened):** The prior revision halved the integral window. Codex correctly flagged this as too weak — halving 100-155 ms·s integrals still leaves them above the 30 ms·s threshold. The new behavior:

1. **Cap-and-clamp** every entry in `_integral_window` to `(threshold - 1.0) / window_size` so the resulting `_last_integral_ms_s` lands at exactly `threshold - 1.0` ms·s (strictly below the 30 ms·s gate).
2. **Recompute `_headroom_state` synchronously** after the cap so the recovery gate can flip on the next adjust() call, not the cycle-after-next.
3. **Rate-limit logging** to one INFO log per `anti_windup_cycles` interval (not every cycle while the streak is hot). The `anti_windup_triggers` counter (already serialized by Plan 201-13) is the primary observability surface.

**Three coordinated YAML keys**, all docsis_mode-gated, all going through `KNOWN_AUTORATE_PATHS`:

- `red_decay_step_pct: float = 0.02` (NEW — Option B step size as fraction of setpoint)
- `red_decay_delta_max_pct: float = 0.10` (NEW — Option B clamp distance below setpoint as fraction of setpoint)
- `anti_windup_cycles: int = 60` (PRESERVED from prior revision — 60 cycles = 3s @ 50ms)

**REMOVED from prior revision:** `sustained_red_cycles` is **deleted**. Option B has no fall-through threshold by red_streak; the gate is purely on `current_rate` band. This is a deliberate simplification per codex suggestion. Plan 201-13 already dropped this field in revision 2 (coordinated edit during the same /gsd-plan-phase --reviews pass); Task 4 of this plan verifies that coordination is intact.

**No link-type branching:** every new code path is gated on `self._docsis_mode` and YAML keys. Non-DOCSIS deployments are byte-identical (CLAUDE.md NON-NEGOTIABLE).

**Output:** ~30-50 lines of new/changed code in queue_controller.py, 4 new test classes + 2 updated existing tests in test_queue_controller.py, two new YAML keys + one removal in autorate_config.py + check_config_validators.py, configs/spectrum.yaml updated, CHANGELOG.md and docs/CONFIGURATION.md updated, coordination edits in Plan 201-13 to drop the deleted-knob serialization.
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
@.planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md
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
        return int(self.current_rate * self.factor_down)  # <-- DEFECT SITE
    if self.green_streak >= self.green_required:
        ...  # push-up clamp (already correct)
    if zone == "YELLOW":
        ...  # YELLOW decay (already correct)
    self._yellow_decay_streak = 0
    return self.current_rate
```

`_update_integral(delta_ms)` (queue_controller.py:241-256) — returns `(integral_ms_s, state)`. The returned `state` is the value to track for the streak counter.

`_classify_zone_3state` recomputes `_headroom_state` based on `_last_integral_ms_s`. The anti-windup helper must update `_last_integral_ms_s` AND directly recompute `_headroom_state` (mirroring the same logic used inside the classifier) so a subsequent push-up evaluation sees the corrected state without waiting for the next cycle.

YAML key registration: `src/wanctl/check_config_validators.py:KNOWN_AUTORATE_PATHS` — every new key MUST be added (SAFE-06 unknown-key warning).

YAML schema: `src/wanctl/autorate_config.py` — D-08 keeps these as restart-required.

Constructor pattern: keyword-only with safe default = no behavior change. See queue_controller.py:47-52.

DOCSIS-mode gate idiom: `if self._docsis_mode and self._setpoint_bps is not None:` (used 3 times already).

**Test conflicts to update (codex MEDIUM-CODEX-1):**
- `tests/test_queue_controller.py:3574` — `TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint`
- `tests/test_queue_controller.py:3640` — `TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state`

Both currently expect multiplicative decay at setpoint; both must be rewritten.

**Coordinated drop in Plan 201-13:** Plan 201-13 was updated to revision 2 in the same /gsd-plan-phase --reviews pass that produced this rev-3 plan. Both plans now agree: `sustained_red_cycles` is deleted from the controller AND not serialized to /health. Task 4 of this plan verifies the coordination is intact (no drift).
</interfaces>

<tdd_cycle>
RED → GREEN → REFACTOR. The cycle table above IS the spec.

**Replay corpus (calibrated cascade arithmetic — preserves prior plan's BLOCKER 3 fix):**
- Pre-fix: `12_000_000 * (0.9 ** 18) = 1_801_135` bps ≈ 1.80 Mbit << floor=8M → sustained floor residence (canary 201-11 failure mode).
- Post-fix Option B: cycles 1-5 step down 240k each, cycle 6 hits clamp at 10.8M, cycles 7-18 hold at 10.8M. floor_hit_cycles=0.

The replay test asserts the **exact** post-fix rate at every cycle (1 through 18), not just the end state. This is codex suggestion: "Add a mandatory cycle table to the replay test comments and assert the exact expected post-fix rates for cycles 1-18."

**Property test (codex suggestion):** sample 1000+ random `(current_rate, red_streak, setpoint, factor_down)` tuples in BOTH docsis and legacy modes; assert `new_rate <= current_rate` for every sample. This is the strongest invariant check available.
</tdd_cycle>

<feature>
  <name>Bounded-absolute RED decay (docsis_mode-gated, two-regime)</name>
  <files>src/wanctl/queue_controller.py, tests/test_queue_controller.py</files>
  <behavior>
    Two-regime RED-branch behavior under `docsis_mode=true`:

    REGIME A — current_rate >= (setpoint_bps - delta_max_bps):
      - delta_max_bps = max(1, int(setpoint_bps * red_decay_delta_max_pct))  # default 10% of setpoint
      - step_bps      = max(1, int(setpoint_bps * red_decay_step_pct))       # default 2% of setpoint
      - clamp_bps     = setpoint_bps - delta_max_bps
      - new_rate      = max(int(current_rate - step_bps), clamp_bps)
      - INVARIANT: step_bps > 0 always, so new_rate < current_rate UNLESS clamp held; max(...) cannot exceed current_rate when current_rate >= clamp_bps. Therefore new_rate <= current_rate always.

    REGIME B — current_rate < (setpoint_bps - delta_max_bps) OR docsis_mode=false OR setpoint_bps is None:
      - new_rate = int(current_rate * factor_down)
      - enforce_rate_bounds (called downstream in adjust()) clamps at floor_red_bps.
      - INVARIANT: factor_down=0.9 < 1.0 always shrinks; new_rate < current_rate.

    Combined invariant (BLOCKER 1, preserved): when zone=RED, new_rate <= current_rate ALWAYS in every regime. Verified by a property test (TestDocsisModeRedNonIncreaseProperty) sampling >= 1000 tuples in BOTH modes.
  </behavior>
  <implementation>
    1. Add YAML keys `red_decay_step_pct: float = 0.02` and `red_decay_delta_max_pct: float = 0.10` to QueueController.__init__ (keyword-only). Register both in KNOWN_AUTORATE_PATHS as `continuous_monitoring.upload.red_decay_step_pct` and `continuous_monitoring.upload.red_decay_delta_max_pct`. Add to autorate_config.py schema.
    2. **DELETE** the prior revision's `sustained_red_cycles` keyword arg + attribute + YAML registration. Replace with the two new keys above. Coordinate with Plan 201-13 (Task 4 of this plan).
    3. Add to configs/spectrum.yaml under `continuous_monitoring.upload:`: `red_decay_step_pct: 0.02` and `red_decay_delta_max_pct: 0.10` (with comments explaining the cycle-1-to-18 holding behavior).
    4. Refactor RED branch in `_compute_rate_3state`:
       ```python
       if self.red_streak >= 1:
           self._yellow_decay_streak = 0
           if self._docsis_mode and self._setpoint_bps is not None:
               delta_max_bps = max(1, int(self._setpoint_bps * self._red_decay_delta_max_pct))
               clamp_bps = self._setpoint_bps - delta_max_bps
               if self.current_rate >= clamp_bps:
                   # REGIME A: bounded-absolute decay; clamp at (setpoint - delta_max).
                   # Floor_hit_cycles=0 across the canary 20260504T231334Z 18-cycle RED burst.
                   # Codex Option B (201-REVIEWS HIGH-CODEX-1).
                   step_bps = max(1, int(self._setpoint_bps * self._red_decay_step_pct))
                   return max(int(self.current_rate - step_bps), clamp_bps)
           # REGIME B (sustained overload below band) AND REGIME C (legacy):
           # legacy multiplicative decay; enforce_rate_bounds clamps at floor_red_bps.
           return int(self.current_rate * self.factor_down)
       ```
  </implementation>
</feature>

<feature>
  <name>Integral anti-windup with cap-and-clamp + immediate headroom recompute (docsis_mode-gated)</name>
  <files>src/wanctl/queue_controller.py, tests/test_queue_controller.py</files>
  <behavior>
    Track `self._headroom_exhausted_streak: int` — incremented every cycle `_update_integral` returns "EXHAUSTED", reset to 0 every cycle "AVAILABLE".

    When `docsis_mode=true` AND `_headroom_exhausted_streak >= anti_windup_cycles` AND `current_rate == floor_red_bps`:
      - **Cap-and-clamp every entry** in `self._integral_window` so the resulting integral lands at exactly `(self._integral_threshold_ms_s - 1.0)` (strictly below threshold). Concretely: clear the deque, then push N copies of `((threshold - 1.0) / 0.05) / N` where N = window maxlen, so `sum * 0.05 == threshold - 1.0`. (Codex MEDIUM-CODEX-2: prior `halve` left integral above threshold and gated recovery.)
      - **Recompute `self._last_integral_ms_s` AND `self._headroom_state` SYNCHRONOUSLY** in the same call (not deferred to next `_update_integral`). After the cap, call `self._recompute_headroom_state()` (new helper, mirrors the AVAILABLE/EXHAUSTED branch in `_update_integral`).
      - Reset `self._headroom_exhausted_streak = 0` after the cap.
      - Increment `self._anti_windup_triggers` counter (serialized by Plan 201-13).
      - **Rate-limited INFO log** at most once per `anti_windup_cycles` interval (track `self._last_anti_windup_log_cycle: int` — only log if current cycle - last >= anti_windup_cycles; primary observability is the queryable counter, not log spam).

    When `docsis_mode=false`: streak still computed (cheap) but never triggers (gated on docsis_mode).
  </behavior>
  <implementation>
    1. Preserve `anti_windup_cycles: int = 60` keyword param + YAML registration from prior revision.
    2. Init `self._headroom_exhausted_streak: int = 0`, `self._anti_windup_triggers: int = 0`, `self._last_anti_windup_log_cycle: int = -10**9`, `self._cycle_count: int = 0`.
    3. Modify `_update_integral` to bump/reset streak based on returned state. Increment `self._cycle_count` once per cycle (in adjust(), after the integral update).
    4. Add helper `_recompute_headroom_state()` mirroring the threshold logic in `_update_integral`:
       ```python
       def _recompute_headroom_state(self) -> None:
           if len(self._integral_window) < (self._integral_window.maxlen or 0):
               self._headroom_state = "EXHAUSTED"
               return
           if self._last_integral_ms_s <= self._integral_threshold_ms_s:
               self._headroom_state = "AVAILABLE"
           else:
               self._headroom_state = "EXHAUSTED"
       ```
    5. Add helper `_apply_anti_windup_if_needed()` called once per cycle from `adjust()` AFTER `_update_integral` and BEFORE `_classify_zone_3state`:
       ```python
       def _apply_anti_windup_if_needed(self) -> None:
           if not self._docsis_mode:
               return
           if self._headroom_exhausted_streak < self._anti_windup_cycles:
               return
           if self.current_rate != self.floor_red_bps:
               return
           # Cap-and-clamp integral STRICTLY BELOW threshold (codex MEDIUM-CODEX-2).
           target_ms_s = max(0.0, self._integral_threshold_ms_s - 1.0)
           maxlen = self._integral_window.maxlen or 1
           per_sample = (target_ms_s / 0.05) / maxlen
           self._integral_window.clear()
           for _ in range(maxlen):
               self._integral_window.append(per_sample)
           self._last_integral_ms_s = sum(self._integral_window) * 0.05
           # Recompute headroom_state SYNCHRONOUSLY (codex MEDIUM-CODEX-2).
           self._recompute_headroom_state()
           self._headroom_exhausted_streak = 0
           self._anti_windup_triggers += 1
           # Rate-limited INFO log (codex MEDIUM-CODEX-2).
           if self._cycle_count - self._last_anti_windup_log_cycle >= self._anti_windup_cycles:
               self._logger.info(
                   "[ANTI-WINDUP] %s integral capped to %.2f ms*s after %d EXHAUSTED cycles at floor",
                   self.name, target_ms_s, self._anti_windup_cycles,
               )
               self._last_anti_windup_log_cycle = self._cycle_count
       ```
  </implementation>
</feature>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (RED): Write failing tests for bounded-absolute decay + cycle-1-18 cycle table + property test + anti-windup cap-and-clamp; UPDATE tests at lines 3574 and 3640</name>
  <read_first>
    - tests/test_queue_controller.py (TestDocsisModeIntegralClassifier, TestDocsisModeSetpointClamp at lines 3517-3650 — fixture + `_make_docsis_controller` helper)
    - tests/test_queue_controller.py:3574 (TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint — the existing test that must be UPDATED, not silently broken)
    - tests/test_queue_controller.py:3640 (TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state — second existing test that must be UPDATED)
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json (1453 floor cycles)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md (root-cause section)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (HIGH-CODEX-1, MEDIUM-CODEX-1, MEDIUM-CODEX-2)
    - src/wanctl/queue_controller.py (current _compute_rate_3state and _update_integral)
  </read_first>
  <files>tests/test_queue_controller.py</files>
  <action>
    **Part A — Update two existing tests (codex MEDIUM-CODEX-1):**

    1. `TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint` at line 3574: rename to `test_red_decay_at_setpoint_bounded_step` and rewrite assertions to expect Option B output:
       ```python
       def test_red_decay_at_setpoint_bounded_step(self):
           # Updated for Plan 201-14 revision 3 (codex MEDIUM-CODEX-1).
           # Old behavior: rate < 12_000_000 (factor_down=0.9 multiplicative).
           # New behavior: rate == 12_000_000 - max(1, int(12_000_000 * 0.02)) == 11_760_000 (Option B).
           # Rationale: bounded-absolute decay prevents the 12->floor cascade observed
           # in canary 20260504T231334Z (1453 floor cycles in 1022s loaded window).
           ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
           ctrl.current_rate = 12_000_000
           ctrl.red_streak = 1
           rate = ctrl._compute_rate_3state("RED")
           assert rate == 11_760_000  # 12M - 240k step, above clamp at 10.8M
           assert rate < 12_000_000   # legacy invariant: rate decreased on first RED (HIGH-CODEX-2)
       ```

    2. `TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state` at line 3640: rename to `test_red_immediate_bounded_decay_under_docsis_mode` and rewrite:
       ```python
       def test_red_immediate_bounded_decay_under_docsis_mode(self):
           # Updated for Plan 201-14 revision 3 (codex MEDIUM-CODEX-1).
           # The "fast-trip" semantic remains — RED still produces immediate rate decrease —
           # but the magnitude under docsis_mode is now bounded-absolute (240k step) not
           # multiplicative (factor_down=0.9). HIGH-CODEX-2 invariant preserved.
           ctrl = _make_docsis_controller()
           ctrl.current_rate = 12_000_000
           ctrl._headroom_state = "AVAILABLE"
           ctrl._cake_aligned = True
           zone, rate, _ = ctrl.adjust(22.0, 22.0 + 50.0, target_delta=5.0, warn_delta=15.0)
           assert zone == "RED"
           assert rate == 11_760_000  # bounded-absolute step, NOT int(12_000_000 * factor_down)
           assert rate < 12_000_000   # still strict decrease (asymmetry preserved)
       ```

    Also add a NEW test in the SAME `TestRedFastTripUnchangedDocsisMode` class to retain the legacy-mode behavior assertion:
       ```python
       def test_red_immediate_decay_legacy_mode_unchanged(self):
           # Byte-identity check: docsis_mode=False keeps multiplicative factor_down.
           ctrl = _make_docsis_controller(docsis_mode=False, setpoint_bps=None)
           ctrl.current_rate = 12_000_000
           zone, rate, _ = ctrl.adjust(22.0, 22.0 + 50.0, target_delta=5.0, warn_delta=15.0)
           assert zone == "RED"
           assert rate == int(12_000_000 * ctrl.factor_down)  # 10_800_000
       ```

    **Part B — Add four new test classes AFTER `TestDocsisModeCakeCorroborator`:**

    **`TestDocsisModeBoundedAbsoluteDecay`** — covers Option B regimes:
      - test_regime_a_at_setpoint_steps_down_240k: setpoint=12M, rate=12M, red_streak=1 → 11_760_000.
      - test_regime_a_above_setpoint_steps_down_240k: setpoint=12M, rate=15M, red_streak=1 → 14_760_000 (above setpoint also takes the step; 15M >= 10.8M clamp).
      - test_regime_a_clamps_at_setpoint_minus_delta_max: setpoint=12M, rate=10_900_000 (above clamp=10.8M but below setpoint), red_streak=3 → max(10_660_000, 10_800_000) == 10_800_000.
      - test_regime_a_holds_at_clamp: setpoint=12M, rate=10_800_000 (== clamp), red_streak=5 → 10_800_000 (max(10_560_000, 10_800_000)).
      - test_regime_b_below_band_falls_through_to_factor_down: setpoint=12M, delta_max=1.2M (so clamp=10.8M), rate=10_500_000 (below clamp), red_streak=2 → int(10_500_000 * 0.9) == 9_450_000 (REGIME B legacy multiplicative).
      - test_regime_c_legacy_mode_unchanged: docsis_mode=False, rate=12M, red_streak=1 → int(12M * 0.9) == 10_800_000 (BYTE-IDENTICAL).
      - test_no_setpoint_falls_through_to_legacy: docsis_mode=True, setpoint_bps=None, rate=12M, red_streak=1 → int(12M * 0.9) (REGIME B / safe default).

    **`TestDocsisModeRedNonIncreaseProperty`** (codex suggestion — RED property test):
      - test_red_never_increases_rate_docsis_mode: parametrize over ~1000 sampled tuples (current_rate ∈ [floor=8M, ceiling=18M], setpoint ∈ [8M, 16M], red_streak ∈ [1, 50], factor_down=0.9, red_decay_step_pct=0.02, red_decay_delta_max_pct=0.10). For every sample with docsis_mode=True, assert `_compute_rate_3state("RED") <= current_rate`. Use `random.Random(42)` seed for determinism.
      - test_red_never_increases_rate_legacy_mode: same property but docsis_mode=False; new_rate must equal `int(current_rate * factor_down)` exactly and be <= current_rate.

    **`TestDocsisModeIntegralAntiWindup`** (anti-windup cap-and-clamp, codex MEDIUM-CODEX-2):
      - test_headroom_exhausted_streak_increments: feed 70 saturated samples; assert ctrl._headroom_exhausted_streak >= 60.
      - test_headroom_exhausted_streak_resets_on_available: feed 30 saturated then 30 idle; assert _headroom_exhausted_streak == 0.
      - test_anti_windup_caps_integral_below_threshold: docsis_mode=true, ctrl.current_rate = ctrl.floor_red_bps, fill _integral_window with values producing >= 30 ms·s integral, accumulate streak >= 60. After adjust() once: assert `ctrl._last_integral_ms_s < ctrl._integral_threshold_ms_s` (strictly below — NOT just halved). Specifically: assert `abs(ctrl._last_integral_ms_s - (ctrl._integral_threshold_ms_s - 1.0)) < 0.01`.
      - test_anti_windup_recomputes_headroom_state_synchronously: same setup; before adjust() assert ctrl._headroom_state == "EXHAUSTED"; after adjust() assert ctrl._headroom_state == "AVAILABLE" (synchronously, NOT next cycle).
      - test_anti_windup_triggers_counter_increments: assert ctrl._anti_windup_triggers == 1 after first trigger; == 2 after second trigger.
      - test_anti_windup_log_rate_limited: trigger anti-windup twice in rapid succession (within `anti_windup_cycles`); assert only ONE INFO log emitted (use caplog or mock _logger). Trigger third time AFTER anti_windup_cycles elapsed; assert second log emitted.
      - test_anti_windup_does_not_fire_above_floor: ctrl.current_rate = ctrl.floor_red_bps + 100_000, accumulate streak >= 60; assert _last_integral_ms_s unchanged AND _anti_windup_triggers == 0.
      - test_anti_windup_legacy_mode_no_op: docsis_mode=False, accumulate any streak; assert no cap fires.

    **`TestDocsisModeReplayCanary11`** (cycle-1-to-18 explicit table assertion — codex suggestion):
      - test_red_burst_18_cycles_explicit_table: docsis_mode=true, setpoint=12_000_000, floor=8_000_000, ceiling=18_000_000, red_decay_step_pct=0.02, red_decay_delta_max_pct=0.10. Set ctrl.current_rate = 12_000_000. Loop red_streak in 1..18, calling `_compute_rate_3state("RED")` directly with that streak. After each call, set ctrl.current_rate = returned_rate (simulating real flow). Assert the EXACT expected rate at every cycle:
        ```python
        EXPECTED_BY_CYCLE = {
            1: 11_760_000,    # 12M - 240k step
            2: 11_520_000,
            3: 11_280_000,
            4: 11_040_000,
            5: 10_800_000,    # hits clamp
            6: 10_800_000,    # held at clamp
            7: 10_800_000,
            8: 10_800_000,
            9: 10_800_000,
            10: 10_800_000,
            11: 10_800_000,
            12: 10_800_000,
            13: 10_800_000,
            14: 10_800_000,
            15: 10_800_000,
            16: 10_800_000,
            17: 10_800_000,
            18: 10_800_000,
        }
        ```
        For every cycle, assert `returned_rate == EXPECTED_BY_CYCLE[cycle]` AND `returned_rate > floor_red_bps` (no floor hit).
      - test_red_burst_18_cycles_no_floor_hits_via_adjust: full integration through adjust() with synthesized delta_ms producing RED zone for 18 cycles. Track ctrl.floor_hit_cycles; assert it stays 0 across the entire 18-cycle window. (This is the canary corpus replay; pre-fix would have shown floor_hit_cycles >= 7.)
      - test_below_band_overload_falls_through_legacy: docsis_mode=true, setpoint=12M, rate=10_500_000 (below clamp=10.8M), feed 10 RED cycles. Track current_rate descent; assert it follows int(rate * 0.9) per cycle (REGIME B engaged) AND eventually clamps at floor_red_bps via enforce_rate_bounds.

      Class header comment:
        ```python
        # Calibrated against canary 20260504T231334Z (1453 floor cycles in 1022s loaded window
        # at 50ms cadence; 1Hz secondary saw 84 floor samples).
        # Pre-fix cascade arithmetic (multiplicative factor_down=0.9):
        #   12_000_000 * (0.9 ** 18) = 1_801_135 bps (1.80 Mbit) << floor=8M
        # Post-fix Option B (bounded-absolute decay + clamp at setpoint - 10%):
        #   step=240k, clamp=10.8M; cycles 1-5 step down; cycles 6-18 hold at clamp.
        #   floor_hit_cycles = 0 across all 18 cycles.
        # Codex 201-REVIEWS HIGH-CODEX-1: cycle table assertion is the BLOCKER fix.
        ```

    All Part B tests must FAIL before Task 2 lands. Part A tests (the two updates) will also fail because the implementation hasn't landed yet.

    Commit: `test(201-14): update conflicting tests + add bounded-absolute decay tests + cycle table + property test + anti-windup cap-and-clamp tests`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeBoundedAbsoluteDecay tests/test_queue_controller.py::TestDocsisModeRedNonIncreaseProperty tests/test_queue_controller.py::TestDocsisModeIntegralAntiWindup tests/test_queue_controller.py::TestDocsisModeReplayCanary11 -v 2>&1 | grep -E 'failed|FAILED' | wc -l | grep -qE '^[1-9][0-9]*$'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "class TestDocsisModeBoundedAbsoluteDecay:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModeRedNonIncreaseProperty:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModeIntegralAntiWindup:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModeReplayCanary11:" tests/test_queue_controller.py` == 1
    - `grep -q "test_red_decay_at_setpoint_bounded_step" tests/test_queue_controller.py` (renamed test from line 3574)
    - `grep -q "test_red_immediate_bounded_decay_under_docsis_mode" tests/test_queue_controller.py` (renamed test from line 3640)
    - `grep -q "test_red_immediate_decay_legacy_mode_unchanged" tests/test_queue_controller.py` (new legacy-mode regression test)
    - `grep -q "test_red_burst_18_cycles_explicit_table" tests/test_queue_controller.py` (cycle table test present)
    - `grep -q "EXPECTED_BY_CYCLE" tests/test_queue_controller.py` (cycle table dict present)
    - `grep -qE "test_red_decay_takes_rate_below_setpoint" tests/test_queue_controller.py` returns NO match (old test name removed; renamed in place per codex MEDIUM-CODEX-1)
    - `grep -qE "test_red_immediate_decay_regardless_of_integral_state" tests/test_queue_controller.py` returns NO match (old test name removed)
    - Total NEW test count across the four new classes >= 19 (7+2+8+3)
    - At least 15 of the 19+ new tests FAIL when run against the pre-implementation queue_controller.py (RED step)
    - The two UPDATED tests also FAIL pre-implementation (their new assertions don't match the old factor_down=0.9 behavior)
  </acceptance_criteria>
  <done>
    Four new test classes exist; two existing tests updated and renamed; >= 21 tests total are RED. Commit recorded.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (GREEN): Implement bounded-absolute decay + anti-windup cap-and-clamp; remove `sustained_red_cycles`; register two new YAML keys</name>
  <read_first>
    - src/wanctl/queue_controller.py (Task 1 tests now exist and FAIL)
    - src/wanctl/autorate_config.py (lines 182-194)
    - src/wanctl/check_config_validators.py (lines 28-180)
    - src/wanctl/wan_controller.py:402-437 (UL QueueController constructor wiring)
    - configs/spectrum.yaml (lines 67-89)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (HIGH-CODEX-1 cycle table, MEDIUM-CODEX-2 anti-windup)
  </read_first>
  <files>src/wanctl/queue_controller.py, src/wanctl/autorate_config.py, src/wanctl/check_config_validators.py, src/wanctl/wan_controller.py, configs/spectrum.yaml</files>
  <action>
    Implement Option B + anti-windup cap-and-clamp. Goal: all Task 1 tests PASS, no existing test regresses.

    1. **queue_controller.py constructor** — keyword-only params:
       ```python
       red_decay_step_pct: float = 0.02,          # NEW (Option B step)
       red_decay_delta_max_pct: float = 0.10,     # NEW (Option B clamp distance)
       anti_windup_cycles: int = 60,              # PRESERVED
       # sustained_red_cycles REMOVED — Option B has no fall-through threshold
       ```
       Store as `self._red_decay_step_pct`, `self._red_decay_delta_max_pct`, `self._anti_windup_cycles`. Init `self._headroom_exhausted_streak: int = 0`, `self._anti_windup_triggers: int = 0`, `self._last_anti_windup_log_cycle: int = -10**9`, `self._cycle_count: int = 0`.

    2. **queue_controller.py `_update_integral`** — at end, update streak:
       ```python
       if state == "EXHAUSTED":
           self._headroom_exhausted_streak += 1
       else:
           self._headroom_exhausted_streak = 0
       ```

    3. **queue_controller.py `_compute_rate_3state` RED branch** — replace unconditional `factor_down` decay with Option B:
       ```python
       if self.red_streak >= 1:
           self._yellow_decay_streak = 0
           if self._docsis_mode and self._setpoint_bps is not None:
               delta_max_bps = max(1, int(self._setpoint_bps * self._red_decay_delta_max_pct))
               clamp_bps = self._setpoint_bps - delta_max_bps
               if self.current_rate >= clamp_bps:
                   # REGIME A: bounded-absolute decay (codex Option B, HIGH-CODEX-1).
                   # Cycle table cycles 1-18 holds floor_hit_cycles=0 against
                   # canary 20260504T231334Z 18-cycle RED burst corpus.
                   # HIGH-CODEX-2: rate decreases immediate (step > 0 always when
                   # current_rate > clamp_bps); CLAUDE.md spine preserved.
                   step_bps = max(1, int(self._setpoint_bps * self._red_decay_step_pct))
                   return max(int(self.current_rate - step_bps), clamp_bps)
           # REGIME B (below band, sustained overload) AND REGIME C (legacy):
           # legacy multiplicative decay; enforce_rate_bounds clamps at floor_red_bps.
           return int(self.current_rate * self.factor_down)
       ```

    4. **queue_controller.py `_recompute_headroom_state` helper** — add new method per <feature> spec (mirrors threshold logic from `_update_integral`).

    5. **queue_controller.py `_apply_anti_windup_if_needed` helper** — add per <feature> spec. Cap-and-clamp integral to `(threshold - 1.0)` ms*s, recompute headroom_state synchronously, rate-limit logs via `_last_anti_windup_log_cycle` and `_cycle_count`.

    6. **queue_controller.py `adjust()`** — between `_update_integral` call and `_classify_zone_3state` call:
       ```python
       self._cycle_count += 1
       self._apply_anti_windup_if_needed()
       ```

    7. **autorate_config.py** — add `red_decay_step_pct` (float, default 0.02) and `red_decay_delta_max_pct` (float, default 0.10) to upload schema. **REMOVE `sustained_red_cycles`** if it was added in the prior revision. Both new keys are float-only, do not participate in threshold ordering, restart-required (D-08).

    8. **check_config_validators.py** — add to KNOWN_AUTORATE_PATHS:
       ```python
       "continuous_monitoring.upload.red_decay_step_pct",
       "continuous_monitoring.upload.red_decay_delta_max_pct",
       ```
       **REMOVE `continuous_monitoring.upload.sustained_red_cycles`** if present (it was added in the prior revision but is no longer used).

    9. **wan_controller.py** — wire new keys into upload QueueController constructor at lines 402-437:
       ```python
       red_decay_step_pct=float(getattr(config, "red_decay_step_pct", 0.02)),
       red_decay_delta_max_pct=float(getattr(config, "red_decay_delta_max_pct", 0.10)),
       anti_windup_cycles=int(getattr(config, "anti_windup_cycles", 60)),
       ```
       Add explicit-presence flags `_red_decay_step_pct_explicit`, `_red_decay_delta_max_pct_explicit`, `_anti_windup_cycles_explicit`. **REMOVE `sustained_red_cycles=` if present.**

    10. **configs/spectrum.yaml** — under `continuous_monitoring.upload:`, add:
        ```yaml
            # Phase 201 gap-closure rev 3 (Codex Option B for HIGH-CODEX-1):
            # Bounded-absolute RED decay. step=2% of setpoint per cycle (240k for setpoint=12M);
            # clamp at setpoint - delta_max where delta_max=10% (clamp=10.8M for setpoint=12M).
            # Cycles 1-5 step down 12M->10.8M; cycles 6+ hold at clamp.
            # floor_hit_cycles=0 across the canary 20260504T231334Z 18-cycle RED burst.
            red_decay_step_pct: 0.02
            red_decay_delta_max_pct: 0.10
            # 60 cycles = 3s; cap-and-clamp integral STRICTLY BELOW threshold so recovery
            # is not gated on a stuck signal (codex MEDIUM-CODEX-2; halve was insufficient).
            anti_windup_cycles: 60
        ```
        **REMOVE `sustained_red_cycles: 8`** if previously added (no longer used).

    11. Run pytest. All Task 1 tests must PASS. Commit: `feat(201-14): bounded-absolute RED decay (Option B) + anti-windup cap-and-clamp; rev 3 closes codex HIGH-CODEX-1/2 + MEDIUM-CODEX-1/2`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeBoundedAbsoluteDecay tests/test_queue_controller.py::TestDocsisModeRedNonIncreaseProperty tests/test_queue_controller.py::TestDocsisModeIntegralAntiWindup tests/test_queue_controller.py::TestDocsisModeReplayCanary11 -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeSetpointClamp::test_red_decay_at_setpoint_bounded_step tests/test_queue_controller.py::TestRedFastTripUnchangedDocsisMode -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py -q</automated>
    <automated>.venv/bin/ruff check src/wanctl/queue_controller.py src/wanctl/autorate_config.py src/wanctl/check_config_validators.py src/wanctl/wan_controller.py</automated>
    <automated>.venv/bin/mypy src/wanctl/queue_controller.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "red_decay_step_pct: float = 0.02" src/wanctl/queue_controller.py`
    - `grep -q "red_decay_delta_max_pct: float = 0.10" src/wanctl/queue_controller.py`
    - `grep -q "anti_windup_cycles: int = 60" src/wanctl/queue_controller.py`
    - **`sustained_red_cycles` removed**: `grep -E "sustained_red_cycles" src/wanctl/queue_controller.py src/wanctl/autorate_config.py src/wanctl/check_config_validators.py src/wanctl/wan_controller.py | grep -v '^#' | wc -l | grep -qE '^0$'`
    - `grep -q "self._red_decay_step_pct" src/wanctl/queue_controller.py`
    - `grep -q "self._red_decay_delta_max_pct" src/wanctl/queue_controller.py`
    - `grep -q "_recompute_headroom_state" src/wanctl/queue_controller.py`
    - `grep -q "_apply_anti_windup_if_needed" src/wanctl/queue_controller.py`
    - `grep -q "_last_anti_windup_log_cycle" src/wanctl/queue_controller.py` (rate-limited logging)
    - `grep -q "self._integral_threshold_ms_s - 1.0" src/wanctl/queue_controller.py` (cap-and-clamp below threshold)
    - `grep -q "continuous_monitoring.upload.red_decay_step_pct" src/wanctl/check_config_validators.py`
    - `grep -q "continuous_monitoring.upload.red_decay_delta_max_pct" src/wanctl/check_config_validators.py`
    - `grep -q "red_decay_step_pct: 0.02" configs/spectrum.yaml`
    - `grep -q "red_decay_delta_max_pct: 0.10" configs/spectrum.yaml`
    - `grep -q "anti_windup_cycles: 60" configs/spectrum.yaml`
    - All four new test classes pass; both updated tests pass
    - `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeReplayCanary11::test_red_burst_18_cycles_explicit_table -v` exits 0 — the 18-cycle table is the BLOCKER fix
    - Hot-path slice passes; no test count shrink
    - SAFE-05 byte-identity: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestAdjust3StateRateAdjustments tests/test_queue_controller.py::TestDocsisModeByteIdentity -v` exits 0 with same test count as pre-Task-2
    - ruff and mypy clean
  </acceptance_criteria>
  <done>
    Option B implemented; cycle 1-18 table assertion green; anti-windup cap-and-clamp synchronously recomputes headroom; existing tests updated not broken; SAFE-05 byte-identity preserved. Commit recorded.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3 (REFACTOR): Inline comments, CHANGELOG, docs/CONFIGURATION.md, SAFE-05 byte-identity verification</name>
  <read_first>
    - src/wanctl/queue_controller.py (post-Task-2)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md (D-17)
    - CHANGELOG.md
  </read_first>
  <files>src/wanctl/queue_controller.py, CHANGELOG.md, docs/CONFIGURATION.md</files>
  <action>
    1. **Inline comments.** Docstring for `_apply_anti_windup_if_needed`: cite canary 20260504T231334Z (1453 floor cycles, 30-155 ms·s integral range observed) AND VERIFICATION.md root-cause section AND codex MEDIUM-CODEX-2 cap-and-clamp rationale. Comment block above the new RED-branch docsis path: cite codex HIGH-CODEX-1 and the cycle-1-18 expected table (link to test class).

    2. **CHANGELOG.md** under v1.42.x:
       ```markdown
       ### Fixed
       - **Phase 201 gap-closure (rev 3, Codex cross-AI driven):** DOCSIS-aware UL mode no longer cascades current_rate from setpoint to floor under sustained RED. Replaces multiplicative factor_down=0.9 with **bounded-absolute decay** (codex Option B): step 2% of setpoint per cycle, clamped at setpoint − 10%. Cycle 1-18 expected rates explicitly tabled and asserted in tests. Adds integral anti-windup with cap-and-clamp (strictly below threshold, not halve) and synchronous headroom_state recompute. All gated on `continuous_monitoring.upload.docsis_mode: true`. Non-DOCSIS deployments are byte-identical. Closes the 1453-floor-cycle margin from canary 20260504T231334Z.
       ```

    3. **docs/CONFIGURATION.md** under Phase 201 section: document `red_decay_step_pct` (default 0.02) and `red_decay_delta_max_pct` (default 0.10) and `anti_windup_cycles` (default 60). Match D-08 restart-required pattern. **Remove** any `sustained_red_cycles` documentation if added in the prior revision.

    4. **SAFE-05 verification.** Run legacy regression slice:
       ```
       .venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestAdjust3StateRateAdjustments tests/test_queue_controller.py::TestStateTransitionSequences tests/test_queue_controller.py::TestDocsisModeByteIdentity -v
       ```
       Test count must equal pre-Task-2 count. Document count in commit message.

    5. Final commit: `refactor(201-14): doc + CHANGELOG + SAFE-05 byte-identity verified (rev 3)`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q</automated>
    <automated>grep -q "Phase 201 gap-closure (rev 3" CHANGELOG.md</automated>
    <automated>grep -q "red_decay_step_pct" docs/CONFIGURATION.md</automated>
    <automated>grep -q "red_decay_delta_max_pct" docs/CONFIGURATION.md</automated>
    <automated>grep -q "anti_windup_cycles" docs/CONFIGURATION.md</automated>
    <automated>grep -E "sustained_red_cycles" docs/CONFIGURATION.md | grep -v '^#' | wc -l | grep -qE '^0$'</automated>
    <automated>.venv/bin/ruff format --check src/wanctl/queue_controller.py</automated>
  </verify>
  <acceptance_criteria>
    - All test_queue_controller.py tests pass
    - `grep -q "canary 20260504T231334Z" src/wanctl/queue_controller.py` (root-cause traceability)
    - `grep -q "HIGH-CODEX-1" src/wanctl/queue_controller.py` (codex driver inline)
    - CHANGELOG.md mentions "rev 3" and "Codex cross-AI driven"
    - docs/CONFIGURATION.md documents all three knobs; `sustained_red_cycles` absent
    - ruff format check passes
  </acceptance_criteria>
  <done>
    Control-model amendment is documented and SAFE-05 byte-identity is verified. Commit recorded.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4 (COORDINATION VERIFICATION): Verify Plan 201-13 already dropped `sustained_red_cycles` (already coordinated in this revision pass)</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md (already revised to rev 2 during /gsd-plan-phase --reviews)
  </read_first>
  <files>(none — verification only)</files>
  <action>
    Plan 201-13 was updated to revision 2 during the same /gsd-plan-phase --reviews pass that produced this Plan 201-14 rev 3. The `sustained_red_cycles` /health field was already dropped from 201-13. This task verifies that coordination is intact (no drift between the two PLAN.md files), and is a pure read/verify task — no file edits required.

    1. Verify 201-13 frontmatter shows `revision: 2`:
       ```
       grep -E "^revision: 2" .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md
       ```
    2. Verify 201-13 does NOT serialize `sustained_red_cycles` (only deletion-context refs remain — frontmatter comment, drop-rationale, negative grep checks):
       ```
       # No `"sustained_red_cycles": int(qc_health.get(...))` or `"sustained_red_cycles": int(getattr(self, ...))` action snippets:
       grep -E '"sustained_red_cycles": int\(' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md | wc -l
       # Expected: 0
       ```
    3. Verify 201-13 documents six absorbed/new fields (3 original + 3 absorbed), not seven:
       ```
       grep -E "six.*new fields|six diagnostic|six.*Phase 201|12 Phase 201 fields" .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md | head -3
       ```

    If any of the three checks fails (drift between rev-3 of this plan and rev-2 of 201-13), STOP and replan; the executor must not proceed to Task 1 of Plan 201-13 because the two plans would target divergent /health surfaces.
  </action>
  <verify>
    <automated>grep -E '^revision: 2' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md</automated>
    <automated>grep -E '"sustained_red_cycles": int\(' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md | wc -l | tr -d '[:space:]' | grep -qE '^0$'</automated>
    <automated>grep -E "six.*new fields|12 Phase 201 fields" .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md | wc -l | tr -d '[:space:]' | grep -qE '^[1-9]'</automated>
  </verify>
  <acceptance_criteria>
    - 201-13 frontmatter shows `revision: 2`
    - `sustained_red_cycles` action snippets absent (only negative-criterion / deletion-rationale refs remain)
    - 201-13 documents 12 total Phase 201 /health fields (six existing + six new), NOT 13
  </acceptance_criteria>
  <done>
    Plan 201-13 rev 2 and Plan 201-14 rev 3 are coordinated; the deleted `sustained_red_cycles` knob is consistently absent from both planning artifacts. Executor may safely proceed to Task 1 of Plan 201-13 next.
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
Must exit 0. Cycle-1-18 table test must be green:
```
.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeReplayCanary11::test_red_burst_18_cycles_explicit_table -v
```

Static checks:
```
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/wanctl/
```
</verification>

<success_criteria>
- Bounded-absolute decay (Option B) implemented and gated on docsis_mode + setpoint band
- Cycle-1-18 expected rate table embedded in test as `EXPECTED_BY_CYCLE` dict; every cycle assertion green; floor_hit_cycles == 0 across all 18 cycles
- HIGH-CODEX-1 closed: 18-cycle replay produces zero floor hits (vs prior revision's cycle-11+ cascade)
- HIGH-CODEX-2 closed: bounded-absolute step decreases rate on every RED cycle (no first-RED-at-setpoint exception); CLAUDE.md "rate decreases immediate" preserved
- MEDIUM-CODEX-1 closed: tests at lines 3574 and 3640 explicitly updated and renamed; not silently broken
- MEDIUM-CODEX-2 closed: anti-windup cap-and-clamp lands integral STRICTLY below threshold; headroom_state recomputed synchronously; logging rate-limited via `_last_anti_windup_log_cycle`
- `sustained_red_cycles` knob deleted; Plan 201-13 coordinated to drop the corresponding /health field
- Property test (TestDocsisModeRedNonIncreaseProperty) passes 1000+ samples in BOTH docsis and legacy modes
- SAFE-05 byte-identity preserved (legacy mode TestDocsisModeByteIdentity passes)
- ruff and mypy clean; CHANGELOG and docs/CONFIGURATION.md updated
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md` per the standard template. Include: revision number (3); list of behaviors changed (bounded-absolute decay, cap-and-clamp anti-windup, deleted sustained_red_cycles); cycle-1-18 measured-rate table from test output; replay test outcome (floor_hit_cycles=0 over 18-cycle window); property test sample count + pass rate; SAFE-05 byte-identity confirmation; codex review findings closed (HIGH-CODEX-1, HIGH-CODEX-2, MEDIUM-CODEX-1, MEDIUM-CODEX-2).
</output>
