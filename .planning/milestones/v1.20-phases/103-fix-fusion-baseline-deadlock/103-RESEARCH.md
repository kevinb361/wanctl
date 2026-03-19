# Phase 103: Fix Fusion Baseline Deadlock - Research

**Researched:** 2026-03-19
**Domain:** RTT fusion + baseline EWMA interaction, control loop signal integrity
**Confidence:** HIGH

## Summary

The fusion baseline deadlock is a structural bug in how `_compute_fused_rtt()` feeds into `update_ewma()` and `_update_baseline_if_idle()`. When IRTT RTT diverges from ICMP RTT (due to different network paths), the fused signal permanently inflates or deflates `load_rtt` relative to `baseline_rtt`, creating a persistent delta that either freezes baseline updates forever or drifts baseline to an incorrect value.

The root cause is simple: both `load_rtt` and `baseline_rtt` are driven by the same fused signal, but baseline freeze logic uses `delta = load_rtt - baseline_rtt` as its gate. When IRTT path RTT differs from ICMP path RTT by a fixed offset, this offset gets baked into `load_rtt` but baseline either cannot track it (freeze) or tracks it incorrectly (drift to a non-ICMP value). The fix must ensure baseline update logic operates on the ICMP-only signal, not the fused signal.

**Primary recommendation:** Pass ICMP filtered_rtt (pre-fusion) to `_update_baseline_if_idle()` while keeping fused_rtt for `load_rtt` EWMA. This preserves baseline as an ICMP-derived reference point while fusion enhances congestion detection sensitivity.

## The Deadlock Mechanism (Detailed)

### Current Data Flow (lines 2596-2597 of autorate_continuous.py)

```
measured_rtt (raw ICMP)
  -> signal_processor.process() -> filtered_rtt (Hampel-filtered ICMP)
  -> _compute_fused_rtt(filtered_rtt) -> fused_rtt (0.7*ICMP + 0.3*IRTT)
  -> update_ewma(fused_rtt)
      -> load_rtt = EWMA(fused_rtt)         # Fast EWMA, always updates
      -> _update_baseline_if_idle(fused_rtt)  # Slow EWMA, conditional
          -> delta = load_rtt - baseline_rtt
          -> if delta < 3ms: baseline_rtt = EWMA(fused_rtt)
```

### Scenario A: IRTT > ICMP (ATT Case -- THE DEADLOCK)

Production values: ATT ICMP ~29ms, IRTT Dallas ~43ms

```
Idle state:
  fused_rtt = 0.7 * 29 + 0.3 * 43 = 33.2ms
  load_rtt converges -> 33.2ms
  baseline_rtt initially ~31ms (from config)
  delta = 33.2 - 31 = 2.2ms < 3ms threshold -> baseline updates toward 33.2ms
  baseline converges -> ~33ms

Under light congestion (ICMP goes to 35ms, IRTT stays 43ms):
  fused_rtt = 0.7 * 35 + 0.3 * 43 = 37.4ms
  load_rtt converges -> 37.4ms
  delta = 37.4 - 33 = 4.4ms > 3ms -> BASELINE FREEZES

  The real ICMP delta is only 35 - 29 = 6ms (should be YELLOW at most)
  But the system sees delta = 4.4ms which is correct for the fused signal.
  HOWEVER: baseline is now stuck at 33ms (a FUSION artifact, not true ICMP baseline).
```

The problem compounds: baseline drifts to a fused value (33ms) that no longer represents the true ICMP idle latency (29ms). This means:
- The 3ms freeze threshold is tested against a fused-vs-fused delta, which is correct
- But baseline_rtt itself is contaminated -- it no longer represents ICMP idle RTT
- Zone thresholds (GREEN < 15ms delta, YELLOW < 45ms) are designed for ICMP-derived deltas
- With fused baseline of 33ms and fused load of 37.4ms, delta = 4.4ms (looks GREEN)
- Real ICMP load = 35ms vs real ICMP idle = 29ms = 6ms delta (also GREEN, but different)
- Under heavy congestion, IRTT dampens the signal: ICMP 80ms -> fused 0.7*80 + 0.3*43 = 68.9ms
- delta = 68.9 - 33 = 35.9ms vs true ICMP delta = 80 - 29 = 51ms
- **Fusion MASKS real congestion by dampening the fused signal with stale IRTT**

