# Requirements: wanctl

**Defined:** 2026-04-02
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.27 Requirements

Requirements for v1.27 Performance & QoS milestone. Each maps to roadmap phases.

### Cycle Budget (PERF)

- [x] **PERF-01**: Operator can identify which subsystems consume the most cycle time under RRUL load via profiling instrumentation
- [x] **PERF-02**: Controller maintains cycle budget within target interval under sustained RRUL load (optimize hot path or adjust interval)
- [x] **PERF-03**: Health endpoint exposes cycle budget regression indicator that warns when utilization exceeds configurable threshold

### QoS / Diffserv (QOS)

- [ ] **QOS-01**: Operator can verify whether DSCP marks survive the L2 bridge path from MikroTik mangle to CAKE tins
- [ ] **QOS-02**: CAKE tins correctly separate traffic by DSCP class so EF/CS5 traffic gets lower latency than BE/BK
- [ ] **QOS-03**: `wanctl-check-cake` validates DSCP mark survival through the bridge path as an automated check

### Upload Tuning (TUNE)

- [ ] **TUNE-01**: UL step_up and factor_down A/B tested on linux-cake transport via RRUL flent with documented results
- [ ] **TUNE-02**: Winning UL parameters deployed to production config with validation dates

### Hysteresis Monitoring (HYST)

- [x] **HYST-01**: Health endpoint exposes per-minute suppression rate with windowed counters
- [x] **HYST-02**: Controller logs periodic suppression rate at INFO level during active congestion events
- [ ] **HYST-03**: AlertEngine fires Discord alert when suppression rate exceeds configurable threshold (potential false negative detection)

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Infrastructure

- **INFRA-01**: Prometheus/Grafana metrics export (infrastructure not yet deployed, deferred from v1.23)

### Tuning

- **TUNE-03**: RRUL A/B tuning sweep for ATT WAN (deferred from v1.26 todo)

### Testing

- **TEST-01**: Integration test for router communication (deferred from v1.23 todo)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Adaptive cycle interval (auto-adjust) | Adds complexity; manual decision after profiling is safer |
| Multi-reflector DSCP testing | Single bridge path audit is sufficient for v1.27 |
| ATT WAN tuning sweep | Focus on Spectrum; ATT deferred to future milestone |
| Machine learning bandwidth prediction | Unnecessary complexity |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PERF-01 | Phase 131 | Complete |
| PERF-02 | Phase 132 | Complete |
| PERF-03 | Phase 132 | Complete |
| QOS-01 | Phase 133 | Pending |
| QOS-02 | Phase 134 | Pending |
| QOS-03 | Phase 134 | Pending |
| TUNE-01 | Phase 135 | Pending |
| TUNE-02 | Phase 135 | Pending |
| HYST-01 | Phase 136 | Complete |
| HYST-02 | Phase 136 | Complete |
| HYST-03 | Phase 136 | Pending |

**Coverage:**
- v1.27 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---
*Requirements defined: 2026-04-02*
*Last updated: 2026-04-02 after roadmap creation*
