---
phase: 201-docsis-aware-ul-congestion-control
plan: 04
type: tdd
wave: 2
depends_on: [02, 03, 09]
files_modified:
  - src/wanctl/queue_controller.py
  - tests/test_phase_201_replay.py
  - tests/test_phase_195_replay.py
autonomous: true
requirements: [VALN-06]
tags: [phase-201, wave-2, controller, integral, setpoint-clamp, cake-corroborator, augment-not-replace]

must_haves:
  truths:
    - "QueueController accepts six new Phase 201 kwargs and stores them as instance state with safe defaults so legacy callers are byte-identical (D-17)"
    - "_update_integral computes integral-of-positive-delta over a configurable window and returns headroom state AVAILABLE/EXHAUSTED with conservative window-not-full default"
    - "_is_cake_aligned_for_pushup is categorical AND-gate (backlog_low AND delay_delta_low AND not cold_start) — never µs/ms ratio"
    - "Setpoint clamp injects in GREEN+sustained-streak push-up branch — RED decay byte-identical to legacy; YELLOW gains a docsis-only above-setpoint pull-down branch (REVIEWS MED-4) but legacy YELLOW path is byte-identical"
    - "RED fast-trip path (delta > warn_delta) returns rate <= current_rate * factor_down regardless of integral or CAKE state (ARCH-03 invariant)"
    - "REVIEWS HIGH-5: cycle-level floor-hit counter (self.floor_hit_cycles) increments at every 50ms cycle whose computed rate equals floor_red_bps; monotonic per daemon lifetime; Plan 05-T2 exposes via /health.wans[].upload.floor_hit_cycles_total"
    - "REVIEWS HIGH-4: replay against Phase 200 Attempt 3 capture, expanded 20x via hold-last interpolation to 50ms cadence, produces ZERO floor-hit cycles in DOCSIS-mode controller (synthetic VALN-06 closure under cycle-fidelity conditions)"
    - "REVIEWS MED-4: above-setpoint controller in sustained YELLOW pulls DOWN to setpoint (factor_down_yellow=1.0 hold-above edge case closed)"
  artifacts:
    - path: src/wanctl/queue_controller.py
      provides: "DOCSIS-mode integral + setpoint clamp + CAKE corroborator inside QueueController; legacy path unchanged"
      contains: "_update_integral"
    - path: tests/test_phase_201_replay.py
      provides: "Wired replay test against Attempt 3 NDJSON corpus; legacy byte-identity test"
      contains: "TestAttempt3ReplayWithDocsisMode"
  key_links:
    - from: "src/wanctl/queue_controller.py:_compute_rate_3state"
      to: "src/wanctl/queue_controller.py:_update_integral"
      via: "self._headroom_state read in GREEN+sustained branch"
      pattern: "_headroom_state.*AVAILABLE"
    - from: "src/wanctl/queue_controller.py:adjust"
      to: "src/wanctl/queue_controller.py:_is_cake_aligned_for_pushup"
      via: "self._cake_aligned set BEFORE classify"
      pattern: "_cake_aligned"
---

<objective>
Wave 2 controller core. Lands the AUGMENT-not-replace integral path, CAKE corroborator AND-gate, setpoint clamp, and cycle-fidelity floor-hit counter inside `QueueController`. Legacy 3-state path is byte-identical when `docsis_mode=False`. Replays Phase 200 Attempt 3 NDJSON through the new controller — with **20-cycle hold-last expansion per 1 Hz NDJSON sample (REVIEWS HIGH-4)** — and asserts zero floor hits as the synthetic VALN-06 contract.

Per RESEARCH §1 headline finding: AUGMENT, not REPLACE. RED fast-trip stays exactly as it is in `_classify_zone_3state` lines 147-153. The integral runs as a separate headroom-probe gate that only interacts with the GREEN+sustained-streak push-up path.

Wave 0 tests landed in Plan 201-02 (TestDocsisModeIntegralClassifier, TestDocsisModeSetpointClamp, TestDocsisModeCakeCorroborator, TestDocsisModeByteIdentity, TestRedFastTripUnchangedDocsisMode, TestDocsisModeAboveSetpointYellowPulldown [REVIEWS MED-4], TestDocsisModeFloorHitCounter [REVIEWS HIGH-5], TestAttempt3ReplayWithDocsisMode, TestLegacyByteIdentity) all turn GREEN at the end of this plan.

