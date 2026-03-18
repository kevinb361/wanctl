# Architecture Patterns: v1.20 Adaptive Tuning Integration

**Domain:** Adaptive parameter optimization for real-time CAKE bandwidth controller
**Researched:** 2026-03-18
**Confidence:** HIGH (direct source code analysis of all integration points in 26K LOC codebase)

## Executive Summary

The adaptive tuning engine integrates with the existing 50ms control loop by running as a
periodic analyzer during the established hourly maintenance window. The existing architecture
already provides every needed primitive: SQLite metrics history with read-only access,
SIGUSR1 hot-reload for zero-downtime toggle, per-WAN config isolation, and health endpoint
patterns. No new threads, no new processes, no new IPC. The tuning engine piggybacks on
the hourly maintenance pass that already exists in the main daemon loop.

## Recommended Architecture

### Overview: Tuning as Maintenance-Window Task

```
                    Hourly Maintenance Window (existing)
                              |
                              v
    +-------------------+   query_metrics()   +------------------+
    | SQLite metrics.db | -----------------> | ParameterAnalyzer |
    | (existing, WAL)   |   read-only conn   |  - per-WAN query  |
    +-------------------+                    |  - 24h lookback   |
                                             |  - 1m granularity |
                                             +--------+---------+
                                                      |
                                        list[TuningResult]
                                                      |
                                                      v
                                             +--------+---------+
                                             | ParameterApplier |
                                             |  - bounds check  |
                                             |  - max_step_pct  |
                                             |  - convergence   |
                                             +--------+---------+
                                                      |
                              +---------------+-------+-------+---------------+
                              |               |               |               |
                              v               v               v               v
                        WANController   SQLite tuning_  Health endpoint  Log WARNING
                        attrs updated   params table    tuning section   old->new
```

### Why Maintenance Window, Not Background Thread

The existing main loop already has an hourly maintenance pass:

```python
# autorate_continuous.py lines 3505-3540 (existing code, unchanged)
if now - last_maintenance >= MAINTENANCE_INTERVAL:
    cleanup_old_metrics(maintenance_conn, ...)
    downsample_metrics(maintenance_conn, ...)
    vacuum_if_needed(maintenance_conn, ...)
    last_maintenance = now
```

Tuning analysis adds to this window because:

1. **No thread synchronization** -- tuning modifies WANController attributes (thresholds, alphas)
   that are read in the 50ms hot loop. Running in the main thread between cycles means no
   concurrent access. GIL protects simple float/int assignments, but complex multi-attribute
   updates benefit from same-thread execution.
2. **Analysis is fast** -- querying 1440 rows of 1-minute aggregates (24h) takes <50ms.
   Statistical analysis (percentiles, distribution fitting) on ~1500 values takes <10ms.
   Total tuning pass: <100ms for 2 WANs. Well within the maintenance window.
3. **Proven pattern** -- maintenance already runs in the main thread between cycles.
   Adding tuning here follows the same execution model.
4. **No lifecycle management** -- no thread start/stop, no join timeout, no stop_event.

### Why Not a Separate Background Thread

While IRTTThread uses a background thread, that's because IRTT measurements block for
1+ seconds (network I/O). Tuning analysis is pure computation on in-memory data. The
overhead difference:

| Operation | Duration | Thread justified? |
|-----------|----------|-------------------|
| IRTT measurement | 1000-2000ms (network) | YES |
| Webhook delivery | 100-5000ms (network) | YES |
| Tuning analysis | 50-100ms (CPU + SQLite) | NO |

A background thread would add complexity (parameter synchronization, stop event, cleanup)
for an operation that takes less than 2 hot-loop cycles.

## Component Boundaries

