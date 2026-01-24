# Requirements: wanctl v1.4

**Defined:** 2026-01-23
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.4 Requirements

Requirements for steering daemon observability. Each maps to roadmap phases.

### Health Endpoint

- [ ] **HLTH-01**: Steering daemon exposes HTTP health endpoint on port 9102
- [ ] **HLTH-02**: Health endpoint responds to GET / and GET /health
- [ ] **HLTH-03**: Response is JSON with status, uptime_seconds, version fields
- [ ] **HLTH-04**: Returns 200 OK when healthy, 503 Service Unavailable when degraded
- [ ] **HLTH-05**: Health server runs in background thread (daemon=True)
- [ ] **HLTH-06**: Health server supports clean shutdown

### Steering State

- [ ] **STEER-01**: Health response includes current steering state (enabled/disabled)
- [ ] **STEER-02**: Health response includes confidence scores from ConfidenceController
- [ ] **STEER-03**: Health response includes primary WAN congestion state
- [ ] **STEER-04**: Health response includes secondary WAN congestion state
- [ ] **STEER-05**: Health response includes last decision timestamp

### Integration

- [ ] **INTG-01**: Health server starts during steering daemon initialization
- [ ] **INTG-02**: Health server stops during steering daemon shutdown
- [ ] **INTG-03**: Health status updates reflect current daemon state

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Metrics History

- **METR-01**: Rolling window of recent measurements
- **METR-02**: Historical steering decisions log
- **METR-03**: Prometheus-compatible /metrics endpoint

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Prometheus integration | Keep self-contained, no external dependencies |
| WebSocket streaming | Complexity, polling sufficient |
| Authentication | Internal network only, localhost binding |
| Config reload via API | Config is file-based, restart to reload |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| HLTH-01 | TBD | Pending |
| HLTH-02 | TBD | Pending |
| HLTH-03 | TBD | Pending |
| HLTH-04 | TBD | Pending |
| HLTH-05 | TBD | Pending |
| HLTH-06 | TBD | Pending |
| STEER-01 | TBD | Pending |
| STEER-02 | TBD | Pending |
| STEER-03 | TBD | Pending |
| STEER-04 | TBD | Pending |
| STEER-05 | TBD | Pending |
| INTG-01 | TBD | Pending |
| INTG-02 | TBD | Pending |
| INTG-03 | TBD | Pending |

**Coverage:**
- v1.4 requirements: 14 total
- Mapped to phases: 0
- Unmapped: 14 ⚠️

---
*Requirements defined: 2026-01-23*
*Last updated: 2026-01-23 after initial definition*
