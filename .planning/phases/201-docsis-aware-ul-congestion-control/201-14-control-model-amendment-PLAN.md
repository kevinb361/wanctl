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
  - tests/test_autorate_config.py
  - tests/test_check_config.py
  - CHANGELOG.md
  - docs/CONFIGURATION.md
autonomous: true
gap_closure: true
revision: 4  # Round-3 revision — closes codex 201-REVIEWS.md round-2 HIGH-CODEX-2 (PARTIALLY-CLOSED, strict-decrease language) + MEDIUM-NEW-2 (config validators for new red-decay knobs).
revision_driver: "201-REVIEWS.md round 2 — closes HIGH-CODEX-2 (replace strict-decrease invariant text with 'immediate bounded decrease until clamp, then hold at clamp above floor') and MEDIUM-NEW-2 (add config-load validators: 0 < red_decay_step_pct <= red_decay_delta_max_pct < 1.0 AND when docsis_mode=true: setpoint_bps * (1 - red_decay_delta_max_pct) > floor_red_bps)."
requirements: [VALN-06]
tags: [phase-201, gap-closure, control-model, bounded-absolute-decay, anti-windup, tdd, docsis-gated, codex-revised, codex-round-3]

must_haves:
  truths:
    - "When docsis_mode=true AND zone=RED AND current_rate >= (setpoint_bps - delta_max_bps), RED decay is BOUNDED-ABSOLUTE — subtract a fixed step per cycle, clamp at (setpoint_bps - delta_max_bps). No multiplicative cascade. The 12 Mbit -> floor cascade observed in canary 20260504T231334Z is structurally impossible across the canary's 18-cycle longest RED burst."
    - "When current_rate < (setpoint_bps - delta_max_bps) OR docsis_mode=false: legacy multiplicative `factor_down` decay engages and enforce_rate_bounds clamps at floor_red_bps."
    - "**REV 4 (codex HIGH-CODEX-2 PARTIALLY-CLOSED closure):** The DOCSIS-mode RED-cycle invariant is now stated honestly: **immediate bounded decrease on every RED cycle until clamp, then hold at clamp above floor.** The pre-clamp regime (cycles 1-5 in the canary corpus) decreases rate by `step_bps` per cycle (CLAUDE.md spine 'rate decreases immediate' is preserved). The at-clamp regime (cycles 6+) holds rate at `clamp_bps = setpoint_bps - delta_max_bps`, which by validator-proven invariant is strictly above `floor_red_bps`. There is NO 'strict decrease on every RED cycle' claim — that text contradicted the algorithm and was removed from this plan, the test docstring, and the queue_controller.py inline comments."
    - "BLOCKER 1 invariant (preserved from prior revision): when zone=RED and docsis_mode=true, new_rate <= current_rate ALWAYS, in EVERY regime. Bounded-absolute decay cannot raise rate (max(rate-step, clamp) <= rate when rate >= clamp). Verified by a property test sampling thousands of (rate, red_streak, setpoint) tuples."
    - "Cycle-1 through cycle-18 expected post-fix rates are explicitly tabled and asserted in the replay test. floor_hit_cycles == 0 across the entire 18-cycle RED burst. Cycles 1-5 step down 240k each (immediate bounded decrease); cycles 6-18 hold at clamp 10.8M (above 8M floor)."
    - "Integral anti-windup: when docsis_mode=true AND _headroom_exhausted_streak >= anti_windup_cycles AND current_rate == floor_red_bps, the integral window is CAPPED-AND-CLAMPED to a value strictly BELOW threshold (not merely halved) AND _headroom_state is recomputed IMMEDIATELY (not deferred to next cycle) so recovery is not gated on a stuck signal. Logging is RATE-LIMITED: at most one INFO log per anti_windup_cycles trigger interval; the queryable counter `anti_windup_triggers` is the primary observability surface."
    - "Recovery still requires green_streak >= green_required (no relaxation of push-up gate)."
    - "All control-model changes are docsis_mode-gated: when docsis_mode=false, every code path returns the SAME value as before this plan (byte-identical legacy 3-state UL behavior). No link-type Python branching — gating is on `self._docsis_mode` (already YAML-driven)."
    - "Flash-wear protection preserved: last_applied_ul_rate dedup is upstream of QueueController (in WANController); this plan changes only QueueController.adjust() return values, so dedup semantics are unchanged."
    - "Existing tests at tests/test_queue_controller.py:3574 (test_red_decay_takes_rate_below_setpoint) and :3640 (test_red_immediate_decay_regardless_of_integral_state) are EXPLICITLY UPDATED with revised expectations and recorded rationale; not silently broken."
    - "**REV 4 (codex MEDIUM-NEW-2 closure):** Config-load validators reject unsafe `red_decay_step_pct` / `red_decay_delta_max_pct` values BEFORE the daemon constructs QueueController. Three invariants enforced at the same place existing autorate validators live (`autorate_config.py` Config init AND `check_config_validators.py` for offline check-config diagnostics): (a) `0 < red_decay_step_pct`; (b) `red_decay_step_pct <= red_decay_delta_max_pct`; (c) `red_decay_delta_max_pct < 1.0`; (d) when `docsis_mode=true` AND `setpoint_mbps` and `floor_mbps` are both present: `setpoint_bps * (1 - red_decay_delta_max_pct) > floor_red_bps` — i.e., the clamp must be strictly above floor, otherwise the bug returns by construction. Test cases cover above/below/at-equality boundaries (at-equality MUST reject)."
  artifacts:
    - path: src/wanctl/queue_controller.py
      provides: "Bounded-absolute RED decay (two-regime: in-setpoint-band vs below-band) + integral anti-windup with immediate headroom recompute, all docsis_mode-gated"
      contains: "_compute_rate_3state"
    - path: src/wanctl/autorate_config.py
      provides: "Config-load validators for red_decay_step_pct, red_decay_delta_max_pct, and docsis-mode clamp-above-floor invariant (codex MEDIUM-NEW-2)"
      contains: "red_decay_delta_max_pct"
    - path: src/wanctl/check_config_validators.py
      provides: "KNOWN_AUTORATE_PATHS registration + offline check-config validators mirroring the daemon-side validators (codex MEDIUM-NEW-2 — same logic, different surface)"
      contains: "red_decay_delta_max_pct"
    - path: tests/test_queue_controller.py
      provides: "TestDocsisModeBoundedAbsoluteDecay + TestDocsisModeIntegralAntiWindup + TestDocsisModeReplayCanary11 + TestDocsisModeRedNonIncreaseProperty + UPDATED TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint + UPDATED TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state"
      contains: "TestDocsisModeBoundedAbsoluteDecay"
    - path: tests/test_autorate_config.py
      provides: "TestRedDecayValidators — boundary tests for codex MEDIUM-NEW-2 (above/below/at-equality)"
      contains: "TestRedDecayValidators"
    - path: tests/test_check_config.py
      provides: "TestCheckConfigRedDecayValidators — same boundary suite at the offline-diagnostic surface"
      contains: "TestCheckConfigRedDecayValidators"
  key_links:
    - from: "src/wanctl/queue_controller.py:_compute_rate_3state RED branch"
      to: "self._docsis_mode + self._setpoint_bps + self._red_decay_step_pct + self._red_decay_delta_max_pct"
      via: "if docsis_mode and current_rate >= (setpoint - delta_max): new_rate = max(current_rate - step, setpoint - delta_max); else: legacy factor_down"
      pattern: "_red_decay_delta_max_pct|_red_decay_step_pct"
    - from: "src/wanctl/queue_controller.py:_apply_anti_windup_if_needed"
      to: "self._integral_window + self._headroom_state recompute"
      via: "cap-and-clamp integral to (threshold - 1.0) and recompute headroom_state synchronously"
      pattern: "_apply_anti_windup_if_needed"
    - from: "src/wanctl/autorate_config.py validate-on-load (Config.__init__)"
      to: "raise ConfigError when red_decay_step_pct <= 0, red_decay_step_pct > red_decay_delta_max_pct, red_decay_delta_max_pct >= 1.0, or (docsis_mode and clamp <= floor)"
      via: "validator block placed alongside existing target<warn ordering check (autorate_config.py:182-194)"
      pattern: "red_decay_delta_max_pct.*floor_red_bps"
