# Phase 161: Adaptive Recovery - Research

**Researched:** 2026-04-10
**Domain:** Exponential rate probing with CAKE signal safety guards in autorate control loop
**Confidence:** HIGH

## Summary

Phase 161 replaces the constant `step_up_bps` rate recovery in `QueueController._compute_rate_3state()` and `_compute_rate_4state()` with exponential probing that multiplies the step size by 1.5x each consecutive GREEN cycle (after `green_required` is met). The probe multiplier resets to 1.0 immediately on any non-GREEN zone transition. Above 90% of ceiling, recovery reverts to linear `step_up_bps` to prevent overshoot.

The key change is scoped to QueueController, which currently computes recovery as `current_rate + step_up_bps` unconditionally. The new behavior: `current_rate + step_up_bps * probe_multiplier` where `probe_multiplier` starts at 1.0 and scales by 1.5x each recovery step. CAKE signals act as a guard -- if the CAKE snapshot shows drops or backlog above threshold during recovery (via the existing DETECT-01/DETECT-02 from Phase 160), the zone won't be GREEN and the multiplier resets.

**Arithmetic impact:** DL recovery from GREEN floor (550 Mbps) to 90% ceiling (846 Mbps) drops from 4.4s to 1.05s with 1.5x multiplier. UL recovery (8 -> 29 Mbps) drops from 0.62s to 0.45s. The exponential probing is most impactful on DL where the recovery gap is large (296 Mbps vs 21 Mbps UL).

