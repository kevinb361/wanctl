# Phase 111: Auto-Tuning Production Hardening - Research

**Researched:** 2026-03-25
**Domain:** Adaptive tuning config bounds + signal processing rate normalization
**Confidence:** HIGH

## Summary

Phase 111 is a targeted hardening pass on the v1.20 auto-tuning system based on 6 days of production data (130 adjustments, 0 reverts). Two categories of change: (1) YAML config bound widening for 4 parameters stuck at limits across both WANs, and (2) a code fix in SIGP-01 (tune_hampel_sigma) where the outlier rate calculation divides by a fixed constant `SAMPLES_PER_MINUTE=1200` instead of computing expected samples from the actual time gap between consecutive DB records, underestimating the rate by 60x.

The code change is surgical: one line in `signal_processing.py` (line 123), removal of the now-unused `SAMPLES_PER_MINUTE` constant, and an update to `MAX_WINDOW` from 15 to 21 to unblock the ATT window size ceiling. Config changes are 4 YAML value edits. No architectural spine, state machine, or core control logic is touched.

**Primary recommendation:** Fix SIGP-01 rate normalization using actual time gaps and `CYCLE_INTERVAL`, widen 4 config bounds in YAML, and update `MAX_WINDOW` constant to 21 to match the new ATT bound ceiling.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- ATT: hampel_window_size max: 15 -> 21
- Spectrum: target_bloat_ms min: 10 -> 5
- Spectrum: warn_bloat_ms min: 25 -> 15
- Spectrum: baseline_rtt_max min: 30 -> 25
- SIGP-01 bug fix: replace `delta / SAMPLES_PER_MINUTE` with `delta / max(time_gap * 20, 1)` using actual time between consecutive timestamps
- Remove SAMPLES_PER_MINUTE constant (becomes unused)
- The `20` comes from 20Hz cycle rate (50ms interval) -- use existing CYCLE_INTERVAL constant if available
- Unit tests for tune_hampel_sigma with various recording densities (1s, 5s, 60s gaps)
- Test edge cases: zero time gap, counter reset (negative delta), single sample

### Claude's Discretion
- Whether to add a dedicated constant for cycle rate (20) vs computing from CYCLE_INTERVAL
- Test fixture structure and parametrization approach
- Whether to log a warning when time_gap is 0 between records

### Deferred Ideas (OUT OF SCOPE)
- Bound saturation detection (log when parameter hits bound repeatedly)
- ATT fusion/IRTT enablement (separate concern, link is stable without it)
- Tuning frequency reduction when all params converged (optimization, not needed)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIGP-01-FIX | Fix SIGP-01 outlier rate denominator: use actual time gap between records instead of fixed SAMPLES_PER_MINUTE | Code analysis confirms bug at line 123 of signal_processing.py; CYCLE_INTERVAL=0.05 already exists at line 73; math verified: `1/CYCLE_INTERVAL=20` matches the 20Hz cycle rate |
| BOUNDS-SPECTRUM | Widen 3 Spectrum tuning bounds: target_bloat_ms min 10->5, warn_bloat_ms min 25->15, baseline_rtt_max min 30->25 | Config structure verified in configs/spectrum.yaml lines 128-155; no code constants block these ranges; strategies derive candidates from data and rely solely on config bounds for clamping |
| BOUNDS-ATT | Widen ATT tuning bound: hampel_window_size max 15->21 | Config structure verified in configs/att.yaml lines 113-140; CRITICAL: MAX_WINDOW=15 in signal_processing.py line 54 also caps strategy proposals; must update MAX_WINDOW to 21 or the config change alone has no effect |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Change policy:** Explain before changing, prefer analysis over implementation. Priority: stability > safety > clarity > elegance.
- **Architectural spine:** READ-ONLY. Do not modify control model, state logic, flash wear protection, or steering spine.
- **Portable controller:** Link-agnostic code, all variability in YAML config.
- **Testing:** `.venv/bin/pytest tests/ -v` for full suite. Skip full test suite for config-only changes.
- **Formatting:** `.venv/bin/ruff format src/ tests/` and `.venv/bin/ruff check src/ tests/`
- **No refactoring** of core logic, algorithms, thresholds, or timing without approval.

## Architecture Patterns

### Files Touched