---

<objective>
**Gap-closure Plan 2 of 4. PRIMARY DEFECT FIX. Revision 4 — closes codex round-2 PARTIALLY-CLOSED HIGH-CODEX-2 + MEDIUM-NEW-2 from 201-REVIEWS.md.**

This is the control-model amendment that closes the 1453-cycle floor-peg gap from canary 20260504T231334Z. Revision 3 (codex round 1) replaced the multiplicative-decay-with-fall-through algorithm with **bounded-absolute decay** (Option B). Codex round-2 confirmed the math is sound (independent re-derivation matches: clamp = setpoint × (1 − delta_max) = 10.8M; 18-cycle replay yields floor_hits = 0).

**Round-3 revision adds two corrections on top of rev 3:**

1. **HIGH-CODEX-2 (PARTIALLY-CLOSED) — invariant language fix.** Rev-3 plan text said "rate decreases on every RED cycle." That contradicts Option B because cycles 6+ hold at clamp. Replace the strict-decrease language with: **"immediate bounded decrease on every RED cycle until clamp, then hold at clamp above floor."** Update plan text (this objective + must_haves), the test docstring on `TestDocsisModeReplayCanary11`, and the inline comment block in `queue_controller.py:_compute_rate_3state` RED branch. The CLAUDE.md spine "rate decreases immediate" is still preserved on the pre-clamp cycles where it actually applies; the at-clamp hold is a deliberate algorithmic property (clamp by validator is strictly > floor), not an exception.

2. **MEDIUM-NEW-2 — config validators for the new red-decay knobs.** The rev-3 plan added `red_decay_step_pct` and `red_decay_delta_max_pct` as constructor params + YAML keys but did not add load-time validation. If an operator (or a future config edit) sets `red_decay_delta_max_pct = 0.99` or `red_decay_delta_max_pct = 0.50` against `setpoint_mbps = 12, floor_mbps = 8`, the clamp falls AT or BELOW floor and the original bug returns by construction (clamp = 12M × 0.50 = 6M < 8M floor → cycles 6+ hold at 6M, but enforce_rate_bounds clamps that back to floor every cycle = floor-pegging). Validators close that hole at config-load time, before QueueController is constructed. Three invariants:
   - **(a)** `0 < red_decay_step_pct`
   - **(b)** `red_decay_step_pct <= red_decay_delta_max_pct`
   - **(c)** `red_decay_delta_max_pct < 1.0`
   - **(d)** When `docsis_mode = true` AND both `setpoint_mbps` and `floor_mbps` are present in the same config block: assert `setpoint_bps × (1 − red_decay_delta_max_pct) > floor_red_bps`. At-equality MUST reject (clamp == floor would still floor-peg under cycle 6+ hold).

   Validators land in TWO places per the existing wanctl pattern (PATTERNS.md, also visible in v1.41 ARB-05 implementation):
   - `src/wanctl/autorate_config.py` — daemon-side, raises ConfigError during Config.__init__, fail-closed (daemon does not start with bad knobs).
   - `src/wanctl/check_config_validators.py` — operator-side `wanctl check-config` reports the same errors offline so they can be caught BEFORE deploy.

**Algorithm (Option B — bounded absolute decay, unchanged from rev 3):**

```
REGIME A (in-band, docsis-gated):
  IF docsis_mode AND zone == RED AND current_rate >= (setpoint - delta_max):
      step      = max(1, int(setpoint * red_decay_step_pct))      # default 2% of setpoint
      delta_max = max(1, int(setpoint * red_decay_delta_max_pct)) # default 10% of setpoint
      clamp     = setpoint - delta_max                             # validator-proven > floor
      new_rate  = max(int(current_rate - step), clamp)

REGIME B (out-of-band sustained overload):
  ELIF current_rate < (setpoint - delta_max) OR docsis_mode=false:
      new_rate = int(current_rate * factor_down)   # legacy multiplicative
      # enforce_rate_bounds clamps at floor_red_bps downstream
```

**Cycle 1-18 expected post-fix rate table (setpoint=12M, step=240_000, delta_max=1_200_000, clamp=10_800_000, floor=8_000_000):**

| Cycle | red_streak | rate (entering) | Regime | new_rate (exiting)                | Behavior label                |
|-------|------------|-----------------|--------|-----------------------------------|-------------------------------|
| 1     | 1          | 12,000,000      | A      | 11,760,000                        | immediate bounded decrease    |
| 2     | 2          | 11,760,000      | A      | 11,520,000                        | immediate bounded decrease    |
| 3     | 3          | 11,520,000      | A      | 11,280,000                        | immediate bounded decrease    |
| 4     | 4          | 11,280,000      | A      | 11,040,000                        | immediate bounded decrease    |
| 5     | 5          | 11,040,000      | A      | 10,800,000                        | reaches clamp                 |
| 6     | 6          | 10,800,000      | A      | 10,800,000 (clamp held)           | hold at clamp above floor     |
| 7-18  | 7-18       | 10,800,000      | A      | 10,800,000 (clamp held)           | hold at clamp above floor     |

**Result:** floor_hit_cycles = 0 across all 18 cycles. Validator (d) ensures `clamp = 10.8M > floor = 8M` — the at-clamp hold cannot regress to floor by construction.

**Removed from rev 3 (still removed):** `sustained_red_cycles` is **deleted**. Plan 201-13 rev 2/3 dropped the corresponding /health field. Task 4 of this plan verifies that coordination remains intact.

**Output:** ~30-50 lines of new/changed code in queue_controller.py + ~20-40 lines of new validator code in autorate_config.py + check_config_validators.py, 4 new test classes + 2 updated existing tests in test_queue_controller.py, 1 new test class in test_autorate_config.py + 1 in test_check_config.py for the validators, two new YAML keys in autorate_config.py + check_config_validators.py + configs/spectrum.yaml updated, CHANGELOG.md and docs/CONFIGURATION.md updated.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json
@src/wanctl/queue_controller.py
@src/wanctl/autorate_config.py
@src/wanctl/check_config_validators.py
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
    ...
