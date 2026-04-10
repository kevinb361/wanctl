# Phase 101: Signal Processing Tuning - Research

**Researched:** 2026-03-19
**Domain:** Adaptive signal processing parameter optimization (Hampel filter, EWMA alpha) from per-WAN production metrics
**Confidence:** HIGH

## Summary

Phase 101 adds three signal processing tuning strategies to the existing tuning framework (Phase 98-100): Hampel sigma optimization from outlier rate analysis, Hampel window size from autocorrelation analysis, and load EWMA alpha from settling time analysis. All three follow the proven StrategyFn pattern from congestion_thresholds.py -- pure functions taking `(metrics_data, current_value, bounds, wan_name)` and returning `TuningResult | None`. The round-robin bottom-up layering requirement (SIGP-04) is the only architecturally novel element, requiring a layer-tagging mechanism so the maintenance loop rotates between signal processing, EWMA, and threshold strategy groups across successive tuning cycles.

The existing infrastructure fully supports this phase. Signal quality metrics (`wanctl_signal_jitter_ms`, `wanctl_signal_variance_ms2`, `wanctl_signal_confidence`, `wanctl_signal_outlier_count`) and raw RTT metrics (`wanctl_rtt_ms`, `wanctl_rtt_load_ewma_ms`) are already persisted to SQLite at 20Hz and downsampled to 1m/5m/1h granularity. The tuning analyzer, applier, safety/revert module, and maintenance loop wiring are all in place. The `_apply_tuning_to_controller` function already handles `alpha_load` and `alpha_baseline` but needs extension for `hampel_sigma_threshold` and `hampel_window_size` (requires setting attributes on `SignalProcessor` instance). Zero new Python dependencies are needed -- all analysis uses stdlib `statistics` module.

The primary risk is Pitfall 3 from the milestone research: changing signal processing parameters immediately changes the metrics used to evaluate them. The mitigation is target-based tuning with a settling period. Hampel sigma is tuned toward a target outlier rate (configurable, default 5-15%), not by minimizing a feedback metric. EWMA alpha is tuned by analyzing step response characteristics (settling time) from raw RTT data, independent of the current alpha value. The bottom-up layering ensures signal processing stabilizes before EWMA or threshold tuning runs.

**Primary recommendation:** Implement three StrategyFn functions in a new `signal_processing.py` strategy module, extend `_apply_tuning_to_controller` to handle signal processing parameters, and add layer-based round-robin selection in the maintenance loop.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SIGP-01 | Hampel sigma optimized per-WAN based on outlier rate analysis | Target outlier rate approach: compute current outlier rate from wanctl_signal_outlier_count deltas, adjust sigma toward configurable target range (5-15%) |
| SIGP-02 | Hampel window size optimized per-WAN based on autocorrelation analysis | Lag-1 autocorrelation of raw RTT: high autocorrelation (slow-varying signal) suggests larger window, low autocorrelation (noisy) suggests smaller window |
| SIGP-03 | Load EWMA alpha tuned from settling time analysis | Step response analysis: detect RTT step changes, measure how long load_ewma takes to settle within 5% of new level, adjust alpha to hit target settling time |
| SIGP-04 | Signal chain tuned bottom-up, one layer per tuning cycle | Layer tagging: strategies tagged as "signal", "ewma", or "threshold"; round-robin selection of one layer per tuning cycle in maintenance loop |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| statistics (stdlib) | 3.12 | quantiles, stdev, mean, median | Already used by congestion_thresholds.py; zero dep policy |
| collections.deque (stdlib) | 3.12 | Rolling window for autocorrelation | Already used by SignalProcessor |
| math (stdlib) | 3.12 | exp, log for alpha/time-constant conversion | Trivial, already imported elsewhere |

### Supporting
No new dependencies needed. All analysis builds on existing:
- `wanctl.tuning.analyzer.run_tuning_analysis` -- strategy orchestration
- `wanctl.tuning.models.TuningResult` -- output format
- `wanctl.tuning.applier.apply_tuning_results` -- bounds + persistence
- `wanctl.tuning.safety` -- revert detection + hysteresis lock
- `wanctl.storage.reader.query_metrics` -- SQLite access

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual autocorrelation | numpy.correlate | numpy is an anti-feature (zero new deps policy) |
| scipy.optimize for alpha | Manual settling time calc | scipy is an anti-feature |

