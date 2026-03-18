# Technology Stack: v1.20 Adaptive Tuning

**Project:** wanctl v1.20
**Researched:** 2026-03-18
**Confidence:** HIGH (all recommendations use existing stdlib + SQLite patterns)

## Executive Summary

Adaptive tuning for wanctl is fundamentally a **statistical analysis problem over historical SQLite metrics**, not a machine learning or optimization library problem. The system already has everything it needs:

1. **Data source**: SQLite metrics.db with per-cycle RTT, jitter, variance, confidence, congestion state, IRTT, and fusion data -- at raw (50ms), 1m, 5m, and 1h granularities.
2. **Math**: Python 3.12 `statistics` module provides `quantiles()`, `median()`, `stdev()`, `mean()`, `NormalDist`, and `fmean()` -- sufficient for percentile analysis, distribution fitting, and statistical inference.
3. **Storage**: The existing `MetricsWriter` singleton and `query_metrics()` reader provide thread-safe read/write access.
4. **Integration**: The SIGUSR1 hot-reload pattern (proven in v1.13, v1.19) enables zero-downtime parameter updates.

**Bottom line: Zero new Python dependencies. Zero new system packages. The entire adaptive tuning system builds on stdlib `statistics` + `collections` + existing SQLite infrastructure.** This is the correct approach because:

- The project constraint is "no external monitoring dependencies" (PROJECT.md)
- scipy/numpy would add ~50MB to container images for trivially implementable math
- The tuning algorithms are percentile analysis + bounded parameter adjustment -- not gradient descent or ML
- Python 3.12 `statistics.quantiles()` already does the heavy lifting (used in `storage/reader.py` via `compute_summary()`)

---

## Recommended Stack

### Core Technologies (Already Present -- No Changes)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| Python | 3.12 | Runtime | Existing |
| SQLite (WAL mode) | 3.x (system) | Historical metrics storage and analysis source | Existing |
| statistics (stdlib) | 3.12 built-in | quantiles(), median(), stdev(), NormalDist for distribution analysis | Existing |
| collections.deque (stdlib) | 3.12 built-in | Bounded rolling windows for real-time parameter tracking | Existing pattern |
| math (stdlib) | 3.12 built-in | log, exp, sqrt for EWMA alpha calculations | Existing |
| json (stdlib) | 3.12 built-in | Parameter snapshot serialization | Existing |
| time (stdlib) | 3.12 built-in | Monotonic timestamps for tuning cadence | Existing |
| logging (stdlib) | 3.12 built-in | Tuning decision audit trail | Existing |

### New Modules (All stdlib -- No New Dependencies)

| Module | Purpose | Why This |
|--------|---------|----------|
| `statistics.quantiles(n=100)` | Compute p5/p25/p50/p75/p95 of RTT distributions for threshold calibration | Already in codebase (reader.py), just need targeted queries |
| `statistics.NormalDist` | Fit RTT distributions to compute z-scores and tail probabilities | Stdlib since 3.8, enables principled threshold selection |
| `statistics.stdev` + `statistics.mean` | Compute coefficient of variation for convergence detection | Already used throughout codebase |
| `dataclasses.dataclass(frozen=True)` | TuningResult snapshots for observability and persistence | Matches existing SignalResult, AsymmetryResult pattern |

### Existing Infrastructure Consumed (No Changes Needed)

| Component | How Tuner Uses It | Integration Point |
|-----------|-------------------|-------------------|
| `storage/reader.py::query_metrics()` | Read historical RTT, jitter, variance, confidence, state | Read-only SQLite queries with time range + WAN filter |
| `storage/writer.py::MetricsWriter` | Persist tuning decisions and parameter snapshots | write_metric() with new metric names |
| `storage/schema.py` | Add tuning_params table for parameter history | New table in create_tables() |
| `signal_utils.py::is_reload_requested()` | Detect SIGUSR1 for tuning parameter application | Existing pattern from fusion/wan_state reload |
| `config_validation_utils.py` | Validate computed parameters against bounds | Existing validate_* functions |
| Health endpoint (`health_check.py`) | Expose tuning state, last adjustment, parameter values | Existing pattern from signal_quality/fusion sections |
| YAML config | Tuning bounds, cadence, enable/disable flag | Existing pattern from signal_processing/fusion sections |

---

## What NOT to Add

### Explicitly Rejected: External Optimization Libraries