**REVIEWS amendments (2026-05-04, see 201-REVIEWS.md):**
- **HIGH-4 (replay timing fidelity, Option A chosen):** Plan 04-T3 expands each 1 Hz NDJSON sample into 20 synthetic 50ms cycles via *hold-last interpolation* (load_rtt and cake fields held constant across the 20 cycles). Reasoning: Option A (cycle-fidelity replay) gives stronger evidence than Option B (downgrade to coarse regression); the planner's Option B fallback would weaken the synthetic VALN-06 closure claim. Hold-last (vs linear interpolation) is more conservative — it doesn't smooth out the RTT-delta peaks that drive the integral. Documented in test docstring AND in RESEARCH.md Assumptions Log (planner adds A11 entry in Plan 04-T3).
- **HIGH-5 (cycle-level floor-hit counter):** Plan 04-T2 adds `self.floor_hit_cycles: int = 0` and increments it inside `_compute_rate_3state` whenever the computed rate equals `self.floor_red_bps`. This is the cycle-fidelity (50ms) VALN-06 evidence vector. Plan 05-T2 exposes it as additive `/health.wans[].upload.floor_hit_cycles_total`. Plans 11/12 verdict against counter delta, not snapshot rates.
- **MED-4 (above-setpoint YELLOW pull-down):** Plan 04-T2 adds a setpoint pull-down branch in `_compute_rate_3state`'s YELLOW arm: when `self._docsis_mode and self._setpoint_bps and current_rate > self._setpoint_bps and self._headroom_state == "EXHAUSTED" and yellow_streak >= dwell_cycles`, return `min(current_rate * factor_down_yellow, self._setpoint_bps)`. Closes the R5 (`factor_down_yellow=1.0`) edge case where a controller pushed above setpoint can hold there indefinitely.
- **HIGH-3 (stub removal):** acceptance criterion at the plan level — `grep -c 'Wave 0 stub' tests/test_queue_controller.py tests/test_phase_201_replay.py` returns 0 after Plan 04 completes (every implemented stub has its xfail/fail decorator removed).

Output: `queue_controller.py` extended with ~100 net-new lines (was ~80; +20 for floor_hit_cycles + above-setpoint YELLOW); replay test wired with 20-cycle expansion; SAFE-05 v1.42 pins re-baselined for controller surface; RESEARCH.md A11 assumption log entry.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-03-SUMMARY.md
@src/wanctl/queue_controller.py
@src/wanctl/cake_signal.py
</context>

<interfaces>
<!-- The contracts from Plan 201-02 Wave 0 tests. -->

QueueController.__init__ NEW kwargs (keyword-only, with defaults preserving legacy):
  docsis_mode: bool = False
  setpoint_bps: int | None = None
  integral_window_seconds: float = 2.0
  integral_threshold_ms_s: float = 30.0
  cake_backlog_low_threshold_bytes: int = 5000
  cake_delay_delta_low_threshold_us: int = 5000

QueueController NEW state attributes:
  self._docsis_mode: bool
  self._setpoint_bps: int | None
  self._integral_window: deque[float]   # maxlen = round(window_seconds / 0.05)
  self._integral_threshold_ms_s: float
  self._cake_backlog_low_threshold_bytes: int
  self._cake_delay_delta_low_threshold_us: int
  self._headroom_state: str             # "AVAILABLE" | "EXHAUSTED" — default EXHAUSTED
  self._cake_aligned: bool              # default False
  self._last_integral_ms_s: float       # default 0.0
  # REVIEWS HIGH-5 (2026-05-04): cycle-fidelity floor-hit counter.
  # Public (no underscore) because Plan 05-T2 exposes via /health and
  # Plans 11/12 read deltas across loaded windows.
  self.floor_hit_cycles: int = 0

QueueController NEW methods:
  def _update_integral(self, delta_ms: float) -> tuple[float, str]: ...
  def _is_cake_aligned_for_pushup(self, cake: "CakeSignalSnapshot | None") -> bool: ...

QueueController existing methods MODIFIED:
  __init__: append new kwargs + state init + DOCSIS current_rate seed
  adjust: BEFORE existing _classify_zone_3state call, when docsis_mode, run _update_integral and set _cake_aligned
  _compute_rate_3state: GREEN+sustained branch gains setpoint clamp; other branches unchanged

Cycle interval anchor:
  CYCLE_INTERVAL_SECONDS = 0.05  # 50ms; defined in cake_signal.py:36 — DO NOT redefine in queue_controller.py
  -> Window size: round(integral_window_seconds / 0.05)
  -> Per-sample contribution to integral_ms_s: 0.05 * delta_ms
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend QueueController.__init__ with DOCSIS-mode kwargs and state</name>
  <files>src/wanctl/queue_controller.py</files>
  <read_first>
    - src/wanctl/queue_controller.py (full file — under 280 lines, single Read)
    - src/wanctl/cake_signal.py:30-50 (locate CYCLE_INTERVAL_SECONDS literal)
    - tests/test_queue_controller.py — TestDocsisModeIntegralClassifier, TestDocsisModeCakeCorroborator (the contracts)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "src/wanctl/queue_controller.py (controller / state-machine — augment)"
  </read_first>
  <behavior>
    - Adding `from collections import deque` at the top of the file (with TYPE_CHECKING import for CakeSignalSnapshot) is the only import change.
    - All new kwargs are keyword-only with the defaults shown in <interfaces>.
    - Window size is computed as `max(1, round(integral_window_seconds / 0.05))` — at least 1 to prevent zero-length deque.
    - When `docsis_mode is True and setpoint_bps is not None`, the constructor seeds `self.current_rate = min(self.current_rate, self._setpoint_bps)` AFTER the existing current_rate initialization so the controller starts at setpoint instead of ceiling on daemon start (RESEARCH §4 recommendation).
    - When `docsis_mode is False`, every new attribute is still initialized but takes no effect — the legacy code paths never read them, preserving byte-identity (D-17).
  </behavior>
  <action>
