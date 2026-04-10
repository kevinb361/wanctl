# Phase 102: Advanced Tuning - Research

**Researched:** 2026-03-19
**Domain:** Cross-signal parameter adaptation (fusion weights, reflector scoring, baseline bounds) + operator tuning history CLI
**Confidence:** HIGH

## Summary

Phase 102 adds four capabilities to the tuning framework: (1) adaptive fusion ICMP/IRTT weight based on per-signal reliability scoring, (2) reflector min_score threshold tuning from observed success rate distributions, (3) baseline RTT bounds auto-adjustment from observed baseline history percentiles, and (4) a `wanctl-history --tuning` CLI flag for operator review of tuning adjustment history.

All four requirements follow established patterns. ADVT-01/02/03 are new StrategyFn pure functions matching the existing `Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]` signature. They slot into the layer rotation system from Phase 101, likely as a fourth "advanced" layer. ADVT-04 follows the `--alerts` pattern in history.py: add `--tuning` flag, add `query_tuning_params()` to `storage/reader.py`, add `format_tuning_table()` formatter. The tuning_params SQLite table already exists with the exact schema needed.

The key data availability analysis: (a) Fusion weights -- `wanctl_signal_variance_ms2`, `wanctl_signal_confidence`, `wanctl_irtt_rtt_ms`, `wanctl_irtt_ipdv_ms`, and `wanctl_irtt_loss_up_pct`/`wanctl_irtt_loss_down_pct` are all persisted to SQLite. (b) Reflector scores -- the reflector_events table stores deprioritization/recovery transitions, but per-reflector success rates are NOT persisted (only runtime deques in ReflectorScorer). The strategy must use reflector_events event frequency or proxy via outlier/failure metrics. (c) Baseline bounds -- `wanctl_rtt_baseline_ms` is persisted every cycle, giving a rich p5/p95 distribution for bounds derivation.

**Primary recommendation:** Create `src/wanctl/tuning/strategies/advanced.py` with three StrategyFn functions, add a fourth layer to the layer rotation, add `query_tuning_params()` to storage reader, and add `--tuning` flag to history.py. Split into 2 plans: strategies + applier extension (Plan 1), CLI + wiring (Plan 2).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADVT-01 | Fusion ICMP/IRTT weight adapted based on per-signal reliability scoring | Per-signal variance/loss metrics (wanctl_signal_variance_ms2, wanctl_irtt_loss_*_pct, wanctl_irtt_ipdv_ms) are all persisted to SQLite. Strategy computes reliability score per signal from variance + loss rate, derives ICMP weight proportional to ICMP's relative reliability |
| ADVT-02 | Reflector min_score threshold tuned from observed success rate distribution | reflector_events table tracks deprioritization/recovery. Strategy analyzes event frequency relative to current min_score: too many deprioritizations means min_score is too strict, too few means too lenient. Proxy approach via deprioritization rate |
| ADVT-03 | Baseline RTT bounds auto-adjusted from p5/p95 of observed baseline history | wanctl_rtt_baseline_ms persisted every cycle at raw granularity, downsampled to 1m. p5/p95 of 24h baseline distribution provides natural bounds with margin |
| ADVT-04 | wanctl-history --tuning displays tuning adjustment history with time-range filtering | tuning_params table already has timestamp, wan_name, parameter, old_value, new_value, confidence, rationale, data_points, reverted columns. Add query_tuning_params() to reader.py, --tuning flag to history.py |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| statistics (stdlib) | 3.12 | quantiles, mean, stdev for distribution analysis | Already used by all existing strategies; zero dep policy |
| sqlite3 (stdlib) | 3.12 | Read tuning_params table for CLI | Already used by storage/reader.py |
| tabulate | 0.9.0 | Table formatting for --tuning output | Already installed, used by history.py |