**Installation:** None needed. Zero new dependencies.

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/tuning/strategies/
    __init__.py                     # (exists)
    base.py                         # TuningStrategy Protocol (exists)
    congestion_thresholds.py        # (exists, Phase 99)
    signal_processing.py            # NEW: Hampel sigma, Hampel window, EWMA alpha
```

### Pattern 1: StrategyFn Pure Function (Existing Pattern)
**What:** Each tuning strategy is a pure function matching `StrategyFn = Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]`
**When to use:** Every new tuning parameter
**Example (from congestion_thresholds.py):**
```python
def calibrate_target_bloat(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    # Analyze metrics_data, return TuningResult or None
```
All three new strategies MUST match this exact signature.

### Pattern 2: Layer-Tagged Strategy Registration
**What:** Strategies are organized into layers for round-robin selection. Each layer represents a stage in the signal chain (signal processing -> EWMA -> thresholds).
**When to use:** SIGP-04 requires bottom-up tuning with one layer per cycle.
**Example:**
```python
# In maintenance loop, strategies are organized by layer:
SIGNAL_LAYER = [
    ("hampel_sigma_threshold", tune_hampel_sigma),
    ("hampel_window_size", tune_hampel_window),
]
EWMA_LAYER = [
    ("alpha_load", tune_alpha_load),
]
THRESHOLD_LAYER = [
    ("target_bloat_ms", calibrate_target_bloat),
    ("warn_bloat_ms", calibrate_warn_bloat),
]
ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER]

# Round-robin: tuning_cycle_index % len(ALL_LAYERS) selects the active layer
active_layer = ALL_LAYERS[wc._tuning_layer_index % len(ALL_LAYERS)]
wc._tuning_layer_index += 1
```
This ensures signal processing stabilizes before EWMA tuning runs, and EWMA stabilizes before threshold tuning.

### Pattern 3: Target-Based Tuning (Signal Processing Specific)
**What:** Instead of optimizing a metric, tune toward a configurable target value.
**When to use:** When the tunable parameter directly affects the metric being measured (feedback loop risk).
**Example:**
```python
# Hampel sigma tuned toward target outlier rate (e.g., 0.10 = 10%)
# If current outlier rate > target_max -> decrease sigma (more aggressive filtering)
# If current outlier rate < target_min -> increase sigma (less aggressive filtering)
target_outlier_rate_min = 0.05  # 5%
target_outlier_rate_max = 0.15  # 15%
```
This breaks the feedback loop because the target is fixed (from config), not derived from the metric itself.

### Pattern 4: Applying Signal Processing Parameters to WANController
**What:** `_apply_tuning_to_controller` must be extended to set signal processing parameters on the `SignalProcessor` instance.
**When to use:** When the tuned parameter lives on a sub-object rather than directly on WANController.
**Example:**
```python
# In _apply_tuning_to_controller:
elif r.parameter == "hampel_sigma_threshold":
    wc.signal_processor._sigma_threshold = r.new_value
elif r.parameter == "hampel_window_size":
    new_size = int(r.new_value)
    wc.signal_processor._window_size = new_size
    wc.signal_processor._window = deque(wc.signal_processor._window, maxlen=new_size)
    wc.signal_processor._outlier_window = deque(
        wc.signal_processor._outlier_window, maxlen=new_size
    )