| Component | Responsibility | New/Modified | Communicates With |
|-----------|---------------|--------------|-------------------|
| `tuning/analyzer.py` | Query metrics, compute distributions, derive parameter candidates per WAN | **NEW** | storage/reader.py (read), strategies (call) |
| `tuning/strategies/*.py` | Per-parameter pure-function derivation logic | **NEW** | stdlib statistics only |
| `tuning/applier.py` | Validate bounds, apply parameters, persist decisions, detect reverts | **NEW** | WANController attrs (write), MetricsWriter (persist) |
| `tuning/models.py` | TuningResult, TuningConfig, TuningState frozen dataclasses | **NEW** | Used by analyzer, applier, health endpoint |
| `WANController._apply_tuning()` | Accept TuningResult list, update live instance attributes | **MODIFIED** (~40 lines) | Receives from applier |
| `WANController._reload_tuning_config()` | Re-read `tuning:` section on SIGUSR1 | **MODIFIED** (~30 lines) | signal_utils (trigger) |
| `HealthCheckHandler` | Add `tuning` section to health JSON response | **MODIFIED** (~25 lines) | Reads TuningState |
| `storage/schema.py` | Add TUNING_PARAMS_SCHEMA for audit table | **MODIFIED** (~15 lines) | create_tables() |
| `autorate_continuous.py main()` | Call tuning in maintenance window | **MODIFIED** (~15 lines) | analyzer + applier |
| `autorate_continuous.py Config` | Parse `tuning:` YAML section | **MODIFIED** (~40 lines) | BaseConfig pattern |

## Data Flow: Detailed Per-Step

### Step 1: Metric Collection (existing, NO changes)

Every 50ms cycle, WANController.run_cycle() writes to SQLite:

```python
# Lines 2378-2427 of autorate_continuous.py (existing)
metrics_batch = [
    (ts, wan_name, "wanctl_rtt_ms", measured_rtt, None, "raw"),
    (ts, wan_name, "wanctl_rtt_baseline_ms", self.baseline_rtt, None, "raw"),
    (ts, wan_name, "wanctl_rtt_delta_ms", delta, None, "raw"),
    (ts, wan_name, "wanctl_rate_download_mbps", dl_rate / 1e6, None, "raw"),
    (ts, wan_name, "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
    (ts, wan_name, "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
    (ts, wan_name, "wanctl_signal_confidence", sr.confidence, None, "raw"),
    (ts, wan_name, "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
    (ts, wan_name, "wanctl_rtt_fused_ms", fused_rtt, None, "raw"),
    (ts, wan_name, "wanctl_rtt_load_ewma_ms", self.load_rtt, None, "raw"),
]
```

The downsampler (existing, lines 24-43 of storage/downsampler.py) creates 1-minute aggregates
after 1 hour. These 1m aggregates are what the tuning analyzer queries.

### Step 2: Tuning Analysis (new, in maintenance window)

```python
# In main loop, after existing maintenance tasks:
if tuning_enabled and now - last_tuning >= tuning_cadence:
    for wan_info in controller.wan_controllers:
        wc = wan_info["controller"]
        results = run_tuning_analysis(wc.wan_name, db_path, wc, tuning_config)
        if results:
            wc._apply_tuning(results)
            persist_tuning_results(results, metrics_writer)
    last_tuning = now
```

### Step 3: Statistical Analysis (new, pure functions)

```python
# tuning/strategies/thresholds.py
def derive_green_threshold(
    rtt_deltas: list[float],
    current_value: float,
    bounds: dict[str, float],
    max_change_pct: float,
) -> TuningResult | None:
    """Derive GREEN->YELLOW threshold from clean RTT delta distribution.

    Uses p75 of deltas during GREEN periods as the baseline for
    the green threshold. Conservative: only moves threshold downward
    if p75 is consistently below current value.
    """
    if len(rtt_deltas) < 100:
        return None  # Insufficient data

    percentiles = quantiles(rtt_deltas, n=100)
    candidate = percentiles[74]  # p75

    # Clamp to safety bounds
    clamped = max(bounds["min"], min(bounds["max"], candidate))

    # Enforce max change rate per cycle
    max_delta = current_value * (max_change_pct / 100.0)
    if abs(clamped - current_value) > max_delta:
        direction = 1 if clamped > current_value else -1
        clamped = current_value + max_delta * direction

    # Skip trivial changes (< 1% difference)
    if abs(clamped - current_value) / max(current_value, 0.01) < 0.01:
        return None

    return TuningResult(
        parameter="target_bloat_ms",
        old_value=current_value,
        new_value=round(clamped, 1),
        confidence=min(1.0, len(rtt_deltas) / 1000),
        rationale=f"p75 RTT delta = {candidate:.1f}ms ({len(rtt_deltas)} samples)",
        data_points=len(rtt_deltas),
    )
```