First read the full `src/wanctl/queue_controller.py` to identify:
- Existing `__init__` keyword-only signature end (where to append new kwargs)
- Where `self.current_rate` is currently initialized
- Whether `from collections import deque` is already imported (it is not, per PATTERNS.md)
- Whether `from typing import TYPE_CHECKING` is present
- The exact name of the `floor_red_bps`/`ceiling_bps` attributes used by `enforce_rate_bounds`

Update imports at the top:
```python
from collections import deque
from typing import TYPE_CHECKING, Any  # extend existing typing import
if TYPE_CHECKING:
    from wanctl.cake_signal import CakeSignalSnapshot
```

Append to `__init__` keyword-only signature (after the last existing kwarg, before the body):

```python
        # ... existing kwargs ...
        consecutive_yellow_decay_clamp: int = 0,
        # Phase 201 (DOCSIS-aware UL control mode) — keyword-only with safe
        # defaults. Legacy callers are byte-identical because docsis_mode
        # defaults False and the new branches gate on it.
        docsis_mode: bool = False,
        setpoint_bps: int | None = None,
        integral_window_seconds: float = 2.0,
        integral_threshold_ms_s: float = 30.0,
        cake_backlog_low_threshold_bytes: int = 5000,
        cake_delay_delta_low_threshold_us: int = 5000,
```

Append to the end of the existing `__init__` body (after `self._last_zone = "GREEN"` or equivalent terminal init):

```python
        # Phase 201 — DOCSIS-aware UL control mode internals.
        # All initialized unconditionally; only consulted when docsis_mode=True.
        self._docsis_mode: bool = docsis_mode
        self._setpoint_bps: int | None = setpoint_bps
        # Cycle is 50ms (cake_signal.CYCLE_INTERVAL_SECONDS); use literal here
        # to avoid an import cycle with the legacy module surface.
        _window_size = max(1, round(integral_window_seconds / 0.05))
        self._integral_window: deque[float] = deque(maxlen=_window_size)
        self._integral_threshold_ms_s: float = integral_threshold_ms_s
        self._cake_backlog_low_threshold_bytes: int = cake_backlog_low_threshold_bytes
        self._cake_delay_delta_low_threshold_us: int = cake_delay_delta_low_threshold_us
        self._headroom_state: str = "EXHAUSTED"  # safe default; AVAILABLE only after window full
        self._cake_aligned: bool = False
        self._last_integral_ms_s: float = 0.0
        # REVIEWS HIGH-5: cycle-fidelity floor-hit counter (monotonic, daemon
        # lifetime). Initialized for ALL controllers (legacy + docsis) so the
        # /health field is always present; legacy controllers simply never
        # increment it because their rate decisions go through the legacy
        # path that doesn't gate on setpoint-clamp logic, but the counter
        # is still incremented uniformly when _compute_rate_3state returns
        # floor_red_bps (this is correct: ANY controller that hits floor
        # under sustained load has a real measurement signal).
        self.floor_hit_cycles: int = 0
        # DOCSIS-mode current_rate seed (RESEARCH §4 recommendation):
        # avoid a 1-cycle ceiling-touch at daemon start by initializing at
        # min(current_rate, setpoint_bps) when docsis_mode active.
        if self._docsis_mode and self._setpoint_bps is not None:
            self.current_rate = min(self.current_rate, self._setpoint_bps)
```