### Supporting
No new dependencies. Builds entirely on existing infrastructure:
- `wanctl.tuning.analyzer.run_tuning_analysis` -- strategy orchestration
- `wanctl.tuning.models.TuningResult` -- output format
- `wanctl.tuning.applier.apply_tuning_results` -- bounds + persistence
- `wanctl.tuning.safety` -- revert detection + hysteresis lock
- `wanctl.storage.reader.query_metrics` -- SQLite metrics access
- `wanctl.storage.schema.TUNING_PARAMS_SCHEMA` -- tuning history table

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Deprioritization event frequency proxy (ADVT-02) | Per-reflector success rate persistence | Would require new metrics columns and write amplification; event frequency is sufficient |
| Separate tuning CLI tool | wanctl-history --tuning | Out of scope per REQUIREMENTS.md; --tuning flag matches --alerts pattern |

**Installation:** None needed. Zero new dependencies.

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/tuning/strategies/
    __init__.py                     # (exists)
    base.py                         # TuningStrategy Protocol (exists)
    congestion_thresholds.py        # (exists, Phase 99)
    signal_processing.py            # (exists, Phase 101)
    advanced.py                     # NEW: fusion weight, reflector min_score, baseline bounds

src/wanctl/
    storage/reader.py               # ADD: query_tuning_params()
    history.py                      # ADD: --tuning flag, format_tuning_table()
    autorate_continuous.py          # MODIFY: add ADVANCED_LAYER to ALL_LAYERS, extend _apply_tuning_to_controller
```

### Pattern 1: StrategyFn Pure Function (Established)
**What:** Each tuning strategy is a pure function matching `StrategyFn = Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]`
**When to use:** All new tunable parameters (ADVT-01, 02, 03)
**Example:**
```python
# Source: src/wanctl/tuning/strategies/congestion_thresholds.py
def calibrate_target_bloat(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    ...
```

### Pattern 2: Layer-Tagged Round-Robin (Established in Phase 101)
**What:** Strategies are grouped into layers; maintenance loop rotates one layer per tuning cycle.
**Current layers:**
```python
SIGNAL_LAYER = [("hampel_sigma_threshold", tune_hampel_sigma), ("hampel_window_size", tune_hampel_window)]
EWMA_LAYER = [("load_time_constant_sec", tune_alpha_load)]
THRESHOLD_LAYER = [("target_bloat_ms", calibrate_target_bloat), ("warn_bloat_ms", calibrate_warn_bloat)]
ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER]
```
**Extension:** Add `ADVANCED_LAYER`:
```python
ADVANCED_LAYER = [
    ("fusion_icmp_weight", tune_fusion_weight),
    ("reflector_min_score", tune_reflector_min_score),
    ("baseline_rtt_min", tune_baseline_bounds_min),
    ("baseline_rtt_max", tune_baseline_bounds_max),
]
ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER, ADVANCED_LAYER]
```

### Pattern 3: CLI Query Mode (Established in history.py)
**What:** `--tuning` flag parallels `--alerts` flag -- separate query path with its own formatter.
**Example from existing code:**
```python
# Source: src/wanctl/history.py:414-430
if args.alerts:
    from wanctl.storage.reader import query_alerts
    results = query_alerts(db_path=args.db, start_ts=start_ts, end_ts=end_ts, wan=args.wan)
    if not results:
        print("No alerts found for the specified time range.")
        return 0
    if args.json_output:
        print(format_alerts_json(results))
    else:
        print(format_alerts_table(results))
    return 0
