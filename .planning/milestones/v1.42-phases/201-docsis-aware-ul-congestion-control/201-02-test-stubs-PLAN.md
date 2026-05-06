---
phase: 201-docsis-aware-ul-congestion-control
plan: 02
type: tdd
wave: 0
depends_on: [01]
files_modified:
  - tests/test_queue_controller.py
  - tests/test_autorate_config.py
  - tests/test_check_config.py
  - tests/test_wan_controller.py
  - tests/test_phase200_canary_script.py
  - tests/test_phase_201_replay.py
  - tests/test_phase201_predeploy_gate.py
autonomous: true
requirements: [VALN-06]
tags: [phase-201, wave-0, tdd, validation, nyquist]

must_haves:
  truths:
    - "Every Phase 201 production-code task in Waves 1-3 has a failing test that defines its expected behavior"
    - "RED state of TDD cycle is committed before any production code runs (anti-shallow-execution gate)"
    - "Test names map 1:1 to RESEARCH.md Wave 0 Gaps and Per-Task Verification Map"
  artifacts:
    - path: tests/test_queue_controller.py
      provides: "TestDocsisModeIntegralClassifier, TestDocsisModeSetpointClamp, TestDocsisModeCakeCorroborator, TestDocsisModeByteIdentity, TestRedFastTripUnchangedDocsisMode, TestDocsisModeAboveSetpointYellowPulldown (REVIEWS MED-4), TestDocsisModeFloorHitCounter (REVIEWS HIGH-5)"
      contains: "class TestDocsisModeIntegralClassifier"
    - path: tests/test_autorate_config.py
      provides: "TestPhase201Schema, TestSafe06Phase201KeysKnown"
      contains: "class TestPhase201Schema"
    - path: tests/test_check_config.py
      provides: "TestDocsisModeValidation"
      contains: "class TestDocsisModeValidation"
    - path: tests/test_wan_controller.py
      provides: "TestPhase201HealthAdditive (incl. floor_hit_cycles_total + tightened setpoint_mbps semantics per REVIEWS HIGH-5/LOW-1), TestPhase201FlashWear, TestSigusr1ReloadScopePhase201"
      contains: "class TestPhase201HealthAdditive"
    - path: tests/test_phase200_canary_script.py
      provides: "TestPhase201Preflight"
      contains: "class TestPhase201Preflight"
    - path: tests/test_phase_201_replay.py
      provides: "TestAttempt3ReplayWithDocsisMode, TestLegacyByteIdentity"
      contains: "class TestAttempt3ReplayWithDocsisMode"
    - path: tests/test_phase201_predeploy_gate.py
      provides: "TestPredeployGate (smoke skeleton; full content in Plan 201-07)"
      contains: "class TestPredeployGate"
  key_links:
    - from: "tests/test_queue_controller.py"
      to: "tests/fixtures/phase201_replay_corpus.py"
      via: "from tests.fixtures.phase201_replay_corpus import synthesize_sustained_load_trace, synthesize_idle_trace"
      pattern: "phase201_replay_corpus"
    - from: "tests/test_phase_201_replay.py"
      to: "tests/fixtures/phase201_replay_corpus.py"
      via: "load_attempt3_trace fixture"
      pattern: "load_attempt3_trace"
---

<objective>
Wave 0 Nyquist anchor: write the failing-test scaffolding for every Phase 201 production-code change in Waves 1–3. Each test class anchors a behavior that a later plan must satisfy. Tests are intentionally RED at the end of this plan — they make implementation tasks impossible to skip.

Per VALIDATION.md `Wave 0 Requirements`: no `type: execute` task may write production code under `src/wanctl/queue_controller.py` or `src/wanctl/wan_controller.py` until the corresponding test stub exists. This plan creates those stubs.

**Strict RED contract (REVIEWS HIGH-3, 2026-05-04):** Wave 0 stubs MUST use `pytest.xfail("Wave 0 stub — Plan NN", strict=True)` or `pytest.fail("Wave 0 stub — must be implemented in Plan NN before this test runs")`. `pytest.skip(...)` is FORBIDDEN for stubs that anchor a real implementation contract — skipped tests don't enforce implementation, so a phase could "pass green" while leaving production code uncovered. The only exception is when the test's *symbol target* literally cannot be imported yet (e.g. predeploy gate script before Plan 07) — in that case `pytest.skip(...)` is allowed at the FUNCTION level only, but the stub must be REMOVED in the implementing plan (acceptance grep `grep -c 'Wave 0 stub' tests/test_*.py` returns 0 after that plan completes).

**New test stubs added in this revision (REVIEWS HIGH-5, MED-4):**
- `TestDocsisModeFloorHitCounter::test_floor_hit_counter_increments_when_rate_hits_floor` (Plan 04 contract — runtime counter for cycle-fidelity VALN-06 evidence; closes the 1 Hz vs 50ms cadence gap Codex flagged).
- `TestPhase201HealthAdditive::test_floor_hit_cycles_total_runtime_field_present` (Plan 05 contract — additive `/health.wans[].upload.floor_hit_cycles_total`).
- `TestDocsisModeSetpointClamp::test_above_setpoint_yellow_pulls_to_setpoint` (Plan 04 contract — when `current_rate > setpoint AND headroom EXHAUSTED AND YELLOW sustained`, controller pulls rate DOWN to setpoint; closes the `factor_down_yellow=1.0` hold-above-setpoint edge case Codex flagged).

Output: 7 test files extended/created with 17 named test classes (originally 14; +3 stubs from REVIEWS) mapped to the RESEARCH §7 / VALIDATION Per-Task Verification Map.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-01-SUMMARY.md
</context>

<interfaces>
<!-- Anticipated production-code surfaces (built in Waves 1-3). Tests must compile against these symbols. -->

