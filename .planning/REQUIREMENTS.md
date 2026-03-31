# Requirements: wanctl v1.24

**Defined:** 2026-03-30
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.24 Requirements

Requirements for EWMA Boundary Hysteresis milestone. Each maps to roadmap phases.

### State Machine Hysteresis (HYST)

- [x] **HYST-01**: Controller requires N consecutive above-threshold cycles before transitioning GREEN->YELLOW (dwell timer), preventing single-cycle jitter from triggering rate clamping
- [x] **HYST-02**: Controller uses a deadband margin so YELLOW->GREEN recovery requires delta dropping below (target_bloat_ms - deadband_ms), preventing oscillation at the exact threshold boundary
- [x] **HYST-03**: Dwell counter resets to zero when delta drops below threshold, so only sustained congestion triggers YELLOW
- [x] **HYST-04**: Upload state machine applies same hysteresis logic as download (both directions protected)

### Configuration (CONF)

- [x] **CONF-01**: Hysteresis parameters (dwell_cycles, deadband_ms) configurable in YAML under `continuous_monitoring.thresholds`
- [x] **CONF-02**: SIGUSR1 hot-reload updates hysteresis parameters without service restart (consistent with existing reload pattern)
- [x] **CONF-03**: Sensible defaults that work without config changes (dwell_cycles=3, deadband_ms=3.0)

### Observability (OBSV)

- [ ] **OBSV-01**: Health endpoint exposes hysteresis state (dwell_counter, deadband_margins, transitions_suppressed count)
- [ ] **OBSV-02**: Log messages indicate when transitions are suppressed by dwell timer ("transition suppressed, dwell N/M")

### Validation (VALN)

- [ ] **VALN-01**: Production validation shows zero flapping alerts during prime-time evening window (vs 1-3 pairs/evening baseline)
- [ ] **VALN-02**: Genuine sustained congestion (RRUL stress test) still triggers YELLOW within acceptable latency (< 500ms additional detection delay)

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Prometheus/Grafana Export

- **OBSV-03**: Prometheus metrics endpoint for external TSDB scraping
- **OBSV-04**: Grafana dashboard templates for latency/throughput visualization

## Out of Scope

| Feature                                          | Reason                                                                  |
| ------------------------------------------------ | ----------------------------------------------------------------------- |
| YELLOW->RED hysteresis                           | RED transitions are already protected by sustained threshold checks     |
| Upload-specific thresholds                       | Upload uses same delta-based detection, shared hysteresis is sufficient |
| Adaptive hysteresis (auto-tuning dwell/deadband) | Premature -- fixed values need production validation first              |
| Rate ramp smoothing                              | Separate concern from state transition hysteresis, future milestone     |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase     | Status   |
| ----------- | --------- | -------- |
| HYST-01     | Phase 121 | Complete |
| HYST-02     | Phase 121 | Complete |
| HYST-03     | Phase 121 | Complete |
| HYST-04     | Phase 121 | Complete |
| CONF-01     | Phase 122 | Complete |
| CONF-02     | Phase 122 | Complete |
| CONF-03     | Phase 122 | Complete |
| OBSV-01     | Phase 123 | Pending  |
| OBSV-02     | Phase 123 | Pending  |
| VALN-01     | Phase 124 | Pending  |
| VALN-02     | Phase 124 | Pending  |

**Coverage:**

- v1.24 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---

_Requirements defined: 2026-03-30_
_Last updated: 2026-03-30 after roadmap creation_