```
**Critical:** Changing `_window_size` requires resizing both `_window` and `_outlier_window` deques. Using `deque(existing_deque, maxlen=new_size)` preserves the most recent elements.

### Anti-Patterns to Avoid
- **Feedback-metric tuning:** Do NOT tune Hampel sigma by minimizing jitter or variance. This creates a positive feedback loop (lower sigma -> more replacement -> lower variance -> sigma thinks it should go even lower).
- **Raw data queries:** Do NOT query raw-granularity metrics. At 20Hz, 24h = 1.7M rows per metric per WAN. Always use 1m granularity (1440 rows/day).
- **Cross-layer tuning in same cycle:** Do NOT tune signal processing and thresholds in the same cycle. Signal changes alter the data thresholds consume.
- **Alpha-from-alpha derivation:** Do NOT tune alpha by comparing EWMA outputs at different alphas. This is circular. Use step response analysis from RAW RTT data instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile computation | Manual sorting + index | `statistics.quantiles()` | Stdlib, tested, correct |
| Autocorrelation function | Nested loops on raw data | Lag-1 autocorrelation formula on 1m AVG data | Full ACF is O(n^2); lag-1 is O(n) and sufficient for window sizing |
| Step detection | Threshold-based detector | Delta between consecutive 1m averages exceeding a multiple of jitter | Simple, robust, no sliding-window complexity |
| Time constant conversion | Manual alpha/tc formulas | `alpha = cycle_interval / time_constant` (already in Config) | The conversion is already established in autorate_continuous.py |

**Key insight:** All analysis operates on 1m-granularity SQLite data, not raw 20Hz samples. The downsampler already computes AVG for all signal metrics. This limits analysis precision to 1-minute resolution, which is fine for hourly tuning decisions.

## Common Pitfalls

### Pitfall 1: Outlier Count is Monotonically Increasing
**What goes wrong:** `wanctl_signal_outlier_count` is a lifetime counter, not a rate. Querying the 1m-downsampled AVG gives the mid-bucket counter value, not the outlier rate. Using this directly as "outlier rate" gives nonsensical values that grow over time.
**Why it happens:** The metric was designed for health endpoint display (total count), not rate analysis. The downsampler AVGs it (not MODE, not DELTA).
**How to avoid:** Compute outlier rate as delta of outlier_count between successive 1m timestamps divided by the expected sample count per minute (1200 at 20Hz). Formula: `rate = (count[t] - count[t-60]) / 1200.0`. Alternatively, use `wanctl_signal_jitter_ms` and `wanctl_signal_variance_ms2` as proxies for noise level, since these are EWMA values that ARE meaningful as 1m AVG.
**Warning signs:** If computed outlier rate > 1.0 or increases monotonically, you are reading the counter, not the rate.
**Recommended approach:** Compute outlier rate from delta of consecutive 1m outlier_count values. The delta between adjacent minutes gives outliers-per-minute. Divide by samples-per-minute (1200) for rate.

### Pitfall 2: Deque Resize on Window Size Change
**What goes wrong:** Changing `_window_size` on SignalProcessor without resizing the deque means the old maxlen persists. New samples eventually fill to the old size, but the Hampel median/MAD computation uses `list(self._window)` which reflects the old window.
**Why it happens:** `deque(maxlen=N)` is immutable after construction. Setting `_window_size` is just changing an int attribute; it does not resize the deque.
**How to avoid:** Replace both deques: `self._window = deque(self._window, maxlen=new_size)` and `self._outlier_window = deque(self._outlier_window, maxlen=new_size)`. This preserves the most recent N elements.
**Warning signs:** Window size parameter changes in tuning_params table but outlier rate doesn't change.

### Pitfall 3: Trivial Change Filter Blocks Small Alpha Adjustments
**What goes wrong:** `apply_tuning_results` skips changes where `abs(clamped - old) < 0.1`. But alpha_load is typically ~0.025 (for 2s time constant at 50ms interval). A 10% step is 0.0025, which is well below the 0.1 threshold. Alpha changes are silently skipped.
**Why it happens:** The trivial change threshold was designed for congestion thresholds (10-30ms range), not alpha values (0.001-0.1 range).
**How to avoid:** The trivial change filter must use relative comparison for small parameters, OR the alpha should be tuned as time_constant_sec (range 0.5-10s) and converted to alpha at apply time. The latter is cleaner because time constants are in a human-readable range.
**Recommendation:** Tune `load_time_constant_sec` (not `alpha_load` directly). The strategy output is a time constant; `_apply_tuning_to_controller` converts to alpha via `alpha = 0.05 / tc`. This puts the tuned value in the 0.5-10s range where the 0.1 trivial filter is appropriate.

### Pitfall 4: Round-Robin Layer Index Persistence
**What goes wrong:** `_tuning_layer_index` starts at 0 on every daemon restart. If the daemon restarts between tuning cycles, the layer sequence resets and the same layer may run repeatedly.
**Why it happens:** The index is runtime-only state (not persisted to state file or SQLite).
**How to avoid:** This is acceptable. The worst case is one layer runs twice before the rotation continues. The tuning is hourly, so a restart gap of <3 hours means at most one repeated layer. Convergence detection prevents redundant adjustments.
**Warning signs:** Not a real problem -- document and accept.

### Pitfall 5: Autocorrelation on Downsampled Data
**What goes wrong:** Computing autocorrelation on 1m AVG data instead of raw 20Hz data loses the high-frequency structure that determines optimal Hampel window size. The 1m AVG smooths out the very noise you're trying to characterize.
**Why it happens:** Raw data queries are too expensive (Pitfall 6 in milestone research).
**How to avoid:** Autocorrelation of 1m data is still informative: it captures minute-to-minute temporal structure (diurnal patterns, ISP routing changes). The Hampel window (3-15 samples at 20Hz = 0.15-0.75s) operates at a different time scale than 1m data, so the autocorrelation at 1m granularity measures "signal persistence" -- how slowly the underlying RTT changes. High persistence (high autocorrelation) means larger windows are safe because the signal changes slowly.
**Alternative:** Use `wanctl_signal_jitter_ms` (EWMA of consecutive sample deltas) as a proxy. High jitter = noisy = smaller window. Low jitter = stable = larger window. This avoids the autocorrelation computation entirely and may be more robust.

## Code Examples

### SIGP-01: Hampel Sigma Tuning Strategy
```python
# Target-based approach: tune sigma toward a target outlier rate range.
# Outlier rate computed from wanctl_signal_outlier_count deltas.