| Library | Why Rejected |
|---------|-------------|
| scipy | 50MB+ dependency for `scipy.optimize.minimize`. The tuning problem is bounded percentile analysis, not unconstrained optimization. |
| numpy | 30MB+ dependency. Python `statistics.quantiles()` handles percentile computation. `collections.deque` handles windowing. |
| pandas | Massive dependency. SQLite queries with `WHERE timestamp >= ? AND metric_name = ?` do the same filtering. |
| scikit-learn | ML overkill. No training/inference loop needed -- just statistical analysis of historical data. |
| optuna / hyperopt | Hyperparameter search frameworks. Tuning here is deterministic percentile-to-parameter mapping, not search. |
| bayesian-optimization | Gaussian process based. Unnecessary complexity for 6-8 bounded scalar parameters. |

### Explicitly Rejected: External Monitoring/Storage

| Technology | Why Rejected |
|------------|-------------|
| Prometheus | Project constraint: self-contained, no external monitoring dependencies |
| InfluxDB | SQLite already stores time-series metrics with automatic downsampling |
| Redis | No inter-process state sharing needed; tuning runs inside the daemon |

### Explicitly Rejected: Approaches

| Approach | Why Rejected |
|----------|-------------|
| Reinforcement learning | Requires thousands of episodes to converge. Production network is not a simulation environment. |
| Neural network tuning | Overkill for 6-8 scalar parameters with known physical meaning and bounded ranges. |
| Genetic algorithms | Population-based search is inappropriate for a single production system. |
| Bayesian optimization | Requires surrogate model fitting. Percentile analysis is faster, simpler, and more interpretable. |
| Online gradient descent | No differentiable objective function -- congestion control is discrete state transitions. |

---

## Algorithm Design (Stdlib-Only Implementation)

### Core Pattern: Percentile-Based Parameter Derivation

The tuning algorithm follows a simple, proven pattern used in network engineering (CoDel, BBR):

1. **Query**: Fetch N hours of historical metrics from SQLite (e.g., 24h of 1m aggregates = 1440 rows per WAN per metric)
2. **Analyze**: Compute percentile distribution using `statistics.quantiles(data, n=100)`
3. **Derive**: Map percentiles to parameter values via bounded formulas
4. **Clamp**: Enforce min/max bounds from YAML config
5. **Apply**: Update parameter via SIGUSR1 reload or direct attribute assignment (within daemon process)

```python
# Example: Derive congestion threshold from RTT distribution
# This is the entire algorithm -- no optimization library needed
from statistics import quantiles, median, stdev

def derive_green_threshold(rtt_deltas: list[float], config_bounds: dict) -> float:
    """Derive GREEN->YELLOW threshold from historical RTT delta distribution.

    Uses p75 of clean (non-congested) RTT deltas as the threshold,
    clamped to configured bounds.
    """
    if len(rtt_deltas) < 100:
        return config_bounds["default"]

    percentiles = quantiles(rtt_deltas, n=100)
    # p75 of delta distribution = normal operating range upper bound
    candidate = percentiles[74]

    # Clamp to safety bounds
    return max(config_bounds["min"], min(config_bounds["max"], candidate))
```

### Per-Parameter Tuning Strategy

Each parameter has a specific statistical derivation. No general-purpose optimizer needed.

| Parameter | Data Source | Statistical Method | Safety Bound |
|-----------|-----------|-------------------|-------------|
| hampel_sigma_threshold | signal_outlier_count, signal_variance | Outlier rate targeting: adjust sigma to achieve 5-15% outlier rate | [2.0, 5.0] |
| hampel_window_size | signal_jitter_ms | Autocorrelation length: window should span 1-2 jitter cycles | [5, 15] |
| EWMA load alpha | rtt_delta_ms during GREEN | Response time: alpha = cycle_interval / optimal_time_constant | [0.005, 0.05] |
| EWMA baseline alpha | rtt_baseline_ms drift rate | Baseline stability: slower alpha when baseline is stable | [0.0001, 0.005] |
| fusion icmp_weight | signal_confidence, irtt_rtt_ms | Protocol reliability: weight toward higher-confidence signal | [0.5, 0.9] |
| target_bloat_ms (GREEN->YELLOW) | rtt_delta_ms during GREEN periods | p75 of clean RTT delta distribution | [5, 25] |
| warn_bloat_ms (YELLOW->SOFT_RED) | rtt_delta_ms during YELLOW periods | p90 of moderate congestion delta | [20, 80] |
| reflector min_score | reflector_events, ping success rate | Score threshold that separates reliable from unreliable hosts | [0.6, 0.95] |
| baseline_rtt_bounds | rtt_baseline_ms | p5/p95 of observed baseline distribution | [computed, computed] |

### Convergence Strategy