### Scenario B: IRTT < ICMP (Spectrum Case -- OVER-SENSITIVITY)

Production values: Spectrum ICMP ~25ms (idle), IRTT Dallas ~19ms

```
Idle state:
  fused_rtt = 0.7 * 25 + 0.3 * 19 = 23.2ms
  load_rtt converges -> 23.2ms
  baseline converges -> ~23ms (BELOW true ICMP idle!)

Under congestion (ICMP goes to 40ms, IRTT stays 19ms):
  fused_rtt = 0.7 * 40 + 0.3 * 19 = 33.7ms
  delta = 33.7 - 23 = 10.7ms

  True ICMP delta = 40 - 25 = 15ms (exactly at GREEN/YELLOW boundary)
  Fused delta = 10.7ms (still GREEN -- IRTT dampens congestion signal AGAIN)
```

### Scenario C: IRTT Staleness Oscillation

IRTT cadence = 10s, ICMP cadence = 50ms (200x difference). Between IRTT updates:
- For 10 seconds, the same IRTT value is reused across ~200 ICMP cycles
- If ICMP drops while IRTT is stale-but-within-3x-cadence (30s), fused signal is wrong
- When IRTT finally goes stale (age > 30s), fusion falls back to ICMP-only
- This creates a step change in the signal: fused -> ICMP-only -> fused
- Each step perturbs load_rtt EWMA, creating spurious delta oscillations

### Core Insight

**Baseline RTT is an ICMP-derived concept.** It represents the idle propagation delay measured by ICMP pings to CDN reflectors. Fusing a different-path IRTT signal into this value corrupts its meaning. The fix is architectural: baseline must be driven by ICMP-only signal, while load_rtt can use the fused signal for enhanced congestion sensitivity.

## Architecture Patterns

### Recommended Fix: Split Signal Path

```python
# CURRENT (broken):
fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
self.update_ewma(fused_rtt)  # Both load_rtt AND baseline_rtt get fused signal

# FIXED:
fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
self._update_load_rtt(fused_rtt)           # load_rtt uses fused signal
self._update_baseline_if_idle(signal_result.filtered_rtt)  # baseline uses ICMP only
```

This means `update_ewma()` must be split into two separate calls, or `_update_baseline_if_idle()` must receive a separate `icmp_rtt` argument.

### Option 1: Separate update_ewma into two calls (RECOMMENDED)

```python
def run_cycle(self):
    signal_result = self.signal_processor.process(...)
    fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)

    # Fast EWMA: uses fused signal for enhanced congestion detection
    self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * fused_rtt

    # Slow EWMA: uses ICMP-only for true baseline tracking
    self._update_baseline_if_idle(signal_result.filtered_rtt)
```

**Pros:** Minimal change, clear intent, preserves baseline as ICMP reference
**Cons:** `update_ewma()` method signature changes or is removed

### Option 2: Pass ICMP RTT separately to _update_baseline_if_idle

```python
def update_ewma(self, fused_rtt: float, icmp_rtt: float) -> None:
    self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * fused_rtt
    self._update_baseline_if_idle(icmp_rtt)
```

**Pros:** Keeps update_ewma as single entry point
**Cons:** Changes method signature (breaks callers), mixes concerns

### Option 3: Baseline delta uses ICMP-only load_rtt (REJECTED)

Track a separate `icmp_load_rtt` for baseline comparison. This is over-engineered -- two load_rtt EWMAs running in parallel adds complexity without benefit.

### Recommended: Option 1

Split the call site in `run_cycle()`. This is the smallest, safest change. The `update_ewma()` method can remain for backward compatibility (tests that call it directly) but `run_cycle()` inlines the two operations.

### Impact on Congestion Detection

Zone determination uses `delta = load_rtt - baseline_rtt`:

```python
# adjust_4state (line 1376):
delta = load_rtt - baseline_rtt
```

