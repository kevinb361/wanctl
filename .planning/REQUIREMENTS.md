# Requirements: wanctl v1.3

**Defined:** 2026-01-21
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.3 Requirements

Requirements for v1.3 Reliability & Hardening. Derived from CONCERNS.md analysis.

### Critical Safety Tests

- [x] **TEST-01**: Baseline RTT remains frozen during sustained load (delta > 3ms threshold)
- [x] **TEST-02**: State file corruption recovery handles partial JSON writes gracefully
- [x] **TEST-03**: REST API failure triggers automatic SSH transport failover

### Deployment Safety

- [x] **DEPLOY-01**: Rename `configs/steering_config.yaml` -> `configs/steering.yaml`
- [x] **DEPLOY-02**: Deploy script fails fast when production config is missing
- [x] **DEPLOY-03**: Deployment validation script checks state files, queues, router reachability

### Edge Case Tests

- [x] **TEST-04**: Rate limiter handles rapid daemon restarts without burst exceeding limit
- [x] **TEST-05**: Dual fallback failure (ICMP + TCP) returns safe defaults, not stale data

## Future Requirements

None currently. All identified items included in v1.3.

## Out of Scope

| Feature                         | Reason                                             |
| ------------------------------- | -------------------------------------------------- |
| Steering daemon health endpoint | Lower priority than test coverage (v1.4 candidate) |
| Multi-site deployment patterns  | Not needed for single-site production              |
| Config template automation      | Manual deployment working, low ROI                 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase    | Status   |
| ----------- | -------- | -------- |
| TEST-01     | Phase 21 | Complete |
| TEST-02     | Phase 21 | Complete |
| TEST-03     | Phase 21 | Complete |
| DEPLOY-01   | Phase 22 | Complete |
| DEPLOY-02   | Phase 22 | Complete |
| DEPLOY-03   | Phase 22 | Complete |
| TEST-04     | Phase 23 | Complete |
| TEST-05     | Phase 23 | Complete |

**Coverage:**

- v1.3 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0

---

_Requirements defined: 2026-01-21_
_Last updated: 2026-01-21 after Phase 23 completion_