### Step 4: Parameter Application (new, on WANController)

```python
# In WANController._apply_tuning():
def _apply_tuning(self, results: list[TuningResult]) -> None:
    for r in results:
        if r.parameter == "target_bloat_ms":
            old = self.green_threshold
            self.green_threshold = r.new_value
            self.logger.warning(
                f"[TUNING] {self.wan_name}: target_bloat_ms "
                f"{old:.1f}->{r.new_value:.1f} ({r.rationale})"
            )
        elif r.parameter == "warn_bloat_ms":
            old = self.soft_red_threshold
            self.soft_red_threshold = r.new_value
            self.logger.warning(...)
        elif r.parameter == "alpha_load":
            old = self.alpha_load
            self.alpha_load = r.new_value
            self.logger.warning(...)
        # Signal processing params need method call
        elif r.parameter == "hampel_sigma_threshold":
            old = self.signal_processor._sigma_threshold
            self.signal_processor._sigma_threshold = r.new_value
            self.logger.warning(...)
```

**Critical: Runtime-only changes.** YAML is never written. Tuned values reset on daemon
restart. SIGUSR1 reverts to YAML values (operator always has reset escape hatch).

## Answers to Specific Integration Questions

### 1. Where does the tuning engine run?

**In the main daemon loop, during the hourly maintenance window.** The maintenance window
(lines 3505-3540 of autorate_continuous.py) already runs cleanup, downsampling, and VACUUM
every 3600 seconds. Tuning analysis adds ~100ms to this window.

```python
# Existing maintenance block extended:
if now - last_maintenance >= MAINTENANCE_INTERVAL:
    # Existing: cleanup, downsample, vacuum
    run_existing_maintenance(maintenance_conn, ...)

    # New: tuning analysis (if enabled)
    if tuning_config.get("enabled", False):
        for wan_info in controller.wan_controllers:
            wc = wan_info["controller"]
            results = analyze_and_tune(wc, db_path, tuning_config)
            if results:
                wc._apply_tuning(results)

    last_maintenance = now
```

Cadence can be decoupled from maintenance if needed (separate `last_tuning` timer), but
1-hour is the natural starting cadence for slow-convergence tuning.

### 2. How does it read historical metrics from SQLite?

Uses **existing `query_metrics()` from `storage/reader.py`** (lines 19-99). This opens a
read-only SQLite connection (`file:{path}?mode=ro`), separate from the MetricsWriter
singleton. No new database infrastructure needed.

```python
from wanctl.storage.reader import query_metrics

rtt_data = query_metrics(
    db_path=db_path,
    start_ts=int(time.time()) - 86400,  # 24h lookback
    metrics=["wanctl_rtt_delta_ms", "wanctl_signal_variance_ms2",
             "wanctl_signal_confidence", "wanctl_state"],
    wan=wan_name,
    granularity="1m",  # 1-minute aggregates: ~1440 rows for 24h
)
```

**Use 1m granularity for 24h analysis.** Raw data at 20Hz produces 1.7M rows/day -- that
would make SQLite aggregate queries take seconds. The existing downsampler already creates
1m averages after 1 hour (storage/downsampler.py DOWNSAMPLE_THRESHOLDS). For 7-day trend
analysis, use "5m" granularity (~2016 rows).

### 3. How does it apply tuned parameters to running WANControllers?

**Direct attribute mutation** on WANController instances. This is safe because tuning runs
in the maintenance window of the **same main thread** as the hot loop -- between cycles,
not concurrent with them.