QueueController.__init__ NEW kwargs (planned for Plan 201-04):
  docsis_mode: bool = False
  setpoint_bps: int | None = None
  integral_window_seconds: float = 2.0
  integral_threshold_ms_s: float = 30.0
  cake_backlog_low_threshold_bytes: int = 5000
  cake_delay_delta_low_threshold_us: int = 5000

QueueController NEW methods (Plan 201-04):
  _update_integral(delta_ms: float) -> tuple[float, str]   # returns (integral_ms_s, headroom_state)
  _is_cake_aligned_for_pushup(cake: CakeSignalSnapshot | None) -> bool

QueueController NEW state attributes (Plan 201-04):
  self._docsis_mode, self._setpoint_bps,
  self._integral_window (deque),
  self._integral_threshold_ms_s,
  self._cake_backlog_low_threshold_bytes,
  self._cake_delay_delta_low_threshold_us,
  self._headroom_state (str: "AVAILABLE"|"EXHAUSTED"),
  self._cake_aligned (bool),
  self._last_integral_ms_s (float)

Config (autorate_config.py) NEW attributes (Plan 201-03):
  config.docsis_mode (bool, default False)
  config.setpoint_mbps (int|float|None)
  config.integral_window_seconds (float, default 2.0)
  config.integral_threshold_ms_s (float, default 30.0)
  config.cake_backlog_low_threshold_bytes (int, default 5000)
  config.cake_delay_delta_low_threshold_us (int, default 5000)
  config._docsis_mode_explicit, config._setpoint_mbps_explicit, ... (presence flags)

KNOWN_AUTORATE_PATHS additions (Plan 201-03):
  "continuous_monitoring.upload.docsis_mode"
  "continuous_monitoring.upload.setpoint_mbps"
  "continuous_monitoring.upload.integral_window_seconds"
  "continuous_monitoring.upload.integral_threshold_ms_s"
  "continuous_monitoring.upload.cake_backlog_low_threshold_bytes"
  "continuous_monitoring.upload.cake_delay_delta_low_threshold_us"

/health additive fields under .wans[].upload (Plan 201-05):
  "docsis_mode_active": bool
  "setpoint_mbps": float | None
  "headroom_state": str
  "rtt_integral_ms_s": float
  "cake_aligned": bool

Validator (check_config_validators.py) NEW function (Plan 201-03):
  _validate_docsis_mode_setpoint(cm: dict) -> list[CheckResult]