```
configs/spectrum.yaml          # 3 bound value changes (BOUNDS-SPECTRUM)
configs/att.yaml               # 1 bound value change (BOUNDS-ATT)
src/wanctl/tuning/strategies/signal_processing.py  # SIGP-01 fix + MAX_WINDOW update
tests/test_signal_processing_strategy.py           # New tests for various recording densities
```

### SIGP-01 Rate Normalization Fix

**Current code (line 123):**
```python
rate = delta / SAMPLES_PER_MINUTE
```

**Fixed code:**
```python
time_gap = sorted_ts[i] - sorted_ts[i - 1]
samples_per_gap = max(time_gap / CYCLE_INTERVAL, 1.0)
rate = delta / samples_per_gap
```

**Key insight:** `CYCLE_INTERVAL = 0.05` already exists at line 73. Computing `1/CYCLE_INTERVAL = 20` (samples per second) and multiplying by `time_gap` gives the expected sample count for any recording interval. The `max(..., 1.0)` guards against division by zero when time_gap is 0.

**Math verification (backwards compatibility):** With 60-second gaps (existing test fixture spacing):
- Old: `delta / 1200`
- New: `delta / max(60 / 0.05, 1)` = `delta / 1200` -- identical. Existing tests pass unchanged.

### MAX_WINDOW Constant Update

**Pitfall discovered:** The `MAX_WINDOW = 15` constant in `signal_processing.py` (line 54) is used by `tune_hampel_window` to cap proposals during interpolation. If only the ATT config bound is widened to 21 but `MAX_WINDOW` stays at 15, the strategy will never propose above 15 and the config change has no effect.

**Fix:** Update `MAX_WINDOW = 15` to `MAX_WINDOW = 21` at line 54. This is safe because:
1. Per-WAN config bounds still enforce the actual ceiling for each WAN
2. Spectrum config keeps max: 15, so Spectrum proposals above 15 get clamped by the applier
3. ATT config moves to max: 21, allowing the strategy to propose up to 21

The comment should reflect the new maximum: `# Maximum before detection latency (per-WAN bounds enforce actual limits)`

### Config Bound Changes (Pure YAML)

**Spectrum (configs/spectrum.yaml lines 128-155):**

| Parameter | Field | Old | New | Rationale |
|-----------|-------|-----|-----|-----------|
| target_bloat_ms | min | 10.0 | 5.0 | Pegged at floor; link may benefit from tighter threshold |
| warn_bloat_ms | min | 25.0 | 15.0 | Pegged at floor |
| baseline_rtt_max | min | 30.0 | 25.0 | Pegged at floor; p95 RTT ~24ms, 25ms gives margin |

**ATT (configs/att.yaml lines 113-140):**

| Parameter | Field | Old | New | Rationale |
|-----------|-------|-----|-----|-----------|
| hampel_window_size | max | 15 | 21 | Tuner pegged at ceiling 3+ days; jitter 0.34ms wants wider window |

### Existing Test Fixture Pattern

The `_make_metrics` helper in `test_signal_processing_strategy.py` generates timestamps with 60-second gaps (`start_ts + i * 60`). Tests use counter increment values designed around the old `delta / 1200` math:
- 240 per 60s = 240/1200 = 20% rate
- 120 per 60s = 120/1200 = 10% rate
- 12 per 60s = 12/1200 = 1% rate

After the fix, with 60s gaps: `delta / max(60/0.05, 1)` = `delta / 1200` -- same math. All 20 existing tests in `test_signal_processing_strategy.py` pass unchanged.

### New Test Strategy

New tests should verify rate consistency across different recording intervals. The `_make_metrics` helper needs a variant or parametrization that supports variable time gaps.

**Recommended approach:** Parametrize with `@pytest.mark.parametrize` over recording intervals:

```python
@pytest.mark.parametrize("gap_sec", [1, 5, 60])
def test_rate_consistent_across_recording_intervals(self, gap_sec):
    """Same physical outlier rate produces same result regardless of recording density."""
    # Target: 20% outlier rate at 20Hz = 4 outliers/second
    # Over gap_sec: outliers_per_gap = 4 * gap_sec
    n = 100
    outliers_per_gap = 4 * gap_sec  # 20% of 20Hz
    counts = [i * outliers_per_gap for i in range(n)]
    metrics = [
        {"timestamp": 1000000 + i * gap_sec, "metric_name": "wanctl_signal_outlier_count", "value": float(c)}
        for i, c in enumerate(counts)
    ]
    result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
    assert result is not None
    # 20% > 15% max -> should decrease sigma
    assert result.new_value < 3.0
```