Do NOT touch any existing kwarg defaults or any existing init line. Verify with a diff that the only changes are: imports, the appended kwargs, and the appended init block.
  </action>
  <acceptance_criteria>
    - `grep -c "from collections import deque" src/wanctl/queue_controller.py` returns 1.
    - `grep -c "self._docsis_mode" src/wanctl/queue_controller.py` returns >= 2.
    - `grep -c "self._setpoint_bps" src/wanctl/queue_controller.py` returns >= 2.
    - `grep -c "self._integral_window" src/wanctl/queue_controller.py` returns >= 2.
    - `grep -c "self._headroom_state" src/wanctl/queue_controller.py` returns >= 2.
    - `grep -c "self._cake_aligned" src/wanctl/queue_controller.py` returns >= 2.
    - `grep -c "docsis_mode: bool = False" src/wanctl/queue_controller.py` returns 1.
    - **REVIEWS HIGH-5:** `grep -c "self.floor_hit_cycles" src/wanctl/queue_controller.py` returns >= 2 (init + increment site after Task 2).
    - Constructor exists in test surface: `python3 -c "from wanctl.queue_controller import QueueController; q=QueueController(name='x',floor_green=1,floor_yellow=1,floor_soft_red=1,floor_red=1,ceiling=18000000,step_up=5000000,factor_down=0.9,factor_down_yellow=1.0,green_required=3,dwell_cycles=3,deadband_ms=3.0,docsis_mode=True,setpoint_bps=12000000); print(q._docsis_mode, q._headroom_state, len(q._integral_window), q.floor_hit_cycles)"` prints `True EXHAUSTED 0 0`.
    - `.venv/bin/ruff check src/wanctl/queue_controller.py` returns 0.
    - `.venv/bin/mypy src/wanctl/queue_controller.py` returns 0.
    - Hot-path slice still passes for non-DOCSIS tests: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k 'not (DocsisMode or RedFastTripUnchangedDocsisMode)'` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k 'not (DocsisMode or RedFastTripUnchangedDocsisMode)' &amp;&amp; .venv/bin/ruff check src/wanctl/queue_controller.py &amp;&amp; .venv/bin/mypy src/wanctl/queue_controller.py</automated>
  </verify>
  <done>Constructor accepts new kwargs; state initialized correctly; DOCSIS seed for current_rate active; legacy tests unchanged; static checks clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add _update_integral, _is_cake_aligned_for_pushup, and setpoint clamp in adjust+_compute_rate_3state</name>
  <files>src/wanctl/queue_controller.py</files>
  <read_first>
    - src/wanctl/queue_controller.py (re-read AFTER Task 1 to see current state)
    - tests/test_queue_controller.py — TestDocsisModeIntegralClassifier, TestDocsisModeSetpointClamp, TestDocsisModeCakeCorroborator, TestDocsisModeByteIdentity, TestRedFastTripUnchangedDocsisMode (these are the contracts for THIS task)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md sections 1, 2, 3 (the algorithm)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "Adjust seam" + "New helpers" + "Existing _compute_rate_3state body to mirror" (the verbatim shape)
  </read_first>
  <behavior>
    - `_update_integral(delta_ms)` appends `max(0, delta_ms)` to `self._integral_window`, computes `integral_ms_s = sum(self._integral_window) * 0.05`, returns (integral_ms_s, "EXHAUSTED") if window not full, else returns AVAILABLE iff integral_ms_s <= self._integral_threshold_ms_s.
    - `_is_cake_aligned_for_pushup(cake)` returns False on `cake is None or cake.cold_start`, else `(cake.backlog_bytes <= self._cake_backlog_low_threshold_bytes) and (cake.max_delay_delta_us <= self._cake_delay_delta_low_threshold_us)`.
    - `adjust()` is modified ONLY to insert two lines BEFORE the existing `_classify_zone_3state` call, gated on `if self._docsis_mode`: update integral and CAKE-alignment state. The existing classifier and rate-decision code paths are otherwise untouched.
    - `_compute_rate_3state()` GREEN+sustained-streak branch gains a setpoint clamp: when `self._docsis_mode and self._setpoint_bps is not None and not (self._headroom_state == "AVAILABLE" and self._cake_aligned)`, return `min(raw_rate, self._setpoint_bps)`; otherwise return `raw_rate`. RED and YELLOW branches are byte-identical to legacy.
  </behavior>
  <action>
Add the two helper methods at module-class scope (immediately after the existing `_classify_zone_3state` method or at a similar logical location — locate via grep; place near other helpers):

```python
    def _update_integral(self, delta_ms: float) -> tuple[float, str]:
        """Append delta sample, return (integral_ms_s, headroom_state).

        Phase 201 RESEARCH §1. Negative deltas clamp to zero (transient
        improvements add no headroom credit). Window-not-full is conservative
        (EXHAUSTED) — controller stays clamped at setpoint until enough samples
        accumulate. Cycle interval is 50ms; integral_ms_s = sum * 0.05.
        """
        self._integral_window.append(max(0.0, float(delta_ms)))
        integral_ms_s = sum(self._integral_window) * 0.05
        self._last_integral_ms_s = integral_ms_s
        if len(self._integral_window) < (self._integral_window.maxlen or 0):
            return integral_ms_s, "EXHAUSTED"
        if integral_ms_s <= self._integral_threshold_ms_s:
            return integral_ms_s, "AVAILABLE"
        return integral_ms_s, "EXHAUSTED"

    def _is_cake_aligned_for_pushup(
        self, cake: "CakeSignalSnapshot | None"
    ) -> bool:
        """Categorical AND-gate: backlog low AND max_delay_delta_us low.

        Phase 197 mirror — never µs/ms ratio (Phase 200 RETRO Codex pushback).
        Cold-start veto-deny is intentional (RESEARCH Pitfall 4).
        """
        if cake is None or getattr(cake, "cold_start", False):
            return False
        backlog_low = cake.backlog_bytes <= self._cake_backlog_low_threshold_bytes
        delay_low = cake.max_delay_delta_us <= self._cake_delay_delta_low_threshold_us
        return bool(backlog_low and delay_low)
```

Modify `adjust()` — insert two lines BEFORE the existing `_classify_zone_3state` call (locate via grep; the call form is `zone = self._classify_zone_3state(delta, target_delta, warn_delta, cake_snapshot)` per PATTERNS.md):

```python
        # Phase 201: integral + cake-alignment update BEFORE classify.
        # Consumes the same delta the classifier consumes — preserves
        # asymmetry-gate semantics (RESEARCH Open Question 4).
        if self._docsis_mode:
            self._last_integral_ms_s, self._headroom_state = self._update_integral(delta)
            self._cake_aligned = self._is_cake_aligned_for_pushup(cake_snapshot)
        zone = self._classify_zone_3state(delta, target_delta, warn_delta, cake_snapshot)
