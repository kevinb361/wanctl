# Requirements: wanctl v1.3

**Defined:** 2026-01-21
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.3 Requirements

Requirements for v1.3 Reliability & Hardening. Derived from CONCERNS.md analysis.

### Critical Safety Tests

- [ ] **TEST-01**: Baseline RTT remains frozen during sustained load (delta > 3ms threshold)
- [ ] **TEST-02**: State file corruption recovery handles partial JSON writes gracefully
- [ ] **TEST-03**: REST API failure triggers automatic SSH transport failover

### Deployment Safety

- [ ] **DEPLOY-01**: Rename `configs/steering_config.yaml` → `configs/steering.yaml`
- [ ] **DEPLOY-02**: Deploy script fails fast when production config is missing
- [ ] **DEPLOY-03**: Deployment validation script checks state files, queues, router reachability

### Edge Case Tests

- [ ] **TEST-04**: Rate limiter handles rapid daemon restarts without burst exceeding limit
- [ ] **TEST-05**: Dual fallback failure (ICMP + TCP) returns safe defaults, not stale data

## Future Requirements

None currently. All identified items included in v1.3.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Steering daemon health endpoint | Lower priority than test coverage (v1.4 candidate) |
| Multi-site deployment patterns | Not needed for single-site production |
| Config template automation | Manual deployment working, low ROI |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-01 | TBD | Pending |
| TEST-02 | TBD | Pending |
| TEST-03 | TBD | Pending |
| DEPLOY-01 | TBD | Pending |
| DEPLOY-02 | TBD | Pending |
| DEPLOY-03 | TBD | Pending |
| TEST-04 | TBD | Pending |
| TEST-05 | TBD | Pending |

**Coverage:**
- v1.3 requirements: 8 total
- Mapped to phases: 0
- Unmapped: 8 ⚠️

---
*Requirements defined: 2026-01-21*
*Last updated: 2026-01-21 after initial definition*