Tunable attributes on WANController (lines 1363-1375 of autorate_continuous.py):
- `self.green_threshold` (target_bloat_ms) -- GREEN->YELLOW transition
- `self.soft_red_threshold` (warn_bloat_ms) -- YELLOW->SOFT_RED transition
- `self.hard_red_threshold` (hard_red_bloat_ms) -- SOFT_RED->RED transition
- `self.accel_threshold` (accel_threshold_ms) -- spike detection
- `self.alpha_baseline` -- baseline EWMA smoothing
- `self.alpha_load` -- load EWMA smoothing

Tunable attributes on SignalProcessor (lines 97-105 of signal_processing.py):
- `self.signal_processor._sigma_threshold` -- Hampel outlier sensitivity
- `self.signal_processor._window_size` -- requires window rebuild (deferred)

### 4. How does it interact with SIGUSR1 reload?

**SIGUSR1 reverts all tuned parameters to YAML values.** This extends the existing reload
chain (fusion, dry_run, wan_state, webhook_url) with one more _reload method.

```python
# autorate_continuous.py lines 3542-3549 (extend existing handler):
if is_reload_requested():
    for wan_info in controller.wan_controllers:
        wan_info["controller"]._reload_fusion_config()     # existing
        wan_info["controller"]._reload_tuning_config()     # NEW
    reset_reload_state()
```

The `_reload_tuning_config()` method:
1. Re-reads `tuning:` section from YAML (same pattern as `_reload_fusion_config`)
2. If tuning was enabled and is now disabled: revert all params to YAML originals
3. If tuning was disabled and is now enabled: mark ready for next analysis cycle
4. If bounds changed: apply new bounds, revert any out-of-bounds tuned values

**YAML is always the reset escape hatch.** Operator can always `kill -USR1 <pid>` to
return to hand-tuned parameters.

### 5. What new components are needed vs extending existing ones?

**New files (5):**

| File | Purpose | LOC estimate |
|------|---------|-------------|
| `src/wanctl/tuning/models.py` | TuningResult, TuningConfig, TuningState frozen dataclasses | ~80 |
| `src/wanctl/tuning/analyzer.py` | Per-WAN metric query + strategy orchestration | ~200 |
| `src/wanctl/tuning/strategies/thresholds.py` | Threshold derivation (target, warn, hard_red) | ~150 |
| `src/wanctl/tuning/strategies/signal_params.py` | Hampel sigma, EWMA alpha derivation | ~150 |
| `src/wanctl/tuning/applier.py` | Bounds validation, application, persistence, revert | ~150 |

**Modified files (4):**

| File | Change | Lines added |
|------|--------|-------------|
| `autorate_continuous.py` | WANController._apply_tuning(), _reload_tuning_config(); main() maintenance wiring; Config tuning section | ~120 |
| `health_check.py` | `tuning` section in health JSON | ~25 |
| `storage/schema.py` | TUNING_PARAMS_SCHEMA table definition | ~15 |
| YAML example configs | `tuning:` section with defaults | ~15 each |

**Total estimated new code:** ~730 lines implementation + ~600 lines tests = ~1330 lines

### 6. How to handle per-WAN parameter specialization?

The existing architecture already provides per-WAN isolation. Each WAN has:

- **Independent WANController** instance with its own threshold/alpha attributes (line 3057)
- **Independent Config** parsed from separate YAML files (spectrum.yaml, att.yaml)
- **SQLite metrics tagged** with `wan_name` column (line 2381)

The tuning analyzer iterates per-WAN:

```python
for wan_info in controller.wan_controllers:
    wc = wan_info["controller"]
    # Query metrics for THIS WAN only
    data = query_metrics(wan=wc.wan_name, ...)
    # Analyze THIS WAN's unique distribution
    results = run_strategies(data, wc, bounds)
    # Apply to THIS WAN's controller only
    wc._apply_tuning(results)
```

This naturally produces different tuning for each WAN. Spectrum (24ms baseline, 14% outlier
rate) gets different Hampel sigma than ATT (31ms baseline, 0% outliers). The portable
controller invariant is maintained: same code, different parameters per config.

## Tunable Parameter Categories

### Category 1: Congestion Thresholds (HIGH value, LOW risk -- build first)

