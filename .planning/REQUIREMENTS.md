# Requirements: wanctl v1.33

**Defined:** 2026-04-10
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.33 Requirements

Requirements for Detection Threshold Tuning milestone. A/B validate v1.32 CAKE detection parameters on the live linux-cake system.

### Pre-Test Gate

- [ ] **VALID-02**: Baseline drop rate and backlog measured at idle for 24h before any tuning begins

### Detection Thresholds

- [ ] **THRESH-01**: drop_rate_threshold is A/B tested against alternatives under RRUL and confirmed or updated
- [ ] **THRESH-02**: backlog_threshold_bytes is A/B tested against alternatives under RRUL and confirmed or updated
- [ ] **THRESH-03**: refractory_cycles is A/B tested (20, 40, 60 cycles) under RRUL and confirmed or updated

### Recovery Tuning

- [ ] **RECOV-04**: probe_multiplier_factor is A/B tested (1.0, 1.5, 2.0) under RRUL and confirmed or updated
- [ ] **RECOV-05**: probe_ceiling_pct is A/B tested (0.85, 0.9, 0.95) under RRUL and confirmed or updated

### Validation

- [ ] **VALID-01**: All parameter changes deployed and stable in production for 24h soak

### Storage Observability And DB Decision

- [x] **PH165-OBS-01**: Shared SQLite writer paths record bounded in-memory contention telemetry for write duration, success, and lock-failure outcomes without changing existing commit/rollback behavior
- [x] **PH165-OBS-02**: Autorate deferred queue pressure, steering direct-write volume, and maintenance/checkpoint contention signals are observable without writing telemetry back into SQLite
- [x] **PH165-OBS-03**: Autorate and steering operator surfaces expose storage contention status with stable, bounded payload fields and low-overhead Prometheus-style metrics
- [x] **PH165-DEC-04**: A tested decision helper/report classifies measured results into keep shared DB, reduce write pressure further, or plan split DBs later, with no migration performed unless that gate is explicitly reached

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| VALID-02 | 162 | Pending |
| THRESH-01 | 163 | Pending |
| THRESH-02 | 163 | Pending |
| THRESH-03 | 163 | Pending |
| RECOV-04 | 163 | Pending |
| RECOV-05 | 163 | Pending |
| VALID-01 | 164 | Pending |
| PH165-OBS-01 | 165 | Complete |
| PH165-OBS-02 | 165 | Complete |
| PH165-OBS-03 | 165 | Complete |
| PH165-DEC-04 | 165 | Complete |

## Out of Scope

- Per-direction threshold tuning (DL vs UL separate thresholds) — measure first, tune only if data shows need
- Time-of-day tuning segmentation — independent feature, defer to v1.34
- Peak delay threshold tuning — peak_delay is disabled, not yet integrated into detection
- Backlog-per-tin thresholds — current aggregate is sufficient until data shows otherwise
