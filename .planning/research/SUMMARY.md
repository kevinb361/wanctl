# Research Summary: v1.20 Adaptive Tuning

**Domain:** Self-optimizing parameter tuning for dual-WAN CAKE controller
**Researched:** 2026-03-18
**Overall confidence:** HIGH

## Executive Summary

Adaptive tuning for wanctl v1.20 is a statistical analysis problem, not a machine learning or optimization problem. The system already possesses all the infrastructure needed: 24+ hours of per-WAN metrics in SQLite at multiple granularities, Python 3.12 stdlib statistics module with quantiles/median/stdev/NormalDist, proven SIGUSR1 hot-reload pattern, and embedded-in-daemon component architecture. Zero new Python dependencies are needed.

The core algorithm is percentile-based parameter derivation: query historical RTT delta distributions from SQLite, compute p75/p90 percentiles via `statistics.quantiles()`, map percentiles to congestion thresholds, and clamp to YAML-defined safety bounds. This follows the same approach used in network congestion control (BBR uses percentile-based BtlBw/RTprop estimation; CoDel uses adaptive interval/target thresholds). The approach is deterministic, interpretable, and trivially testable with synthetic data.

The primary risk is feedback oscillation (identifier-controller interaction): changing parameters changes the metrics used to derive parameters. This is mitigated by slow cadence (hourly), small steps (10% max change), round-robin across parameter categories, convergence detection, and automatic revert on degradation. All mitigation strategies are simple arithmetic -- no complex control theory needed.

The feature set spans 6-8 tunable parameter categories across signal processing (Hampel sigma/window, EWMA alphas), congestion control (GREEN/YELLOW/RED thresholds), and cross-signal parameters (fusion weights, reflector scoring bounds, baseline RTT bounds). Each parameter has a dedicated strategy function -- a pure function from metrics data to TuningResult -- making the system highly modular and independently testable.

## Key Findings

**Stack:** Zero new dependencies. Python stdlib `statistics` + existing SQLite infrastructure provide everything needed.
**Architecture:** Embedded analyzer/applier in autorate daemon, piggyback on hourly maintenance window, SIGUSR1 enable/disable.
**Critical pitfall:** Feedback oscillation from identifier-controller interaction -- mitigated by slow cadence, small steps, and round-robin tuning.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Tuning Foundation** - Framework, models, config, enable/disable, health endpoint, SQLite schema
   - Addresses: Table stakes (ships disabled, safety bounds, SIGUSR1, persistence)
   - Avoids: Pitfall 5 (MagicMock trap), Pitfall 8 (tight bounds)
   - Standard patterns, unlikely to need deeper research

2. **Congestion Threshold Calibration** - target_bloat_ms, warn_bloat_ms from RTT delta percentiles
   - Addresses: Highest-impact differentiator (percentile-based threshold derivation)
   - Avoids: Pitfall 1 (oscillation) via max_change_pct, Pitfall 2 (insufficient data) via min_data_hours
   - Needs careful design of state-filtered analysis (GREEN-only data for threshold derivation)

3. **Revert Detection** - Monitor congestion rate post-adjustment, auto-revert on degradation
   - Addresses: Table stake (revert capability)
   - Avoids: Pitfall 7 (revert oscillation) via hysteresis lock
   - Needs precise definition of "congestion rate" metric

4. **Signal Processing Tuning** - Hampel sigma/window, EWMA alpha optimization
   - Addresses: Key differentiator (per-WAN noise profile tuning)
   - Avoids: Pitfall 3 (feedback loop) via target-based tuning with settling period
   - Needs deeper research on target outlier rate selection

5. **Advanced Tuning** - Fusion weights, reflector scoring, baseline bounds
   - Addresses: Remaining differentiators
   - Avoids: Pitfall 9 (cross-WAN contamination) via independent per-WAN analysis
   - Lower impact individually, can be deferred if earlier phases take longer

**Phase ordering rationale:**
- Foundation (1) must come first -- all other phases build on the framework
- Threshold calibration (2) before signal processing tuning (4) because thresholds have higher impact and simpler derivation
- Revert detection (3) must exist before signal processing tuning (4) because signal processing parameter changes are harder to evaluate
- Advanced tuning (5) depends on all prior phases being stable

**Research flags for phases:**
- Phase 2: Needs careful design of state-filtering (which GREEN-period metrics to use)
- Phase 3: Needs precise definition of "congestion rate increase" -- which metric(s), what time window
- Phase 4: May need phase-specific research on target outlier rate and settling time
- Phases 1, 5: Standard patterns, unlikely to need research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (zero new deps) | HIGH | Verified: statistics.quantiles(), NormalDist in Python 3.8+ stdlib |
| Features | HIGH | Clear parameter categories with known statistical derivation methods |
| Architecture | HIGH | Extends 4 proven patterns (alerting, fusion, signal processing, wan_state) |
| Pitfalls | HIGH | Identifier-controller interaction is well-documented in control theory literature |
| Threshold calibration | HIGH | Percentile-based approach used in BBR, CoDel |
| Signal processing tuning | MEDIUM | Target outlier rate selection is empirical, not theoretically derived |
| Revert logic | MEDIUM | Defining "congestion rate increase" requires careful metric selection |

## Gaps to Address

- **Target outlier rate for Hampel**: Research suggests 5-15% range but optimal rate for this system is empirical. May need experimentation during Phase 4.
- **Revert metric definition**: "Congestion rate" could mean state transitions per hour, time in RED, or average congestion delta. Needs decision during Phase 3 planning.
- **Baseline RTT bounds lookback**: 24h may be insufficient for baseline bounds (ISP maintenance is weekly). Consider 7-day lookback for this specific parameter.
- **Upload tuning**: Upload uses 3-state model (not 4-state). Threshold derivation needs adaptation. Deferred to after download tuning is proven.