After the fix:
- `load_rtt` = EWMA of fused signal (reflects both ICMP + IRTT)
- `baseline_rtt` = EWMA of ICMP-only (true idle reference)
- `delta` = fused_load - icmp_baseline

This delta will be **larger** than pure ICMP delta when IRTT is stable (good -- more sensitive to ICMP congestion since IRTT anchors load_rtt lower) and **smaller** when IRTT path is congested too (acceptable -- both paths congested means genuine congestion).

Actually wait -- this creates a NEW asymmetry. When idle:
- load_rtt = fused = 0.7 * 25 + 0.3 * 19 = 23.2ms (Spectrum)
- baseline_rtt = ICMP = 25ms
- delta = 23.2 - 25 = -1.8ms (NEGATIVE!)

Negative delta would put us permanently in GREEN (delta < 15ms threshold), which is correct behavior (idle line). But the baseline would try to update toward the ICMP value of 25ms, which is correct since we're passing ICMP-only to _update_baseline_if_idle.

Let me reconsider. The delta used for baseline freeze check:

```python
delta = self.load_rtt - self.baseline_rtt
if delta < self.baseline_update_threshold:  # delta < 3ms
    # update baseline
```

With split signals at idle:
- load_rtt = 23.2ms (fused), baseline_rtt = 25ms (ICMP)
- delta = 23.2 - 25 = -1.8ms < 3ms -> baseline updates (CORRECT: line is idle)

But the delta check in `_update_baseline_if_idle` uses `self.load_rtt` which is now fused. The question is: should the baseline freeze check use fused load_rtt or ICMP-only load?

**Answer: The baseline freeze delta should also use ICMP-only.** Otherwise:
- Fused load_rtt can be depressed by low IRTT, giving a false "idle" signal
- Or elevated by high IRTT, giving a false "loaded" signal

### Refined Fix: ICMP-only for both baseline operations

```python
def run_cycle(self):
    signal_result = self.signal_processor.process(...)
    icmp_filtered = signal_result.filtered_rtt
    fused_rtt = self._compute_fused_rtt(icmp_filtered)

    # Fast EWMA: fused signal for congestion detection
    self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * fused_rtt

    # Slow EWMA: ICMP-only for baseline (needs its own delta check)
    self._update_baseline_if_idle_icmp(icmp_filtered)
```

```python
def _update_baseline_if_idle_icmp(self, icmp_rtt: float) -> None:
    """Update baseline using ICMP-only signal.

    Delta check also uses an ICMP-derived load estimate to avoid
    fusion-induced false idle/load signals.
    """
    # Use an ICMP-only fast EWMA for the idle check
    self._icmp_load_rtt = (
        (1 - self.alpha_load) * self._icmp_load_rtt + self.alpha_load * icmp_rtt
    )
    delta = self._icmp_load_rtt - self.baseline_rtt

    if delta < self.baseline_update_threshold:
        old_baseline = self.baseline_rtt
        new_baseline = (1 - self.alpha_baseline) * self.baseline_rtt + self.alpha_baseline * icmp_rtt
        # bounds check...
        self.baseline_rtt = new_baseline
```

**But this introduces a second EWMA (icmp_load_rtt)** -- exactly what Option 3 rejected. However, it may be necessary. The alternative is simpler:

### Simplest Correct Fix: Use ICMP filtered_rtt for baseline, fused for load

```python
# In run_cycle():
fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * fused_rtt
self._update_baseline_if_idle(signal_result.filtered_rtt)

# _update_baseline_if_idle remains unchanged BUT its delta check
# uses self.load_rtt (which is fused). This is problematic as analyzed above.
```

The cleanest approach: keep `_update_baseline_if_idle` unchanged but pass it `icmp_rtt` as the `measured_rtt` argument. The delta check inside uses `self.load_rtt` (fused) vs `self.baseline_rtt` (ICMP). When fusion is disabled, these are identical signals. When fusion is enabled, the delta will reflect the fused-vs-ICMP spread. This spread is:
- When idle: fused_load is depressed by low IRTT -> smaller delta -> baseline updates (GOOD)
- When idle: fused_load is elevated by high IRTT -> larger delta -> baseline may freeze (BAD, same deadlock for ATT case!)