Predeploy gate script (Plan 201-07):
  scripts/phase201-predeploy-gate.sh — exits 0 (clean) | 1 (BLOCK with operator-actionable msg) | 2 (ABORT on env/parse error)
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add failing TDD scaffolding for QueueController DOCSIS-mode internals</name>
  <files>tests/test_queue_controller.py</files>
  <read_first>
    - tests/test_queue_controller.py:1-160 (existing fixtures + 3-state test patterns to mirror)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "tests/test_queue_controller.py (extend)"
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md sections 1, 2, 3 (integral, corroborator, setpoint clamp)
    - src/wanctl/queue_controller.py:1-280 (current QueueController API surface — need to know existing kwargs to extend without breakage)
    - src/wanctl/cake_signal.py:80-170 (CakeSignalSnapshot — for fixture construction)
  </read_first>
  <behavior>
    - TestDocsisModeIntegralClassifier: window-not-full -> EXHAUSTED; integral <= 30.0 ms·s on idle -> AVAILABLE; integral > 30.0 on sustained load -> EXHAUSTED.
    - TestDocsisModeSetpointClamp: GREEN streak with headroom_AVAILABLE AND cake_aligned -> rate climbs above setpoint toward ceiling; either signal absent -> rate clamps at <= setpoint_bps.
    - **TestDocsisModeSetpointClamp::test_above_setpoint_yellow_pulls_to_setpoint (REVIEWS MED-4):** when `current_rate > setpoint AND headroom_state == "EXHAUSTED" AND zone == "YELLOW" AND yellow_streak >= dwell_cycles`, the controller's rate output is `min(current_rate * factor_down_yellow, setpoint_bps)` — i.e., it pulls DOWN to setpoint. Closes the R5 (`factor_down_yellow=1.0`) edge case where a controller pushed above setpoint can hold there indefinitely under sustained YELLOW.
    - TestDocsisModeCakeCorroborator: cold_start=True -> False; backlog > threshold -> False; max_delay_delta_us > threshold -> False; both low + not cold -> True.
    - TestDocsisModeByteIdentity: docsis_mode=False produces byte-identical (zone, rate) sequence vs current 3-state controller on a 60-cycle deterministic delta sequence.
    - TestRedFastTripUnchangedDocsisMode: docsis_mode=True with delta > warn_delta returns RED zone and rate = current_rate * factor_down regardless of integral state (ARCH-03 invariant).
    - **TestDocsisModeFloorHitCounter (REVIEWS HIGH-5):** `test_floor_hit_counter_increments_when_rate_hits_floor` — when `_compute_rate_3state` returns a rate that equals `floor_red_bps`, `self.upload.floor_hit_cycles` increments by 1. `test_floor_hit_counter_does_not_increment_when_above_floor` — rate above floor leaves counter unchanged. `test_floor_hit_counter_starts_at_zero` — fresh controller has counter == 0. This counter is the cycle-fidelity (50ms) VALN-06 evidence vector that closes the 1 Hz `/health` polling gap (Codex review HIGH-5).
    - All tests are expected to FAIL at the end of Plan 201-02 (the kwargs, methods, and counter don't exist yet); they are the contracts Plans 201-04 and 201-05 must satisfy.
  </behavior>
  <action>
Append to `tests/test_queue_controller.py` (do NOT remove or alter existing tests). Add a top-of-file import block under any existing imports:

```python
# Phase 201 imports (Plan 201-02 stubs).
import pytest
from collections import deque
from tests.fixtures.phase201_replay_corpus import (
    synthesize_sustained_load_trace,
    synthesize_idle_trace,
)
```

Then add the following five test classes verbatim:

```python
def _make_docsis_controller(
    *,
    docsis_mode: bool = True,
    setpoint_bps: int | None = 12_000_000,
    integral_window_seconds: float = 2.0,
    integral_threshold_ms_s: float = 30.0,
    cake_backlog_low_threshold_bytes: int = 5000,
    cake_delay_delta_low_threshold_us: int = 5000,
):
    """Construct a QueueController with Phase 201 DOCSIS-mode kwargs.

    Mirrors the shape that Plan 201-04 will land in
    `src/wanctl/queue_controller.py`. This helper deliberately uses the
    NEW keyword-only signature so tests fail loud if Plan 201-04 forgets
    to add a kwarg.
    """
    from wanctl.queue_controller import QueueController
    return QueueController(
        name="TestUpload-DOCSIS",
        floor_green=8_000_000, floor_yellow=8_000_000, floor_soft_red=8_000_000,
        floor_red=8_000_000,
        ceiling=18_000_000,
        step_up=5_000_000,
        factor_down=0.90,
        factor_down_yellow=1.0,
        green_required=3,
        dwell_cycles=3,
        deadband_ms=3.0,
        consecutive_yellow_decay_clamp=40,
        docsis_mode=docsis_mode,
        setpoint_bps=setpoint_bps,
        integral_window_seconds=integral_window_seconds,
        integral_threshold_ms_s=integral_threshold_ms_s,
        cake_backlog_low_threshold_bytes=cake_backlog_low_threshold_bytes,
        cake_delay_delta_low_threshold_us=cake_delay_delta_low_threshold_us,
    )


def _cake_snapshot(*, backlog_bytes=0, max_delay_delta_us=0, cold_start=False):
    from wanctl.cake_signal import CakeSignalSnapshot
    return CakeSignalSnapshot(
        drop_rate=0.0, total_drop_rate=0.0,
        backlog_bytes=backlog_bytes,
        peak_delay_us=max_delay_delta_us + 100,
        tins=(), cold_start=cold_start,
        avg_delay_us=max_delay_delta_us + 50, base_delay_us=50,
        max_delay_delta_us=max_delay_delta_us,
    )


class TestDocsisModeIntegralClassifier:
    def test_window_not_full_is_exhausted(self):
        ctrl = _make_docsis_controller()
        # Push 5 small samples; window expects 40 (2.0s / 50ms).
        for _ in range(5):
            integral, state = ctrl._update_integral(1.0)
        assert state == "EXHAUSTED"

    def test_full_idle_window_is_available(self):
        ctrl = _make_docsis_controller(integral_threshold_ms_s=30.0)
        # 40 cycles of 0.0 delta -> integral = 0 ms·s -> AVAILABLE.
        for _ in range(40):
            integral, state = ctrl._update_integral(0.0)
        assert state == "AVAILABLE"
        assert integral == pytest.approx(0.0, abs=1e-9)

    def test_full_loaded_window_is_exhausted(self):
        ctrl = _make_docsis_controller(integral_threshold_ms_s=30.0)
        # 40 cycles of 30 ms delta -> integral = 30 * 0.05 * 40 = 60.0 ms·s -> EXHAUSTED.
        for _ in range(40):
            integral, state = ctrl._update_integral(30.0)
        assert state == "EXHAUSTED"
        assert integral > 30.0

    def test_negative_delta_clamped_to_zero(self):
        ctrl = _make_docsis_controller(integral_threshold_ms_s=30.0)
        # Negative deltas (transient improvements) MUST NOT add headroom credit nor
        # contaminate the integral. Per RESEARCH §1: max(0, delta).
        for _ in range(40):
            integral, state = ctrl._update_integral(-5.0)
        assert integral == pytest.approx(0.0, abs=1e-9)
        assert state == "AVAILABLE"


class TestDocsisModeSetpointClamp:
    def test_clamp_at_setpoint_when_headroom_exhausted(self):
        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        ctrl.current_rate = 12_000_000
        ctrl._headroom_state = "EXHAUSTED"
        ctrl._cake_aligned = False
        ctrl.green_streak = ctrl.green_required
        rate = ctrl._compute_rate_3state("GREEN")
        assert rate <= 12_000_000

    def test_lift_toward_ceiling_when_both_signals_aligned(self):
        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        ctrl.current_rate = 12_000_000
        ctrl._headroom_state = "AVAILABLE"
        ctrl._cake_aligned = True
        ctrl.green_streak = ctrl.green_required
        rate = ctrl._compute_rate_3state("GREEN")
        assert rate > 12_000_000

    def test_clamp_when_headroom_available_but_cake_misaligned(self):
        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        ctrl.current_rate = 12_000_000
        ctrl._headroom_state = "AVAILABLE"
        ctrl._cake_aligned = False  # CAKE veto
        ctrl.green_streak = ctrl.green_required
        rate = ctrl._compute_rate_3state("GREEN")
        assert rate <= 12_000_000

    def test_red_decay_takes_rate_below_setpoint(self):
        # Setpoint clamp gates UP-only; RED decay must reach floor regardless.
        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        ctrl.current_rate = 12_000_000
        ctrl.red_streak = 1
        rate = ctrl._compute_rate_3state("RED")
        assert rate < 12_000_000


class TestDocsisModeCakeCorroborator:
    def test_cold_start_returns_false(self):
        ctrl = _make_docsis_controller()
        snap = _cake_snapshot(cold_start=True)
        assert ctrl._is_cake_aligned_for_pushup(snap) is False

    def test_high_backlog_returns_false(self):
        ctrl = _make_docsis_controller(cake_backlog_low_threshold_bytes=5000)
        snap = _cake_snapshot(backlog_bytes=10_000, max_delay_delta_us=0)
        assert ctrl._is_cake_aligned_for_pushup(snap) is False

    def test_high_delay_delta_returns_false(self):
        ctrl = _make_docsis_controller(cake_delay_delta_low_threshold_us=5000)
        snap = _cake_snapshot(backlog_bytes=0, max_delay_delta_us=10_000)
        assert ctrl._is_cake_aligned_for_pushup(snap) is False

    def test_both_low_and_warm_returns_true(self):
        ctrl = _make_docsis_controller(
            cake_backlog_low_threshold_bytes=5000,
            cake_delay_delta_low_threshold_us=5000,
        )
        snap = _cake_snapshot(backlog_bytes=100, max_delay_delta_us=100)
        assert ctrl._is_cake_aligned_for_pushup(snap) is True

    def test_none_snapshot_returns_false(self):
        ctrl = _make_docsis_controller()
        assert ctrl._is_cake_aligned_for_pushup(None) is False


class TestDocsisModeByteIdentity:
    def test_legacy_path_unchanged_when_docsis_disabled(self):
        # docsis_mode=False MUST produce a controller whose adjust() output
        # for a deterministic delta sequence matches a vanilla 3-state
        # controller with identical legacy kwargs. D-17 invariant.
        from wanctl.queue_controller import QueueController
        legacy = QueueController(
            name="L", floor_green=8_000_000, floor_yellow=8_000_000,
            floor_soft_red=8_000_000, floor_red=8_000_000,
            ceiling=18_000_000, step_up=5_000_000,
            factor_down=0.90, factor_down_yellow=1.0,
            green_required=3, dwell_cycles=3, deadband_ms=3.0,
            consecutive_yellow_decay_clamp=40,
        )
        docsis_off = _make_docsis_controller(
            docsis_mode=False, setpoint_bps=None,
        )
        # 60 cycles, a deterministic mix of low and high deltas.
        deltas = [(i % 7) * 1.5 for i in range(60)]
        legacy_trace, docsis_trace = [], []
        for d in deltas:
            l_zone, l_rate, _ = legacy.adjust(22.0, 22.0 + d, 5.0, 15.0)
            o_zone, o_rate, _ = docsis_off.adjust(22.0, 22.0 + d, 5.0, 15.0)
            legacy_trace.append((l_zone, l_rate))
            docsis_trace.append((o_zone, o_rate))
        assert legacy_trace == docsis_trace


class TestRedFastTripUnchangedDocsisMode:
    def test_red_immediate_decay_regardless_of_integral_state(self):
        ctrl = _make_docsis_controller()
        ctrl.current_rate = 12_000_000
        # Force AVAILABLE+aligned to make sure they DO NOT delay RED.
        ctrl._headroom_state = "AVAILABLE"
        ctrl._cake_aligned = True
        # delta > warn_delta -> RED.
        zone, rate, _ = ctrl.adjust(22.0, 22.0 + 50.0, target_delta=5.0, warn_delta=15.0)
        assert zone == "RED"
        assert rate < 12_000_000  # immediate factor_down decay


# ----------------------------------------------------------------------
# REVIEWS MED-4: above-setpoint YELLOW edge case.
# With factor_down_yellow=1.0 (R5 retained per CONTEXT D-10), a controller
# that has pushed above setpoint can hold there indefinitely in YELLOW.
# Phase 201 contract: when current_rate > setpoint AND headroom EXHAUSTED
# AND YELLOW sustained (>= dwell_cycles), the rate output MUST pull DOWN
# to setpoint. This test class anchors that contract for Plan 04-T2.
# ----------------------------------------------------------------------
# Append to TestDocsisModeSetpointClamp (above) instead of new class so
# the YELLOW pull-down test sits next to the GREEN clamp tests.

class TestDocsisModeAboveSetpointYellowPulldown:
    def test_above_setpoint_yellow_pulls_to_setpoint(self):
        """REVIEWS MED-4: above-setpoint hold-in-YELLOW must pull DOWN."""
        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        # Simulate post-push-up state: current_rate above setpoint.
        ctrl.current_rate = 15_000_000
        ctrl._headroom_state = "EXHAUSTED"
        ctrl._cake_aligned = False
        # Force YELLOW with sustained streak (>= dwell_cycles).
        ctrl.yellow_streak = ctrl.dwell_cycles + 1
        rate = ctrl._compute_rate_3state("YELLOW")
        # Plan 04-T2 contract: pull DOWN to setpoint, do not hold above.
        assert rate <= 12_000_000, (
            f"YELLOW above-setpoint hold violation: rate={rate} > setpoint=12_000_000. "
            f"factor_down_yellow=1.0 + setpoint clamp must pull DOWN under sustained YELLOW."
        )

    def test_above_setpoint_yellow_legacy_unaffected(self):
        """D-17 invariant: docsis_mode=False keeps legacy YELLOW semantics."""
        from wanctl.queue_controller import QueueController
        legacy = QueueController(
            name="L", floor_green=8_000_000, floor_yellow=8_000_000,
            floor_soft_red=8_000_000, floor_red=8_000_000,
            ceiling=18_000_000, step_up=5_000_000,
            factor_down=0.90, factor_down_yellow=1.0,
            green_required=3, dwell_cycles=3, deadband_ms=3.0,
            consecutive_yellow_decay_clamp=40,
        )
        legacy.current_rate = 15_000_000
        legacy.yellow_streak = legacy.dwell_cycles + 1
        rate_legacy = legacy._compute_rate_3state("YELLOW")
        # Legacy hold-above-setpoint behavior preserved (no setpoint concept).
        # Test asserts the LEGACY rate is whatever it was — we just don't crash.
        assert rate_legacy is not None


# ----------------------------------------------------------------------
# REVIEWS HIGH-5: cycle-fidelity floor-hit counter.
# VALN-06 says "no loaded cycle reaches floor" at the 50ms cycle interval.
# 1 Hz /health polling can miss 50ms floor touches (1000x coarser).
# Plan 04-T2 contract: increment self.floor_hit_cycles whenever
# _compute_rate_3state returns floor_red_bps. Plan 05-T2 exposes it
# as additive /health.wans[].upload.floor_hit_cycles_total. Plans 11+12
# verdict against counter delta, not snapshot rates.
# ----------------------------------------------------------------------

class TestDocsisModeFloorHitCounter:
    def test_floor_hit_counter_starts_at_zero(self):
        ctrl = _make_docsis_controller()
        assert getattr(ctrl, "floor_hit_cycles", None) == 0

    def test_floor_hit_counter_increments_when_rate_hits_floor(self):
        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        ctrl.current_rate = 12_000_000
        # Force a RED decay path that lands at floor.
        ctrl.red_streak = 100  # accumulated RED -> rate decays to floor
        for _ in range(50):
            rate = ctrl._compute_rate_3state("RED")
            ctrl.current_rate = rate
            if rate == ctrl.floor_red_bps:
                break
        else:
            assert False, "expected RED decay to reach floor in 50 cycles"
        # The cycle that LANDED at floor should have incremented the counter.
        assert ctrl.floor_hit_cycles >= 1, (
            f"floor_hit_cycles should be >= 1 after a floor-hit cycle; got {ctrl.floor_hit_cycles}"
        )

    def test_floor_hit_counter_does_not_increment_when_above_floor(self):
        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        ctrl.current_rate = 12_000_000
        ctrl._headroom_state = "AVAILABLE"
        ctrl._cake_aligned = True
        ctrl.green_streak = ctrl.green_required
        before = ctrl.floor_hit_cycles
        rate = ctrl._compute_rate_3state("GREEN")
        # Rate should be at or above setpoint (well above floor)
        assert rate > ctrl.floor_red_bps
        assert ctrl.floor_hit_cycles == before
```

These tests will fail at the end of this plan because `QueueController.__init__` does not yet accept the new kwargs. That is the intended Wave 0 RED state.

Add a TODO marker comment at the top of the new block: `# Phase 201 Wave 0 RED scaffolding — implementation in Plans 201-04 / 201-05.`
  </action>
  <acceptance_criteria>
    - `grep -c "class TestDocsisModeIntegralClassifier" tests/test_queue_controller.py` returns 1.
    - `grep -c "class TestDocsisModeSetpointClamp" tests/test_queue_controller.py` returns 1.
    - `grep -c "class TestDocsisModeCakeCorroborator" tests/test_queue_controller.py` returns 1.
    - `grep -c "class TestDocsisModeByteIdentity" tests/test_queue_controller.py` returns 1.
    - `grep -c "class TestRedFastTripUnchangedDocsisMode" tests/test_queue_controller.py` returns 1.
    - **REVIEWS MED-4:** `grep -c "class TestDocsisModeAboveSetpointYellowPulldown" tests/test_queue_controller.py` returns 1.
    - **REVIEWS HIGH-5:** `grep -c "class TestDocsisModeFloorHitCounter" tests/test_queue_controller.py` returns 1.
    - **REVIEWS HIGH-3:** `grep -c "pytest.skip" tests/test_queue_controller.py` returns 0 for the new Phase 201 test classes (they use AttributeError-on-call to fail naturally; no `pytest.skip(...)` used in this file's new content). Verify via: `awk '/class TestDocsisMode|class TestRedFastTripUnchangedDocsisMode/{p=1} /^class [A-Z]/{if(!/TestDocsisMode|TestRedFastTripUnchangedDocsisMode/)p=0} p' tests/test_queue_controller.py | grep -c 'pytest.skip'` returns 0.
    - `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k 'DocsisMode or RedFastTripUnchangedDocsisMode'` shows the new tests COLLECTING (not import-erroring) — they are expected to FAIL on assertion or AttributeError, not on collection error.
    - Existing 3-state and other tests in `tests/test_queue_controller.py` MUST still pass: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k 'not (DocsisMode or RedFastTripUnchangedDocsisMode)'` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k 'not (DocsisMode or RedFastTripUnchangedDocsisMode)' &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_queue_controller.py --collect-only -q -k 'DocsisMode or RedFastTripUnchangedDocsisMode' | grep -q 'TestDocsisModeIntegralClassifier'</automated>
  </verify>
  <done>5 new test classes added; pre-existing tests still green; new tests collect (expected to fail on assertion until Plan 201-04 lands).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add config / validator / wan_controller / canary / replay / predeploy stubs</name>
  <files>tests/test_autorate_config.py, tests/test_check_config.py, tests/test_wan_controller.py, tests/test_phase200_canary_script.py, tests/test_phase_201_replay.py, tests/test_phase201_predeploy_gate.py</files>
  <read_first>
    - tests/test_autorate_config.py (header + an existing schema-test class to mirror; locate via grep)
    - tests/test_check_config.py (existing validator-error tests to mirror)
    - tests/test_wan_controller.py:71-223 (UL threshold-config tests to mirror)
    - tests/test_phase200_canary_script.py (existing preflight test patterns; locate via grep)
    - tests/test_phase_197_replay.py:1-100 (canonical replay shape — copy structure)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md sections "tests/test_phase_201_replay.py (NEW)", "tests/test_check_config.py (extend)", "scripts/phase201-predeploy-gate.sh (NEW)"
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md §7 (Per-Task Verification Map), §9 (Predeploy gate)
  </read_first>
  <behavior>
    - test_autorate_config.py adds:
        TestPhase201Schema::test_docsis_mode_default_false
        TestPhase201Schema::test_docsis_mode_true_requires_setpoint_mbps_raises
        TestPhase201Schema::test_setpoint_below_floor_raises
        TestPhase201Schema::test_setpoint_above_ceiling_raises
        TestPhase201Schema::test_explicit_presence_flags_are_presence_based
        TestSafe06Phase201KeysKnown::test_all_phase201_keys_in_known_autorate_paths
    - test_check_config.py adds:
        TestDocsisModeValidation::test_missing_setpoint_emits_error_when_docsis_true
        TestDocsisModeValidation::test_setpoint_below_floor_emits_error
        TestDocsisModeValidation::test_setpoint_above_ceiling_emits_error
        TestDocsisModeValidation::test_legacy_yaml_byte_identical (no docsis_mode -> validator emits no docsis-related rows)
    - test_wan_controller.py adds:
        TestPhase201HealthAdditive::test_docsis_mode_active_runtime_field_present
        TestPhase201HealthAdditive::test_setpoint_mbps_runtime_field_reflects_state_not_yaml (REVIEWS LOW-1: docstring tightened — see action)
        TestPhase201HealthAdditive::test_legacy_health_unchanged_when_docsis_disabled (D-16 + Phase 200 RETRO Lesson 1)
        TestPhase201HealthAdditive::test_floor_hit_cycles_total_runtime_field_present (REVIEWS HIGH-5 — additive `/health.wans[].upload.floor_hit_cycles_total`)
        TestPhase201FlashWear::test_steady_state_no_router_writes_when_rate_unchanged
        TestSigusr1ReloadScopePhase201::test_docsis_keys_not_live_tunable
    - test_phase200_canary_script.py adds:
        TestPhase201Preflight::test_env_yaml_docsis_mode_match_pass
        TestPhase201Preflight::test_env_yaml_docsis_mode_mismatch_aborts
        TestPhase201Preflight::test_env_yaml_setpoint_mbps_mismatch_aborts
        TestPhase201Preflight::test_health_docsis_key_absent_aborts
        TestPhase201Preflight::test_health_docsis_false_aborts
        TestPhase201Preflight::test_remote_python_yaml_missing_aborts (closes WR-02)
    - test_phase_201_replay.py (NEW) adds:
        TestAttempt3ReplayWithDocsisMode::test_no_floor_hits_with_setpoint_12
        TestLegacyByteIdentity::test_no_docsis_key_byte_identical_3state
    - test_phase201_predeploy_gate.py (NEW) adds:
        TestPredeployGate::test_clean_yaml_passes
        TestPredeployGate::test_target_bloat_ms_in_upload_blocks
        TestPredeployGate::test_warn_bloat_ms_in_upload_blocks
        TestPredeployGate::test_docsis_mode_true_without_setpoint_blocks
        TestPredeployGate::test_factor_down_yellow_alone_passes
        TestPredeployGate::test_consecutive_yellow_decay_clamp_alone_passes
  </behavior>
  <action>
For each file, append (do not modify existing content) the listed test class blocks. Use `pytest.skip("Wave 0 stub — implementation in Plan 201-XX")` ONLY when the symbol the test references literally cannot be imported yet (e.g. predeploy gate script). Otherwise the tests should be written to fail naturally on assertion or AttributeError.

CRITICAL FOR PER-KEY EXPLICIT FLAG TEST (D-03 Codex catch):
```python
class TestPhase201Schema:
    def test_explicit_presence_flags_are_presence_based(self, tmp_path):
        # Per Phase 200 Codex pre-review: presence-based, NEVER value-derived.
        # Operator setting docsis_mode: false (matching default) MUST still
        # produce _docsis_mode_explicit=True (because the key was written).
        from wanctl.autorate_config import Config
        yaml_text = '''
continuous_monitoring:
  upload:
    docsis_mode: false
'''
        cfg_path = tmp_path / "test.yaml"
        cfg_path.write_text(yaml_text)
        cfg = Config(str(cfg_path))
        assert cfg._docsis_mode_explicit is True  # KEY WAS WRITTEN
        assert cfg.docsis_mode is False
```

CRITICAL HEALTH-RUNTIME-STATE TEST (Phase 200 RETRO Lesson 1 — must NOT use JSON fixture):
```python
class TestPhase201HealthAdditive:
    @pytest.mark.xfail(strict=True, reason="Wave 0 stub — Plan 201-05")
    def test_setpoint_mbps_runtime_field_reflects_state_not_yaml(
        self, mock_autorate_config
    ):
        """`/health.wans[].upload.setpoint_mbps` is the *active configured
        setpoint* (runtime state read from `self.upload._setpoint_bps`),
        NOT the YAML-configured value AND NOT the current rate. Phase 200
        RETRO Plan 05 bug 2 trap.

        REVIEWS LOW-1 (2026-05-04): the field is runtime state by design
        (D-16). Tests should NOT imply it changes when `current_rate` changes.
        SIGUSR1 reload is OUT OF SCOPE per D-08, so re-reading YAML at runtime
        does NOT update this field — only a daemon restart does. This test
        anchors that invariant: setpoint_mbps reflects the active configured
        setpoint, not the current rate.
        """
        # Build a controller with setpoint_mbps=12 in config but a
        # current_rate of 8 Mbit (post-floor-hit recovery scenario);
        # /health.upload.setpoint_mbps MUST equal 12 (YAML config), NOT 8
        # (current_rate). And current_rate != setpoint_mbps under load.
        # Implementation in Plan 201-05 must populate this from
        # self.upload._setpoint_bps — not from config object directly,
        # not from current_rate.
        # Strict xfail: will REMAIN xfailing until Plan 201-05 wires the
        # field; if it accidentally passes before then, pytest fails the test
        # (reverse-protected against silent green).
        raise AssertionError("Wave 0 stub — implementation lands in Plan 201-05")


    @pytest.mark.xfail(strict=True, reason="Wave 0 stub — Plan 201-05 (REVIEWS HIGH-5)")
    def test_floor_hit_cycles_total_runtime_field_present(
        self, mock_autorate_config
    ):
        """REVIEWS HIGH-5 (2026-05-04): /health.wans[].upload.floor_hit_cycles_total
        is the cycle-fidelity (50ms) floor-hit counter exposed for canary +
        soak verdict comparisons.

        VALN-06 contract is "no loaded *cycle* reaches floor" at the 50ms
        cycle interval. Canary + soak verdicts derived from 1 Hz /health
        polling miss 50ms floor touches (1000x coarser). The runtime
        counter `self.upload.floor_hit_cycles` (Plan 04-T2) is exposed
        here as `floor_hit_cycles_total` (Plan 05-T2). Plans 11/12 verdict
        gate compares counter DELTAS across the loaded window, not snapshot
        rates.

        Implementation in Plan 201-05: read `self.upload.floor_hit_cycles`
        (int, monotonic since daemon start) and expose as
        `floor_hit_cycles_total` in the per-WAN upload health dict.
        """
        raise AssertionError("Wave 0 stub — implementation lands in Plan 201-05")
```

For predeploy gate test file, use a `subprocess.run` shell test pattern (script doesn't exist yet, mark with skip):
```python
import subprocess
from pathlib import Path
import pytest
import textwrap

GATE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "phase201-predeploy-gate.sh"

@pytest.fixture
def fake_remote_yaml(tmp_path, monkeypatch):
    """Create a tmp YAML and short-circuit the gate's SSH probe via env override.

    The actual gate script (Plan 201-07) MUST honor an env var
    PHASE201_LOCAL_YAML_OVERRIDE that bypasses SSH for tests. Plan 201-07
    will add this fail-safe; if missing, all tests in this class skip.
    """
    if not GATE_SCRIPT.exists():
        pytest.skip("phase201-predeploy-gate.sh not yet created (Plan 201-07)")
    return tmp_path

class TestPredeployGate:
    def test_clean_yaml_passes(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text(textwrap.dedent("""
            continuous_monitoring:
              upload:
                docsis_mode: true
                setpoint_mbps: 12
                factor_down_yellow: 1.0
                consecutive_yellow_decay_clamp: 40
        """).strip())
        env = {"PHASE201_LOCAL_YAML_OVERRIDE": str(yaml_path), "PATH": "/usr/bin:/bin"}
        result = subprocess.run(
            ["bash", str(GATE_SCRIPT)], env=env, capture_output=True, timeout=15
        )
        assert result.returncode == 0, result.stderr.decode()

    def test_target_bloat_ms_in_upload_blocks(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text(textwrap.dedent("""
            continuous_monitoring:
              upload:
                docsis_mode: true
                setpoint_mbps: 12
                target_bloat_ms: 42
        """).strip())
        env = {"PHASE201_LOCAL_YAML_OVERRIDE": str(yaml_path), "PATH": "/usr/bin:/bin"}
        result = subprocess.run(
            ["bash", str(GATE_SCRIPT)], env=env, capture_output=True, timeout=15
        )
        assert result.returncode == 1
        assert b"target_bloat_ms" in result.stdout + result.stderr

    # ... mirror shape for warn_bloat_ms, missing-setpoint, and the two ALLOW cases.
```

For the replay test:
```python
import pytest
from tests.fixtures.phase201_replay_corpus import (
    load_attempt3_trace, ATTEMPT3_VERDICT_PATH,
)

class TestAttempt3ReplayWithDocsisMode:
    @pytest.mark.xfail(strict=True, reason="Wave 0 stub — Plan 201-04 Task 3 (REVIEWS HIGH-3)")
    def test_no_floor_hits_with_setpoint_12_cycle_fidelity(self, phase201_attempt3_trace):
        """REVIEWS HIGH-4 (2026-05-04): cycle-fidelity replay contract.

        Replays Attempt 3's load_rtt + cake samples through the DOCSIS-mode
        controller, EXPANDING each 1 Hz NDJSON sample into 20 synthetic
        50ms cycles via hold-last interpolation (load_rtt and cake fields
        held constant across the 20 cycles). This makes the integral window
        (2.0s = 40 cycles) and YELLOW dwell counters operate at the same
        cadence as production (50ms cycle interval, per CYCLE_INTERVAL_SECONDS
        in cake_signal.py).

        Without expansion, a 2-second integral window stretches to 40
        replay-seconds because each NDJSON sample = one controller cycle —
        Codex review HIGH-4 caught this. The expansion turns a 900s loaded
        capture into a 18000-cycle replay (still a coarse model — the
        cycle-internal RTT variation is lost — but the integral and dwell
        windows now sample at the right cadence).

        Contract: floor_hits == 0 across the expanded loaded window.

        Implementation lands in Plan 201-04 Task 3 (with `_synth_cake_from_sample`
        producing 20 cycles per sample). Strict xfail until then.
        """
        if not phase201_attempt3_trace:
            pytest.skip("Attempt 3 trace empty — corpus loader missing or NDJSON moved")
        raise AssertionError("Wave 0 stub — replay harness wired in Plan 201-04 Task 3")

class TestLegacyByteIdentity:
    @pytest.mark.xfail(strict=True, reason="Wave 0 stub — Plan 201-04 Task 3 (REVIEWS HIGH-3)")
    def test_no_docsis_key_byte_identical_3state(self, phase201_sustained_load_trace):
        """When `docsis_mode` key is absent from YAML, the (zone, rate)
        sequence on a synthetic trace MUST match the legacy 3-state
        controller exactly (D-17 invariant).
        """
        raise AssertionError("Wave 0 stub — implementation in Plan 201-04 Task 3")
```

For the canary preflight test class, use the existing `subprocess` + `--self-test` dispatch pattern in `tests/test_phase200_canary_script.py` (per Phase 200 Plan 11 hardening); locate via grep before writing. Skip individual tests if the corresponding `--self-test` subcommand doesn't yet exist (Plan 201-08 will add `--self-test phase201-preflight` and friends).

Use this header comment in every new file or new section:
```python
# Phase 201 Wave 0 RED scaffolding — Plan 201-02 stubs.
# Implementation lands in Plans 201-03 (config/validator),
# 201-04 (controller core), 201-05 (telemetry / wan_controller),
# 201-07 (predeploy gate), 201-08 (canary extension).
```
  </action>
  <acceptance_criteria>
    - `grep -c "class TestPhase201Schema" tests/test_autorate_config.py` returns 1.
    - `grep -c "class TestSafe06Phase201KeysKnown" tests/test_autorate_config.py` returns 1.
    - `grep -c "class TestDocsisModeValidation" tests/test_check_config.py` returns 1.
    - `grep -c "class TestPhase201HealthAdditive" tests/test_wan_controller.py` returns 1.
    - `grep -c "class TestPhase201FlashWear" tests/test_wan_controller.py` returns 1.
    - `grep -c "class TestSigusr1ReloadScopePhase201" tests/test_wan_controller.py` returns 1.
    - **REVIEWS HIGH-5:** `grep -c "test_floor_hit_cycles_total_runtime_field_present" tests/test_wan_controller.py` returns 1.
    - **REVIEWS LOW-1:** `grep -c "active configured setpoint" tests/test_wan_controller.py` returns >= 1 (docstring tightened to clarify runtime-state semantics).
    - **REVIEWS HIGH-3 (xfail-strict enforcement):** `grep -c '@pytest.mark.xfail(strict=True' tests/test_wan_controller.py` returns >= 2 for Phase 201 stubs (the setpoint_mbps and floor_hit_cycles_total tests). `grep -c '@pytest.mark.xfail(strict=True' tests/test_phase_201_replay.py` returns >= 2.
    - **REVIEWS HIGH-3 (no skip-only stubs):** for stubs that anchor real implementation contracts, the file does NOT use bare `pytest.skip("Wave 0 stub")` — verify with `grep -B 1 'Wave 0 stub' tests/test_wan_controller.py tests/test_phase_201_replay.py | grep -c 'pytest.skip'` returns 0 (only xfail-strict allowed for symbol-importable stubs).
    - `grep -c "class TestPhase201Preflight" tests/test_phase200_canary_script.py` returns 1.
    - `test -f tests/test_phase_201_replay.py` succeeds; `grep -c "class TestAttempt3ReplayWithDocsisMode" tests/test_phase_201_replay.py` returns 1; `grep -c "class TestLegacyByteIdentity" tests/test_phase_201_replay.py` returns 1.
    - `test -f tests/test_phase201_predeploy_gate.py` succeeds; `grep -c "class TestPredeployGate" tests/test_phase201_predeploy_gate.py` returns 1.
    - `grep -c "presence-based" tests/test_autorate_config.py` returns >= 1 (D-03 Codex catch documented).
    - `grep -c "Phase 200 RETRO Lesson 1" tests/test_wan_controller.py | tr -d ' '` returns >= 1 (Plan 05 bug 2 trap documented).
    - Hot-path slice still passes: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q -k 'not (DocsisMode or RedFastTripUnchangedDocsisMode or Phase201)'` returns 0.
    - All new tests collect without ImportError: `.venv/bin/pytest -o addopts='' tests/test_phase_201_replay.py tests/test_phase201_predeploy_gate.py tests/test_phase200_canary_script.py tests/test_autorate_config.py tests/test_check_config.py tests/test_wan_controller.py --collect-only -q` exits 0 (collection succeeds; some tests may xfail/skip).
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_phase_201_replay.py tests/test_phase201_predeploy_gate.py tests/test_phase200_canary_script.py tests/test_autorate_config.py tests/test_check_config.py tests/test_wan_controller.py --collect-only -q &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q -k 'not (DocsisMode or RedFastTripUnchangedDocsisMode or Phase201)'</automated>
  </verify>
  <done>All 7 test files contain the named test classes; existing tests still pass; new tests collect cleanly (red but importable). Anti-shallow gate: Wave 1+ implementation cannot proceed without satisfying these contracts.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| test runner → wanctl source code | Tests assume the symbol surface defined in `<interfaces>`; if a Wave 1+ task drifts from those names, tests fail loud — that's the point. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-04 | Tampering | A future planner skips Wave 0 and writes production code without the contract tests | mitigate | VALIDATION.md `Wave 0 Requirements` is the gate; this plan creates the artifacts that gate references. CI grep checks (acceptance_criteria) prevent removal. |
| T-201-05 | Repudiation | Test names drift from RESEARCH/PATTERNS docs | mitigate | Test class names are spelled out in PATTERNS.md and RESEARCH §7; acceptance_criteria pin them via `grep -c "class TestX"` returning 1. |
| T-201-06 | Tampering | Predeploy gate test bypassed in CI by silently skipping | mitigate | Acceptance criteria require the test FILES to exist and the test CLASSES to be present; skip-only is permitted at the function level (because Wave 0 cannot run a non-existent script), but the class scaffold must be there for Plan 201-07 to populate. |
</threat_model>

<verification>
1. Each named test class exists in its target file (10 grep checks).
2. New test files collect without ImportError.
3. Pre-existing test suite slice still green (no regression to TDD baseline).
4. Phase 200 Codex catches (D-03 presence-based, Plan 05 bug 2 health-runtime) are referenced in test docstrings/comments.
</verification>

<success_criteria>
- 14 named test classes added across 7 files (5 in queue_controller from Task 1, 9 in remaining from Task 2).
- Hot-path regression slice still green.
- Per-Task Verification Map row entries can now reference these tests directly (Plan 201-12 fills VALIDATION.md).
- Anti-shallow gate active: every Wave 1+ implementation task has a failing test waiting.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-02-SUMMARY.md` listing the 14 test classes, which plan implements each, and the count of pre-existing tests still green (Phase 200 baseline ~578 hot-path).
</output>