```

### Pattern 4: Storage Reader Query Function (Established)
**What:** Read-only sqlite3 connection, WHERE builder, ORDER DESC, dict results.
**Source:** `query_alerts()` in `storage/reader.py` (lines 102-188).

### Anti-Patterns to Avoid
- **Modifying ReflectorScorer to persist per-host success rates:** Write amplification. Use event frequency from reflector_events table instead.
- **Using wanctl_rtt_fused_ms for fusion reliability:** This metric is written but NOT in STORED_METRICS. Do not rely on it being consistently available. Use ICMP variance + IRTT loss/jitter separately.
- **Tuning baseline_rtt_min and baseline_rtt_max as separate strategy calls sharing one metric query:** They should be computed together from the same baseline distribution and returned as two separate TuningResults from a single function call (or split into two paired strategies that query the same data).
- **Setting fusion weight outside 0.0-1.0 range:** The fusion config validation enforces this hard constraint.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQLite query with filters | Custom SQL builder | Follow query_alerts() pattern in reader.py | Consistent error handling, read-only connection, WHERE builder |
| Table formatting | Manual string formatting | tabulate library (already imported in history.py) | Consistent column alignment, edge cases handled |
| Parameter clamping | Manual bounds + step | clamp_to_step() from tuning/models.py | Two-phase clamping, 0.001 floor, already tested |
| Revert detection | Custom safety logic | check_and_revert() from tuning/safety.py | Already handles congestion rate measurement, revert threshold |
| Layer rotation | Custom scheduling | Existing `wc._tuning_layer_index % len(ALL_LAYERS)` | Proven pattern, just extend ALL_LAYERS list |

**Key insight:** All infrastructure exists. This phase is purely about adding new strategy functions and a CLI query path, not building new systems.

## Common Pitfalls

### Pitfall 1: ADVT-01 Fusion Weight Requires Fusion To Be Enabled
**What goes wrong:** Strategy queries IRTT metrics to assess reliability, but IRTT may not be running or fusion may be disabled. No IRTT data means no reliability comparison possible.
**Why it happens:** Fusion ships disabled by default (`fusion.enabled: false`). IRTT is also disabled by default.
**How to avoid:** Strategy returns None when IRTT metrics are absent (< MIN_SAMPLES threshold). The strategy is advisory -- it won't break when fusion is disabled, it simply won't produce a result.
**Warning signs:** Strategy always returns None in test environments without IRTT data.

### Pitfall 2: ADVT-02 Reflector Success Rates Not Directly Persisted
**What goes wrong:** Expecting per-reflector success rate time-series in SQLite. Only reflector_events (deprioritization/recovery transitions) are persisted.
**Why it happens:** ReflectorScorer keeps rolling deques in memory. Per-host success rates are NOT written to SQLite.
**How to avoid:** Use deprioritization event frequency as a proxy. If no deprioritization events exist in the lookback window, min_score is working well. If deprioritization events are too frequent, min_score may be too strict. If deprioritization events are rare but reflector quality is poor (high outlier rate), min_score may be too lenient.
**Warning signs:** Strategy tries to query per-host success rates from metrics table and gets empty results.

### Pitfall 3: Baseline Bounds p5/p95 With Outliers
**What goes wrong:** Baseline RTT values near bounds may contain outliers (e.g., baseline drift toward corrupted values before the bounds check rejects them). Using raw p5/p95 without filtering could produce too-tight bounds.
**Why it happens:** Baseline updates are EWMA-smoothed but can still drift during sustained conditions.
**How to avoid:** Use p5/p95 with a margin (e.g., p5 * 0.9 for min, p95 * 1.1 for max) to prevent bounds from becoming so tight that normal baseline variation triggers rejection. Keep hard safety floor (e.g., 1.0ms min, never below hardware limits).
**Warning signs:** Baseline bounds shrink to a very narrow range, causing frequent "outside bounds" warnings.

### Pitfall 4: clamp_to_step Rounding for Small Values
**What goes wrong:** `clamp_to_step()` rounds to 1 decimal place. For parameters like `reflector_min_score` (0.0-1.0 range), the rounding may be too coarse (0.75 vs 0.78 lost).
**Why it happens:** `round(clamped, 1)` truncates precision.
**How to avoid:** For min_score (0.0-1.0 range with typical values near 0.7-0.9), 1-decimal rounding is adequate (0.7, 0.8, 0.9 are meaningful steps). For fusion weight (0.0-1.0), same reasoning applies. This is acceptable given the 10% max step constraint.
**Warning signs:** Parameter oscillates between two adjacent rounded values.

### Pitfall 5: --tuning and --alerts Mutual Exclusivity
**What goes wrong:** User passes both `--tuning` and `--alerts`. Which wins?
**Why it happens:** Both are `store_true` flags on the same parser.
**How to avoid:** Use `add_mutually_exclusive_group()` or check priority (tuning before alerts before default metrics). Match existing pattern -- if the existing code does NOT use mutual exclusion for --alerts, follow the same approach.
**Warning signs:** Both flags set simultaneously produces confusing output.

### Pitfall 6: _apply_tuning_to_controller Missing New Parameters
**What goes wrong:** Strategy produces TuningResult but the applier doesn't know how to set the value on WANController.
**Why it happens:** _apply_tuning_to_controller uses if/elif chain -- new parameters need new branches.
**How to avoid:** Extend _apply_tuning_to_controller with:
- `fusion_icmp_weight` -> `wc._fusion_icmp_weight`
- `reflector_min_score` -> `wc._reflector_scorer._min_score`
- `baseline_rtt_min` -> `wc.baseline_rtt_min`
- `baseline_rtt_max` -> `wc.baseline_rtt_max`
**Warning signs:** TuningResult applied but parameter unchanged on controller.

### Pitfall 7: current_params Dict Missing New Parameters
**What goes wrong:** The current_params dict built before `run_tuning_analysis()` doesn't include the new parameters, so `current_value` lookup returns None and the strategy is skipped.
**Why it happens:** current_params is manually constructed in the maintenance loop code.
**How to avoid:** Extend current_params with:
```python
"fusion_icmp_weight": wc._fusion_icmp_weight,
"reflector_min_score": wc._reflector_scorer._min_score,
"baseline_rtt_min": wc.baseline_rtt_min,
"baseline_rtt_max": wc.baseline_rtt_max,
```

## Code Examples

### ADVT-01: Fusion Weight Strategy Approach
```python
# Reliability score for each signal based on variance and loss
# ICMP: use wanctl_signal_variance_ms2 (lower = more reliable)
# IRTT: use wanctl_irtt_ipdv_ms + wanctl_irtt_loss_up/down_pct