```

`_update_integral(delta_ms)` (queue_controller.py:241-256) — returns `(integral_ms_s, state)`.

`_classify_zone_3state` recomputes `_headroom_state` based on `_last_integral_ms_s`. Anti-windup helper must update `_last_integral_ms_s` AND directly recompute `_headroom_state` synchronously.

YAML key registration: `src/wanctl/check_config_validators.py:KNOWN_AUTORATE_PATHS` — every new key MUST be added (SAFE-06 unknown-key warning).

**Validator pattern (codex MEDIUM-NEW-2, mirrors v1.41 ARB-05 ordering check):**

`autorate_config.py` already has the v1.41 ordering check at lines 182-194 that compares `target_bloat_ms < warn_bloat_ms`. The new validators land in the SAME logical block — extend that section. The same pattern is mirrored in `check_config_validators.py` for `wanctl check-config`. Both surfaces must enforce the SAME invariants (codex MEDIUM-NEW-2 wants belt + suspenders).

Daemon-side raise pattern:
```python
# autorate_config.py inside Config.__init__ or _validate(self):
if upload.get("red_decay_step_pct") is not None:
    step = float(upload["red_decay_step_pct"])
    if step <= 0:
        raise ConfigError("continuous_monitoring.upload.red_decay_step_pct must be > 0")
if upload.get("red_decay_delta_max_pct") is not None:
    dmax = float(upload["red_decay_delta_max_pct"])
    if dmax >= 1.0:
        raise ConfigError("continuous_monitoring.upload.red_decay_delta_max_pct must be < 1.0")
    if upload.get("red_decay_step_pct") is not None and float(upload["red_decay_step_pct"]) > dmax:
        raise ConfigError("red_decay_step_pct must be <= red_decay_delta_max_pct")
    # Clamp-above-floor invariant (codex MEDIUM-NEW-2 invariant d):
    if upload.get("docsis_mode") is True \
       and upload.get("setpoint_mbps") is not None \
       and upload.get("floor_mbps") is not None:
        setpoint_bps = float(upload["setpoint_mbps"]) * 1_000_000
        floor_bps    = float(upload["floor_mbps"]) * 1_000_000
        clamp_bps    = setpoint_bps * (1.0 - dmax)
        if clamp_bps <= floor_bps:
            raise ConfigError(
                f"docsis_mode requires setpoint_mbps * (1 - red_decay_delta_max_pct) > floor_mbps; "
                f"got clamp={clamp_bps/1e6:.2f} Mbps <= floor={floor_bps/1e6:.2f} Mbps. "
                f"Either reduce red_decay_delta_max_pct or raise setpoint_mbps."
            )