| Parameter | WANController attr | Tuning Signal | Safety Bounds | Analysis Method |
|-----------|--------------------|---------------|---------------|-----------------|
| `target_bloat_ms` | `green_threshold` | p75 of delta during GREEN | [3, 30] ms | Percentile of clean delta distribution |
| `warn_bloat_ms` | `soft_red_threshold` | p95 of delta during load | [10, 100] ms | Percentile of loaded delta distribution |
| `hard_red_bloat_ms` | `hard_red_threshold` | p99 of delta during load | [30, 200] ms | Tail percentile |
| `accel_threshold_ms` | `accel_threshold` | p99.9 of delta-accel | [5, 50] ms | Acceleration distribution tail |

**Why first:** Thresholds affect when state transitions happen, not how aggressively
rates change. Floor/ceiling/factor_down remain unchanged. Safest possible first tuning.

### Category 2: EWMA Parameters (MEDIUM value, MEDIUM risk -- build second)

| Parameter | WANController attr | Tuning Signal | Safety Bounds |
|-----------|--------------------|---------------|---------------|
| `alpha_load` | `alpha_load` | Optimal responsiveness from variance analysis | [0.005, 0.5] |
| `alpha_baseline` | `alpha_baseline` | Baseline drift rate | [0.0001, 0.01] |

**Analysis method:** If signal variance is high and alpha is low, the EWMA is under-reacting
(too smooth). If consecutive state changes flip rapidly (flapping metric from alerting), alpha
is too high (too reactive). Optimal alpha minimizes flapping while maintaining response time.

### Category 3: Signal Processing (LOW value, LOW risk -- build third)

| Parameter | SignalProcessor attr | Tuning Signal | Safety Bounds |
|-----------|---------------------|---------------|---------------|
| `hampel_sigma_threshold` | `_sigma_threshold` | `outlier_rate` metric | [2.0, 5.0] |
| `jitter_time_constant_sec` | `_jitter_alpha` | Jitter tracking accuracy | [0.5, 10.0] |
| `variance_time_constant_sec` | `_variance_alpha` | Variance tracking accuracy | [1.0, 20.0] |

**Why last:** Signal processing is observation mode. Tuning these affects the quality of
the input signal to EWMA but does not directly cause state transitions.

### Category 4: Rate Control Parameters (HIGH risk -- DEFER to v1.21+)

| Parameter | Why Defer |
|-----------|-----------|
| `floor_*_mbps` | Directly sets minimum throughput. Tuning this wrong starves the connection. |
| `ceiling_mbps` | Maximum throughput cap. Wrong value causes persistent congestion. |
| `factor_down` | Congestion decay aggression. Wrong value causes oscillation or under-reaction. |
| `step_up_mbps` | Recovery speed. Wrong value causes slow recovery or overshoot. |
| `green_required` | Recovery hysteresis. Wrong value causes premature recovery or excessive delay. |

## SQLite Schema Extension

```sql
-- Tuning parameter adjustment history (append-only audit log)
CREATE TABLE IF NOT EXISTS tuning_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    wan_name TEXT NOT NULL,
    parameter TEXT NOT NULL,
    old_value REAL NOT NULL,
    new_value REAL NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT,
    data_points INTEGER NOT NULL,
    reverted INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tuning_timestamp
    ON tuning_params(timestamp);

CREATE INDEX IF NOT EXISTS idx_tuning_wan_param
    ON tuning_params(wan_name, parameter, timestamp);
```

## Health Endpoint Extension

```json
{
  "wans": [{
    "name": "Spectrum",
    "tuning": {
      "enabled": true,
      "last_analysis_ago_sec": 1847,
      "next_analysis_in_sec": 1753,
      "parameters_adjusted": 2,
      "total_adjustments": 14,
      "total_reverts": 1,
      "hours_of_data": 24.0,
      "active_adjustments": [
        {
          "parameter": "target_bloat_ms",
          "yaml_value": 15.0,
          "tuned_value": 13.2,
          "confidence": 0.85
        },
        {
          "parameter": "hampel_sigma_threshold",
          "yaml_value": 3.0,
          "tuned_value": 2.7,
          "confidence": 0.72
        }
      ]
    }
  }]
}
```