**Conservative by design:**
- Maximum parameter change per tuning cycle: 10% of current value (configurable)
- Minimum data requirement: 1 hour of metrics before first adjustment
- Convergence detection: stop adjusting when coefficient of variation of recent parameters < 5%
- Revert trigger: if congestion rate increases >20% after adjustment, revert to previous values

All of this is simple arithmetic on `statistics.stdev()` / `statistics.mean()` -- no convergence proofs or Lyapunov analysis needed for bounded parameter clamping.

---

## Integration Architecture

### Data Flow

```
SQLite metrics.db (existing)
    |
    v
ParameterAnalyzer (new module)
    - query_metrics() for historical data
    - statistics.quantiles() for distribution analysis
    - Per-parameter derivation functions
    |
    v
TuningResult (frozen dataclass)
    - parameter_name, old_value, new_value, confidence, rationale
    |
    v
ParameterApplier (new module)
    - Validates bounds (config_validation_utils pattern)
    - Applies to WANController attributes
    - Persists to tuning_params table
    - Logs decisions at WARNING level
```

### Cadence

| Aspect | Value | Rationale |
|--------|-------|-----------|
| Analysis interval | 1 hour | Aligns with existing hourly maintenance window |
| Data lookback | 24 hours | Enough for diurnal pattern; uses 1m aggregates (1440 rows) |
| Application timing | During maintenance cycle | Piggyback on existing hourly cleanup/downsample/VACUUM |
| Minimum data | 1 hour of raw data | Prevent premature tuning on startup |

### SIGUSR1 Reload Extension

The existing SIGUSR1 handler iterates `wan_controllers` and calls per-controller reload methods. Adaptive tuning adds to this chain:

```
SIGUSR1 -> is_reload_requested()
    -> _reload_fusion_config()  (existing)
    -> _reload_tuning_config()  (new: enable/disable, bounds, cadence)
```

This follows the proven pattern: re-read YAML, validate, log old->new transition, update instance attributes.

---

## SQLite Schema Addition

### tuning_params Table

```sql
CREATE TABLE IF NOT EXISTS tuning_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    wan_name TEXT NOT NULL,
    parameter TEXT NOT NULL,
    old_value REAL NOT NULL,
    new_value REAL NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT,
    data_hours REAL NOT NULL,
    reverted INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tuning_params_wan_time
    ON tuning_params(wan_name, timestamp);

CREATE INDEX IF NOT EXISTS idx_tuning_params_param
    ON tuning_params(parameter, wan_name, timestamp);
```

This follows the existing pattern from `schema.py`: simple flat table, indexed for time-range queries, compatible with existing `query_metrics()` style reader functions.

---

## YAML Configuration Section

```yaml
# Adaptive tuning (optional, disabled by default)
tuning:
  enabled: false           # Ships disabled, opt-in via SIGUSR1 or config
  cadence_hours: 1         # How often to analyze and propose adjustments
  lookback_hours: 24       # Historical data window for analysis
  min_data_hours: 1        # Minimum data before first tuning cycle
  max_change_pct: 10       # Maximum % change per parameter per cycle
  revert_threshold_pct: 20 # Revert if congestion rate increases by this %

  # Per-parameter bounds (safety rails)
  bounds:
    hampel_sigma: { min: 2.0, max: 5.0 }
    hampel_window: { min: 5, max: 15 }
    target_bloat_ms: { min: 5, max: 25 }
    warn_bloat_ms: { min: 20, max: 80 }
    fusion_icmp_weight: { min: 0.5, max: 0.9 }
    # ... additional parameters
```

This follows the proven config pattern from `signal_processing`, `reflector_quality`, `fusion`, and `alerting` sections: optional dict with defaults, warn+disable on invalid config.

---

## New File Structure

```
src/wanctl/
    tuning/
        __init__.py               # Module exports
        analyzer.py               # ParameterAnalyzer: queries metrics, derives parameters
        applier.py                # ParameterApplier: validates, applies, persists
        models.py                 # TuningResult, TuningConfig dataclasses
        strategies/
            __init__.py
            hampel.py             # Hampel sigma + window tuning strategy
            ewma.py               # EWMA alpha tuning strategy
            thresholds.py         # Congestion threshold tuning strategy
            fusion.py             # Fusion weight tuning strategy
            reflector.py          # Reflector scoring tuning strategy
            baseline.py           # Baseline RTT bounds tuning strategy
```

Each strategy module is a pure function: `(metrics_data, current_value, bounds) -> TuningResult`. No classes, no state, no dependencies beyond stdlib. Testable in isolation with synthetic data.