```

Offline-diagnostic mirror in `check_config_validators.py` follows the existing pattern there: each validator returns a list of error/warning strings; the same four invariants must be enforced with identical messages.

**Test conflicts to update (codex MEDIUM-CODEX-1, already closed in rev 3 — preserve in rev 4):**
- `tests/test_queue_controller.py:3574` — `TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint` → renamed `test_red_decay_at_setpoint_bounded_step`
- `tests/test_queue_controller.py:3640` — `TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state` → renamed `test_red_immediate_bounded_decay_under_docsis_mode`

**Coordinated drop in Plan 201-13:** Plan 201-13 was updated to revision 2 (now 3) in the same /gsd-plan-phase --reviews passes. `sustained_red_cycles` is deleted from controller AND not serialized to /health. Plan 201-13 rev 3 ALSO adds `red_decay_step_pct` and `red_decay_delta_max_pct` as runtime-state echoes in /health (codex MEDIUM-CODEX-3) — Task 4 of this plan verifies the cross-plan coordination is intact.
</interfaces>

<tdd_cycle>
RED → GREEN → REFACTOR. The cycle table in <objective> IS the spec. Validator boundary tests (codex MEDIUM-NEW-2) are separate from cycle-table tests but follow the same RED → GREEN flow.
</tdd_cycle>

<feature>
  <name>Bounded-absolute RED decay (docsis_mode-gated, two-regime)</name>
  <files>src/wanctl/queue_controller.py, tests/test_queue_controller.py</files>
  <behavior>
    Two-regime RED-branch behavior under `docsis_mode=true`:

    REGIME A — current_rate >= (setpoint_bps - delta_max_bps):
      - delta_max_bps = max(1, int(setpoint_bps * red_decay_delta_max_pct))
      - step_bps      = max(1, int(setpoint_bps * red_decay_step_pct))
      - clamp_bps     = setpoint_bps - delta_max_bps   # validator-proven > floor_red_bps
      - new_rate      = max(int(current_rate - step_bps), clamp_bps)
      - **Invariant (rev 4 wording):** "immediate bounded decrease on every RED cycle until clamp, then hold at clamp above floor". Pre-clamp: new_rate < current_rate (step_bps > 0). At/past clamp: new_rate == clamp_bps == previous current_rate (held). Validator (d) makes the at-clamp hold safe (clamp > floor).

    REGIME B — current_rate < (setpoint_bps - delta_max_bps) OR docsis_mode=false OR setpoint_bps is None:
      - new_rate = int(current_rate * factor_down)
      - enforce_rate_bounds clamps at floor_red_bps downstream.

    Combined invariant (BLOCKER 1, preserved): when zone=RED, new_rate <= current_rate ALWAYS in every regime.
  </behavior>
  <implementation>
    1. Add YAML keys `red_decay_step_pct: float = 0.02` and `red_decay_delta_max_pct: float = 0.10` to QueueController.__init__ (keyword-only). Register both in KNOWN_AUTORATE_PATHS as `continuous_monitoring.upload.red_decay_step_pct` and `continuous_monitoring.upload.red_decay_delta_max_pct`. Add to autorate_config.py schema.
    2. **DELETE** any prior-revision `sustained_red_cycles` keyword arg + attribute + YAML registration.
    3. Add to configs/spectrum.yaml under `continuous_monitoring.upload:`: `red_decay_step_pct: 0.02` and `red_decay_delta_max_pct: 0.10` (with comments explaining the cycle-1-to-18 holding behavior).
    4. Refactor RED branch in `_compute_rate_3state` (see Task 2 step 3 for verbatim code).
  </implementation>
</feature>

<feature>
  <name>Integral anti-windup with cap-and-clamp + immediate headroom recompute (docsis_mode-gated)</name>
  <files>src/wanctl/queue_controller.py, tests/test_queue_controller.py</files>
  <behavior>
    Track `self._headroom_exhausted_streak: int` — incremented every cycle `_update_integral` returns "EXHAUSTED", reset to 0 every cycle "AVAILABLE".

    When `docsis_mode=true` AND `_headroom_exhausted_streak >= anti_windup_cycles` AND `current_rate == floor_red_bps`:
      - Cap-and-clamp every entry in `self._integral_window` so the resulting integral lands at exactly `(self._integral_threshold_ms_s - 1.0)` (strictly below threshold).
      - Recompute `self._last_integral_ms_s` AND `self._headroom_state` SYNCHRONOUSLY (call `self._recompute_headroom_state()` helper).
      - Reset `self._headroom_exhausted_streak = 0`.
      - Increment `self._anti_windup_triggers` counter.
      - Rate-limited INFO log via `self._last_anti_windup_log_cycle`.
  </behavior>
  <implementation>See Task 2 step 5.</implementation>
</feature>

<feature>
  <name>Config-load validators for red-decay knobs (codex MEDIUM-NEW-2)</name>
  <files>src/wanctl/autorate_config.py, src/wanctl/check_config_validators.py, tests/test_autorate_config.py, tests/test_check_config.py</files>
  <behavior>
    Four invariants enforced at config load time, fail-closed:
      (a) `0 < red_decay_step_pct`
      (b) `red_decay_step_pct <= red_decay_delta_max_pct`
      (c) `red_decay_delta_max_pct < 1.0`
      (d) when `docsis_mode=true` AND both `setpoint_mbps` and `floor_mbps` present:
          `setpoint_bps * (1 - red_decay_delta_max_pct) > floor_red_bps`  (strict inequality; at-equality REJECTS)

    Test boundaries (per invariant):
      (a) red_decay_step_pct = 0.0 → reject; = -0.01 → reject; = 0.01 → accept.
      (b) step = 0.05, delta_max = 0.05 → accept (boundary); step = 0.06, delta_max = 0.05 → reject; step = 0.04, delta_max = 0.05 → accept.
      (c) delta_max = 1.0 → reject; = 0.999 → accept; = 1.5 → reject.
      (d) docsis_mode=true, setpoint=12, floor=8, delta_max=1/3 → clamp == 8.0 == floor → reject (at-equality);
          docsis_mode=true, setpoint=12, floor=8, delta_max=0.30 → clamp = 8.4 > 8 → accept;
          docsis_mode=true, setpoint=10, floor=8, delta_max=0.20 → clamp = 8.0 == floor → reject;
          docsis_mode=false, any combo → invariant (d) NOT enforced (legacy).
  </behavior>
  <implementation>
    1. In `autorate_config.py` Config validation (alongside existing v1.41 target<warn ordering check at ~lines 182-194), add the four-invariant block per <interfaces>. Use the project's `ConfigError` exception type (or whatever the existing target<warn check raises — match it).
    2. In `check_config_validators.py` add a parallel validator function (matches the existing pattern in the file). Same four invariants, same error message texts (so a grep finds both surfaces).
    3. Tests: in `tests/test_autorate_config.py` add class `TestRedDecayValidators` covering the boundary table above. In `tests/test_check_config.py` add `TestCheckConfigRedDecayValidators` covering the same boundaries via the offline-check surface.
  </implementation>
</feature>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (RED): Write failing tests — Option B math (cycle table + property), anti-windup cap-and-clamp, codex MEDIUM-NEW-2 validator boundaries; UPDATE tests at lines 3574 and 3640</name>
  <read_first>
    - tests/test_queue_controller.py (TestDocsisModeIntegralClassifier, TestDocsisModeSetpointClamp at lines 3517-3650 — fixture + `_make_docsis_controller` helper)
    - tests/test_queue_controller.py:3574 (TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint — UPDATE, do not silently break)
    - tests/test_queue_controller.py:3640 (TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state — UPDATE, do not silently break)
    - tests/test_autorate_config.py (find existing v1.41 ordering tests to mirror fixture style)
    - tests/test_check_config.py (find existing validator-boundary tests to mirror style)
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json (1453 floor cycles)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (HIGH-CODEX-1, HIGH-CODEX-2, MEDIUM-CODEX-1, MEDIUM-CODEX-2, MEDIUM-NEW-2)
    - src/wanctl/queue_controller.py
    - src/wanctl/autorate_config.py (current Config validation block, ~lines 182-194)
    - src/wanctl/check_config_validators.py (validator pattern in file)
  </read_first>
  <files>tests/test_queue_controller.py, tests/test_autorate_config.py, tests/test_check_config.py</files>
  <action>
    **Part A — Update two existing tests (codex MEDIUM-CODEX-1):**

    1. `TestDocsisModeSetpointClamp::test_red_decay_takes_rate_below_setpoint` at line 3574 → rename `test_red_decay_at_setpoint_bounded_step`; assert rate goes from 12_000_000 to 11_760_000 on first RED at setpoint. Docstring cites canary 20260504T231334Z and codex MEDIUM-CODEX-1.

    2. `TestRedFastTripUnchangedDocsisMode::test_red_immediate_decay_regardless_of_integral_state` at line 3640 → rename `test_red_immediate_bounded_decay_under_docsis_mode`; assert rate == 11_760_000 (bounded-absolute step, NOT factor_down=0.9). Docstring updated for **rev-4 invariant wording**: "Immediate bounded decrease on first RED cycle (pre-clamp regime). Cycles 6+ would HOLD at clamp 10.8M; that is the at-clamp regime, not a violation of the spine — see TestDocsisModeReplayCanary11 for the full table."

    Add a NEW test in the SAME `TestRedFastTripUnchangedDocsisMode` class:
       ```python
       def test_red_immediate_decay_legacy_mode_unchanged(self):
           # Byte-identity check: docsis_mode=False keeps multiplicative factor_down.
           ctrl = _make_docsis_controller(docsis_mode=False, setpoint_bps=None)
           ctrl.current_rate = 12_000_000
           zone, rate, _ = ctrl.adjust(22.0, 22.0 + 50.0, target_delta=5.0, warn_delta=15.0)
           assert zone == "RED"
           assert rate == int(12_000_000 * ctrl.factor_down)  # 10_800_000
       ```

    **Part B — Add four new test classes in tests/test_queue_controller.py AFTER `TestDocsisModeCakeCorroborator`:**

    `TestDocsisModeBoundedAbsoluteDecay` (Option B regimes):
      - test_regime_a_at_setpoint_steps_down_240k: rate=12M → 11_760_000.
      - test_regime_a_above_setpoint_steps_down_240k: rate=15M → 14_760_000.
      - test_regime_a_clamps_at_setpoint_minus_delta_max: rate=10_900_000 → max(10_660_000, 10_800_000) = 10_800_000.
      - test_regime_a_holds_at_clamp: rate=10_800_000 → 10_800_000 (at-clamp hold).
      - test_regime_b_below_band_falls_through_to_factor_down: rate=10_500_000 → int(10_500_000 * 0.9) = 9_450_000.
      - test_regime_c_legacy_mode_unchanged: docsis_mode=False, rate=12M → int(12M * 0.9) = 10_800_000.
      - test_no_setpoint_falls_through_to_legacy: docsis_mode=True, setpoint=None → legacy.

    `TestDocsisModeRedNonIncreaseProperty` (codex property test):
      - test_red_never_increases_rate_docsis_mode: 1000+ random tuples, assert new_rate <= current_rate.
      - test_red_never_increases_rate_legacy_mode: same, docsis_mode=False; new_rate == int(rate * factor_down).

    `TestDocsisModeIntegralAntiWindup` (codex MEDIUM-CODEX-2 cap-and-clamp):
      - test_headroom_exhausted_streak_increments
      - test_headroom_exhausted_streak_resets_on_available
      - test_anti_windup_caps_integral_below_threshold (assert `abs(_last_integral_ms_s - (threshold - 1.0)) < 0.01`)
      - test_anti_windup_recomputes_headroom_state_synchronously (EXHAUSTED → AVAILABLE same call)
      - test_anti_windup_triggers_counter_increments
      - test_anti_windup_log_rate_limited (only one INFO log per anti_windup_cycles interval)
      - test_anti_windup_does_not_fire_above_floor
      - test_anti_windup_legacy_mode_no_op

    `TestDocsisModeReplayCanary11` (cycle 1-18 explicit table):
      - test_red_burst_18_cycles_explicit_table: assert exact rate for each cycle 1..18 against EXPECTED_BY_CYCLE dict (per <objective> table). **Class docstring (rev 4 wording fix, codex HIGH-CODEX-2):** "Cycles 1-5 = immediate bounded decrease (240k step); cycles 6-18 = hold at clamp 10.8M, above 8M floor. The at-clamp hold is by design (validator (d) ensures clamp > floor); it is NOT a violation of the CLAUDE.md 'rate decreases immediate' spine, which applies to RED detection latency on the pre-clamp cycles where it is observable."
      - test_red_burst_18_cycles_no_floor_hits_via_adjust (full integration; floor_hit_cycles stays 0)
      - test_below_band_overload_falls_through_legacy

    **Part C — codex MEDIUM-NEW-2 validator boundary tests:**

    In `tests/test_autorate_config.py` add class `TestRedDecayValidators` covering all 4 invariants × 3 boundaries each (above / at / below), per the boundary table in <feature> "Config-load validators". Each test constructs a Config dict with the relevant upload block and asserts EITHER `Config(...)` raises (or its module-level loader raises) for the reject cases OR loads successfully for the accept cases. Specifically include:

    - test_step_pct_must_be_positive (0.0, -0.01 reject; 0.01 accept)
    - test_step_pct_must_be_le_delta_max (step=0.05/dmax=0.05 accept; step=0.06/dmax=0.05 reject; step=0.04/dmax=0.05 accept)
    - test_delta_max_must_be_lt_one (1.0 reject; 0.999 accept; 1.5 reject)
    - test_docsis_mode_clamp_must_exceed_floor (docsis_mode=true, setpoint=12, floor=8, dmax=1/3 reject [clamp == floor]; dmax=0.30 accept; setpoint=10, floor=8, dmax=0.20 reject [clamp == floor])
    - test_docsis_mode_false_skips_clamp_invariant (docsis_mode=false, dmax=0.99 → accept because invariant (d) only applies under docsis_mode)
    - test_at_equality_clamp_equals_floor_rejects (codex MEDIUM-NEW-2 explicit "at-equality must reject")

    In `tests/test_check_config.py` add class `TestCheckConfigRedDecayValidators` covering the SAME boundaries via the offline-check surface. Same six tests, but invoking the check_config_validators function rather than constructing Config directly.

    All Part B + Part C tests must FAIL before Task 2 lands. Part A tests will also fail.

    Commit: `test(201-14): rev-4 update conflicting tests + add bounded-absolute decay tests + cycle table + property test + anti-windup cap-and-clamp tests + codex MEDIUM-NEW-2 validator boundary tests`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeBoundedAbsoluteDecay tests/test_queue_controller.py::TestDocsisModeRedNonIncreaseProperty tests/test_queue_controller.py::TestDocsisModeIntegralAntiWindup tests/test_queue_controller.py::TestDocsisModeReplayCanary11 -v 2>&1 | grep -E 'failed|FAILED' | wc -l | tr -d '[:space:]' | grep -qE '^[1-9][0-9]*$'</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_autorate_config.py::TestRedDecayValidators -v 2>&1 | grep -E 'failed|FAILED' | wc -l | tr -d '[:space:]' | grep -qE '^[1-9][0-9]*$'</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_check_config.py::TestCheckConfigRedDecayValidators -v 2>&1 | grep -E 'failed|FAILED' | wc -l | tr -d '[:space:]' | grep -qE '^[1-9][0-9]*$'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "class TestDocsisModeBoundedAbsoluteDecay:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModeRedNonIncreaseProperty:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModeIntegralAntiWindup:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestDocsisModeReplayCanary11:" tests/test_queue_controller.py` == 1
    - `grep -c "class TestRedDecayValidators:" tests/test_autorate_config.py` == 1
    - `grep -c "class TestCheckConfigRedDecayValidators:" tests/test_check_config.py` == 1
    - `grep -q "test_red_decay_at_setpoint_bounded_step" tests/test_queue_controller.py`
    - `grep -q "test_red_immediate_bounded_decay_under_docsis_mode" tests/test_queue_controller.py`
    - `grep -q "test_red_immediate_decay_legacy_mode_unchanged" tests/test_queue_controller.py`
    - `grep -q "test_red_burst_18_cycles_explicit_table" tests/test_queue_controller.py`
    - `grep -q "EXPECTED_BY_CYCLE" tests/test_queue_controller.py`
    - **Rev-4 docstring/invariant text update:** `grep -q "hold at clamp above floor" tests/test_queue_controller.py` (codex HIGH-CODEX-2 wording fix in TestDocsisModeReplayCanary11 docstring)
    - `grep -q "test_at_equality_clamp_equals_floor_rejects" tests/test_autorate_config.py` (codex MEDIUM-NEW-2 explicit boundary)
    - `grep -q "test_docsis_mode_clamp_must_exceed_floor" tests/test_autorate_config.py`
    - `grep -qE "test_red_decay_takes_rate_below_setpoint" tests/test_queue_controller.py` returns NO match (old test name removed)
    - `grep -qE "test_red_immediate_decay_regardless_of_integral_state" tests/test_queue_controller.py` returns NO match (old test name removed)
    - **Negative wording check (codex HIGH-CODEX-2):** `grep -E "rate decreases on every RED cycle" tests/test_queue_controller.py` returns 0 lines (old strict-decrease language removed)
    - Total NEW test count >= 25 (7+2+8+3 in queue_controller + 6 in autorate_config + 6 in check_config = 32 minimum)
    - Most/all of those tests FAIL when run pre-implementation
  </acceptance_criteria>
  <done>
    Six new test classes exist (4 in test_queue_controller, 1 each in test_autorate_config + test_check_config); two existing tests updated and renamed; >= 25 tests total are RED. Rev-4 invariant wording installed in test docstrings. Commit recorded.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (GREEN): Implement bounded-absolute decay + anti-windup cap-and-clamp + codex MEDIUM-NEW-2 validators; remove `sustained_red_cycles`; register two new YAML keys</name>
  <read_first>
    - src/wanctl/queue_controller.py (Task 1 tests now exist and FAIL)
    - src/wanctl/autorate_config.py (lines 182-194 for ordering-check pattern)
    - src/wanctl/check_config_validators.py (lines 28-180 for KNOWN_AUTORATE_PATHS + validator pattern)
    - src/wanctl/wan_controller.py:402-437 (UL QueueController constructor wiring)
    - configs/spectrum.yaml (lines 67-89)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (round-2 NEW + round-1 HIGH/MEDIUM)
  </read_first>
  <files>src/wanctl/queue_controller.py, src/wanctl/autorate_config.py, src/wanctl/check_config_validators.py, src/wanctl/wan_controller.py, configs/spectrum.yaml</files>
  <action>
    Implement Option B + anti-windup cap-and-clamp + codex MEDIUM-NEW-2 validators. Goal: all Task 1 tests PASS, no existing test regresses.

    1. **queue_controller.py constructor** — keyword-only params:
       ```python
       red_decay_step_pct: float = 0.02,          # NEW (Option B step)
       red_decay_delta_max_pct: float = 0.10,     # NEW (Option B clamp distance)
       anti_windup_cycles: int = 60,              # PRESERVED
       # sustained_red_cycles REMOVED
       ```
       Store as `self._red_decay_step_pct`, `self._red_decay_delta_max_pct`, `self._anti_windup_cycles`. Init `self._headroom_exhausted_streak: int = 0`, `self._anti_windup_triggers: int = 0`, `self._last_anti_windup_log_cycle: int = -10**9`, `self._cycle_count: int = 0`.

    2. **queue_controller.py `_update_integral`** — at end, update streak per <feature>.

    3. **queue_controller.py `_compute_rate_3state` RED branch** — replace unconditional factor_down with Option B:
       ```python
       if self.red_streak >= 1:
           self._yellow_decay_streak = 0
           if self._docsis_mode and self._setpoint_bps is not None:
               delta_max_bps = max(1, int(self._setpoint_bps * self._red_decay_delta_max_pct))
               clamp_bps = self._setpoint_bps - delta_max_bps
               if self.current_rate >= clamp_bps:
                   # REGIME A: bounded-absolute decay (codex Option B, HIGH-CODEX-1).
                   # Rev-4 invariant (codex HIGH-CODEX-2): immediate bounded decrease on every
                   # RED cycle until clamp, then hold at clamp above floor. Pre-clamp cycles
                   # decrease rate by step_bps; at-clamp cycles hold (clamp > floor by validator (d)).
                   # Cycle table cycles 1-18 holds floor_hit_cycles=0 against canary 20260504T231334Z.
                   step_bps = max(1, int(self._setpoint_bps * self._red_decay_step_pct))
                   return max(int(self.current_rate - step_bps), clamp_bps)
           # REGIME B (below band) AND REGIME C (legacy):
           return int(self.current_rate * self.factor_down)
       ```

    4. **queue_controller.py `_recompute_headroom_state`** — new helper per <feature>.

    5. **queue_controller.py `_apply_anti_windup_if_needed`** — new helper per <feature>:
       ```python
       def _apply_anti_windup_if_needed(self) -> None:
           if not self._docsis_mode:
               return
           if self._headroom_exhausted_streak < self._anti_windup_cycles:
               return
           if self.current_rate != self.floor_red_bps:
               return
           target_ms_s = max(0.0, self._integral_threshold_ms_s - 1.0)
           maxlen = self._integral_window.maxlen or 1
           per_sample = (target_ms_s / 0.05) / maxlen
           self._integral_window.clear()
           for _ in range(maxlen):
               self._integral_window.append(per_sample)
           self._last_integral_ms_s = sum(self._integral_window) * 0.05
           self._recompute_headroom_state()
           self._headroom_exhausted_streak = 0
           self._anti_windup_triggers += 1
           if self._cycle_count - self._last_anti_windup_log_cycle >= self._anti_windup_cycles:
               self._logger.info(
                   "[ANTI-WINDUP] %s integral capped to %.2f ms*s after %d EXHAUSTED cycles at floor",
                   self.name, target_ms_s, self._anti_windup_cycles,
               )
               self._last_anti_windup_log_cycle = self._cycle_count
       ```

    6. **queue_controller.py `adjust()`** — between `_update_integral` and `_classify_zone_3state`:
       ```python
       self._cycle_count += 1
       self._apply_anti_windup_if_needed()
       ```

    7. **autorate_config.py schema + validators (codex MEDIUM-NEW-2):**
       - Add `red_decay_step_pct` (float, default 0.02) and `red_decay_delta_max_pct` (float, default 0.10) to upload schema. **REMOVE `sustained_red_cycles`** if previously added. Restart-required (D-08).
       - Add the four-invariant validator block per <interfaces> alongside the existing v1.41 target<warn ordering check at ~lines 182-194. Use the same exception type the ordering check raises (read the file to confirm — likely `ConfigError`). Each violation must include the offending key name and the offending value in the message.

    8. **check_config_validators.py:**
       - Add to KNOWN_AUTORATE_PATHS:
         ```python
         "continuous_monitoring.upload.red_decay_step_pct",
         "continuous_monitoring.upload.red_decay_delta_max_pct",
         ```
         **REMOVE `continuous_monitoring.upload.sustained_red_cycles`** if present.
       - Add a parallel validator (mirrors the autorate_config.py block) that yields the same four error strings into the offline-check report. Match the existing function signature pattern in the file.

    9. **wan_controller.py** — wire new keys into upload QueueController constructor at lines 402-437:
       ```python
       red_decay_step_pct=float(getattr(config, "red_decay_step_pct", 0.02)),
       red_decay_delta_max_pct=float(getattr(config, "red_decay_delta_max_pct", 0.10)),
       anti_windup_cycles=int(getattr(config, "anti_windup_cycles", 60)),
       ```
       Add explicit-presence flags `_red_decay_step_pct_explicit`, `_red_decay_delta_max_pct_explicit`, `_anti_windup_cycles_explicit`. **REMOVE `sustained_red_cycles=` if present.**

    10. **configs/spectrum.yaml** — under `continuous_monitoring.upload:`, add:
        ```yaml
            # Phase 201 gap-closure rev 4 (Codex Option B for HIGH-CODEX-1; rev-4 wording for HIGH-CODEX-2):
            # Bounded-absolute RED decay. Pre-clamp cycles 1-5: immediate bounded decrease
            # (step=2% of setpoint = 240k for setpoint=12M). At-clamp cycles 6+: hold at
            # clamp = setpoint - delta_max where delta_max=10% (clamp=10.8M for setpoint=12M).
            # Validator (d) ensures clamp > floor (codex MEDIUM-NEW-2): 10.8M > 8M floor.
            # floor_hit_cycles=0 across the canary 20260504T231334Z 18-cycle RED burst.
            red_decay_step_pct: 0.02
            red_decay_delta_max_pct: 0.10
            # 60 cycles = 3s; cap-and-clamp integral STRICTLY BELOW threshold (codex MEDIUM-CODEX-2).
            anti_windup_cycles: 60
        ```
        **REMOVE `sustained_red_cycles: 8`** if present.

    11. Run pytest. All Task 1 tests must PASS. Commit: `feat(201-14): rev-4 bounded-absolute RED decay + anti-windup cap-and-clamp + codex MEDIUM-NEW-2 validators; closes round-2 HIGH-CODEX-2 (wording) + MEDIUM-NEW-2 (validators)`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeBoundedAbsoluteDecay tests/test_queue_controller.py::TestDocsisModeRedNonIncreaseProperty tests/test_queue_controller.py::TestDocsisModeIntegralAntiWindup tests/test_queue_controller.py::TestDocsisModeReplayCanary11 -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_autorate_config.py::TestRedDecayValidators -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_check_config.py::TestCheckConfigRedDecayValidators -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeSetpointClamp::test_red_decay_at_setpoint_bounded_step tests/test_queue_controller.py::TestRedFastTripUnchangedDocsisMode -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py tests/test_check_config.py -q</automated>
    <automated>.venv/bin/ruff check src/wanctl/queue_controller.py src/wanctl/autorate_config.py src/wanctl/check_config_validators.py src/wanctl/wan_controller.py</automated>
    <automated>.venv/bin/mypy src/wanctl/queue_controller.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "red_decay_step_pct: float = 0.02" src/wanctl/queue_controller.py`
    - `grep -q "red_decay_delta_max_pct: float = 0.10" src/wanctl/queue_controller.py`
    - `grep -q "anti_windup_cycles: int = 60" src/wanctl/queue_controller.py`
    - **`sustained_red_cycles` removed**: `grep -E "sustained_red_cycles" src/wanctl/queue_controller.py src/wanctl/autorate_config.py src/wanctl/check_config_validators.py src/wanctl/wan_controller.py | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^0$'`
    - `grep -q "self._red_decay_step_pct" src/wanctl/queue_controller.py`
    - `grep -q "self._red_decay_delta_max_pct" src/wanctl/queue_controller.py`
    - `grep -q "_recompute_headroom_state" src/wanctl/queue_controller.py`
    - `grep -q "_apply_anti_windup_if_needed" src/wanctl/queue_controller.py`
    - `grep -q "_last_anti_windup_log_cycle" src/wanctl/queue_controller.py`
    - `grep -q "self._integral_threshold_ms_s - 1.0" src/wanctl/queue_controller.py`
    - `grep -q "continuous_monitoring.upload.red_decay_step_pct" src/wanctl/check_config_validators.py`
    - `grep -q "continuous_monitoring.upload.red_decay_delta_max_pct" src/wanctl/check_config_validators.py`
    - `grep -q "red_decay_step_pct: 0.02" configs/spectrum.yaml`
    - `grep -q "red_decay_delta_max_pct: 0.10" configs/spectrum.yaml`
    - `grep -q "anti_windup_cycles: 60" configs/spectrum.yaml`
    - **codex MEDIUM-NEW-2 validators present in BOTH surfaces:**
      - `grep -qE "red_decay_step_pct.*must be > 0|red_decay_step_pct.*0" src/wanctl/autorate_config.py`
      - `grep -qE "red_decay_delta_max_pct.*< 1\\.0|red_decay_delta_max_pct.*1\\.0" src/wanctl/autorate_config.py`
      - `grep -qE "setpoint.*red_decay_delta_max_pct.*floor|clamp.*floor" src/wanctl/autorate_config.py`
      - Same three patterns in `src/wanctl/check_config_validators.py`
    - All four new test_queue_controller classes pass; both updated tests pass; both validator-test classes pass
    - `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeReplayCanary11::test_red_burst_18_cycles_explicit_table -v` exits 0
    - Hot-path slice passes; no test count shrink
    - SAFE-05 byte-identity: legacy mode tests still pass with same count as pre-Task-2
    - ruff and mypy clean
  </acceptance_criteria>
  <done>
    Option B implemented; cycle 1-18 table green; anti-windup cap-and-clamp synchronously recomputes headroom; codex MEDIUM-NEW-2 validators reject all four invariant violations at config-load time on both surfaces; existing tests updated; SAFE-05 byte-identity preserved. Commit recorded.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3 (REFACTOR): Inline comments updated for rev-4 invariant wording (codex HIGH-CODEX-2); CHANGELOG; docs/CONFIGURATION.md including codex MEDIUM-NEW-2 validator semantics; SAFE-05 byte-identity verification</name>
  <read_first>
    - src/wanctl/queue_controller.py (post-Task-2)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md (D-17)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (HIGH-CODEX-2 wording, MEDIUM-NEW-2 validator semantics)
    - CHANGELOG.md
  </read_first>
  <files>src/wanctl/queue_controller.py, CHANGELOG.md, docs/CONFIGURATION.md</files>
  <action>
    1. **Inline comments** — update the comment block above the new RED-branch docsis path to use the rev-4 wording (codex HIGH-CODEX-2): "immediate bounded decrease on every RED cycle until clamp, then hold at clamp above floor". DO NOT use the phrase "rate decreases on every RED cycle" anywhere — that text is contradicted by Option B. Cite codex HIGH-CODEX-1 (Option B math) AND HIGH-CODEX-2 (wording fix) AND MEDIUM-NEW-2 (validator (d) makes the at-clamp hold safe).

    2. Docstring for `_apply_anti_windup_if_needed`: cite canary 20260504T231334Z (1453 floor cycles, 30-155 ms*s integral range observed) AND VERIFICATION.md root-cause section AND codex MEDIUM-CODEX-2 cap-and-clamp rationale.

    3. **CHANGELOG.md** under v1.42.x:
       ```markdown
       ### Fixed
       - **Phase 201 gap-closure (rev 4, Codex round-2 driven):** DOCSIS-aware UL mode no longer cascades current_rate from setpoint to floor under sustained RED. Replaces multiplicative factor_down=0.9 with **bounded-absolute decay** (codex Option B): step 2% of setpoint per cycle, clamped at setpoint − 10%. Invariant (rev-4 wording, codex HIGH-CODEX-2): immediate bounded decrease on every RED cycle until clamp, then hold at clamp above floor. Cycle 1-18 expected rates explicitly tabled and asserted. Adds integral anti-windup with cap-and-clamp (strictly below threshold, not halve) and synchronous headroom_state recompute. Adds config-load validators (codex MEDIUM-NEW-2) that reject unsafe red-decay knobs: 0 < step_pct, step_pct ≤ delta_max_pct < 1.0, and (under docsis_mode) clamp must be strictly > floor. All control changes gated on `continuous_monitoring.upload.docsis_mode: true`. Non-DOCSIS deployments are byte-identical. Closes the 1453-floor-cycle margin from canary 20260504T231334Z.
       ```

    4. **docs/CONFIGURATION.md** under Phase 201 section: document `red_decay_step_pct` (default 0.02), `red_decay_delta_max_pct` (default 0.10), and `anti_windup_cycles` (default 60). Match D-08 restart-required pattern. Add a "Validation" subsection documenting the four invariants enforced at config load (codex MEDIUM-NEW-2):
       - `red_decay_step_pct` must be > 0
       - `red_decay_step_pct` must be ≤ `red_decay_delta_max_pct`
       - `red_decay_delta_max_pct` must be < 1.0
       - When `docsis_mode: true`: `setpoint_mbps × (1 − red_decay_delta_max_pct) > floor_mbps` (strict; at-equality rejects). Include a worked example: setpoint=12, floor=8 → max safe `red_decay_delta_max_pct < 1/3 = 0.333…`.
       **Remove** any `sustained_red_cycles` documentation if present.

    5. **SAFE-05 byte-identity verification.** Run legacy regression slice:
       ```
       .venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestAdjust3StateRateAdjustments tests/test_queue_controller.py::TestStateTransitionSequences tests/test_queue_controller.py::TestDocsisModeByteIdentity -v
       ```
       Test count must equal pre-Task-2 count. Document count in commit message.

    6. Final commit: `refactor(201-14): rev-4 docs + CHANGELOG + invariant wording (codex HIGH-CODEX-2) + SAFE-05 byte-identity verified`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q</automated>
    <automated>grep -q "Phase 201 gap-closure (rev 4" CHANGELOG.md</automated>
    <automated>grep -q "red_decay_step_pct" docs/CONFIGURATION.md</automated>
    <automated>grep -q "red_decay_delta_max_pct" docs/CONFIGURATION.md</automated>
    <automated>grep -q "anti_windup_cycles" docs/CONFIGURATION.md</automated>
    <automated>grep -qE "clamp.*floor|setpoint.*delta_max.*floor" docs/CONFIGURATION.md</automated>
    <automated>grep -q "hold at clamp above floor" src/wanctl/queue_controller.py</automated>
    <automated>grep -E "rate decreases on every RED cycle" src/wanctl/queue_controller.py | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^0$'</automated>
    <automated>grep -E "sustained_red_cycles" docs/CONFIGURATION.md | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^0$'</automated>
    <automated>.venv/bin/ruff format --check src/wanctl/queue_controller.py</automated>
  </verify>
  <acceptance_criteria>
    - All test_queue_controller.py tests pass
    - `grep -q "canary 20260504T231334Z" src/wanctl/queue_controller.py`
    - `grep -q "HIGH-CODEX-1" src/wanctl/queue_controller.py`
    - **Rev-4 wording (codex HIGH-CODEX-2):** `grep -q "hold at clamp above floor" src/wanctl/queue_controller.py`
    - **Rev-4 negative wording check:** `grep -E "rate decreases on every RED cycle" src/wanctl/queue_controller.py` returns 0 lines
    - CHANGELOG.md mentions "rev 4" and "Codex round-2 driven" and "MEDIUM-NEW-2"
    - docs/CONFIGURATION.md documents all three knobs and the four-invariant validator section; `sustained_red_cycles` absent
    - ruff format check passes
  </acceptance_criteria>
  <done>
    Control-model amendment is documented with rev-4 wording correction; codex MEDIUM-NEW-2 validator semantics surfaced in operator docs; SAFE-05 byte-identity preserved. Commit recorded.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4 (COORDINATION VERIFICATION): Verify Plan 201-13 rev 3 coordinated drops AND adds the two REV-3 active-knob /health fields</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md (rev 3)
  </read_first>
  <files>(none — verification only)</files>
  <action>
    Plan 201-13 was updated to revision 3 during the same /gsd-plan-phase --reviews round-3 pass that produced this Plan 201-14 rev 4. Two coordination items must hold:

    1. `sustained_red_cycles` /health field is NOT serialized in 201-13 (carried over from rev 2).
    2. `red_decay_step_pct` AND `red_decay_delta_max_pct` ARE serialized in 201-13 as runtime-state echoes (codex MEDIUM-CODEX-3 active-knob proof for canary preflight in Plan 201-15 rev 3).

    Verify:
    1. `grep -E "^revision: 3" .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md`
    2. `grep -E '"sustained_red_cycles": (int|float)\(' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md` returns 0 lines (only deletion-context refs in negative criteria allowed).
    3. `grep -q '"red_decay_step_pct": float' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md` AND `grep -q '"red_decay_delta_max_pct": float' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md` — both REV-3 active-knob serialization snippets are present.

    If any of the three checks fails, STOP and replan; the executor must not proceed to Task 1 of Plan 201-13 because the two plans would target divergent /health surfaces.
  </action>
  <verify>
    <automated>grep -E '^revision: 3' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md</automated>
    <automated>grep -E '"sustained_red_cycles": (int|float)\(' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md | wc -l | tr -d '[:space:]' | grep -qE '^0$'</automated>
    <automated>grep -q '"red_decay_step_pct": float' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md</automated>
    <automated>grep -q '"red_decay_delta_max_pct": float' .planning/phases/201-docsis-aware-ul-congestion-control/201-13-health-diagnostic-extension-PLAN.md</automated>
  </verify>
  <acceptance_criteria>
    - 201-13 frontmatter shows `revision: 3`
    - `sustained_red_cycles` action snippets absent from 201-13
    - `red_decay_step_pct` and `red_decay_delta_max_pct` serialization snippets PRESENT in 201-13 (REV-3 active-knob, codex MEDIUM-CODEX-3)
  </acceptance_criteria>
  <done>
    Plan 201-13 rev 3 and Plan 201-14 rev 4 are coordinated. Executor may safely proceed to Task 1 of Plan 201-13 next.
  </done>