**Primary recommendation:** Add `_probe_multiplier` state to `QueueController`, multiply in `_compute_rate_3state()`/`_compute_rate_4state()` recovery branches, reset on any non-GREEN zone classification. Add `probe_ceiling_pct` config (0.9) and `probe_multiplier` config (1.5) to YAML `cake_signal.recovery` section. Expose probe state in health endpoint.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RECOV-01 | Rate recovery uses exponential probing (1.5x step multiplier) guarded by CAKE signals | QueueController._compute_rate_4state() line 397 currently returns `current_rate + step_up_bps`. Replace with `current_rate + step_up_bps * _probe_multiplier`. Multiplier starts at 1.0, grows by probe_factor (1.5) each step. CAKE guard is implicit: Phase 160's backlog suppression (DETECT-02) resets green_streak, preventing recovery when CAKE signals are unhealthy. |
| RECOV-02 | Probing reverts to linear step_up above 90% of ceiling to prevent overshoot | Before computing probe step, check `current_rate >= ceiling * probe_ceiling_pct`. If true, use `step_up_bps` (multiplier=1.0). This prevents the final approach from overshooting with a 113+ Mbps step. |
| RECOV-03 | Probe multiplier resets immediately on any non-GREEN zone transition | In _classify_zone_4state() and _classify_zone_3state(), any path that returns non-GREEN already resets green_streak to 0. Add `_probe_multiplier = 1.0` reset in those same paths. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.12 | Multiplier arithmetic, percentage comparison | No external deps needed [VERIFIED: existing codebase] |
| wanctl.queue_controller | local | Rate computation, zone classification | Phase 160 already has CAKE-aware zone logic [VERIFIED: queue_controller.py] |
| wanctl.cake_signal | local | CakeSignalConfig for new recovery config fields | Existing config dataclass [VERIFIED: cake_signal.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.0+ | Unit tests | Already in dev deps [VERIFIED: pyproject.toml] |

**No new dependencies required.** Phase 161 is pure arithmetic change within existing modules.

## Architecture Patterns

### Where Probe Multiplier Fits in the Existing Flow

```
run_cycle():
  _run_cake_stats()              # Phase 159: reads CAKE snapshot
  _run_congestion_assessment()   # Calls QueueController.adjust_4state()
     -> _classify_zone_4state()  # Returns zone, resets probe on non-GREEN
     -> _compute_rate_4state()   # CHANGED: uses step_up * _probe_multiplier
                                 #   unless above 90% ceiling (linear fallback)
```

The probe multiplier state lives on QueueController, not WANController. Rationale:
- QueueController already owns `step_up_bps`, `green_streak`, `green_required`, `current_rate`, and `ceiling_bps` -- all the data the probe needs
- Probe multiplier resets when zone transitions from GREEN -- QueueController's `_classify_zone_*()` methods are where zone transitions happen
- DL (4-state) and UL (3-state) need independent probe multipliers -- each has its own QueueController instance [VERIFIED: wan_controller.py:292-320]

### Pattern 1: Probe Multiplier State on QueueController

**What:** New instance variables on QueueController for probe state.
**When to use:** Always -- initialized in `__init__`, updated in rate computation.

```python
# Source: proposed extension of QueueController.__init__ [VERIFIED: queue_controller.py:24-78]
class QueueController:
    def __init__(
        self,
        ...
        probe_multiplier_factor: float = 1.5,   # NEW: 1.5x growth per step
        probe_ceiling_pct: float = 0.9,          # NEW: revert to linear above 90%
    ):
        ...
        # Exponential probe state (Phase 161: RECOV-01, RECOV-02, RECOV-03)
        self._probe_multiplier: float = 1.0      # Current multiplier (1.0 = linear)
        self._probe_multiplier_factor: float = probe_multiplier_factor
        self._probe_ceiling_pct: float = probe_ceiling_pct
        self._probe_step_count: int = 0           # Cumulative probe steps for health
```

### Pattern 2: Exponential Probing in Rate Computation

**What:** Replace constant `step_up_bps` with `step_up_bps * _probe_multiplier` in recovery branches.
**Where:** `_compute_rate_4state()` and `_compute_rate_3state()`.

```python
# Source: proposed modification of _compute_rate_4state [VERIFIED: queue_controller.py:388-400]
def _compute_rate_4state(self, zone: str) -> tuple[int, int]:
    """Compute new rate and floor for 4-state logic. Returns (rate, floor)."""
    state_floor = self.floor_green_bps

    if self.red_streak >= 1:
        return int(self.current_rate * self.factor_down), self.floor_red_bps
    if zone == "SOFT_RED":
        return self.current_rate, self.floor_soft_red_bps
    if self.green_streak >= self.green_required:
        # RECOV-01 + RECOV-02: exponential probing, linear above ceiling_pct
        step = self._compute_probe_step()
        return self.current_rate + step, state_floor
    if zone == "YELLOW":
        return int(self.current_rate * self.factor_down_yellow), self.floor_yellow_bps
    return self.current_rate, state_floor
```

```python
# Source: new helper method on QueueController
def _compute_probe_step(self) -> int:
    """Compute recovery step with exponential probing.

    Returns step_up_bps * probe_multiplier, then advances multiplier.
    Reverts to linear (multiplier=1.0) above probe_ceiling_pct of ceiling.
    """
    # RECOV-02: Above 90% ceiling, use linear step_up (prevent overshoot)
    if self.current_rate >= self.ceiling_bps * self._probe_ceiling_pct:
        self._probe_multiplier = 1.0  # Reset for safety
        return self.step_up_bps

    # RECOV-01: Exponential probing
    step = int(self.step_up_bps * self._probe_multiplier)
    self._probe_multiplier *= self._probe_multiplier_factor  # Grow for next cycle
    self._probe_step_count += 1
    return step
```

### Pattern 3: Multiplier Reset on Non-GREEN Zone

**What:** Any non-GREEN zone classification resets `_probe_multiplier` to 1.0.
**Where:** In `_classify_zone_4state()` and `_classify_zone_3state()`, in every path that sets `green_streak = 0`.

```python
# Source: proposed modification of _classify_zone_4state [VERIFIED: queue_controller.py:304-376]
# In RED path (line 326):
    self.red_streak += 1
    self.soft_red_streak = 0
    self.green_streak = 0
    self._yellow_dwell = 0
    self._probe_multiplier = 1.0  # RECOV-03: reset on non-GREEN
    return "RED"

# In YELLOW path (line 332):
    self.green_streak = 0
    self.soft_red_streak = 0
    self.red_streak = 0
    self._probe_multiplier = 1.0  # RECOV-03: reset on non-GREEN
    # ... dwell bypass logic ...

# In SOFT_RED path via _apply_soft_red_sustain (line 378):
    self.soft_red_streak += 1
    self.green_streak = 0
    self.red_streak = 0
    self._yellow_dwell = 0
    self._probe_multiplier = 1.0  # RECOV-03: reset on non-GREEN

# In deadband-hold-YELLOW path (line 349):
    self.green_streak = 0
    self.soft_red_streak = 0
    self.red_streak = 0
    self._yellow_dwell = 0
    self._probe_multiplier = 1.0  # RECOV-03: reset on non-GREEN
```

**Important:** The GREEN path does NOT reset the multiplier. The multiplier only advances in `_compute_probe_step()`, which is only called when `green_streak >= green_required`. This means the multiplier grows per RECOVERY step, not per GREEN cycle. The `green_required` gate (3 cycles) acts as a safety buffer before each step.

### Pattern 4: CAKE Signal Guard (Implicit via Phase 160)

**What:** CAKE signals guard probing without new code in the probe path.
**How:** Phase 160 already implemented DETECT-02 (backlog suppresses green_streak) and DETECT-01 (drop rate bypasses dwell into YELLOW). These mechanisms prevent probing when CAKE detects congestion:

1. If CAKE backlog is high during GREEN -> green_streak reset to 0 -> no recovery step -> probe doesn't advance
2. If CAKE drop rate triggers dwell bypass -> zone becomes YELLOW -> probe multiplier resets to 1.0
3. If refractory period is active -> CAKE snapshot masked -> normal RTT-only zone classification continues

This is the "guarded by CAKE signals" in RECOV-01. No explicit CAKE check needed in the probe logic itself. The existing zone classification already integrates CAKE signals.

### Pattern 5: YAML Config for Recovery Parameters

**What:** New `recovery` subsection under `cake_signal` for probe parameters.

```yaml
cake_signal:
  enabled: true
  # ... existing fields ...
  recovery:                          # NEW section
    probe_multiplier: 1.5            # Step size multiplier per recovery step
    probe_ceiling_pct: 0.9           # Revert to linear above this % of ceiling
```

**Defaults:** `probe_multiplier=1.5`, `probe_ceiling_pct=0.9`. These are the values specified in the requirements. When `cake_signal.enabled=false`, probe multiplier is still 1.0 (constant step_up, existing behavior preserved).

**Design decision:** Recovery probing is gated behind `cake_signal.enabled`. Without CAKE signal guards (DETECT-01/DETECT-02), aggressive exponential probing would overshoot into congestion before RTT-only detection could respond. The CAKE backlog suppression is the safety net that makes exponential probing safe.

### Pattern 6: Health Endpoint Extension

```python
# Source: extend existing cake_detection in get_health_data [VERIFIED: queue_controller.py:418-437]
"recovery_probe": {
    "probe_multiplier": self._probe_multiplier,
    "probe_multiplier_factor": self._probe_multiplier_factor,
    "probe_ceiling_pct": self._probe_ceiling_pct,
    "probe_step_count": self._probe_step_count,
    "above_ceiling_pct": self.current_rate >= self.ceiling_bps * self._probe_ceiling_pct,
},
```

### Recommended Module Change Scope

```
src/wanctl/
  queue_controller.py    # MODIFY: add probe state to __init__, _compute_probe_step(),
                         #   modify _compute_rate_3state/_compute_rate_4state to use probe,
                         #   reset _probe_multiplier in all non-GREEN paths,
                         #   extend get_health_data() with probe state
  wan_controller.py      # MODIFY: pass probe config to QueueController constructors,
                         #   extend _parse_cake_signal_config for recovery section,
                         #   extend SIGUSR1 reload to update probe params
  cake_signal.py         # MODIFY: add probe_multiplier_factor and probe_ceiling_pct
                         #   to CakeSignalConfig dataclass
```

### Anti-Patterns to Avoid

- **Advancing multiplier on every GREEN cycle (not just recovery steps):** The multiplier should only grow when `green_streak >= green_required` triggers a rate increase. If advanced on every GREEN cycle (including the first 3 accumulation cycles), the first recovery step would already be at 1.5^3 = 3.375x, which is too aggressive. Advance only in `_compute_probe_step()`. [CRITICAL]
- **Putting probe state on WANController instead of QueueController:** The probe multiplier is per-direction (DL/UL have different step_up values and ceilings). QueueController is the right owner since it already owns step_up_bps, current_rate, and ceiling_bps.
- **Forgetting to reset probe in _apply_soft_red_sustain:** SOFT_RED also resets green_streak. The probe multiplier must also reset here. This is a 4-state-only path that's easy to miss.
- **Forgetting to reset probe in deadband-hold-YELLOW:** When delta returns below green_threshold but stays within deadband, the zone is YELLOW and green_streak is 0. Probe must also reset here.
- **Using probe_multiplier when cake_signal is disabled:** Without CAKE guards, exponential probing is unsafe. When cake_signal.enabled is false, the probe parameters should default to `probe_multiplier_factor=1.0` (equivalent to linear step_up). This is the safe fallback.
- **Modifying step_up_bps directly:** The adaptive tuner can modify `step_up_bps` via SIGUSR1. The probe multiplier must multiply the CURRENT step_up_bps, not a cached initial value. This ensures tuner changes are respected.
- **Capping the probe multiplier:** With green_required=3, CAKE backlog guard, and 90% ceiling linear fallback, the multiplier naturally caps itself. Explicit max_multiplier is unnecessary complexity. At step 7, the step would be 170 Mbps, but at that point `current_rate + 170 > 846 (90% ceiling)` so linear kicks in.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CAKE signal guarding | New CAKE check in probe path | Phase 160's DETECT-02 backlog suppression | Already resets green_streak when CAKE shows backlog [VERIFIED: queue_controller.py:366-375] |
| Rate bounds enforcement | Custom ceiling clamp in probe | enforce_rate_bounds() | Already called after _compute_rate_4state [VERIFIED: queue_controller.py:296] |
| Config reload | New reload path for probe params | Extend _reload_cake_signal_config() | Proven SIGUSR1 pattern [VERIFIED: wan_controller.py:1800-1854] |
| Health endpoint | New HTTP section for probe | Extend QueueController.get_health_data() | Existing pattern returns dict merged into response [VERIFIED: queue_controller.py:418-437] |

**Key insight:** The "guarded by CAKE signals" requirement is already satisfied by Phase 160's detection logic. Phase 161 only needs to add the multiplier arithmetic and reset logic. No new CAKE integration code.

## Common Pitfalls

### Pitfall 1: Multiplier Not Resetting on Backlog Suppression
**What goes wrong:** Backlog suppression (DETECT-02) resets green_streak to 0 but probe_multiplier keeps growing. Next time green_streak reaches green_required, probe step is inappropriately large.
**Why it happens:** The backlog suppression path in GREEN branch resets green_streak but is still in a GREEN zone classification -- the non-GREEN reset paths don't execute.
**How to avoid:** Reset `_probe_multiplier = 1.0` whenever `green_streak` is reset to 0 by backlog suppression (in the GREEN branch's backlog guard). This ensures multiplier and green_streak stay synchronized.
**Warning signs:** Large probe steps immediately after backlog clears.

### Pitfall 2: Overshoot at Ceiling Boundary
**What goes wrong:** At 89% of ceiling, probe step is large (e.g., 75 Mbps). After step, rate exceeds ceiling. Next cycle, enforce_rate_bounds clamps to ceiling. But the probe multiplier advanced, so if rate drops and recovers, first step is already at high multiplier.
**Why it happens:** Probe multiplier advances in _compute_probe_step() even if enforce_rate_bounds subsequently clamps.
**How to avoid:** The linear fallback at 90% ceiling prevents this. enforce_rate_bounds handles any edge cases. The multiplier reset on next non-GREEN handles the recovery scenario.
**Warning signs:** Rate pinned at ceiling with high probe_multiplier in health endpoint.

### Pitfall 3: Test Breakage from New Constructor Parameters
**What goes wrong:** Adding required parameters to QueueController.__init__ breaks 116 existing tests.
**Why it happens:** Tests create QueueController with positional or keyword args that don't include probe params.
**How to avoid:** New params MUST have defaults: `probe_multiplier_factor=1.5`, `probe_ceiling_pct=0.9`. With cake_signal disabled (default), behavior is linear (multiplier stays at 1.0). Existing test fixtures don't need modification.
**Warning signs:** Mass test failures on import.

### Pitfall 4: Interaction with Adaptive Tuner's step_up Changes
**What goes wrong:** Tuner modifies step_up_bps via SIGUSR1 hot-reload. If probe cached the old step_up, tuner changes are ignored.
**Why it happens:** `_compute_probe_step()` could capture step_up at init time instead of reading current value.
**How to avoid:** Always read `self.step_up_bps` (the live attribute) in `_compute_probe_step()`. Never cache step_up separately. [VERIFIED: wan_controller.py:131-132 shows tuner modifies step_up_bps directly]
**Warning signs:** Rate recovery behavior doesn't change after SIGUSR1 reload.

### Pitfall 5: UL Probe Growing Too Large for Small Ceiling
**What goes wrong:** UL step_up=5Mbps, ceiling=32Mbps. After 3 exponential steps (5, 7.5, 11.25), total recovery=23.75 Mbps. But step 3 alone (11.25 Mbps) is 35% of ceiling, which could cause UL congestion.
**Why it happens:** 1.5x multiplier on small ceilings produces steps that are large relative to total bandwidth.
**How to avoid:** The 90% ceiling linear fallback (RECOV-02) catches this: 32*0.9=28.8 Mbps. After steps from 8 to ~31 Mbps, linear kicks in. Also, the existing CAKE backlog guard resets green_streak if UL queue backs up. Finally, enforce_rate_bounds clamps at ceiling.
**Warning signs:** UL rate overshoots ceiling and gets clamped. Monitor via health endpoint.

### Pitfall 6: Probe Multiplier Persisted in State File
**What goes wrong:** If _probe_multiplier is saved to state_file and restored on restart, daemon starts with inflated multiplier from previous session.
**Why it happens:** WANController.save_state/load_state persists various counters.
**How to avoid:** Do NOT persist _probe_multiplier. It should always start at 1.0 on daemon restart. The multiplier is transient recovery state, not persistent configuration.
**Warning signs:** Large first recovery step after daemon restart.

## Code Examples

### Example 1: Complete _compute_probe_step Implementation

```python
# Source: proposed new method on QueueController
def _compute_probe_step(self) -> int:
    """Compute recovery step with exponential probing (RECOV-01, RECOV-02).

    Step = step_up_bps * _probe_multiplier, then advance multiplier.
    Above probe_ceiling_pct of ceiling, reverts to linear step_up_bps.

    Returns:
        Step size in bps to add to current_rate.
    """
    # RECOV-02: Linear above ceiling threshold
    if self.current_rate >= self.ceiling_bps * self._probe_ceiling_pct:
        # Don't reset multiplier here -- it resets on next non-GREEN
        return self.step_up_bps

    # RECOV-01: Exponential probing
    step = int(self.step_up_bps * self._probe_multiplier)
    self._probe_multiplier *= self._probe_multiplier_factor
    self._probe_step_count += 1
    return step
```

### Example 2: Modified _compute_rate_3state (Upload)

```python
# Source: proposed modification [VERIFIED: queue_controller.py:211-219]
def _compute_rate_3state(self, zone: str) -> int:
    """Compute new rate for 3-state logic based on zone and streaks."""
    if self.red_streak >= 1:
        return int(self.current_rate * self.factor_down)
    if self.green_streak >= self.green_required:
        return self.current_rate + self._compute_probe_step()  # CHANGED
    if zone == "YELLOW":
        return int(self.current_rate * self.factor_down_yellow)
    return self.current_rate
```

### Example 3: Multiplier Reset Points in 4-State Classification

```python
# Source: all reset points in _classify_zone_4state [VERIFIED: queue_controller.py:304-376]
# Every path that sets green_streak = 0 also resets _probe_multiplier:
#
# 1. RED path (line 326):
#    self.green_streak = 0
#    self._probe_multiplier = 1.0
#
# 2. YELLOW path (line 332-333):
#    self.green_streak = 0
#    self._probe_multiplier = 1.0
#
# 3. SOFT_RED sustain (line 380):
#    self.green_streak = 0
#    self._probe_multiplier = 1.0
#
# 4. Deadband hold YELLOW (line 350-351):
#    self.green_streak = 0
#    self._probe_multiplier = 1.0
#
# 5. GREEN with backlog suppression (DETECT-02, line 370):
#    self.green_streak = 0
#    self._probe_multiplier = 1.0  # CRITICAL: also reset here
```

### Example 4: YAML Config Parsing Extension

```python
# Source: extend _parse_cake_signal_config [VERIFIED: wan_controller.py:626-710]
# After existing detection section parsing:
rec = cs.get("recovery", {})
if not isinstance(rec, dict):
    rec = {}

probe_multiplier = rec.get("probe_multiplier", 1.5)
if not isinstance(probe_multiplier, (int, float)) or isinstance(probe_multiplier, bool) or probe_multiplier < 1.0:
    probe_multiplier = 1.5
probe_multiplier = max(1.0, min(5.0, float(probe_multiplier)))  # Sane bounds

probe_ceiling_pct = rec.get("probe_ceiling_pct", 0.9)
if not isinstance(probe_ceiling_pct, (int, float)) or isinstance(probe_ceiling_pct, bool) or probe_ceiling_pct <= 0:
    probe_ceiling_pct = 0.9
probe_ceiling_pct = max(0.5, min(1.0, float(probe_ceiling_pct)))  # 50%-100% of ceiling
```

### Example 5: Passing Probe Config to QueueController

```python
# Source: proposed extension of WANController.__init__ [VERIFIED: wan_controller.py:292-320]
# In _setup_cake_signal() or after QueueController construction:
if config.enabled and self._cake_signal_supported:
    # ... existing threshold passing ...
    self.download._probe_multiplier_factor = config.probe_multiplier_factor
    self.download._probe_ceiling_pct = config.probe_ceiling_pct
    self.upload._probe_multiplier_factor = config.probe_multiplier_factor
    self.upload._probe_ceiling_pct = config.probe_ceiling_pct
```

**Alternative (cleaner):** Pass probe params via QueueController constructor. But this requires modifying the constructor signature at the call site in WANController.__init__, which is already crowded. The direct attribute assignment pattern matches Phase 160's approach for detection thresholds. [VERIFIED: wan_controller.py:601-608]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Constant step_up_bps per GREEN cycle | Exponential probing with 1.5x multiplier | Phase 161 (this) | DL recovery 4.4s -> 1.05s from floor to 90% ceiling |
| No overshoot protection | Linear above 90% ceiling | Phase 161 (this) | Prevents 100+ Mbps steps near ceiling |
| No probe reset mechanism | Immediate reset on non-GREEN zone | Phase 161 (this) | Ensures probe starts fresh after each congestion event |

**Related work:** cake-autorate (lynxthecat) uses additive increase with a base rate plus a "load high" factor proportional to achieved throughput. wanctl's exponential probing is more aggressive but guarded by direct CAKE queue observation (drops, backlog) rather than pure RTT. The CAKE signal guard is what makes exponential probing safe -- without it, pure RTT latency is too slow to catch the overshoot. [CITED: https://deepwiki.com/lynxthecat/cake-autorate]

**TCP analogy:** This is analogous to TCP slow start (exponential phase) transitioning to congestion avoidance (linear phase). The 90% ceiling threshold acts like `ssthresh`. The probe multiplier reset on non-GREEN acts like the cwnd reset on packet loss. The key difference: wanctl uses direct queue observation (CAKE drops/backlog) as the loss signal, not packet loss itself.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 1.5x multiplier is appropriate growth rate | Architecture Patterns | Too aggressive = overshoot before CAKE detects congestion. Too conservative = minimal improvement over linear. 1.5x is specified in requirements so treated as locked decision. Can be A/B tested since configurable. |
| A2 | 90% ceiling threshold is the right linear fallback point | Architecture Patterns | Too low = goes linear too early, diminishing exponential benefit. Too high = risks overshoot near ceiling. 0.9 is specified in requirements. Configurable for A/B testing. |
| A3 | probe_multiplier_factor=1.0 is safe fallback when cake_signal disabled | Anti-Patterns | Without CAKE guards, exponential probing may overshoot. 1.0 preserves existing linear behavior. Low risk since explicit requirement specifies "guarded by CAKE signals." [ASSUMED] |
| A4 | Not persisting _probe_multiplier in state file is correct | Pitfall 6 | Starting at 1.0 on restart means first recovery is slow. But starting at inflated multiplier could cause immediate overshoot. Conservative default is safer. [ASSUMED] |

## Open Questions (RESOLVED)

1. **Should probe parameters differ for DL vs UL?** — RESOLVED: Start with same params (1.5x, 90% threshold) for both. UL's small ceiling provides natural protection. A/B test independently if needed.
   - Decision: Same params, measure in production.

2. **Should probe_multiplier also reset when backlog suppression fires?** — RESOLVED: YES, reset on backlog suppression for consistency. Prevents stale multiplier carrying over after suppression clears.
   - Decision: Reset probe_multiplier wherever green_streak is set to 0.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with xdist parallel |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_queue_controller.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v --timeout=2` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RECOV-01 | Exponential probing: step grows by 1.5x each recovery cycle | unit | `.venv/bin/pytest tests/test_queue_controller.py::TestExponentialProbing -x` | Wave 0 |
| RECOV-01 | CAKE guard: probing stops when backlog suppresses green_streak | unit | `.venv/bin/pytest tests/test_queue_controller.py::TestProbeCAKEGuard -x` | Wave 0 |
| RECOV-02 | Linear above 90% ceiling: step reverts to base step_up | unit | `.venv/bin/pytest tests/test_queue_controller.py::TestProbeLinearFallback -x` | Wave 0 |
| RECOV-03 | Multiplier reset on YELLOW/RED/SOFT_RED zone transition | unit | `.venv/bin/pytest tests/test_queue_controller.py::TestProbeMultiplierReset -x` | Wave 0 |
| RECOV-03 | Multiplier reset on backlog suppression in GREEN | unit | `.venv/bin/pytest tests/test_queue_controller.py::TestProbeResetOnBacklog -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_queue_controller.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v --timeout=2`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_queue_controller.py::TestExponentialProbing` -- covers RECOV-01 (step growth)
- [ ] `tests/test_queue_controller.py::TestProbeCAKEGuard` -- covers RECOV-01 (CAKE guard)
- [ ] `tests/test_queue_controller.py::TestProbeLinearFallback` -- covers RECOV-02 (90% ceiling)
- [ ] `tests/test_queue_controller.py::TestProbeMultiplierReset` -- covers RECOV-03 (zone reset)
- [ ] `tests/test_queue_controller.py::TestProbeResetOnBacklog` -- covers RECOV-03 (backlog reset)
- [ ] No framework install needed (pytest already configured)
- [ ] Existing 116 tests must pass unchanged (backward compatibility)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Validate probe_multiplier (1.0-5.0) and probe_ceiling_pct (0.5-1.0) in YAML parsing |
| V6 Cryptography | no | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious probe_multiplier in YAML (e.g., 1000.0) | Tampering | Bounds check max(1.0, min(5.0, value)) in config parsing |
| Malicious probe_ceiling_pct (e.g., 0.01) | Tampering | Bounds check max(0.5, min(1.0, value)) in config parsing |
| Probe multiplier growing without bound | Denial of Service (rate overshoot) | Natural bound: 90% ceiling fallback + zone reset + enforce_rate_bounds |

## Sources

### Primary (HIGH confidence)
- Existing codebase `queue_controller.py` -- _compute_rate_4state, _compute_rate_3state, zone classification, green_streak logic [VERIFIED: src/wanctl/queue_controller.py, 437 lines]
- Existing codebase `wan_controller.py` -- _run_congestion_assessment, _parse_cake_signal_config, _reload_cake_signal_config, QueueController construction [VERIFIED: src/wanctl/wan_controller.py]
- Existing codebase `cake_signal.py` -- CakeSignalConfig dataclass, CakeSignalSnapshot [VERIFIED: src/wanctl/cake_signal.py, 304 lines]
- Phase 160 research [VERIFIED: .planning/phases/160-congestion-detection/160-RESEARCH.md]
- Phase 159 research [VERIFIED: .planning/phases/159-cake-signal-infrastructure/159-RESEARCH.md]
- Production config `configs/spectrum.yaml` -- step_up=10, ceiling=940, green_required=3, UL step_up=5, UL ceiling=32 [VERIFIED]

### Secondary (MEDIUM confidence)
- [cake-autorate DeepWiki](https://deepwiki.com/lynxthecat/cake-autorate) -- Rate recovery approach comparison [CITED]

### Tertiary (LOW confidence)
- None. All critical claims verified against codebase or derived from arithmetic.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new deps, all existing code
- Architecture: HIGH -- extends well-understood _compute_rate methods with simple arithmetic
- Pitfalls: HIGH -- derived from careful analysis of all green_streak=0 reset paths and state interactions
- Recovery arithmetic: HIGH -- verified with explicit calculation of DL/UL step progressions

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable domain, extends existing patterns)
