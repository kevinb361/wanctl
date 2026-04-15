# Requirements: wanctl

**Defined:** 2026-04-15
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.38 Requirements

### Measurement Integrity

- [ ] **MEAS-01**: Autorate exposes current reflector measurement quorum in a machine-readable form that distinguishes 3/2/1/0 successful reflectors.
- [x] **MEAS-02**: A background RTT cycle with zero successful reflectors does not continue to present the last cached RTT as a healthy current measurement.
- [ ] **MEAS-03**: Autorate `/health` explicitly surfaces degraded measurement quality when current reflector success is insufficient or current RTT data is stale.
- [ ] **MEAS-04**: Operator-visible health data makes current reflector availability and measurement staleness easy to correlate with live latency behavior.

### Control Safety

- [x] **SAFE-01**: When measurement quality degrades, controller behavior follows explicit bounded semantics instead of silently acting on stale RTT as if it were current.
- [ ] **SAFE-02**: Existing ICMP failure fallback and total-connectivity-loss handling remain intact for real outages and do not regress while adding measurement-degradation handling.

### Verification And Operations

- [ ] **OPER-01**: Operators have a documented bounded procedure to reproduce and inspect measurement degradation during `tcp_12down`.
- [ ] **VALN-01**: Regression coverage proves zero-success, reduced-quorum, and degraded-measurement health behavior without changing core congestion thresholds.

## v2 Requirements

### Follow-on

- **ALRT-01**: Add a dedicated alert path for sustained measurement-quality collapse if the v1.38 operator surfaces prove too passive.
- **ANLY-01**: Add richer historical reporting for reflector-collapse episodes if v1.38 confirms the need for longer-term correlation analysis.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Retuning CAKE congestion thresholds | The live investigation points to measurement resilience first, not threshold semantics |
| Reworking steering policy or WAN selection | Steering stayed healthy during the reproduced failure and is not the lead suspect |
| Generic observability refactor across all health endpoints | This milestone is scoped to the production measurement-collapse gap |
| New transport or reflector architecture | Too large for the first corrective milestone; start by making current behavior explicit and safe |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MEAS-01 | Phase 186 | Pending |
| MEAS-02 | Phase 187 | Complete |
| MEAS-03 | Phase 186 | Pending |
| MEAS-04 | Phase 188 | Pending |
| SAFE-01 | Phase 187 | Complete |
| SAFE-02 | Phase 187 | Pending |
| OPER-01 | Phase 188 | Pending |
| VALN-01 | Phase 188 | Pending |

**Coverage:**
- v1.38 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0

---
*Requirements defined: 2026-04-15*
*Last updated: 2026-04-15 after starting v1.38 milestone*
