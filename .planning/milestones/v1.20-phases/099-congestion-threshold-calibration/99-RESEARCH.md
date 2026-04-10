# Phase 99: Congestion Threshold Calibration - Research

**Researched:** 2026-03-18
**Domain:** Percentile-based congestion threshold derivation from historical RTT delta distributions
**Confidence:** HIGH

## Summary

Phase 99 implements the first concrete tuning strategy for the Phase 98 framework: deriving `target_bloat_ms` (GREEN->YELLOW threshold) from the p75 of GREEN-state RTT delta distributions, and `warn_bloat_ms` (YELLOW->SOFT_RED threshold) from the p90. The Phase 98 foundation provides everything needed -- TuningResult/TuningConfig frozen dataclasses, StrategyFn type alias, run_tuning_analysis() orchestration with warmup/confidence-scaling, apply_tuning_results() with two-phase clamping, and maintenance-window wiring with SIGUSR1. This phase only adds a single new file (the strategy function) and wires it into the existing `strategies=[]` list in the maintenance loop.

The core algorithm is straightforward: query 24 hours of 1-minute aggregated metrics via the existing `query_metrics()` reader, filter to timestamps where `wanctl_state` equals GREEN (value 0.0), extract `wanctl_rtt_delta_ms` values from those GREEN periods, compute p75 and p90 via `statistics.quantiles()`, and return TuningResult objects. Convergence detection adds coefficient of variation tracking -- when CoV of recent derived values drops below a configurable threshold (e.g., 0.05), the parameter is considered converged and the strategy returns None.

The primary technical challenge is the GREEN-state filtering. The metrics table stores `wanctl_state` and `wanctl_rtt_delta_ms` as separate rows with the same timestamp, not as columns on the same row. The strategy function must correlate them by timestamp to identify which RTT delta values occurred during GREEN periods. This is a data-wrangling problem, not a statistical one.

**Primary recommendation:** Implement a single `congestion_thresholds.py` strategy file containing two pure StrategyFn functions (`calibrate_target_bloat` and `calibrate_warn_bloat`) plus a shared `_extract_green_deltas()` helper that performs the timestamp-based GREEN-state filtering. Wire both strategies into the maintenance loop's `strategies=[]` list. Add convergence detection as a stateless CoV check on the derived values within the lookback window.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CALI-01 | `target_bloat_ms` derived from p75 of GREEN-state RTT delta distribution | Strategy function computes p75 via `statistics.quantiles(green_deltas, n=100)[74]`, returns TuningResult with parameter="target_bloat_ms" |
| CALI-02 | `warn_bloat_ms` derived from p90 of GREEN-state RTT delta distribution | Strategy function computes p90 via `statistics.quantiles(green_deltas, n=100)[89]`, returns TuningResult with parameter="warn_bloat_ms" |
| CALI-03 | Convergence detection stops adjusting when parameter coefficient of variation drops below threshold | CoV computed from recent hourly derived values (sliding window of last N derivations); when CoV < configurable threshold (default 0.05), strategy returns None |
| CALI-04 | 24h lookback window captures full diurnal pattern for threshold derivation | TuningConfig.lookback_hours=24 already passes 24h to query_metrics; strategy receives all 1440 one-minute aggregates spanning the full diurnal cycle |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| statistics (stdlib) | Python 3.12 | quantiles(), stdev(), mean() for percentile and CoV computation | Zero dependency, verified: quantiles(data, n=100) gives 99 cut points |
| wanctl.tuning.analyzer | Phase 98 | run_tuning_analysis() orchestration, warmup gate, confidence scaling | Existing framework, StrategyFn type alias ready |
| wanctl.tuning.applier | Phase 98 | apply_tuning_results() with clamp_to_step, persistence, logging | Existing framework, two-phase clamping |
| wanctl.tuning.models | Phase 98 | TuningResult, TuningConfig, SafetyBounds frozen dataclasses | Existing contracts |
| wanctl.storage.reader | v1.7 | query_metrics() read-only SQLite access | Proven pattern, handles missing DB gracefully |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlite3 (stdlib) | Python 3.12 | Direct queries if query_metrics() insufficient for correlated multi-metric queries | Only if timestamp correlation needs custom SQL |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| statistics.quantiles | numpy.percentile | numpy is a heavy dependency; stdlib quantiles handles 1440-point datasets trivially |
| Stateless CoV per call | Persistent convergence state in SQLite | Stateless is simpler; compute CoV from tuning_params history table instead of maintaining state |