TARGET_OUTLIER_RATE_MIN = 0.05  # 5% (too few outliers = sigma too loose)
TARGET_OUTLIER_RATE_MAX = 0.15  # 15% (too many outliers = sigma too tight)
SIGMA_STEP = 0.1  # Adjustment step per tuning cycle

def tune_hampel_sigma(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    # 1. Extract outlier_count values by timestamp
    # 2. Compute per-minute outlier deltas
    # 3. Average to get mean outlier rate
    # 4. If rate > TARGET_MAX: decrease sigma (more filtering)
    #    If rate < TARGET_MIN: increase sigma (less filtering)
    #    If in range: return None (converged)
    ...
```

### SIGP-02: Hampel Window Size Tuning Strategy
```python
# Jitter-based approach: use signal jitter as proxy for noise level.
# High jitter -> smaller window (fast response needed)
# Low jitter -> larger window (stable, can smooth more)

MIN_WINDOW = 5   # Minimum window (3 is too few for robust median)
MAX_WINDOW = 15  # Maximum window (larger = more latency in detection)

def tune_hampel_window(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    # 1. Extract jitter_ms values from metrics
    # 2. Compute median jitter over lookback window
    # 3. Map jitter level to window size:
    #    Low jitter (<1ms) -> MAX_WINDOW (stable signal, smooth more)
    #    High jitter (>5ms) -> MIN_WINDOW (noisy, need fast response)
    #    Interpolate linearly between
    # 4. Return TuningResult if delta from current > threshold
    ...
```

### SIGP-03: Load EWMA Alpha / Time Constant Tuning
```python
# Settling time analysis: detect RTT step changes, measure EWMA response.
# Target: load EWMA settles to within 5% of new level within target_settling_sec.

TARGET_SETTLING_SEC = 2.0  # Target: 2 seconds settling time
# alpha = cycle_interval / time_constant
# settling_time ≈ 3 * time_constant (for 95% settling)
# So: target_tc = TARGET_SETTLING_SEC / 3.0

def tune_alpha_load(
    metrics_data: list[dict],
    current_value: float,  # This is alpha_load
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    # 1. Extract wanctl_rtt_ms (raw) and wanctl_rtt_load_ewma_ms
    # 2. Detect step changes in raw RTT (delta > 2x jitter)
    # 3. For each step: measure how many 1m periods until EWMA
    #    converges within 5% of new level
    # 4. Average settling time across detected steps
    # 5. If settling > target: increase alpha (faster response)
    #    If settling < 0.5 * target: decrease alpha (smoother)
    #    If in range: return None (converged)
    ...
```

### SIGP-04: Layer Round-Robin in Maintenance Loop
```python
# In maintenance loop, replace flat all_strategies with layered selection:

SIGNAL_LAYER = [
    ("hampel_sigma_threshold", tune_hampel_sigma),
    ("hampel_window_size", tune_hampel_window),
]
EWMA_LAYER = [
    ("alpha_load", tune_alpha_load),
]
THRESHOLD_LAYER = [
    ("target_bloat_ms", calibrate_target_bloat),
    ("warn_bloat_ms", calibrate_warn_bloat),
]
ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER]

# Per-WAN layer index stored on WANController: wc._tuning_layer_index
active_layer = ALL_LAYERS[wc._tuning_layer_index % len(ALL_LAYERS)]
wc._tuning_layer_index += 1
# active_layer is passed as strategies= to run_tuning_analysis
```

### Applying Signal Processing Parameters
```python
# Extension to _apply_tuning_to_controller:
elif r.parameter == "hampel_sigma_threshold":
    wc.signal_processor._sigma_threshold = r.new_value
elif r.parameter == "hampel_window_size":
    new_size = int(r.new_value)
    wc.signal_processor._window_size = new_size
    wc.signal_processor._window = deque(
        wc.signal_processor._window, maxlen=new_size
    )
    wc.signal_processor._outlier_window = deque(
        wc.signal_processor._outlier_window, maxlen=new_size
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed hampel_sigma=3.0 for all WANs | Per-WAN sigma from outlier rate analysis | Phase 101 | Spectrum (14% outlier rate) gets tighter sigma; ATT (0%) gets looser sigma |
| Fixed hampel_window=7 for all WANs | Per-WAN window from jitter/autocorrelation | Phase 101 | Noisier WANs get smaller windows for faster response |
| Fixed alpha_load from config | Per-WAN alpha from settling time analysis | Phase 101 | WANs with faster dynamics get higher alpha for faster tracking |
| Flat strategy list (all run every cycle) | Layered round-robin (one group per cycle) | Phase 101 | Isolates signal chain effects; prevents correlated parameter changes |

**Important context:**
- Spectrum has 14% outlier rate with default sigma=3.0 -- this is high, suggesting sigma should decrease (more aggressive filtering)
- ATT has 0% outlier rate -- sigma could increase (less aggressive, preserving more of the signal)
- alpha_load is derived from `load_time_constant_sec` via `alpha = 0.05 / tc` (50ms cycle interval)
- alpha_baseline is architectural (protected zone) -- do NOT tune it

## Open Questions

1. **Target outlier rate range (5-15%)**
   - What we know: Research suggests 5-15% as reasonable. Spectrum is at 14% (near upper bound). ATT is at 0%.
   - What's unclear: Whether the optimal rate varies by WAN type or is universal.
   - Recommendation: Make target_min/target_max configurable in tuning.bounds YAML. Default 5-15%. Let production data guide refinement.

2. **Should alpha_baseline be tunable?**
   - What we know: Baseline update is an architectural invariant (PROTECTED ZONE in code). The update logic is carefully designed to prevent drift under load.
   - What's unclear: Whether alpha_baseline affects convergence enough to warrant tuning.
   - Recommendation: Do NOT tune alpha_baseline in Phase 101. It is in the protected zone. Only tune alpha_load. Document as intentional exclusion.

3. **Tune alpha as time_constant or raw alpha?**
   - What we know: Existing config uses `load_time_constant_sec` (preferred) or `alpha_load` (deprecated). The tuning current_params dict includes `alpha_load` (the raw alpha).
   - What's unclear: Whether the strategy should output time_constant and let apply convert, or output alpha directly.
   - Recommendation: Output alpha_load directly (consistent with current_params dict and _apply_tuning_to_controller), but use time_constant internally for target settling time calculation. The bounds should be specified as alpha bounds (e.g., min 0.005, max 0.1) but document equivalent time constants in comments.

4. **Hampel window size as float or int?**
   - What we know: Window size must be an integer (deque maxlen). TuningResult.new_value is float. clamp_to_step rounds to 1 decimal.
   - What's unclear: Whether rounding at apply time is sufficient.
   - Recommendation: Strategy returns float (e.g., 9.0). `_apply_tuning_to_controller` converts to int via `int(r.new_value)`. Bounds min/max should be integers expressed as floats (e.g., 5.0, 15.0).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via pyproject.toml) |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_signal_processing_tuning.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIGP-01 | Hampel sigma converges toward outlier rate target | unit | `.venv/bin/pytest tests/test_signal_processing_tuning.py::TestTuneHampelSigma -x` | Wave 0 |
| SIGP-02 | Hampel window tuned from jitter/autocorrelation | unit | `.venv/bin/pytest tests/test_signal_processing_tuning.py::TestTuneHampelWindow -x` | Wave 0 |
| SIGP-03 | Load EWMA alpha tuned from settling time | unit | `.venv/bin/pytest tests/test_signal_processing_tuning.py::TestTuneAlphaLoad -x` | Wave 0 |
| SIGP-04 | Layer round-robin selection in maintenance loop | unit+integration | `.venv/bin/pytest tests/test_signal_processing_tuning.py::TestLayerRoundRobin -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_signal_processing_tuning.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_signal_processing_tuning.py` -- covers SIGP-01, SIGP-02, SIGP-03, SIGP-04
- [ ] No framework install needed -- pytest already configured

## Key Technical Details for Planning

### Available SQLite Metrics for Analysis
| Metric | Granularity | Aggregation | Use For |
|--------|-------------|-------------|---------|
| `wanctl_signal_outlier_count` | 1m AVG | Counter (monotonic) | Outlier rate via delta between consecutive minutes |
| `wanctl_signal_jitter_ms` | 1m AVG | EWMA value (meaningful) | Noise level proxy for window sizing |
| `wanctl_signal_variance_ms2` | 1m AVG | EWMA value (meaningful) | Noise level proxy |
| `wanctl_signal_confidence` | 1m AVG | 0-1 score | Signal quality indicator |
| `wanctl_rtt_ms` | 1m AVG | Raw RTT | Step detection for settling time |
| `wanctl_rtt_load_ewma_ms` | 1m AVG | EWMA output | Settling time measurement |
| `wanctl_rtt_delta_ms` | 1m AVG | Delta value | Step detection |
| `wanctl_state` | 1m MODE | State enum | GREEN filtering (reuse from congestion_thresholds.py) |

### What Must Be Extended in _apply_tuning_to_controller
The existing function handles: `target_bloat_ms`, `warn_bloat_ms`, `hard_red_bloat_ms`, `alpha_load`, `alpha_baseline`.
Must add: `hampel_sigma_threshold`, `hampel_window_size`.
Both require setting attributes on `wc.signal_processor` (not directly on `wc`).

### What Must Be Extended in current_params Dict
Lines 3936-3941 of autorate_continuous.py build `current_params` for run_tuning_analysis.
Must add:
```python
"hampel_sigma_threshold": wc.signal_processor._sigma_threshold,
"hampel_window_size": float(wc.signal_processor._window_size),
```

### What Must Be Extended in Maintenance Loop
Lines 3914-3917 define `all_strategies` as a flat list. Must be restructured to layer-based selection per SIGP-04. The `wc._tuning_layer_index` attribute (initialized to 0 in WANController.__init__) tracks rotation.

### Tuning Bounds Defaults for Signal Processing
```yaml
tuning:
  bounds:
    hampel_sigma_threshold:
      min: 1.5   # Very aggressive (catches most deviations)
      max: 5.0   # Very permissive (only extreme outliers)
    hampel_window_size:
      min: 5.0   # Minimum for robust median (3 is too few)
      max: 15.0  # Maximum before latency in detection becomes an issue
    alpha_load:
      min: 0.005  # Very slow (10s time constant at 50ms interval)
      max: 0.1    # Very fast (0.5s time constant at 50ms interval)
```

## Sources

### Primary (HIGH confidence)
- `src/wanctl/signal_processing.py` -- SignalProcessor implementation, Hampel filter, EWMA, confidence scoring
- `src/wanctl/tuning/strategies/congestion_thresholds.py` -- StrategyFn pattern, GREEN-state filtering, convergence detection
- `src/wanctl/tuning/analyzer.py` -- run_tuning_analysis orchestration, StrategyFn type alias
- `src/wanctl/tuning/models.py` -- TuningResult, TuningConfig, SafetyBounds, clamp_to_step
- `src/wanctl/tuning/safety.py` -- Revert detection, hysteresis lock
- `src/wanctl/autorate_continuous.py` -- WANController, EWMA update, maintenance loop wiring
- `src/wanctl/storage/schema.py` -- STORED_METRICS dict, SQLite schema
- `src/wanctl/storage/downsampler.py` -- MODE_AGGREGATION_METRICS, AVG default

### Secondary (MEDIUM confidence)
- `.planning/research/PITFALLS.md` -- Pitfall 3 (signal processing feedback loop), Pitfall 1 (oscillation)
- `.planning/research/SUMMARY.md` -- Target outlier rate 5-15% range
- `.planning/research/FEATURES.md` -- Feature dependencies and anti-features

### Tertiary (LOW confidence)
- Target outlier rate 5-15% is empirical recommendation from milestone research, not theoretically derived. Needs production validation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new deps, all stdlib patterns already proven in Phases 98-100
- Architecture: HIGH - StrategyFn pattern is established and proven; layer round-robin is straightforward
- Pitfalls: HIGH - outlier_count counter trap and deque resize are code-verified facts
- Signal processing tuning algorithms: MEDIUM - target outlier rate range and jitter-based window sizing are reasonable heuristics but not theoretically optimal
- EWMA settling time analysis: MEDIUM - step detection from 1m-averaged data may miss fast steps, but suitable for hourly tuning

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable domain, no external dependency changes expected)