When tuning is disabled:
```json
{
  "tuning": {
    "enabled": false,
    "reason": "disabled"
  }
}
```

## YAML Configuration

```yaml
tuning:
  enabled: false              # Ships disabled (proven pattern)
  cadence_sec: 3600           # Analyze every hour (matches maintenance)
  lookback_hours: 24          # How far back to query metrics
  warmup_hours: 6             # Minimum data before first tuning
  safety:
    max_step_pct: 10          # Max 10% change per tuning cycle
    revert_threshold_pct: 20  # Revert if congestion increases >20%
  bounds:
    target_bloat_ms: {min: 3, max: 30}
    warn_bloat_ms: {min: 10, max: 100}
    hard_red_bloat_ms: {min: 30, max: 200}
    accel_threshold_ms: {min: 5, max: 50}
    alpha_load: {min: 0.005, max: 0.5}
    alpha_baseline: {min: 0.0001, max: 0.01}
    hampel_sigma_threshold: {min: 2.0, max: 5.0}
```

## Patterns to Follow

### Pattern 1: Strategy Functions (Pure, Stateless, Testable)

Each tunable parameter has a dedicated strategy function. Strategies are pure functions:
`(data, current_value, bounds) -> TuningResult | None`. No classes, no instance state.

**Why:** Testable with synthetic data. No mock setup needed. Each strategy is 20-50 lines.

### Pattern 2: Frozen Dataclass Results (Proven: SignalResult, IRTTResult)

TuningResult follows the established pattern: `@dataclass(frozen=True, slots=True)`.

```python
@dataclass(frozen=True, slots=True)
class TuningResult:
    parameter: str        # e.g., "target_bloat_ms"
    old_value: float
    new_value: float
    confidence: float     # 0-1 based on data quantity
    rationale: str        # Human-readable for logs and health endpoint
    data_points: int
```

### Pattern 3: Ship Disabled, SIGUSR1 Toggle (Proven: v1.11, v1.13, v1.19)

Feature ships with `tuning.enabled: false`. Enable via YAML edit + SIGUSR1.

### Pattern 4: Warn+Disable Config Validation (Proven: wan_state, fusion, alerting)

Invalid tuning config warns and disables. Never crashes the daemon.

### Pattern 5: WARNING-Level Logging for Parameter Changes (Proven: SIGUSR1 reloads)

All tuning changes logged at WARNING with old->new transition:
```
WARNING [TUNING] Spectrum: target_bloat_ms 15.0->13.2 (p75 RTT delta=11.8ms, 1247 samples)
```

### Pattern 6: Revert Safety Net

If congestion rate increases after tuning (measured as % of cycles in RED/SOFT_RED),
automatically revert the most recent adjustment and log at ERROR level.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Per-Cycle Tuning
**What:** Adjusting parameters every 50ms.
**Why bad:** Creates feedback oscillation. Parameter change affects the metrics used to
compute the next change. Known instability in self-tuning control systems.
**Instead:** Hourly cadence with 24h lookback.

### Anti-Pattern 2: Coupled Parameter Optimization
**What:** Adjusting all parameters simultaneously.
**Why bad:** Cannot attribute outcomes. If congestion increases after 5 simultaneous changes,
which caused it? Cannot revert individually.
**Instead:** Tune one category per cycle, or limit to N changes per cycle with max_step_pct.

### Anti-Pattern 3: YAML File Mutation
**What:** Writing tuned values to `/etc/wanctl/spectrum.yaml`.
**Why bad:** Operator loses visibility. SIGUSR1 becomes circular. Config drift.
**Instead:** Runtime-only. YAML remains operator truth. Future `wanctl-tune export` CLI.

### Anti-Pattern 4: Unbounded Exploration
**What:** Allowing parameters to reach their full mathematical range.
**Why bad:** Hampel sigma 0.1 flags everything as outlier. Alpha 0.99 reacts to noise.
**Instead:** Tight bounds in YAML `tuning.bounds` section, narrower than Config SCHEMA ranges.