**Therefore: a dual-track approach IS needed.** The delta check must use an ICMP-consistent signal. Two approaches:

### Approach A: Dedicated ICMP load EWMA (small overhead, clean semantics)

Add `_icmp_load_rtt` EWMA that tracks ICMP-only, used solely for baseline freeze decision. Cost: one extra float multiply per cycle (negligible at 50ms).

### Approach B: Raw delta from filtered ICMP (no EWMA, use instantaneous)

Use `abs(icmp_filtered - baseline_rtt)` directly for the freeze check. This avoids a second EWMA but makes the freeze decision more jittery. Given that baseline updates use EWMA smoothing internally (alpha_baseline is very small ~0.001-0.02), the occasional spurious update from a jittery delta is harmless.

### Recommended Approach: B (simplest, no new state)

```python
def _update_baseline_if_idle(self, icmp_rtt: float) -> None:
    """ICMP-only baseline update. Uses instantaneous delta for freeze check."""
    delta = icmp_rtt - self.baseline_rtt  # CHANGED: use ICMP, not load_rtt
    if delta < self.baseline_update_threshold:
        new_baseline = (1 - self.alpha_baseline) * self.baseline_rtt + self.alpha_baseline * icmp_rtt
        # bounds check...
        self.baseline_rtt = new_baseline
```

Wait -- there's a subtlety. The existing code uses `self.load_rtt - self.baseline_rtt` not `measured_rtt - baseline_rtt`. The load_rtt EWMA smooths measurement noise. Using raw `icmp_rtt` directly would be noisier. But baseline alpha is already very small (0.001-0.02), so even if a few noisy samples slip through the freeze gate, baseline barely moves.

Actually, re-reading the code more carefully:

```python
delta = self.load_rtt - self.baseline_rtt  # line 2011
```

This uses the EWMA-smoothed load_rtt, not the raw measurement. The smoothing is important because a single low ICMP sample shouldn't unfreeze baseline during genuine load. The EWMA acts as a filter.

So the most correct fix needs the ICMP-only EWMA (Approach A). But we can simplify by using the ICMP filtered_rtt (already Hampel-filtered, so outliers removed) directly:

### Final Recommended Fix

```python
def _update_baseline_if_idle(self, icmp_filtered_rtt: float) -> None:
    """Update baseline using ICMP-only signal.

    Uses icmp_filtered_rtt (Hampel-filtered, outlier-free) for both
    the freeze gate and the EWMA update. The Hampel filter provides
    sufficient noise rejection without needing a second load EWMA.
    """
    delta = icmp_filtered_rtt - self.baseline_rtt
    if abs(delta) < self.baseline_update_threshold:
        old_baseline = self.baseline_rtt
        new_baseline = (
            (1 - self.alpha_baseline) * self.baseline_rtt
            + self.alpha_baseline * icmp_filtered_rtt
        )
        if not (self.baseline_rtt_min <= new_baseline <= self.baseline_rtt_max):
            return
        self.baseline_rtt = new_baseline
```

Key changes from current code:
1. `delta = icmp_filtered_rtt - self.baseline_rtt` instead of `self.load_rtt - self.baseline_rtt`
2. Uses `abs(delta)` to handle both IRTT > ICMP and IRTT < ICMP cases
3. `measured_rtt` argument is now explicitly ICMP filtered_rtt, not fused

Note on `abs(delta)`: Current code does NOT use abs(), meaning negative deltas (load_rtt < baseline_rtt) always pass the freeze gate. This is intentional -- if load is below baseline, the line is definitely idle. With ICMP-only delta, same logic applies: `icmp_filtered < baseline` means idle. So `abs()` is NOT needed -- keep the existing `delta < threshold` without abs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Second EWMA for ICMP load tracking | Dual load_rtt tracking | Use Hampel-filtered ICMP directly for baseline delta | Hampel filter already removes outliers; additional EWMA adds state, complexity, and a tuning parameter with no clear benefit |
| Fusion-aware baseline thresholds | Dynamic threshold adjustment based on fusion state | Fix the signal path (pass ICMP to baseline) | Adjusting thresholds treats the symptom, not the cause |
| Per-protocol baseline tracking | Separate ICMP baseline and IRTT baseline | Single ICMP baseline with fusion only in load_rtt | Baseline is semantically an ICMP concept; IRTT is a supplementary signal |