```

Modify `_compute_rate_3state()` GREEN+sustained branch — locate the existing `if self.green_streak >= self.green_required:` block and the `raw_rate = self.current_rate + self._compute_probe_step()` line. Insert the clamp BEFORE the existing `return` of that branch:

```python
        if self.green_streak >= self.green_required:
            self._yellow_decay_streak = 0
            raw_rate = self.current_rate + self._compute_probe_step()
            # Phase 201: setpoint clamp on push-up only.
            # Decreases (RED/YELLOW) are unaffected — those branches return earlier.
            if self._docsis_mode and self._setpoint_bps is not None:
                if not (self._headroom_state == "AVAILABLE" and self._cake_aligned):
                    return min(raw_rate, self._setpoint_bps)
            return raw_rate
```

Verify the RED branch (`if self.red_streak >= 1:`) and YELLOW branch (`if zone == "YELLOW":`) and the final `return self.current_rate` are NOT modified. Run a diff and visually confirm.

Add a single new attribute to `get_health_data()` if such a method exists in QueueController — but ONLY if Plan 201-05 hasn't claimed that file's write. Check via the wave-2 plan pair: Plan 201-05 owns `wan_controller.py` health surface; this task owns `queue_controller.py` only. The QueueController-internal health-state fields (docsis_mode_active, setpoint_mbps, headroom_state, rtt_integral_ms_s, cake_aligned) are populated in Plan 201-05 by reading `q._docsis_mode`, `q._setpoint_bps`, etc.; do NOT add a new method here.

Do NOT change any other line in the file.
  </action>
  <acceptance_criteria>
    - `grep -c "def _update_integral" src/wanctl/queue_controller.py` returns 1.
    - `grep -c "def _is_cake_aligned_for_pushup" src/wanctl/queue_controller.py` returns 1.
    - `grep -c "self._update_integral(delta)" src/wanctl/queue_controller.py` returns 1.
    - `grep -c "self._is_cake_aligned_for_pushup(cake_snapshot)" src/wanctl/queue_controller.py` returns 1.
    - `grep -c "min(raw_rate, self._setpoint_bps)" src/wanctl/queue_controller.py` returns >= 1.
    - **REVIEWS MED-4:** `grep -c "yellow_streak >= self.dwell_cycles" src/wanctl/queue_controller.py` returns >= 1 (above-setpoint YELLOW pull-down condition). `grep -c "self.factor_down_yellow" src/wanctl/queue_controller.py` returns >= 1 (the pull-down arithmetic).
    - **REVIEWS HIGH-5:** `grep -c "self.floor_hit_cycles += 1" src/wanctl/queue_controller.py` returns >= 3 (counter wraps at every floor-landing return path: GREEN-clamp, YELLOW-pulldown, RED-decay, fallthrough — at least 3 wrap sites; exact count depends on existing return paths).
    - **REVIEWS HIGH-5:** TestDocsisModeFloorHitCounter passes: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k TestDocsisModeFloorHitCounter` returns 0.
    - **REVIEWS MED-4:** TestDocsisModeAboveSetpointYellowPulldown passes: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k TestDocsisModeAboveSetpointYellowPulldown` returns 0.
    - `grep -v '^#\\|^ *#' src/wanctl/queue_controller.py | grep -c "max_delay_delta_us"` returns >= 1 (corroborator references field).
    - All TestDocsisMode* and TestRedFastTripUnchangedDocsisMode tests pass: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k 'DocsisMode or RedFastTripUnchangedDocsisMode'` returns 0.
    - All pre-existing queue_controller tests still pass: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q` returns 0.
    - Phase 197 replay test still passes (regression gate): `.venv/bin/pytest -o addopts='' tests/test_phase_197_replay.py -q` returns 0.
    - Phase 195 replay test still passes (legacy 3-state replay): `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py -q` returns 0.
    - Hot-path slice green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` returns 0.
    - `.venv/bin/ruff check src/wanctl/queue_controller.py` returns 0.
    - `.venv/bin/mypy src/wanctl/queue_controller.py` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_phase_197_replay.py tests/test_phase_195_replay.py -q &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_health_check.py -q &amp;&amp; .venv/bin/ruff check src/wanctl/queue_controller.py &amp;&amp; .venv/bin/mypy src/wanctl/queue_controller.py</automated>
  </verify>
  <done>Helpers + integral wire-up + setpoint clamp landed; all DOCSIS unit tests green; regression replays still pass; static checks clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire replay test against Attempt 3 corpus + re-baseline SAFE-05 v1.42 pins for controller surface</name>
  <files>tests/test_phase_201_replay.py, tests/test_phase_195_replay.py</files>
  <read_first>
    - tests/test_phase_197_replay.py:1-200 (canonical replay shape — _queue_snapshot, MagicMock, _prepare_queue_primary_controller analog)
    - tests/test_phase_201_replay.py (Plan 201-02 stubs to wire up)
    - tests/fixtures/phase201_replay_corpus.py (loader API)
    - tests/test_phase_195_replay.py:620-680 (SAFE-05 pins to bump for queue_controller surface additions)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md §8 (Replay-Test Corpus)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md (max_delay_delta_us absent — synth that field for replay)
  </read_first>
  <behavior>
    - **REVIEWS HIGH-4 (cycle-fidelity replay, Option A):** TestAttempt3ReplayWithDocsisMode::test_no_floor_hits_with_setpoint_12_cycle_fidelity reads the loaded corpus, builds a DOCSIS-mode QueueController with setpoint_bps=12_000_000 ceiling=18_000_000 floor=8_000_000, expands each 1 Hz NDJSON sample into 20 synthetic 50ms cycles via *hold-last interpolation* (load_rtt_ms, baseline_rtt_ms, cake fields held constant across the 20 cycles), replays the expanded trace, and asserts `ctrl.floor_hit_cycles == 0` (counter delta == 0). The expansion turns the integral window (40 cycles = 2.0s) and YELLOW dwell counter into faithful production cadence. Without expansion, a 2-second integral stretches to ~40 replay-seconds because each NDJSON sample = one controller cycle. Synthesized `max_delay_delta_us` for the CAKE corroborator (since corpus lacks the field): use 0 when backlog_bytes is 0, else 8000 (above the 5ms threshold) to model "high backlog therefore high queue delay" — held constant across the 20 expansion cycles. The expanded replay is intentionally not perfect (cycle-internal RTT variation is lost), but it samples the integral and dwell windows at the right cadence.
    - TestLegacyByteIdentity::test_no_docsis_key_byte_identical_3state replays a synthetic sustained-load trace through (a) a legacy controller and (b) a docsis_mode=False controller and asserts identical (zone, rate) sequences (D-17 invariant).
    - test_phase_195_replay.py SAFE-05 pins re-baselined for queue_controller.py occurrence increases (docsis_mode, setpoint_bps, integral_window_seconds, etc., now appear in queue_controller.py too).
  </behavior>
  <action>