### Anti-Pattern 5: Tuning Steering Daemon
**What:** Autorate daemon tuning steering daemon parameters.
**Why bad:** Cross-process communication needed. Different cadence.
**Instead:** Only tune autorate parameters in v1.20. Steering tuning is a separate future feature.

## Suggested Build Order

### Phase 1: Foundation (models + strategies + analyzer)
- `tuning/models.py`: TuningResult, TuningConfig dataclasses
- `tuning/strategies/thresholds.py`: threshold derivation (pure functions)
- `tuning/analyzer.py`: query orchestration per WAN
- Unit tests with synthetic data (no daemon, no SQLite)
- **Depends on:** existing storage/reader.py
- **Risk:** LOW (pure computation, no runtime effect)

### Phase 2: Wiring + Application (applier + WANController + main)
- `tuning/applier.py`: bounds check, apply, persist
- WANController._apply_tuning() method
- Config._load_tuning_config() parsing
- Main loop maintenance window integration
- Ship disabled (`tuning.enabled: false`)
- **Depends on:** Phase 1
- **Risk:** LOW (disabled by default)

### Phase 3: Observability + SIGUSR1 (health + reload + schema)
- Health endpoint `tuning` section
- _reload_tuning_config() in SIGUSR1 chain
- tuning_params SQLite table
- Example config updates
- **Depends on:** Phase 2
- **Risk:** LOW (extends proven patterns)

### Phase 4: Signal Param Strategies + Revert Safety
- `tuning/strategies/signal_params.py`: Hampel sigma, EWMA alpha derivation
- Automatic revert if congestion increases post-tuning
- **Depends on:** Phase 3
- **Risk:** LOW (extends Phase 1 pattern)

### Phase 5: Graduation
- Enable on Spectrum via YAML + SIGUSR1
- Monitor 24-48h
- Validate recommendations are reasonable
- Enable on ATT
- **Depends on:** Phase 4
- **Risk:** MEDIUM (first production behavioral change)

## Scalability Considerations

| Concern | Current (2 WANs) | At 4 WANs | At 10 WANs |
|---------|------------------|-----------|------------|
| Analysis time per pass | <100ms total | <200ms | <500ms |
| SQLite read load | 1 read-only query per WAN per hour | Same pattern | May batch queries |
| tuning_params table | ~8 rows/day (few params, hourly) | ~16 rows/day | ~40 rows/day |
| Config complexity | 7 bounds in YAML | Same (portable) | Same (portable) |

## Sources

- Direct analysis: `src/wanctl/autorate_continuous.py` (WANController, QueueController, main loop, SIGUSR1 handler)
- Direct analysis: `src/wanctl/signal_processing.py` (SignalProcessor tunables)
- Direct analysis: `src/wanctl/storage/reader.py` (query_metrics read-only pattern)
- Direct analysis: `src/wanctl/storage/schema.py` (STORED_METRICS, table patterns)
- Direct analysis: `src/wanctl/storage/downsampler.py` (granularity levels for analysis input)
- Direct analysis: `src/wanctl/health_check.py` (health endpoint extension point)
- Direct analysis: `src/wanctl/signal_utils.py` (SIGUSR1 reload mechanism)
- Direct analysis: `src/wanctl/config_base.py` (BaseConfig, validate_schema, Config._load_specific_fields)
- Direct analysis: `docs/ARCHITECTURE.md` (portable controller invariants)
- [sqm-autorate](https://github.com/sqm-autorate/sqm-autorate) -- adaptive CAKE bandwidth tuning (comparable project)
- [cake-autorate](https://github.com/lynxthecat/cake-autorate) -- CAKE auto-adjustment via RTT measurement
- [EWMA Adaptive Threshold Algorithm](https://ieeexplore.ieee.org/document/4283671/) -- EWMA in adaptive threshold design
- [Adaptive EWMA Control Chart](https://www.nature.com/articles/s41598-025-09735-z) -- dynamic smoothing constant adjustment
- [Machine Learning Adaptive EWMA](https://www.nature.com/articles/s41598-024-82699-8) -- parameter-free adaptive EWMA
- [Self-tuning controller](https://en.wikipedia.org/wiki/Self-tuning) -- identifier-controller interaction risk