def tune_fusion_weight(
    metrics_data: list[dict],
    current_value: float,   # current icmp_weight (0.0-1.0)
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    # 1. Extract ICMP variance and IRTT jitter/loss metrics
    # 2. Compute ICMP reliability = 1.0 / (1.0 + mean_icmp_variance)
    # 3. Compute IRTT reliability = (1.0 - mean_irtt_loss) / (1.0 + mean_irtt_ipdv)
    # 4. candidate_icmp_weight = icmp_reliability / (icmp_reliability + irtt_reliability)
    # 5. Return TuningResult or None if insufficient data
    ...
```

### ADVT-02: Reflector Min Score Strategy Approach
```python
# Uses reflector_events table (not metrics_data from analyzer)
# This strategy may need direct SQLite query since reflector_events
# is a separate table from metrics.
# Alternative: use outlier rate + confidence metrics as proxy for
# reflector quality, deriving whether min_score is appropriate.

def tune_reflector_min_score(
    metrics_data: list[dict],
    current_value: float,   # current min_score (0.0-1.0)
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    # Approach A (preferred): Use signal confidence as proxy
    # High confidence + no deprioritizations = min_score working
    # Low confidence = reflectors struggling, maybe min_score too strict
    #
    # Approach B: Query reflector_events directly (breaks StrategyFn pattern)
    #
    # Given StrategyFn takes metrics_data (already queried), use confidence:
    # 1. Extract wanctl_signal_confidence values
    # 2. Compute mean confidence over lookback window
    # 3. If mean confidence < 0.5, min_score may be too strict (lower it)
    # 4. If mean confidence > 0.9, min_score may be too lenient (raise it)
    # 5. Return TuningResult with candidate adjusted toward optimal
    ...
```

### ADVT-03: Baseline Bounds Strategy Approach
```python
def tune_baseline_bounds_min(
    metrics_data: list[dict],
    current_value: float,   # current baseline_rtt_min
    bounds: SafetyBounds,   # hard safety bounds for the min bound itself
    wan_name: str,
) -> TuningResult | None:
    # 1. Extract wanctl_rtt_baseline_ms values
    # 2. Compute p5 of baseline distribution
    # 3. candidate_min = p5 * 0.9 (10% margin below observed minimum)
    # 4. Floor at hard minimum (e.g., 1.0ms)
    # 5. Return TuningResult
    ...

def tune_baseline_bounds_max(
    metrics_data: list[dict],
    current_value: float,   # current baseline_rtt_max
    bounds: SafetyBounds,   # hard safety bounds for the max bound itself
    wan_name: str,
) -> TuningResult | None:
    # 1. Extract wanctl_rtt_baseline_ms values
    # 2. Compute p95 of baseline distribution
    # 3. candidate_max = p95 * 1.1 (10% margin above observed maximum)
    # 4. Return TuningResult
    ...
```

### ADVT-04: query_tuning_params Reader Function
```python
# Source pattern: query_alerts() in storage/reader.py
def query_tuning_params(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: int | None = None,
    end_ts: int | None = None,
    wan: str | None = None,
    parameter: str | None = None,
) -> list[dict]:
    """Query tuning parameter adjustment history."""
    # Same read-only connection pattern as query_alerts()
    # SELECT from tuning_params table
    # Optional WHERE: timestamp range, wan_name, parameter
    # ORDER BY timestamp DESC
    ...
```

### ADVT-04: --tuning Flag in history.py
```python
# In create_parser(), add to filter_group:
filter_group.add_argument(
    "--tuning",
    action="store_true",
    help="Show tuning parameter adjustments instead of metrics",
)

# In main(), add before alerts check:
if args.tuning:
    from wanctl.storage.reader import query_tuning_params
    results = query_tuning_params(
        db_path=args.db, start_ts=start_ts, end_ts=end_ts, wan=args.wan,
    )
    if not results:
        print("No tuning adjustments found for the specified time range.")
        return 0
    if args.json_output:
        print(format_tuning_json(results))
    else:
        print(format_tuning_table(results))
    return 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static fusion weights (YAML only) | SIGUSR1 reload of icmp_weight | Phase 97 (v1.19) | Weight can be changed without restart |
| Static reflector min_score (YAML only) | YAML config, no runtime change | Phase 93 (v1.19) | min_score set once at startup |
| Static baseline bounds (YAML only) | YAML config, no runtime change | v1.0 | bounds set once at startup |
| No tuning history visibility | tuning_params SQLite table | Phase 98 (v1.20) | Data stored but no CLI query |

**Current tuning layer rotation:** 3 layers (signal, EWMA, threshold). Phase 102 adds a 4th (advanced). This extends the rotation cycle from 3 to 4 tuning cycles per full round-robin. At hourly cadence, full rotation goes from 3 hours to 4 hours.

## Data Availability Analysis

### ADVT-01: Fusion Weight -- Available Metrics
| Metric | Table | Granularity | Usage |
|--------|-------|-------------|-------|
| wanctl_signal_variance_ms2 | metrics | raw/1m | ICMP signal noise level |
| wanctl_signal_confidence | metrics | raw/1m | ICMP measurement quality |
| wanctl_signal_jitter_ms | metrics | raw/1m | ICMP jitter level |
| wanctl_irtt_rtt_ms | metrics | raw/1m | IRTT measurement availability |
| wanctl_irtt_ipdv_ms | metrics | raw/1m | IRTT jitter (noise) |
| wanctl_irtt_loss_up_pct | metrics | raw/1m | IRTT upstream packet loss |
| wanctl_irtt_loss_down_pct | metrics | raw/1m | IRTT downstream packet loss |

**Constraint:** IRTT runs at ~0.1Hz (10s cadence), ICMP at 20Hz. IRTT data is sparse -- only ~6 samples per minute at 1m granularity. The reliability scoring must account for uneven sample counts.

### ADVT-02: Reflector Min Score -- Available Metrics
| Metric | Table | Usage |
|--------|-------|-------|
| wanctl_signal_confidence | metrics | Proxy for reflector quality |
| reflector_events (deprioritized/recovered) | reflector_events | Direct event frequency |

**Constraint:** Per-reflector success rates are NOT in SQLite. The StrategyFn signature receives `metrics_data` from the standard metrics query. To use reflector_events, the strategy would need a separate query (breaks StrategyFn purity) OR use signal confidence as a proxy (preferred).

### ADVT-03: Baseline Bounds -- Available Metrics
| Metric | Table | Granularity | Usage |
|--------|-------|-------------|-------|
| wanctl_rtt_baseline_ms | metrics | raw/1m | Direct baseline history |

**Rich data:** Baseline RTT is persisted every cycle (20Hz raw), downsampled to 1m. A 24h lookback gives ~1440 data points at 1m granularity -- more than sufficient for reliable p5/p95 computation.

### ADVT-04: Tuning History -- Available Data
| Column | Type | Usage |
|--------|------|-------|
| timestamp | INTEGER | When adjustment occurred |
| wan_name | TEXT | Which WAN |
| parameter | TEXT | Parameter name |
| old_value | REAL | Value before change |
| new_value | REAL | Value after change |
| confidence | REAL | Analysis confidence |
| rationale | TEXT | Human-readable reason |
| data_points | INTEGER | Samples analyzed |
| reverted | INTEGER | 0=forward, 1=revert |

**Complete:** The tuning_params table has everything needed for ADVT-04. No schema changes required.

## _apply_tuning_to_controller Extension

New parameters require new branches in the if/elif chain:

```python
elif r.parameter == "fusion_icmp_weight":
    wc._fusion_icmp_weight = r.new_value
elif r.parameter == "reflector_min_score":
    wc._reflector_scorer._min_score = r.new_value
elif r.parameter == "baseline_rtt_min":
    wc.baseline_rtt_min = r.new_value
elif r.parameter == "baseline_rtt_max":
    wc.baseline_rtt_max = r.new_value
```

Also extend current_params dict in maintenance loop:
```python
current_params = {
    # ... existing params ...
    "fusion_icmp_weight": wc._fusion_icmp_weight,
    "reflector_min_score": wc._reflector_scorer._min_score,
    "baseline_rtt_min": wc.baseline_rtt_min,
    "baseline_rtt_max": wc.baseline_rtt_max,
}
```

## Safety Bounds Recommendations

| Parameter | Suggested Min | Suggested Max | Rationale |
|-----------|---------------|---------------|-----------|
| fusion_icmp_weight | 0.3 | 0.95 | ICMP always dominant (20Hz vs 0.1Hz); never let IRTT dominate |
| reflector_min_score | 0.5 | 0.95 | Below 0.5 is too lenient (bad hosts stay active); above 0.95 is too strict |
| baseline_rtt_min | 1.0 | 30.0 | Floor at 1ms (no sub-ms baselines); ceiling at 30ms reasonable for most ISPs |
| baseline_rtt_max | 30.0 | 200.0 | Floor at 30ms (some WAN baselines are naturally high); ceiling at 200ms |

## Open Questions

1. **ADVT-02 StrategyFn Purity vs Direct Event Query**
   - What we know: StrategyFn receives `metrics_data` from the standard metrics query. Reflector events are in a separate table.
   - What's unclear: Should the strategy break StrategyFn purity to query reflector_events, or use signal confidence as a proxy?
   - Recommendation: Use signal confidence + outlier rate as proxy. This preserves the StrategyFn contract and avoids coupling strategies to specific table schemas. If the proxy proves insufficient, a future phase can add reflector event metrics to the standard pipeline.

2. **Baseline Bounds Min/Max: One Strategy or Two?**
   - What we know: Both bounds derive from the same wanctl_rtt_baseline_ms distribution.
   - What's unclear: One function returning two TuningResults, or two separate functions?
   - Recommendation: Two separate StrategyFn functions (`tune_baseline_bounds_min`, `tune_baseline_bounds_max`). This matches the pattern where each strategy function maps to one parameter name, which is how the analyzer iterates and the applier processes results. Both read the same metric but compute different percentiles.

3. **Layer Position: Where Does ADVANCED_LAYER Go?**
   - What we know: Current order is SIGNAL -> EWMA -> THRESHOLD (bottom-up signal chain).
   - What's unclear: Should ADVANCED come before or after THRESHOLD?
   - Recommendation: After THRESHOLD (4th layer). These parameters are "meta" -- they don't affect the signal chain directly but tune the measurement infrastructure. Running them last ensures the core signal chain has stabilized before adjusting measurement parameters.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_advanced_tuning_strategy.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADVT-01 | Fusion weight adaptation from signal reliability | unit | `.venv/bin/pytest tests/test_advanced_tuning_strategy.py::TestTuneFusionWeight -x` | Wave 0 |
| ADVT-02 | Reflector min_score from success rate proxy | unit | `.venv/bin/pytest tests/test_advanced_tuning_strategy.py::TestTuneReflectorMinScore -x` | Wave 0 |
| ADVT-03 | Baseline bounds from p5/p95 baseline history | unit | `.venv/bin/pytest tests/test_advanced_tuning_strategy.py::TestTuneBaselineBounds -x` | Wave 0 |
| ADVT-04 | wanctl-history --tuning CLI display | unit | `.venv/bin/pytest tests/test_history_tuning.py -x` | Wave 0 |
| ADVT-01/02/03 | _apply_tuning_to_controller extension | unit | `.venv/bin/pytest tests/test_tuning_applier.py -x` | Existing (extend) |
| ADVT-01/02/03 | Layer rotation with 4 layers | unit | `.venv/bin/pytest tests/test_tuning_layer_rotation.py -x` | Existing (extend) |
| ADVT-04 | query_tuning_params reader function | unit | `.venv/bin/pytest tests/test_tuning_history_reader.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_advanced_tuning_strategy.py tests/test_history_tuning.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_advanced_tuning_strategy.py` -- covers ADVT-01, ADVT-02, ADVT-03
- [ ] `tests/test_history_tuning.py` -- covers ADVT-04 (--tuning flag, format_tuning_table)
- [ ] `tests/test_tuning_history_reader.py` -- covers query_tuning_params() in reader.py

## Sources

### Primary (HIGH confidence)
- `src/wanctl/tuning/strategies/congestion_thresholds.py` -- existing StrategyFn pattern, verified
- `src/wanctl/tuning/strategies/signal_processing.py` -- existing StrategyFn pattern, verified
- `src/wanctl/tuning/analyzer.py` -- run_tuning_analysis orchestration, verified
- `src/wanctl/tuning/applier.py` -- apply_tuning_results + _apply_tuning_to_controller, verified
- `src/wanctl/tuning/models.py` -- TuningResult, SafetyBounds, clamp_to_step, verified
- `src/wanctl/storage/schema.py` -- tuning_params table schema, verified
- `src/wanctl/storage/reader.py` -- query_alerts pattern for query_tuning_params, verified
- `src/wanctl/history.py` -- --alerts pattern for --tuning flag, verified
- `src/wanctl/reflector_scorer.py` -- ReflectorScorer._min_score attribute, verified
- `src/wanctl/autorate_continuous.py` -- fusion weight, baseline bounds, layer rotation, maintenance loop, verified

### Secondary (MEDIUM confidence)
- Data availability for ADVT-02 reflector tuning -- reflector_events table exists but proxy approach via signal confidence unvalidated in production

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new dependencies, all existing infrastructure
- Architecture: HIGH - all patterns established in Phase 99/101, just extend
- Pitfalls: HIGH - verified data availability, identified ADVT-02 proxy challenge
- CLI: HIGH - exact pattern match from --alerts implementation

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable infrastructure, no external dependencies)