---

## Testing Strategy

All tuning code is pure functions on in-memory data. Testing uses the existing pattern:

- **Unit tests**: Feed known distributions into strategy functions, verify output parameters
- **Integration tests**: Create in-memory SQLite with known metrics, run full tuning cycle
- **Safety tests**: Verify bounds are enforced, revert triggers work, enable/disable gate works
- **No mocking of optimizer internals** -- the "optimizer" is `statistics.quantiles()`, which is stdlib

Test fixtures: parametrized distributions (low-jitter, high-jitter, asymmetric, bimodal) as lists of floats fed directly into strategy functions.

---

## Version Compatibility

| Component | Minimum Version | Notes |
|-----------|----------------|-------|
| Python | 3.8 (quantiles, NormalDist) | Project requires 3.11+, so safe |
| SQLite | 3.7 (WAL mode) | System SQLite is always newer |
| statistics.quantiles() | 3.8 | Already used in storage/reader.py |
| statistics.NormalDist | 3.8 | Available but not yet used in codebase |
| dataclasses | 3.7 | Already used throughout codebase |

No version concerns. Everything needed is in Python 3.12 stdlib.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Math library | stdlib statistics | scipy.stats | 50MB dep for percentile computation already in stdlib |
| Optimization | Percentile mapping | scipy.optimize | Not an optimization problem -- it is statistical derivation |
| Data access | Existing query_metrics() | pandas DataFrame | DataFrame adds 100MB for SQL WHERE clauses |
| Time series | SQLite 1m aggregates | InfluxDB | External dependency; SQLite aggregation is sufficient |
| Configuration | YAML bounds section | Database-stored bounds | Config is operator-controlled; bounds should be in YAML |
| Parameter storage | New SQLite table | JSON file | Consistent with existing metrics/alerts/benchmarks pattern |
| Tuning cadence | Hourly (maintenance window) | Per-cycle | Per-cycle wastes CPU; hourly is enough for slow convergence |
| Application method | Direct attribute update | SIGUSR1 full reload | Tuning runs inside the daemon -- direct update is simpler |

---

## Installation

```bash
# No new packages needed
# Zero changes to pyproject.toml dependencies
# Zero changes to Dockerfile
# Zero changes to requirements.txt
```

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| No new deps needed | HIGH | Verified: statistics.quantiles(), NormalDist, stdev, mean all in Python 3.8+ stdlib |
| SQLite integration | HIGH | Existing query_metrics() and MetricsWriter patterns are proven (v1.7+) |
| SIGUSR1 reload | HIGH | Pattern used 3 times (dry_run, wan_state, fusion) with zero issues |
| Percentile-based tuning | HIGH | Standard approach in network engineering (CoDel, BBR use percentile-based thresholds) |
| Safety bounds | HIGH | Simple min/max clamping -- mathematically trivial to verify |
| Parameter convergence | MEDIUM | 10% max change + CV-based convergence detection is conservative but untested in this codebase |
| Revert logic | MEDIUM | Requires clear definition of "congestion rate increased" -- needs careful metric selection |

---

## Sources

- [Python statistics module documentation](https://docs.python.org/3/library/statistics.html) - quantiles(), NormalDist, stdev, mean (HIGH confidence)
- [BBR: Congestion-Based Congestion Control (ACM Queue)](https://queue.acm.org/detail.cfm?id=3022184) - percentile-based threshold calibration pattern (HIGH confidence)
- [CoDel: Controlling Queue Delay (ACM Queue)](https://queue.acm.org/detail.cfm?id=2209336) - adaptive threshold approaches in AQM (HIGH confidence)
- [EWMA optimal decay parameter (arXiv)](https://arxiv.org/pdf/2105.14382) - EWMA lambda optimization via SSE minimization (MEDIUM confidence)
- [Hampel filter Python implementation](https://github.com/MichaelisTrofficus/hampel_filter) - Hampel parameter defaults and behavior (MEDIUM confidence)
- [NIST EWMA Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm) - EWMA lambda selection guidelines (HIGH confidence)
- [Stability-preserving PID tuning with RL](https://www.oaepublish.com/articles/ces.2021.15) - conservative baseline + supervisor pattern (MEDIUM confidence)
- [Self-tuning controller Wikipedia](https://en.wikipedia.org/wiki/Self-tuning) - general self-tuning controller theory (MEDIUM confidence)
- [Generalized Hampel Filters (Springer)](https://link.springer.com/article/10.1186/s13634-016-0383-6) - theoretical foundation for Hampel parameter selection (MEDIUM confidence)