## Common Pitfalls

### Pitfall 1: Breaking the update_ewma() contract

**What goes wrong:** Existing tests call `update_ewma()` directly and expect it to update both load_rtt and baseline_rtt. Splitting the call in run_cycle() but leaving update_ewma() intact means tests still pass but the method becomes misleading.
**Why it happens:** 50+ test sites call update_ewma() directly.
**How to avoid:** Keep update_ewma() as-is for backward compat. Override its behavior in run_cycle() by inlining the two-step logic. Or: keep update_ewma() but add an optional `icmp_rtt` parameter that defaults to `measured_rtt` for backward compat.
**Warning signs:** Tests calling update_ewma(fused_rtt) and checking baseline behavior.

### Pitfall 2: Congestion zone delta uses load_rtt which is fused

**What goes wrong:** After the fix, `delta = load_rtt - baseline_rtt` in adjust_4state() computes fused_load - icmp_baseline. This is correct (we WANT fused load for sensitivity) but the delta MAGNITUDE changes compared to pre-fix.
**Why it happens:** Before: fused_load - fused_baseline (close). After: fused_load - icmp_baseline (different magnitudes).
**How to avoid:** Analyze the production impact. For Spectrum (IRTT < ICMP), delta gets LARGER (more sensitive). For ATT (IRTT > ICMP), delta gets SMALLER (less sensitive). This may require threshold recalibration.
**Warning signs:** Different congestion zone behavior after the fix.

### Pitfall 3: State file backward compatibility

**What goes wrong:** State files persist `ewma.baseline_rtt` and `ewma.load_rtt`. After fix, baseline_rtt semantics change (now ICMP-only vs previously fused-influenced). A daemon restart loads the old baseline, which may be the fused-contaminated value.
**Why it happens:** State file is read at startup via load_state().
**How to avoid:** Old baseline values are within bounds (10-60ms range). The ICMP-only EWMA will naturally converge to correct ICMP baseline over time. No migration needed, but initial convergence period should be documented.
**Warning signs:** Baseline drift alert firing after daemon restart post-fix.

### Pitfall 4: Fusion-disabled case must be unchanged

**What goes wrong:** When fusion is disabled (default), fused_rtt = filtered_rtt. The fix must produce IDENTICAL behavior to current code when fusion is disabled.
**Why it happens:** The fix changes the call site even when fusion returns pass-through.
**How to avoid:** Verify that when fusion is disabled: load_rtt EWMA receives filtered_rtt, and baseline receives filtered_rtt -- same as current code where update_ewma(filtered_rtt) does both.
**Warning signs:** Any test regression when fusion is disabled.

### Pitfall 5: Metrics recording uses delta = load_rtt - baseline_rtt

**What goes wrong:** The `wanctl_rtt_delta_ms` metric (line 2705) uses `delta = self.load_rtt - self.baseline_rtt`. After fix, this delta has different semantics (fused_load - icmp_baseline). This is actually CORRECT for operators -- it shows the "effective" congestion delta.
**How to avoid:** Document the semantic change. Possibly add a new metric `wanctl_rtt_icmp_delta_ms` for pure ICMP delta visibility.
**Warning signs:** Dashboard or alerting thresholds behaving differently.

### Pitfall 6: Protected zone modifications require approval

**What goes wrong:** `_update_baseline_if_idle()` is marked as PROTECTED ZONE - ARCHITECTURAL INVARIANT with explicit "DO NOT MODIFY without explicit approval."
**Why it happens:** The function has been carefully protected since early phases.
**How to avoid:** This fix IS the approved modification (Phase 103 explicitly targets this). The modification PRESERVES the invariant (baseline only updates when idle) while FIXING the signal source. Document that the invariant is preserved -- the change is about WHICH signal determines idle, not WHETHER idle-gating occurs.