**Installation:**
```bash
# No new dependencies. Zero packages to install.
```

**Version verification:** N/A -- all stdlib + existing codebase.

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/tuning/
    __init__.py              # Existing - re-exports public API
    models.py                # Existing - TuningResult, TuningConfig, SafetyBounds, clamp_to_step
    analyzer.py              # Existing - run_tuning_analysis(), StrategyFn type alias
    applier.py               # Existing - apply_tuning_results(), persist_tuning_result()
    strategies/
        __init__.py          # Existing - empty docstring
        base.py              # Existing - TuningStrategy Protocol (unused; StrategyFn is the pattern)
        congestion_thresholds.py  # NEW - calibrate_target_bloat(), calibrate_warn_bloat()
```

### Pattern 1: StrategyFn Pure Functions
**What:** Each strategy is a pure function matching the StrategyFn type alias: `Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]`
**When to use:** Every tuning strategy in the system.
**Why:** Testable with synthetic data lists. No mock setup. No instance state. Each function is 30-50 lines.
**Example:**
```python
# Source: wanctl/tuning/analyzer.py (existing type alias)
StrategyFn = Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]

def calibrate_target_bloat(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Derive target_bloat_ms from p75 of GREEN-state RTT delta distribution."""
    green_deltas = _extract_green_deltas(metrics_data)
    if len(green_deltas) < MIN_GREEN_SAMPLES:
        return None
    percentiles = quantiles(green_deltas, n=100)
    candidate = percentiles[74]  # p75
    # ... convergence check, confidence computation, return TuningResult
```

### Pattern 2: Timestamp-Based State Filtering
**What:** Correlate `wanctl_state` values with `wanctl_rtt_delta_ms` values by matching timestamps to identify GREEN-period RTT deltas.
**When to use:** Any strategy that needs state-filtered metrics (GREEN-only, RED-only, etc.).
**Why:** The metrics table stores each metric as a separate row, not as columns. State and delta share the same timestamp per cycle.

**Critical implementation detail:** In 1-minute aggregated data, `wanctl_state` uses MODE aggregation (most common state in the minute). So a 1m bucket with state=0.0 means the majority of that minute was GREEN. This is the correct behavior for threshold derivation -- we want minutes that were predominantly GREEN.

**Example:**
```python
def _extract_green_deltas(metrics_data: list[dict]) -> list[float]:
    """Extract RTT delta values from timestamps where state was GREEN.

    In 1m aggregated data, wanctl_state uses MODE aggregation (most common
    state in the minute). State value 0.0 = GREEN (majority of minute).
    """
    # Build timestamp -> state map
    state_by_ts: dict[int, float] = {}
    delta_by_ts: dict[int, float] = {}

    for row in metrics_data:
        ts = row["timestamp"]
        name = row["metric_name"]
        val = row["value"]
        if name == "wanctl_state":
            state_by_ts[ts] = val
        elif name == "wanctl_rtt_delta_ms":
            delta_by_ts[ts] = val

    # Return deltas where state == GREEN (0.0)
    return [
        delta_by_ts[ts]
        for ts in delta_by_ts
        if state_by_ts.get(ts) == 0.0
    ]
```

### Pattern 3: Convergence Detection via Historical CoV
**What:** Track whether a parameter has stabilized by computing the coefficient of variation of recent derived values.
**When to use:** Every tuning parameter to prevent unnecessary adjustments.
**Why:** Stateless approach -- query recent tuning_params history from SQLite to get last N derived values, compute stdev/mean. When CoV < threshold, the parameter has converged.

**Key design choice:** Convergence is checked within the strategy function, not externally. The strategy queries tuning_params for recent values of its parameter, computes CoV, and returns None if converged. This keeps convergence logic co-located with derivation logic.

**Alternative (simpler):** Compute CoV from the current lookback window's derived percentile values by splitting the window into sub-windows (e.g., 4 x 6-hour windows within 24h). If the p75/p90 derived from each sub-window has low CoV, the parameter is stable. This avoids needing to query tuning_params and is fully stateless.

**Recommended:** The sub-window approach is simpler and more aligned with the pure-function strategy pattern. It doesn't require the strategy to know about SQLite or the tuning_params table.

**Example:**
```python
def _check_convergence(
    green_deltas_by_hour: list[list[float]],
    percentile_index: int,
    threshold: float = 0.05,
) -> bool:
    """Check if a percentile has converged across time sub-windows.

    Splits lookback into sub-windows, computes the target percentile
    in each, and checks if the CoV of those values is below threshold.
    """
    if len(green_deltas_by_hour) < 4:
        return False  # Need at least 4 sub-windows

    sub_values = []
    for chunk in green_deltas_by_hour:
        if len(chunk) < 10:
            continue
        p = quantiles(chunk, n=100)
        sub_values.append(p[percentile_index])

    if len(sub_values) < 3:
        return False

    avg = mean(sub_values)
    if avg < 0.001:
        return True  # Effectively zero, consider converged

    cov = stdev(sub_values) / avg
    return cov < threshold
```

### Pattern 4: Strategy Registration in Maintenance Loop
**What:** Wire strategy functions into the `strategies=[]` argument of `run_tuning_analysis()`.
**When to use:** When adding any new strategy.
**Why:** The Phase 98 maintenance loop already has `strategies=[]` as a placeholder. This phase replaces it with actual strategy tuples.

**Example (from autorate_continuous.py maintenance loop):**
```python
# Current code (Phase 98):
strategies=[],  # No strategies in Phase 98 (framework only)

# After Phase 99:
from wanctl.tuning.strategies.congestion_thresholds import (
    calibrate_target_bloat,
    calibrate_warn_bloat,
)
strategies=[
    ("target_bloat_ms", calibrate_target_bloat),
    ("warn_bloat_ms", calibrate_warn_bloat),
],
```

### Anti-Patterns to Avoid
- **Querying raw granularity data:** 24h at 20Hz = 1.7M rows per metric per WAN. Always use "1m" granularity (1440 rows). The analyzer already enforces this.
- **Filtering by exact float equality on state:** wanctl_state is stored as 0.0 for GREEN. After MODE aggregation in 1m buckets, this is reliable. But never compare with `<` or `>` for state values -- they're categorical, not ordinal for threshold purposes.
- **Using the TuningStrategy Protocol class:** Phase 98 created a Protocol in `strategies/base.py`, but the actual pattern is StrategyFn (a Callable type alias in analyzer.py). Strategy functions should match StrategyFn, not implement the Protocol class.
- **Mutating metrics_data:** The list[dict] is shared across all strategies in a single tuning cycle. Never modify it in-place. The _extract_green_deltas helper creates a new list.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile computation | Manual sorting + index calculation | `statistics.quantiles(data, n=100)` | Edge cases with small datasets, interpolation methods |
| Coefficient of variation | Manual stdev/mean with zero checks | `statistics.stdev(data) / statistics.mean(data)` with guard | Handle zero mean, single-value edge cases |
| Two-phase clamping | Manual bounds + step enforcement | `clamp_to_step()` from tuning/models.py | Already handles floor of 0.001, direction, rounding |
| Metric querying | Custom SQLite reader | `query_metrics()` from storage/reader.py | Read-only connection, missing DB handling, filter parameters |
| Result persistence | Custom INSERT logic | `persist_tuning_result()` from tuning/applier.py | None-safety, exception handling, timestamp |

**Key insight:** Phase 98 built 90% of the infrastructure. Phase 99 is purely a strategy function plus wiring -- no new infrastructure.

## Common Pitfalls

### Pitfall 1: Timestamp Correlation Between State and Delta Metrics
**What goes wrong:** The strategy queries metrics_data and assumes each dict has both state and delta fields. In reality, each metric is a separate row with the same timestamp.
**Why it happens:** The metrics table is a time-series store with one metric per row, not a wide table with columns for each metric.
**How to avoid:** Build explicit timestamp->value maps for both wanctl_state and wanctl_rtt_delta_ms, then join by timestamp. Only include deltas where a matching state timestamp exists.
**Warning signs:** Strategy returns zero GREEN deltas despite the WAN being mostly GREEN. Check that the timestamp correlation is working.

### Pitfall 2: Empty GREEN Deltas After Filtering
**What goes wrong:** During periods of sustained congestion (e.g., ISP maintenance, heavy load), most/all minutes have non-GREEN state. The strategy finds zero GREEN deltas and either crashes on empty list or returns a bad result.
**Why it happens:** 24-hour lookback can coincide with sustained network events.
**How to avoid:** Check `len(green_deltas) < MIN_GREEN_SAMPLES` (recommend 60 = 1 hour of GREEN minutes) before computing percentiles. Return None (no adjustment) when insufficient GREEN data. Log at INFO level with the count.
**Warning signs:** Log messages showing "skipping: only N GREEN samples (need M)" repeatedly.

### Pitfall 3: Feedback Oscillation From Threshold-State Interaction
**What goes wrong:** Lowering target_bloat_ms from 15 to 13 causes more time in YELLOW (deltas between 13-15 that were GREEN now register as YELLOW). Next cycle has fewer GREEN samples, and those samples have lower deltas (the higher ones are now YELLOW). This biases p75 downward, causing further lowering.
**Why it happens:** The threshold defines what counts as GREEN, so changing it changes the GREEN-state data distribution used to compute the next threshold.
**How to avoid:** The 10% max_step_pct from Phase 98 is the primary mitigation. Each cycle can only move the threshold by 10%, so the feedback loop is damped. Additionally, convergence detection (CALI-03) stops adjustment when the derived values stabilize. The hourly cadence provides 1 hour of data collection between adjustments.
**Warning signs:** target_bloat_ms decreasing every cycle without convergence. Monitor via tuning_params table.

### Pitfall 4: wanctl_state Labels Ambiguity
**What goes wrong:** The wanctl_state metric is written twice per cycle -- once in the batch (with `{"direction": "download"}` labels) and potentially again as a transition record (with `{"direction": "download", "reason": "..."}` labels). The 1m aggregate merges these.
**Why it happens:** The downsampler does not filter by labels -- it aggregates all wanctl_state rows for a given wan_name+timestamp bucket using MODE.
**How to avoid:** For 1m data, the MODE aggregation of wanctl_state naturally reflects the dominant state of that minute, regardless of duplicate writes per cycle. The download direction dominates because it's written every cycle. For the threshold strategy, we want download state since download uses 4-state logic. Do not attempt to filter by labels in 1m data -- labels are stripped during aggregation (stored as NULL).
**Warning signs:** None expected -- this is an information pitfall, not a runtime one. The MODE aggregation already does the right thing.

### Pitfall 5: Convergence CoV With Identical Values
**What goes wrong:** If all sub-window percentiles are identical (e.g., all exactly 12.5), stdev is 0.0 and CoV is 0.0/12.5 = 0.0, which is below any threshold. This correctly indicates convergence. However, if mean is 0.0 (all deltas are zero), CoV is 0/0 = NaN.
**Why it happens:** Edge case with perfectly idle network or sensor failure.
**How to avoid:** Guard against zero mean: `if avg < 0.001: return True` (treat as converged since values are effectively zero). Python's statistics.stdev raises StatisticsError for single-value input -- guard with `len(sub_values) >= 2`.
**Warning signs:** Strategy crashes with StatisticsError or produces NaN confidence.

### Pitfall 6: Minimum Data for statistics.quantiles()
**What goes wrong:** `statistics.quantiles(data, n=100)` requires at least 2 data points. With 1 GREEN delta, it raises StatisticsError.
**Why it happens:** Very short GREEN periods or sustained congestion leave few GREEN samples.
**How to avoid:** Enforce minimum 60 GREEN samples (1 hour equivalent) before calling quantiles. This is both statistically necessary (need representative distribution) and prevents the API error.
**Warning signs:** Strategy exception logged by analyzer's try/except wrapper.

## Code Examples

### Core Strategy Function Pattern
```python
# Source: Architecture patterns from ARCHITECTURE.md + Phase 98 analyzer.py

import logging
from statistics import mean, quantiles, stdev

from wanctl.tuning.models import SafetyBounds, TuningResult

logger = logging.getLogger(__name__)

# Minimum GREEN-state 1m samples needed for reliable percentile derivation
MIN_GREEN_SAMPLES = 60  # ~1 hour of GREEN minutes

# State encoding (matches _encode_state in autorate_continuous.py)
STATE_GREEN = 0.0


def _extract_green_deltas(metrics_data: list[dict]) -> list[float]:
    """Extract RTT delta values from timestamps where state was GREEN."""
    state_by_ts: dict[int, float] = {}
    delta_by_ts: dict[int, float] = {}

    for row in metrics_data:
        ts = row["timestamp"]
        name = row["metric_name"]
        val = row["value"]
        if name == "wanctl_state":
            state_by_ts[ts] = val
        elif name == "wanctl_rtt_delta_ms":
            delta_by_ts[ts] = val

    return [
        delta_by_ts[ts]
        for ts in delta_by_ts
        if state_by_ts.get(ts) == STATE_GREEN
    ]


def calibrate_target_bloat(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Derive target_bloat_ms from p75 of GREEN-state RTT delta distribution.

    CALI-01: target_bloat_ms converges toward p75 of GREEN-state deltas.
    CALI-04: Uses full 24h lookback window from metrics_data.
    """
    green_deltas = _extract_green_deltas(metrics_data)
    if len(green_deltas) < MIN_GREEN_SAMPLES:
        logger.info(
            "[TUNING] %s: target_bloat_ms skipped, only %d GREEN samples (need %d)",
            wan_name, len(green_deltas), MIN_GREEN_SAMPLES,
        )
        return None

    percentiles = quantiles(green_deltas, n=100)
    candidate = percentiles[74]  # p75

    # Confidence based on GREEN data coverage
    confidence = min(1.0, len(green_deltas) / 1440.0)  # Full day = 1440 minutes

    return TuningResult(
        parameter="target_bloat_ms",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=f"p75 GREEN delta={candidate:.1f}ms ({len(green_deltas)} samples)",
        data_points=len(green_deltas),
        wan_name=wan_name,
    )
```

### Convergence Detection Pattern
```python
# Source: Phase 99 research -- sub-window CoV approach

def _is_converged(
    green_deltas: list[float],
    timestamps: list[int],
    percentile_index: int,
    cov_threshold: float = 0.05,
    num_windows: int = 4,
) -> bool:
    """Check if percentile has converged across sub-windows of lookback.

    Splits the 24h lookback into num_windows sub-windows, computes the
    target percentile in each, and checks if CoV < threshold.
    """
    if not timestamps or not green_deltas:
        return False

    min_ts = min(timestamps)
    max_ts = max(timestamps)
    window_size = (max_ts - min_ts) / num_windows

    sub_percentiles: list[float] = []
    for i in range(num_windows):
        win_start = min_ts + i * window_size
        win_end = win_start + window_size
        chunk = [
            d for d, t in zip(green_deltas, timestamps)
            if win_start <= t < win_end
        ]
        if len(chunk) < 10:
            return False  # Insufficient data in sub-window
        p = quantiles(chunk, n=100)
        sub_percentiles.append(p[percentile_index])

    if len(sub_percentiles) < 3:
        return False

    avg = mean(sub_percentiles)
    if avg < 0.001:
        return True  # Effectively zero

    cov = stdev(sub_percentiles) / avg
    return cov < cov_threshold
```

### Wiring Into Maintenance Loop
```python
# Source: autorate_continuous.py lines 3867-3872 (Phase 98 placeholder)

# BEFORE (Phase 98):
strategies=[],  # No strategies in Phase 98 (framework only)

# AFTER (Phase 99):
from wanctl.tuning.strategies.congestion_thresholds import (
    calibrate_target_bloat,
    calibrate_warn_bloat,
)
strategies=[
    ("target_bloat_ms", calibrate_target_bloat),
    ("warn_bloat_ms", calibrate_warn_bloat),
],
```

### Test Pattern: Synthetic GREEN-State Data
```python
# Source: test_tuning_analyzer.py pattern extended for state-filtered strategies

import time

def _make_green_metrics(
    count: int = 200,
    base_delta: float = 10.0,
    noise_scale: float = 3.0,
    green_fraction: float = 0.8,
) -> list[dict]:
    """Generate synthetic metrics with mixed GREEN/YELLOW state."""
    now = int(time.time())
    metrics = []
    for i in range(count):
        ts = now - (count - i) * 60  # 1m intervals
        delta = base_delta + (i % 5) * noise_scale / 5  # Varying delta
        is_green = (i / count) < green_fraction  # First 80% GREEN
        state = 0.0 if is_green else 1.0

        metrics.append({
            "timestamp": ts, "wan_name": "Spectrum",
            "metric_name": "wanctl_rtt_delta_ms", "value": delta,
            "labels": None, "granularity": "1m",
        })
        metrics.append({
            "timestamp": ts, "wan_name": "Spectrum",
            "metric_name": "wanctl_state", "value": state,
            "labels": None, "granularity": "1m",
        })
    return metrics
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static YAML thresholds (15ms/45ms/80ms) | Percentile-derived thresholds from RTT distribution | Phase 99 (this phase) | Thresholds adapt to actual link characteristics per WAN |
| Manual parameter tuning | Automatic derivation with safety bounds | v1.20 milestone | Eliminates manual threshold guessing for new deployments |
| No convergence detection | CoV-based convergence stops unnecessary adjustments | Phase 99 (this phase) | Reduces tuning_params table writes and log noise |

**Current defaults being calibrated:**
- target_bloat_ms: 15ms (GREEN->YELLOW) -- Spectrum and ATT both use this
- warn_bloat_ms: 45ms (YELLOW->SOFT_RED) -- Spectrum and ATT both use this
- hard_red_bloat_ms: 80ms (SOFT_RED->RED) -- **out of scope for Phase 99** (deferred)

## Open Questions

1. **Should hard_red_bloat_ms also be calibrated in this phase?**
   - What we know: Success criteria only mention target_bloat_ms and warn_bloat_ms. The requirements (CALI-01 through CALI-04) only reference these two parameters.
   - What's unclear: Whether hard_red_bloat_ms should get a p99-based calibration strategy in this phase or a later phase.
   - Recommendation: Out of scope for Phase 99. Can be added trivially later since the infrastructure supports it. Focus on the two explicitly required parameters.

2. **Should the query fetch specific metric names or all metrics for the WAN?**
   - What we know: query_metrics() can filter by metric name list. The strategy only needs wanctl_rtt_delta_ms and wanctl_state.
   - What's unclear: Whether the analyzer should fetch all metrics and let strategies filter, or whether each strategy should specify its needed metrics.
   - Recommendation: The analyzer currently queries without metric name filtering (all metrics for the WAN). This is fine for 1m granularity over 24h -- roughly 1440 rows x ~10 metrics = 14,400 rows, which is small. No need to change the analyzer. The strategy's _extract_green_deltas() filters client-side.

3. **Convergence threshold default value?**
   - What we know: CoV < 0.05 means the standard deviation is less than 5% of the mean. For a threshold around 15ms, this means the derived p75 varies by less than 0.75ms across sub-windows.
   - What's unclear: Whether 0.05 is the right default. Too low = never converges. Too high = stops too early.
   - Recommendation: Default 0.05 (5% CoV). Make configurable via `tuning.convergence_cov_threshold` in YAML. This can be tuned based on production experience.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via .venv/bin/pytest) |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_tuning_thresholds.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CALI-01 | target_bloat_ms derived from p75 of GREEN-state RTT delta | unit | `.venv/bin/pytest tests/test_tuning_thresholds.py::TestCalibrateTargetBloat -x` | Wave 0 |