Replace the Plan 201-02 skip stubs in `tests/test_phase_201_replay.py` with full implementations:

```python
"""Phase 201 replay tests — Attempt 3 corpus + legacy byte-identity.

Plan 201-04 Task 3 wires these against the live QueueController surface
landed in Plan 201-04 Tasks 1-2. The test_no_floor_hits_with_setpoint_12
case is the synthetic VALN-06 closure contract: replaying Phase 200's
4-floor-hit failure trace through the new control model produces zero
floor hits.
"""
from __future__ import annotations
import pytest
from wanctl.queue_controller import QueueController
from wanctl.cake_signal import CakeSignalSnapshot
from tests.fixtures.phase201_replay_corpus import (
    load_attempt3_trace,
    synthesize_sustained_load_trace,
)


def _make_docsis_controller(*, setpoint_bps: int = 12_000_000):
    return QueueController(
        name="ReplayUL", floor_green=8_000_000, floor_yellow=8_000_000,
        floor_soft_red=8_000_000, floor_red=8_000_000,
        ceiling=18_000_000, step_up=5_000_000,
        factor_down=0.90, factor_down_yellow=1.0,
        green_required=3, dwell_cycles=3, deadband_ms=3.0,
        consecutive_yellow_decay_clamp=40,
        docsis_mode=True, setpoint_bps=setpoint_bps,
        integral_window_seconds=2.0, integral_threshold_ms_s=30.0,
        cake_backlog_low_threshold_bytes=5000,
        cake_delay_delta_low_threshold_us=5000,
    )


def _make_legacy_controller():
    return QueueController(
        name="ReplayLegacy", floor_green=8_000_000, floor_yellow=8_000_000,
        floor_soft_red=8_000_000, floor_red=8_000_000,
        ceiling=18_000_000, step_up=5_000_000,
        factor_down=0.90, factor_down_yellow=1.0,
        green_required=3, dwell_cycles=3, deadband_ms=3.0,
        consecutive_yellow_decay_clamp=40,
    )


def _make_docsis_off_controller():
    """docsis_mode=False with otherwise identical kwargs — must produce
    byte-identical (zone, rate) trace as legacy controller (D-17)."""
    return QueueController(
        name="ReplayDocsisOff", floor_green=8_000_000, floor_yellow=8_000_000,
        floor_soft_red=8_000_000, floor_red=8_000_000,
        ceiling=18_000_000, step_up=5_000_000,
        factor_down=0.90, factor_down_yellow=1.0,
        green_required=3, dwell_cycles=3, deadband_ms=3.0,
        consecutive_yellow_decay_clamp=40,
        docsis_mode=False,
    )


def _synth_cake_from_sample(sample) -> CakeSignalSnapshot | None:
    """Synthesize a CakeSignalSnapshot from a ReplaySample.

    Per 201-01-CORPUS-AUDIT.md, the captured NDJSON has backlog_bytes and
    cold_start but lacks max_delay_delta_us. We model max_delay_delta_us as
    proportional to backlog: high backlog -> high delay-delta. This is a
    conservative model — it makes the corroborator MORE likely to veto
    push-up under load, which is the safe direction for VALN-06.
    """
    if sample.cake_backlog_bytes is None:
        return None
    backlog = int(sample.cake_backlog_bytes)
    # If backlog > 5000 (corroborator threshold), mark delay-delta high too.
    delay_delta = 8000 if backlog > 5000 else 100
    return CakeSignalSnapshot(
        drop_rate=0.0, total_drop_rate=0.0,
        backlog_bytes=backlog,
        peak_delay_us=delay_delta + 100,
        tins=(),
        cold_start=bool(sample.cake_cold_start),
        avg_delay_us=delay_delta + 50, base_delay_us=50,
        max_delay_delta_us=delay_delta,
    )


class TestAttempt3ReplayWithDocsisMode:
    # REVIEWS HIGH-4 (2026-05-04): Option A cycle-fidelity replay.
    # Each 1 Hz NDJSON sample expands to 20 synthetic 50ms cycles via
    # hold-last interpolation. See test docstring for the assumption.
    CYCLES_PER_SAMPLE = 20  # 1 Hz NDJSON -> 20 Hz controller cadence (1/0.05)

    def test_no_floor_hits_with_setpoint_12_cycle_fidelity(self, phase201_attempt3_trace):
        """REVIEWS HIGH-4 (Option A): cycle-fidelity replay.

        VALN-06 synthetic closure contract: replay Attempt 3 against the
        DOCSIS-mode controller, expanding each 1 Hz NDJSON sample into 20
        synthetic 50ms cycles via hold-last interpolation, and expect zero
        floor hits via the cycle-level counter `ctrl.floor_hit_cycles`.

        Why expansion: without it, the controller's 2-second integral
        window (40 cycles) stretches to ~40 replay-seconds because the
        loop treats each 1 Hz NDJSON sample as one controller cycle.
        That gives the integral a 20x slower response than production.

        Hold-last vs linear interpolation: hold-last is more conservative;
        it doesn't smooth out the RTT-delta peaks that drive the integral.
        Linear interpolation would inadvertently lower peak deltas across
        samples and bias the corroborator toward "AVAILABLE" — hold-last
        keeps the worst-case peak in front of the integral the whole second.

        Documented in RESEARCH.md Assumptions Log A11 (planner adds during
        execute-phase as a SUMMARY artifact).

        Direct evidence improved upon: Phase 200 Attempt 3 verdict.json
        ul_floor_hits_during_load=4 (with v1.41 stack).
        """
        if not phase201_attempt3_trace:
            pytest.skip("Attempt 3 corpus empty — see 201-01-CORPUS-AUDIT.md")

        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        target_delta = 5.0  # mirrors Spectrum legacy global target_bloat_ms=15 / 3
        warn_delta = 15.0   # mirrors Spectrum legacy global warn_bloat_ms=75 / 5
        cycles_replayed = 0
        for sample in phase201_attempt3_trace:
            if sample.baseline_rtt_ms is None or sample.load_rtt_ms is None:
                continue
            cake = _synth_cake_from_sample(sample)
            # Hold-last expansion: 20 synthetic cycles per NDJSON sample.
            for _ in range(self.CYCLES_PER_SAMPLE):
                ctrl.adjust(
                    sample.baseline_rtt_ms,
                    sample.load_rtt_ms,
                    target_delta,
                    warn_delta,
                    cake_snapshot=cake,
                )
                cycles_replayed += 1

        assert cycles_replayed > 0, "no samples replayed"
        # REVIEWS HIGH-5: cycle-level floor-hit counter delta == 0
        assert ctrl.floor_hit_cycles == 0, (
            f"Expected zero floor-hit cycles with docsis_mode + setpoint=12; "
            f"got floor_hit_cycles={ctrl.floor_hit_cycles} across "
            f"{cycles_replayed} cycles ({len(phase201_attempt3_trace)} 1 Hz "
            f"samples * {self.CYCLES_PER_SAMPLE} cycles/sample). Phase 201 "
            f"controller would have failed VALN-06 on Attempt 3 capture."
        )


class TestLegacyByteIdentity:
    def test_no_docsis_key_byte_identical_3state(self, phase201_sustained_load_trace):
        legacy = _make_legacy_controller()
        docsis_off = _make_docsis_off_controller()
        target_delta, warn_delta = 5.0, 15.0
        legacy_trace, docsis_trace = [], []
        for s in phase201_sustained_load_trace:
            l_zone, l_rate, _ = legacy.adjust(s.baseline_rtt_ms, s.load_rtt_ms, target_delta, warn_delta)
            d_zone, d_rate, _ = docsis_off.adjust(s.baseline_rtt_ms, s.load_rtt_ms, target_delta, warn_delta)
            legacy_trace.append((l_zone, l_rate))
            docsis_trace.append((d_zone, d_rate))
        assert legacy_trace == docsis_trace, "D-17 invariant: docsis_mode=False is byte-identical to legacy"
```