</task>

</tasks>

<verification>
Full hot-path slice + Phase 201 surfaces + new validator surfaces:
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
- HIGH-CODEX-1 closed (round 1, preserved)
- **HIGH-CODEX-2 PARTIALLY-CLOSED → CLOSED (round 2, rev 4):** invariant wording is "immediate bounded decrease on every RED cycle until clamp, then hold at clamp above floor"; old strict-decrease language eliminated from plan / docstrings / inline comments
- MEDIUM-CODEX-1 closed (round 1, preserved)
- MEDIUM-CODEX-2 closed (round 1, preserved)
- **MEDIUM-NEW-2 closed (round 2, rev 4):** four config-load validators reject unsafe red-decay knobs at both autorate_config.py and check_config_validators.py surfaces; at-equality clamp == floor REJECTS; boundary tests cover above/at/below for each invariant
- `sustained_red_cycles` knob remains deleted; Plan 201-13 rev 3 coordinated to drop the corresponding /health field AND add the two REV-3 active-knob /health fields
- Property test passes 1000+ samples in BOTH docsis and legacy modes
- SAFE-05 byte-identity preserved
- ruff and mypy clean; CHANGELOG and docs/CONFIGURATION.md updated
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md` per the standard template. Include: revision number (4); list of behaviors changed (bounded-absolute decay, cap-and-clamp anti-windup, codex MEDIUM-NEW-2 validators); cycle-1-18 measured-rate table from test output; replay test outcome (floor_hit_cycles=0 over 18-cycle window); property test sample count + pass rate; validator boundary test count; SAFE-05 byte-identity confirmation; codex review findings closed (HIGH-CODEX-1 carried, HIGH-CODEX-2 fully closed by wording fix, MEDIUM-CODEX-1/2 carried, MEDIUM-NEW-2 closed by validators).
</output>
</content>
</invoke>