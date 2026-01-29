# Requirements: wanctl

**Defined:** 2026-01-29
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.8 Requirements

Requirements for Resilience & Robustness milestone. Each maps to roadmap phases.

### Error Recovery

- [x] **ERRR-01**: Controller detects and handles router becoming unreachable mid-cycle
- [x] **ERRR-02**: Controller handles SSH/REST connection drops gracefully with reconnection
- [x] **ERRR-03**: Rate limits are never removed on error (fail-safe/fail-closed behavior)
- [x] **ERRR-04**: Watchdog doesn't restart daemon during transient failures

### Graceful Shutdown

- [ ] **SHUT-01**: SIGTERM handlers work correctly for clean daemon termination
- [ ] **SHUT-02**: In-flight router commands complete or abort cleanly without partial state
- [ ] **SHUT-03**: State files are never corrupted during shutdown
- [ ] **SHUT-04**: All router connections are closed on shutdown (no orphaned connections)

### Contract Tests

- [ ] **CNTR-01**: Document expected RouterOS REST API response format (golden files)
- [ ] **CNTR-02**: Document expected RouterOS SSH command output format (golden files)
- [ ] **CNTR-03**: Tests fail if mocks drift from documented golden file format
- [ ] **CNTR-04**: Track response format changes across RouterOS versions

## Future Requirements

None currently.

## Out of Scope

| Feature                  | Reason                                                       |
| ------------------------ | ------------------------------------------------------------ |
| Chaos engineering        | Manual fault injection sufficient for this scale             |
| Circuit breaker patterns | Existing failover client is sufficient                       |
| RouterOS CHR container   | Contract tests provide coverage without heavy infrastructure |
| VCR-style recording      | Golden files are simpler and more maintainable               |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status   |
| ----------- | ----- | -------- |
| ERRR-01     | 43    | Complete |
| ERRR-02     | 43    | Complete |
| ERRR-03     | 44    | Complete |
| ERRR-04     | 44    | Complete |
| SHUT-01     | 45    | Pending  |
| SHUT-02     | 45    | Pending  |
| SHUT-03     | 45    | Pending  |
| SHUT-04     | 45    | Pending  |
| CNTR-01     | 46    | Pending  |
| CNTR-02     | 46    | Pending  |
| CNTR-03     | 46    | Pending  |
| CNTR-04     | 46    | Pending  |

**Coverage:**

- v1.8 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---

_Requirements defined: 2026-01-29_
_Last updated: 2026-01-29 after Phase 44 completion_
