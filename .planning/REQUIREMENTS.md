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

- [x] **SHUT-01**: SIGTERM handlers work correctly for clean daemon termination
- [x] **SHUT-02**: In-flight router commands complete or abort cleanly without partial state
- [x] **SHUT-03**: State files are never corrupted during shutdown
- [x] **SHUT-04**: All router connections are closed on shutdown (no orphaned connections)

### Contract Tests (Deferred)

- [ ] **CNTR-01**: Document expected RouterOS REST API response format (golden files)
- [ ] **CNTR-02**: Document expected RouterOS SSH command output format (golden files)
- [ ] **CNTR-03**: Tests fail if mocks drift from documented golden file format
- [ ] **CNTR-04**: Track response format changes across RouterOS versions

## v1.9 Requirements

Requirements for Performance & Efficiency milestone. Target: reduce cycle utilization from 60-80% to ~40%.

### Profiling & Measurement

- [x] **PROF-01**: Operator can collect cycle-level profiling data at 50ms production interval for both autorate and steering daemons
- [x] **PROF-02**: Each cycle phase (RTT measurement, router communication, CAKE stats, state management) is individually timed with monotonic timestamps
- [ ] **PROF-03**: Cycle budget utilization (% used, overrun count, slow cycle count) is exposed via health endpoint

### Optimization

- [x] **OPTM-01**: RTT measurement hot path is optimized to reduce its contribution to cycle time
- [x] **OPTM-02**: Router communication path is optimized (batched REST calls, reduced payload, connection reuse)
- [x] **OPTM-03**: CAKE stats collection is optimized if profiling shows it as a significant contributor
- [x] **OPTM-04**: MikroTik router CPU impact under sustained load is reduced from 45% peak

### Telemetry

- [ ] **TELM-01**: Per-subsystem timing data is available in structured logs for production analysis
- [ ] **TELM-02**: Cycle budget metrics are queryable via the existing health endpoint JSON response

## Future Requirements

- [ ] CNTR-01 through CNTR-04 (Contract Tests — deferred from v1.8, no observed mock drift)

## Out of Scope

| Feature                  | Reason                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------ |
| Async I/O rewrite        | Too invasive for marginal gain; subprocess pings are the bottleneck, not Python event loop |
| 25ms cycle interval      | Target ~40% at 50ms first; 25ms can be a future milestone if needed                        |
| Chaos engineering        | Manual fault injection sufficient for this scale                                           |
| Circuit breaker patterns | Existing failover client is sufficient                                                     |
| VCR-style recording      | Golden files are simpler and more maintainable                                             |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status   |
| ----------- | ----- | -------- |
| ERRR-01     | 43    | Complete |
| ERRR-02     | 43    | Complete |
| ERRR-03     | 44    | Complete |
| ERRR-04     | 44    | Complete |
| SHUT-01     | 45    | Complete |
| SHUT-02     | 45    | Complete |
| SHUT-03     | 45    | Complete |
| SHUT-04     | 45    | Complete |
| CNTR-01     | 46    | Deferred |
| CNTR-02     | 46    | Deferred |
| CNTR-03     | 46    | Deferred |
| CNTR-04     | 46    | Deferred |
| PROF-01     | 47    | Complete |
| PROF-02     | 47    | Complete |
| PROF-03     | 49    | Pending  |
| OPTM-01     | 48    | Complete |
| OPTM-02     | 48    | Complete |
| OPTM-03     | 48    | Complete |
| OPTM-04     | 48    | Complete |
| TELM-01     | 49    | Pending  |
| TELM-02     | 49    | Pending  |

**Coverage:**

- v1.8 requirements: 12 total (8 complete, 4 deferred)
- v1.9 requirements: 9 total, mapped to 3 phases
- Unmapped: 0

---

_Requirements defined: 2026-01-29_
_Last updated: 2026-03-06 — OPTM-01/02/03/04 complete (Phase 48)_