**Edge case tests:**
- Zero time gap between records: `max(0 / 0.05, 1) = 1` -- rate equals raw delta, clamped to [0, 1]
- Single sample: returns None (only 1 timestamp, 0 deltas)
- Counter reset (negative delta): already tested, still discarded

### Claude's Discretion Recommendations

1. **Cycle rate constant:** Compute from `CYCLE_INTERVAL` rather than adding a new constant. Expression: `1.0 / CYCLE_INTERVAL` is clear and derived from the source of truth. Adding `SAMPLES_PER_SECOND = 20` would duplicate information.

2. **Test fixture approach:** Add a `_make_metrics_variable_gap` helper or extend `_make_metrics` with a `gap_sec` parameter (default 60 for backwards compatibility). Use `@pytest.mark.parametrize` for the multi-density tests.

3. **Zero time_gap warning:** Log at DEBUG level when time_gap is 0 between records. This is an unusual but not impossible condition (duplicate timestamps). A WARNING would be noisy if it happens frequently; DEBUG is sufficient for troubleshooting.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate normalization | Custom samples-per-interval lookup table | `time_gap / CYCLE_INTERVAL` | Single formula works for all recording densities |
| Bounds enforcement | Manual min/max checks in strategy code | `clamp_to_step()` in applier | Centralized, tested, handles max_step_pct |

## Common Pitfalls

### Pitfall 1: MAX_WINDOW Mismatch with Config Bounds
**What goes wrong:** Config bound for hampel_window_size is widened to max=21, but `MAX_WINDOW=15` in signal_processing.py caps strategy proposals at 15. Tuner remains pegged at 15.
**Why it happens:** Config bounds and code constants are separate clamping layers. The strategy code clamps first (MAX_WINDOW), then the applier clamps again (config bounds).
**How to avoid:** Update MAX_WINDOW to 21 when the config bound is widened. Per-WAN config bounds still enforce per-WAN limits.
**Warning signs:** After deployment, ATT hampel_window_size still shows 15.0 in tuning history despite max bound=21.

### Pitfall 2: Existing Test Breakage from Rate Formula Change
**What goes wrong:** Test author assumes changing `delta / SAMPLES_PER_MINUTE` will break existing tests and rewrites them unnecessarily.
**Why it happens:** Not verifying the math: with 60s gaps, old and new formulas produce identical results.
**How to avoid:** Verify: `delta / max(60/0.05, 1) = delta / 1200 = delta / SAMPLES_PER_MINUTE`. Run existing tests first to confirm they pass.
**Warning signs:** Existing tests modified without need.

### Pitfall 3: Integer Division in Time Gap
**What goes wrong:** Using integer division `time_gap // CYCLE_INTERVAL` loses precision for non-aligned gaps.
**Why it happens:** Timestamps are integers (epoch seconds), but the formula should use float division.
**How to avoid:** Use float division: `time_gap / CYCLE_INTERVAL`. Both operands coerce to float.
**Warning signs:** Rate values slightly off at non-round time gaps.

### Pitfall 4: Config Bound Validation (min > max)
**What goes wrong:** Lowering Spectrum baseline_rtt_max min from 30 to 25 could create min > max if paired incorrectly.
**Why it happens:** baseline_rtt_max bounds are {min: 30, max: 100} -> {min: 25, max: 100}. No issue here. But if someone also changed max to be < 25, SafetyBounds would raise ValueError.
**How to avoid:** Verify each changed bound still satisfies min <= max after editing.
**Warning signs:** Daemon fails to start with "min_value > max_value" error.

## Code Examples

### SIGP-01 Fix (signal_processing.py, tune_hampel_sigma, around line 117-126)

```python
# Current (buggy):
for i in range(1, len(sorted_ts)):
    delta = count_by_ts[sorted_ts[i]] - count_by_ts[sorted_ts[i - 1]]
    if delta < 0:
        continue
    rate = delta / SAMPLES_PER_MINUTE
    rate = max(0.0, min(1.0, rate))
    rates.append(rate)

# Fixed:
for i in range(1, len(sorted_ts)):
    delta = count_by_ts[sorted_ts[i]] - count_by_ts[sorted_ts[i - 1]]
    if delta < 0:
        continue
    time_gap = sorted_ts[i] - sorted_ts[i - 1]
    expected_samples = max(time_gap / CYCLE_INTERVAL, 1.0)
    rate = delta / expected_samples
    rate = max(0.0, min(1.0, rate))
    rates.append(rate)
```