## Code Examples

### Current broken flow (autorate_continuous.py lines 2596-2597)

```python
# Source: src/wanctl/autorate_continuous.py:2596-2597
fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
self.update_ewma(fused_rtt)
```

### update_ewma (lines 1979-1990)

```python
# Source: src/wanctl/autorate_continuous.py:1979-1990
def update_ewma(self, measured_rtt: float) -> None:
    # Fast EWMA for load_rtt (responsive to current conditions)
    self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * measured_rtt
    # Slow EWMA for baseline_rtt (conditional update via protected logic)
    self._update_baseline_if_idle(measured_rtt)
```

### _update_baseline_if_idle (lines 1992-2035)

```python
# Source: src/wanctl/autorate_continuous.py:2011-2035
delta = self.load_rtt - self.baseline_rtt
if delta < self.baseline_update_threshold:
    old_baseline = self.baseline_rtt
    new_baseline = (1 - self.alpha_baseline) * self.baseline_rtt + self.alpha_baseline * measured_rtt
    if not (self.baseline_rtt_min <= new_baseline <= self.baseline_rtt_max):
        return
    self.baseline_rtt = new_baseline
```

### Proposed fix in run_cycle

```python
# FIXED: Split EWMA updates - fused for load, ICMP for baseline
signal_result = self.signal_processor.process(
    raw_rtt=measured_rtt, load_rtt=self.load_rtt, baseline_rtt=self.baseline_rtt,
)
self._last_signal_result = signal_result
fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)

# Load EWMA: uses fused signal for enhanced congestion detection
self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * fused_rtt

# Baseline EWMA: uses ICMP-only for true idle reference
self._update_baseline_if_idle(signal_result.filtered_rtt)
```

### Proposed fix in _update_baseline_if_idle

```python
def _update_baseline_if_idle(self, icmp_rtt: float) -> None:
    """Update baseline RTT ONLY when line is idle.

    PROTECTED ZONE - ARCHITECTURAL INVARIANT
    =========================================
    Uses ICMP-only signal (not fused) for both the freeze gate
    and the baseline EWMA. This prevents IRTT path divergence from
    corrupting baseline semantics.

    The freeze gate uses icmp_rtt vs baseline_rtt (both ICMP-derived)
    instead of load_rtt vs baseline_rtt (mixed fused-vs-ICMP).
    """
    delta = icmp_rtt - self.baseline_rtt
    if delta < self.baseline_update_threshold:
        old_baseline = self.baseline_rtt
        new_baseline = (
            (1 - self.alpha_baseline) * self.baseline_rtt
            + self.alpha_baseline * icmp_rtt
        )
        if not (self.baseline_rtt_min <= new_baseline <= self.baseline_rtt_max):
            self.logger.warning(...)
            return
        self.baseline_rtt = new_baseline
        self.logger.debug(...)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ICMP-only RTT everywhere | Weighted ICMP+IRTT fusion | v1.19 (Phase 96) | Fused signal used for load AND baseline |
| `update_ewma(measured_rtt)` | `update_ewma(fused_rtt)` | v1.19 (Phase 96) | Introduced the deadlock |
| Baseline tracks ICMP idle | Baseline tracks fused idle | v1.19 (Phase 96) | Baseline semantics corrupted |

**The bug was introduced in Phase 96 (Dual-Signal Fusion Core).** Before Phase 96, update_ewma always received ICMP-only filtered_rtt. Phase 96 inserted `_compute_fused_rtt()` between signal processing and EWMA update, changing the signal path for both load AND baseline EWMAs.

## Open Questions

1. **Congestion zone threshold impact**
   - What we know: After fix, delta = fused_load - icmp_baseline. For Spectrum (IRTT < ICMP), this makes delta ~2ms LESS than pure ICMP delta at idle. For ATT (IRTT > ICMP), ~4ms MORE.
   - What's unclear: Whether existing thresholds (15ms/45ms/80ms) need recalibration for the new delta profile.
   - Recommendation: The adaptive tuning system (Phase 99/100/101) will naturally recalibrate. Ship the fix, let tuning converge. Alternatively, analyze production metrics post-fix to confirm threshold adequacy.

2. **update_ewma() method backward compatibility**
   - What we know: ~50+ test callsites use update_ewma(). Changing its behavior breaks tests.
   - What's unclear: Whether to keep update_ewma() as-is (tests pass but method is misleading when fusion enabled) or deprecate it.
   - Recommendation: Keep update_ewma() unchanged. In run_cycle(), replace the single call with two inline operations. Tests that call update_ewma() directly are testing non-fusion behavior and remain correct.

3. **Should baseline drift alert threshold change?**
   - What we know: _check_baseline_drift() compares baseline_rtt to baseline_rtt_initial. After fix, baseline_rtt stays closer to ICMP idle (the initial value), so drift should DECREASE.
   - What's unclear: Whether the 50% drift threshold is still appropriate.
   - Recommendation: No change needed. Less drift = fewer false alerts.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_fusion_core.py tests/test_wan_controller.py -x -q` |
