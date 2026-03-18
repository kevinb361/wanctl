# Feature Landscape: v1.20 Adaptive Tuning

**Domain:** Self-optimizing network congestion controller
**Researched:** 2026-03-18

## Table Stakes

Features expected for a self-tuning controller. Missing = tuning feels broken or unsafe.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-WAN parameter optimization | Each WAN has different RTT characteristics (Spectrum 37ms, ATT 29ms) | Med | Reuses existing per-WAN architecture pattern |
| Safety bounds on all parameters | Production network -- unbounded tuning could cause outages | Low | Simple min/max clamping in YAML config |
| Ships disabled by default | Proven graduation pattern (v1.11, v1.13, v1.19) | Low | `tuning.enabled: false` in YAML |
| Tuning decision logging | Operators must understand WHY parameters changed | Low | WARNING-level log with old/new/rationale |
| Revert capability | Must undo bad parameter changes automatically | Med | Detect congestion rate increase, restore previous values |
| Enable/disable via SIGUSR1 | Zero-downtime toggle, consistent with existing features | Low | Extends existing SIGUSR1 chain |
| Health endpoint tuning section | Consistent with signal_quality, fusion, alerting sections | Low | JSON response with current parameters and last adjustment |
| Minimum data requirement | Cannot tune on insufficient data (startup, fresh deploy) | Low | Skip tuning if < 1 hour of metrics |
| Parameter persistence | Track tuning history for operator review | Low | New SQLite table, follows alerts/benchmarks pattern |

## Differentiators

Features that make the tuning system genuinely valuable rather than just present.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Percentile-based threshold calibration | Congestion thresholds derived from actual RTT distribution, not manual guessing | Med | Core value: p75/p90 of delta distribution maps directly to GREEN/YELLOW/RED thresholds |
| Signal quality auto-tuning | Hampel sigma/window optimized for each WAN's noise profile | Med | Spectrum has 14% outlier rate vs ATT 0% -- different parameters needed |
| Fusion weight adaptation | ICMP/IRTT weight adjusted based on which signal is more reliable per WAN | Med | ATT protocol correlation 0.65 suggests different weighting than Spectrum |
| Convergence detection | Automatically stops adjusting when parameters stabilize | Low | Coefficient of variation < threshold |
| Diurnal awareness | Use 24h lookback to capture full daily pattern | Low | Night (low load) vs evening (peak) have different RTT distributions |
| Conservative rate limiting | Max 10% parameter change per cycle, slow convergence | Low | Prevents oscillation, builds confidence gradually |
| Tuning rationale strings | Each adjustment includes human-readable explanation | Low | "target_bloat_ms: 15.0 -> 13.2 (p75 of clean RTT delta = 13.2ms, 24h data)" |

## Anti-Features

Features to explicitly NOT build. Each would add complexity without proportional value.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Machine learning parameter prediction | Requires training data, model management, prediction uncertainty. 6-8 scalar parameters do not justify ML. | Percentile-based statistical derivation -- deterministic, interpretable, verifiable |
| Real-time (per-cycle) parameter adjustment | Would cause oscillation. Parameters should be stable for hours, not changing every 50ms. | Hourly analysis cadence, piggyback on existing maintenance window |
| Cross-WAN parameter sharing | Each WAN has different ISP, latency profile, and noise characteristics | Independent per-WAN tuning with independent bounds |
| Automatic ceiling/floor adjustment | Bandwidth ceilings are ISP plan limits -- cannot be derived from RTT data | Keep ceiling/floor as manual YAML config. Only tune signal processing and thresholds. |
| Global optimization of all parameters simultaneously | Correlated parameter changes are hard to attribute. Difficult to revert. | Tune one parameter category per cycle, round-robin across categories |
| Tuning dashboard widget | Dashboard is read-only poller. Tuning runs inside the daemon. | Expose tuning state via health endpoint; dashboard shows it via existing poller |
| Tuning CLI tool | Parameters are derived from data, not manually set. CLI adds complexity for no value. | `wanctl-history --tuning` for reviewing past adjustments (extend existing CLI) |
| Automatic reflector list management | Adding/removing reflectors changes measurement topology. Too risky for auto-tuning. | Only tune reflector min_score threshold and window_size, not the host list |

## Feature Dependencies

```
tuning.enabled config -> ParameterAnalyzer can run
    |
    v
Historical metrics (>= 1h) -> ParameterAnalyzer produces TuningResults
    |
    v
TuningResult validation -> ParameterApplier enforces bounds
    |
    v
Parameter application -> WANController attributes updated
    |
    v
Persistence (SQLite tuning_params) -> Revert capability
    |
    v
Health endpoint tuning section -> Operator visibility
    |
    v
SIGUSR1 enable/disable -> Zero-downtime control
```

Critical dependency chain:
- Signal processing metrics (v1.18) MUST exist in SQLite before tuning can analyze them
- Fusion metrics (v1.19 fused_rtt, load_ewma) MUST be persisted for fusion weight tuning
- Tuning MUST run AFTER the existing hourly maintenance (cleanup/downsample) to analyze fresh aggregates

## MVP Recommendation

### Phase 1: Foundation + Threshold Tuning
Build the framework and tune the highest-impact parameters first.

1. **Tuning framework** (analyzer, applier, models, config, enable/disable, health endpoint, SQLite table)
2. **Congestion threshold calibration** (target_bloat_ms, warn_bloat_ms from RTT delta percentiles)
3. **Revert detection** (monitor congestion rate after parameter change, auto-revert if degraded)

Rationale: Congestion thresholds have the highest impact on controller behavior and are the simplest to derive from percentile analysis. Framework enables all subsequent tuning.

### Phase 2: Signal Processing Tuning
Tune the measurement pipeline that feeds the controller.

4. **Hampel sigma/window tuning** (target outlier rate range, autocorrelation-based window sizing)
5. **EWMA alpha tuning** (load time constant from settling time analysis, baseline alpha from drift rate)

Rationale: Signal processing parameters affect measurement quality. Requires Phase 1 framework.

### Phase 3: Advanced Parameter Tuning
Tune cross-signal and scoring parameters.

6. **Fusion weight adaptation** (ICMP vs IRTT reliability scoring)
7. **Reflector scoring bounds** (min_score from observed success rate distribution)
8. **Baseline RTT bounds auto-adjustment** (p5/p95 of observed baseline)

Rationale: These parameters have lower impact individually but collectively refine the system. Depend on Phase 1+2 being stable.

### Defer

- **Upload-specific tuning**: Upload uses 3-state (not 4-state) model. Tune download first, apply learnings to upload.
- **Steering daemon tuning**: Steering confidence weights are in a different daemon. Tune autorate first.
- **OWD asymmetry threshold tuning**: ratio_threshold has limited impact and few data points (IRTT runs at 0.1Hz).

## Sources

- Codebase analysis: autorate_continuous.py Config class, WANController.__init__, signal_processing.py, reflector_scorer.py
- Production data: Spectrum 14% outlier rate vs ATT 0% (from MEMORY.md)
- Production data: ATT IRTT correlation 0.65 (path asymmetry, from MEMORY.md)
- [BBR congestion control](https://queue.acm.org/detail.cfm?id=3022184) -- percentile-based parameter derivation pattern
- [CoDel AQM](https://queue.acm.org/detail.cfm?id=2209336) -- adaptive threshold approach