NOTE: locate the actual attribute name for the floor in QueueController (it may be `self.floor_red_bps` or `self.floor_red`). Check via grep before writing the assertion line. The `enforce_rate_bounds(... floor=self.floor_red_bps ...)` call in the constructor's `adjust` body is the canonical name to mirror.

Then re-baseline `tests/test_phase_195_replay.py` SAFE-05 pins. After Plan 201-04 Task 1 + Task 2 + Task 3 wiring, `docsis_mode`, `setpoint_bps`, `integral_window_seconds`, `integral_threshold_ms_s`, `cake_backlog_low_threshold_bytes`, and `cake_delay_delta_low_threshold_us` now appear in `queue_controller.py` too. Update the `expected_counts` dict pins by:
1. Running the test once to see the new actual counts.
2. Updating the dict to match the new totals.
3. Adding a comment line: `# v1.42 baseline: Phase 201 controller surface (Plan 201-04) added <N> occurrences of <key>`.

Do NOT modify any v1.41 (Phase 200) pins that should remain stable (warn_bloat=12, target_bloat=14, factor_down=17, etc. — these strings should not appear in Plan 201-04's new code).
  </action>
  <acceptance_criteria>
    - `.venv/bin/pytest -o addopts='' tests/test_phase_201_replay.py -q` returns 0 (replay test green; floor_hits=0 contract met).
    - `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py -q` returns 0 (SAFE-05 v1.42 pins match actual).
    - `grep -c "TestAttempt3ReplayWithDocsisMode" tests/test_phase_201_replay.py` returns 1.
    - **REVIEWS HIGH-4:** `grep -c "test_no_floor_hits_with_setpoint_12_cycle_fidelity" tests/test_phase_201_replay.py` returns 1 (renamed from coarse-regression name).
    - **REVIEWS HIGH-4:** `grep -c "CYCLES_PER_SAMPLE" tests/test_phase_201_replay.py` returns >= 1 (cycle expansion constant). `grep -c "hold-last" tests/test_phase_201_replay.py` returns >= 1 (interpolation choice documented).
    - **REVIEWS HIGH-5:** `grep -c "ctrl.floor_hit_cycles" tests/test_phase_201_replay.py` returns >= 1 (counter-delta verdict, not snapshot-rate).
    - **REVIEWS HIGH-3:** `grep -c "Wave 0 stub" tests/test_queue_controller.py tests/test_phase_201_replay.py 2>/dev/null | awk -F: '{s+=$2} END {print s}'` returns 0 (every Wave 0 stub xfail/fail decorator removed by Plan 04 completion).
    - `grep -c "TestLegacyByteIdentity" tests/test_phase_201_replay.py` returns 1.
    - `grep -c "_synth_cake_from_sample" tests/test_phase_201_replay.py` returns >= 1.
    - Hot-path slice green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` returns 0.
    - Full suite still green: `.venv/bin/pytest -q 2>&1 | tail -5` shows pass count >= Phase 200 baseline (~578) + new Phase 201 tests, with 0 failed.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_phase_201_replay.py tests/test_phase_195_replay.py -q &amp;&amp; .venv/bin/pytest -q 2>&amp;1 | tail -3 | grep -E '0 failed|passed'</automated>
  </verify>
  <done>Replay test asserts floor_hits=0 against Attempt 3 corpus; legacy byte-identity test green; SAFE-05 v1.42 pins re-baselined; full suite green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| WANController cycle → QueueController.adjust | UL load_rtt and CakeSignalSnapshot are produced by trusted in-process measurement; no external untrusted input crosses this boundary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-12 | Tampering | Replay test corpus poisoning | accept | Corpus is in-tree under `.planning/phases/200-...`; mutation requires a tracked git commit (Plan 201-01 inherits this). |
| T-201-13 | Tampering | Augment vs replace mistake (RED fast-trip delayed by integral) | mitigate | TestRedFastTripUnchangedDocsisMode asserts immediate RED decay regardless of headroom_state; ARCH-03 invariant locked by test. |
| T-201-14 | Tampering | Setpoint clamp bypasses last_applied_ul_rate flash-wear dedup | mitigate | Plan 201-05 TestPhase201FlashWear adds the regression gate; THIS plan does not modify the router-write layer (clamp lives at rate-decision layer only). |
| T-201-15 | Spoofing | µs/ms ratio sneaks back into corroborator | mitigate | `_is_cake_aligned_for_pushup` is categorical AND-gate; PATTERNS.md cites Phase 200 RETRO Codex pushback explicitly. Test TestDocsisModeCakeCorroborator pins the categorical shape. |
| T-201-16 | DoS | Window-not-full edge case allows premature push-up at daemon start | mitigate | Window-not-full -> EXHAUSTED is the safe default; tested by TestDocsisModeIntegralClassifier::test_window_not_full_is_exhausted. |
| T-201-17 | Tampering | Negative delta credits headroom (over-predicts AVAILABLE) | mitigate | `max(0.0, delta_ms)` clamp in `_update_integral`; tested by test_negative_delta_clamped_to_zero. |
</threat_model>

<verification>
- All Wave 0 unit tests for QueueController DOCSIS-mode internals are GREEN (5 classes from Plan 201-02 Task 1 + replay tests from Plan 201-02 Task 2).
- Phase 197 + Phase 195 replays still green (no regression in legacy paths).
- Full test suite green; SAFE-05 v1.42 baseline matches.
- Static checks clean (ruff + mypy on queue_controller.py).
- Net new code in queue_controller.py is under ~80 lines (per RESEARCH "Don't Hand-Roll" budget).
</verification>

<success_criteria>
- AUGMENT-not-replace shape preserved: legacy 3-state path byte-identical when docsis_mode=False.
- RED fast-trip immediate (ARCH-03).
- Synthetic VALN-06 closure contract: replay floor_hits = 0.
- D-17 byte-identity test green.
- SAFE-05 v1.42 baseline established for controller surface.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-04-SUMMARY.md` with: lines added/modified in queue_controller.py, replay test floor_hits result (must be 0), full-suite pass count, ruff/mypy status, and a one-line note on whether the synth_cake_from_sample assumption (high backlog -> high delay-delta) is conservative enough.
</output>
