# Requirements: wanctl v1.20 Adaptive Tuning

**Defined:** 2026-03-18
**Core Value:** Self-optimizing controller that learns optimal parameters from production metrics

## v1.20 Requirements

Requirements for adaptive parameter tuning. Each maps to roadmap phases.

### Tuning Framework

- [x] **TUNE-01**: Tuning engine ships disabled by default (`tuning.enabled: false` in YAML)
- [x] **TUNE-02**: Tuning can be enabled/disabled via SIGUSR1 without daemon restart
- [x] **TUNE-03**: Each tunable parameter has configurable min/max safety bounds in YAML
- [x] **TUNE-04**: Tuning analyzes per-WAN metrics independently with no cross-WAN contamination
- [x] **TUNE-05**: Tuning decisions logged with old value, new value, and human-readable rationale
- [x] **TUNE-06**: Health endpoint exposes tuning section (enabled, last_run, parameters, adjustments)
- [x] **TUNE-07**: Tuning skips analysis when less than 1 hour of metrics data available
- [x] **TUNE-08**: Tuning adjustments persisted to SQLite for historical review
- [x] **TUNE-09**: Tuning runs during hourly maintenance window (not per-cycle)
- [x] **TUNE-10**: Maximum 10% parameter change per tuning cycle enforced

### Congestion Calibration

- [x] **CALI-01**: `target_bloat_ms` derived from p75 of GREEN-state RTT delta distribution
- [x] **CALI-02**: `warn_bloat_ms` derived from p90 of GREEN-state RTT delta distribution
- [x] **CALI-03**: Convergence detection stops adjusting when parameter coefficient of variation drops below threshold
- [x] **CALI-04**: 24h lookback window captures full diurnal pattern for threshold derivation

### Safety & Revert

- [x] **SAFE-01**: System monitors congestion rate after each parameter adjustment
- [x] **SAFE-02**: Automatic revert to previous values when post-adjustment congestion rate increases
- [x] **SAFE-03**: Hysteresis lock prevents revert oscillation (revert freezes category for configurable cooldown)

### Signal Processing Tuning

- [x] **SIGP-01**: Hampel sigma optimized per-WAN based on outlier rate analysis
- [x] **SIGP-02**: Hampel window size optimized per-WAN based on autocorrelation analysis
- [x] **SIGP-03**: Load EWMA alpha tuned from settling time analysis
- [x] **SIGP-04**: Signal chain tuned bottom-up (signal processing -> EWMA -> thresholds), one layer per cycle

### Advanced Tuning

- [ ] **ADVT-01**: Fusion ICMP/IRTT weight adapted based on per-signal reliability scoring
- [ ] **ADVT-02**: Reflector min_score threshold tuned from observed success rate distribution
- [ ] **ADVT-03**: Baseline RTT bounds auto-adjusted from p5/p95 of observed baseline history
- [ ] **ADVT-04**: `wanctl-history --tuning` displays tuning adjustment history with time-range filtering

## Future Requirements

Deferred to subsequent milestones. Tracked but not in current roadmap.

### Upload-Specific Tuning

- **UPLD-01**: Upload 3-state model threshold calibration (adapted from download 4-state approach)
- **UPLD-02**: Upload-specific EWMA alpha tuning

### Steering Daemon Tuning

- **STRD-01**: Confidence weight auto-tuning in steering daemon
- **STRD-02**: Steer_threshold calibration from steering decision accuracy

### Cross-Signal

- **XSIG-01**: OWD asymmetry ratio_threshold tuning from IRTT data (limited by 0.1Hz cadence)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| ML/scipy/numpy parameter prediction | 6-8 scalar params don't justify ML complexity; percentile stats sufficient |
| Per-cycle parameter adjustment | Would cause oscillation; hourly cadence is safety requirement |
| Cross-WAN parameter sharing | Each WAN has different ISP, latency profile, and noise characteristics |
| Automatic ceiling/floor adjustment | Bandwidth ceilings are ISP plan limits, not derivable from RTT data |
| Simultaneous multi-parameter optimization | Correlated changes hard to attribute; round-robin one category at a time |
| Reflector list management | Adding/removing reflectors changes measurement topology; too risky |
| Dedicated tuning dashboard widget | Dashboard is read-only poller; expose via health endpoint instead |
| Dedicated tuning CLI tool | Parameters derived from data; `wanctl-history --tuning` covers review |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TUNE-01 | Phase 98 | Complete |
| TUNE-02 | Phase 98 | Complete |
| TUNE-03 | Phase 98 | Complete |
| TUNE-04 | Phase 98 | Complete |
| TUNE-05 | Phase 98 | Complete |
| TUNE-06 | Phase 98 | Complete |
| TUNE-07 | Phase 98 | Complete |
| TUNE-08 | Phase 98 | Complete |
| TUNE-09 | Phase 98 | Complete |
| TUNE-10 | Phase 98 | Complete |
| CALI-01 | Phase 99 | Complete |
| CALI-02 | Phase 99 | Complete |
| CALI-03 | Phase 99 | Complete |
| CALI-04 | Phase 99 | Complete |
| SAFE-01 | Phase 100 | Complete |
| SAFE-02 | Phase 100 | Complete |
| SAFE-03 | Phase 100 | Complete |
| SIGP-01 | Phase 101 | Complete |
| SIGP-02 | Phase 101 | Complete |
| SIGP-03 | Phase 101 | Complete |
| SIGP-04 | Phase 101 | Complete |
| ADVT-01 | Phase 102 | Pending |
| ADVT-02 | Phase 102 | Pending |
| ADVT-03 | Phase 102 | Pending |
| ADVT-04 | Phase 102 | Pending |

**Coverage:**
- v1.20 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after roadmap creation*