| Full suite command | `.venv/bin/pytest tests/ -x -q` |

### Phase Requirements -> Test Map

Requirements for this phase are not yet defined in REQUIREMENTS.md. Based on research, the following requirements should be created:

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FBLK-01 | Baseline uses ICMP-only signal, not fused RTT | unit | `.venv/bin/pytest tests/test_fusion_baseline.py::TestBaselineUsesIcmpOnly -x` | No (Wave 0) |
| FBLK-02 | Load EWMA uses fused signal for congestion detection | unit | `.venv/bin/pytest tests/test_fusion_baseline.py::TestLoadEwmaUsesFused -x` | No (Wave 0) |
| FBLK-03 | Baseline updates when ICMP idle, regardless of IRTT divergence | unit | `.venv/bin/pytest tests/test_fusion_baseline.py::TestBaselineUpdatesWithIrttDivergence -x` | No (Wave 0) |
| FBLK-04 | Fusion-disabled behavior is identical to pre-fix | unit | `.venv/bin/pytest tests/test_fusion_baseline.py::TestFusionDisabledIdentical -x` | No (Wave 0) |
| FBLK-05 | Congestion zones use fused load_rtt vs ICMP baseline for delta | unit | `.venv/bin/pytest tests/test_fusion_baseline.py::TestCongestionZoneDelta -x` | No (Wave 0) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_fusion_core.py tests/test_wan_controller.py tests/test_fusion_baseline.py -x -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fusion_baseline.py` -- covers FBLK-01 through FBLK-05
- [ ] No framework install needed (pytest already configured)
- [ ] No shared fixtures needed beyond existing conftest.py patterns

## Sources

### Primary (HIGH confidence)
- `src/wanctl/autorate_continuous.py` lines 2011-2035 -- baseline freeze logic
- `src/wanctl/autorate_continuous.py` lines 2357-2400 -- _compute_fused_rtt
- `src/wanctl/autorate_continuous.py` lines 1979-1990 -- update_ewma
- `src/wanctl/autorate_continuous.py` lines 2596-2597 -- run_cycle signal flow
- `src/wanctl/autorate_continuous.py` lines 1376 -- adjust_4state delta computation
- `.planning/STATE.md` line 78 -- deadlock description

### Secondary (MEDIUM confidence)
- MEMORY.md production values: Spectrum ICMP ~25ms, IRTT ~19ms; ATT ICMP ~29ms, IRTT ~43ms
- ATT protocol correlation 0.65 (path asymmetry, not protocol deprioritization)

### Tertiary (LOW confidence)
- None -- all findings verified directly from codebase

## Metadata

**Confidence breakdown:**
- Deadlock mechanism: HIGH -- directly traced through code, verified with production values
- Fix approach: HIGH -- signal path split is well-understood, minimal change
- Pitfalls: HIGH -- identified from codebase analysis of test patterns and callers
- Threshold impact: MEDIUM -- depends on production behavior, needs empirical validation

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable domain, no external dependencies)