### Config Bound Edit (spectrum.yaml)

```yaml
# Before:
target_bloat_ms:
  min: 10.0
  max: 30.0
warn_bloat_ms:
  min: 25.0
  max: 80.0
baseline_rtt_max:
  min: 30.0
  max: 100.0

# After:
target_bloat_ms:
  min: 5.0     # Widened: tuner pegged at floor
  max: 30.0
warn_bloat_ms:
  min: 15.0    # Widened: tuner pegged at floor
  max: 80.0
baseline_rtt_max:
  min: 25.0    # Widened: tuner pegged at floor, p95 RTT ~24ms
  max: 100.0
```

### Config Bound Edit (att.yaml)

```yaml
# Before:
hampel_window_size:
  min: 5
  max: 15

# After:
hampel_window_size:
  min: 5
  max: 21    # Widened: tuner pegged at ceiling, jitter 0.34ms wants wider window
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_signal_processing_strategy.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIGP-01-FIX | Rate consistent across recording densities (1s, 5s, 60s) | unit | `.venv/bin/pytest tests/test_signal_processing_strategy.py::TestTuneHampelSigma -x` | Extend existing |
| SIGP-01-FIX | Zero time gap produces valid rate | unit | `.venv/bin/pytest tests/test_signal_processing_strategy.py::TestTuneHampelSigma -x` | New test |
| SIGP-01-FIX | Single sample returns None | unit | `.venv/bin/pytest tests/test_signal_processing_strategy.py::TestTuneHampelSigma -x` | New test |
| SIGP-01-FIX | SAMPLES_PER_MINUTE removed from module | unit | `grep -c SAMPLES_PER_MINUTE src/wanctl/tuning/strategies/signal_processing.py` | New assertion |
| BOUNDS-SPECTRUM | Config loads without error after bound changes | unit | `.venv/bin/pytest tests/test_tuning_config.py -x` | Existing covers |
| BOUNDS-ATT | Config loads without error after bound changes | unit | `.venv/bin/pytest tests/test_tuning_config.py -x` | Existing covers |
| BOUNDS-ATT | MAX_WINDOW=21 in code matches config ceiling | unit | Assertion in new test | New test |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_signal_processing_strategy.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New parametrized tests for variable recording density in `tests/test_signal_processing_strategy.py`
- [ ] Edge case tests for zero time gap and single sample
- [ ] Assertion that SAMPLES_PER_MINUTE is removed from module

None of these require new test files or framework changes -- all extend the existing `TestTuneHampelSigma` class in `test_signal_processing_strategy.py`.

## Open Questions

1. **MAX_WINDOW update scope**
   - What we know: MAX_WINDOW=15 must increase to 21 for ATT bound widening to take effect. Spectrum config still caps at 15 via bounds.
   - What's unclear: Should the comment also update the interpolation documentation? The JITTER_LOW -> MAX_WINDOW mapping description says "Maximum before detection latency" which may need revisiting at 21.
   - Recommendation: Update the constant and comment. The detection latency concern is mitigated by per-WAN config bounds -- operators control their own ceiling.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/tuning/strategies/signal_processing.py` -- Full source of SIGP-01 bug, CYCLE_INTERVAL constant, MAX_WINDOW constant
- `src/wanctl/tuning/models.py` -- SafetyBounds, clamp_to_step, TuningConfig
- `src/wanctl/tuning/applier.py` -- Bounds enforcement, trivial change filter
- `src/wanctl/autorate_continuous.py` lines 958-1117 -- Config parsing, bounds loading
- `configs/spectrum.yaml` -- Current Spectrum bounds (lines 128-155)
- `configs/att.yaml` -- Current ATT bounds (lines 113-140)
- `tests/test_signal_processing_strategy.py` -- Existing 20 tests, fixture patterns

### Secondary (MEDIUM confidence)
- Production analysis in CONTEXT.md -- 6-day data, 130 adjustments, specific bound saturation evidence

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pure Python, no new dependencies, existing patterns
- Architecture: HIGH -- single-file code fix + YAML edits, well-understood tuning infrastructure
- Pitfalls: HIGH -- MAX_WINDOW mismatch identified and verified via code analysis, math backwards-compatibility proven

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable internal codebase, no external dependencies)