| CALI-02 | warn_bloat_ms derived from p90 of GREEN-state RTT delta | unit | `.venv/bin/pytest tests/test_tuning_thresholds.py::TestCalibrateWarnBloat -x` | Wave 0 |
| CALI-03 | Convergence detection via CoV threshold | unit | `.venv/bin/pytest tests/test_tuning_thresholds.py::TestConvergenceDetection -x` | Wave 0 |
| CALI-04 | 24h lookback captures diurnal patterns | unit | `.venv/bin/pytest tests/test_tuning_thresholds.py::TestDiurnalLookback -x` | Wave 0 |
| Integration | Strategies wired into maintenance loop | unit | `.venv/bin/pytest tests/test_tuning_wiring.py -x` | Existing (extend) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_tuning_thresholds.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tuning_thresholds.py` -- covers CALI-01, CALI-02, CALI-03, CALI-04
- [ ] Strategy functions in `src/wanctl/tuning/strategies/congestion_thresholds.py`

## Sources

### Primary (HIGH confidence)
- Direct analysis: `src/wanctl/tuning/analyzer.py` -- StrategyFn type alias, run_tuning_analysis() orchestration
- Direct analysis: `src/wanctl/tuning/applier.py` -- apply_tuning_results(), clamp_to_step integration
- Direct analysis: `src/wanctl/tuning/models.py` -- TuningResult, TuningConfig, SafetyBounds, clamp_to_step
- Direct analysis: `src/wanctl/autorate_continuous.py` lines 1346-1466 -- adjust_4state() threshold logic, state encoding
- Direct analysis: `src/wanctl/autorate_continuous.py` lines 3840-3885 -- maintenance loop wiring, strategies=[] placeholder
- Direct analysis: `src/wanctl/autorate_continuous.py` lines 1474-1517 -- _apply_tuning_to_controller parameter mapping
- Direct analysis: `src/wanctl/autorate_continuous.py` lines 2672-2688 -- metrics batch writing (delta + state per cycle)
- Direct analysis: `src/wanctl/storage/downsampler.py` lines 47-52 -- MODE_AGGREGATION_METRICS includes wanctl_state
- Direct analysis: `src/wanctl/storage/reader.py` -- query_metrics() with metric_name, wan, granularity filters
- Direct analysis: `src/wanctl/storage/schema.py` -- wanctl_state encoding (0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED)
- Verified: Python 3.12 statistics.quantiles() with n=100 produces 99 cut points; index [74] = p75, index [89] = p90
- Verified: statistics.quantiles() requires minimum 2 data points (StatisticsError otherwise)

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` -- Strategy function pattern, maintenance window integration
- `.planning/research/PITFALLS.md` -- Pitfall 1 (oscillation), Pitfall 2 (insufficient data), Pitfall 4 (anomalous data)
- `.planning/research/SUMMARY.md` -- Percentile-based threshold derivation confirmed as primary approach

### Tertiary (LOW confidence)
- CoV threshold of 0.05 is a reasonable default but not validated against production data -- needs production tuning

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new deps, all stdlib + existing modules verified
- Architecture: HIGH -- extends Phase 98 foundation exactly as designed, StrategyFn type alias ready
- Pitfalls: HIGH -- timestamp correlation challenge verified by inspecting metrics batch writing and downsampler MODE aggregation
- Convergence detection: MEDIUM -- sub-window CoV approach is sound but default threshold needs production validation

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain, no external dependency changes expected)
