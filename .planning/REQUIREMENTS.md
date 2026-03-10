# Requirements: wanctl v1.12

**Defined:** 2026-03-10
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.12 Requirements

### Deployment Hygiene

- [ ] **DPLY-01**: Dockerfile installs all runtime dependencies from pyproject.toml (icmplib, requests, paramiko, tabulate, cryptography)
- [ ] **DPLY-02**: deploy_refactored.sh installs all runtime dependencies matching pyproject.toml
- [ ] **DPLY-03**: install.sh VERSION matches pyproject.toml version
- [ ] **DPLY-04**: pyproject.toml version updated to 1.12.0

### Dead Code Removal

- [x] **DEAD-01**: pexpect removed from production dependencies (moved to dev extras or removed entirely)
- [x] **DEAD-02**: Dead subprocess import removed from rtt_measurement.py and affected tests refactored to mock icmplib directly
- [x] **DEAD-03**: Dead timeout_total parameter removed from RTTMeasurement API and all callers updated

### Security Hardening

- [x] **SECR-01**: Router password deleted from Config object after router client construction
- [x] **SECR-02**: urllib3 InsecureRequestWarning suppression scoped to session, not process-wide
- [x] **SECR-03**: Default fallback_gateway_ip changed to empty string with disabled behavior when absent
- [x] **SECR-04**: Integration test external IP parameterized via WANCTL_TEST_HOST env var

### Fragile Area Stabilization

- [x] **FRAG-01**: Contract tests enforce autorate-steering state file schema (key path renames cause test failures)
- [x] **FRAG-02**: flap_detector.check_flapping() call-site made explicit (return value used or docstring documents side-effect contract)
- [x] **FRAG-03**: WAN-aware steering config misconfiguration logged at WARNING level (not INFO)

### Infrastructure

- [ ] **INFR-01**: RotatingFileHandler with configurable maxBytes and backupCount in setup_logging()
- [ ] **INFR-02**: Docker build validated (Dockerfile builds successfully with all dependencies)
- [ ] **INFR-03**: Config loading boilerplate extracted to BaseConfig field-declaration pattern
- [ ] **INFR-04**: cryptography package version verified on production containers (>=46.0.5)

## Future Requirements

### Deferred

- **CNTR-01**: Full contract test suite for all inter-daemon interfaces (beyond state file)
- **OPTM-04**: Cycle utilization reduced to ~40% (currently 60-80%)
- **INTG-01**: Integration tests automated with dedicated hardware

## Out of Scope

| Feature | Reason |
|---------|--------|
| Config format migration | Maintain backward compatibility per project constraint |
| MetricsWriter singleton refactor | Test-hostile but covered by existing fixtures and _reset_instance() |
| signal_utils Event refactor | Working correctly, documented as fragile but stable |
| run_cycle() decomposition | Protected by architectural spine policy |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DPLY-01 | Phase 62 | Pending |
| DPLY-02 | Phase 62 | Pending |
| DPLY-03 | Phase 62 | Pending |
| DPLY-04 | Phase 62 | Pending |
| DEAD-01 | Phase 63 | Complete |
| DEAD-02 | Phase 63 | Complete |
| DEAD-03 | Phase 63 | Complete |
| SECR-01 | Phase 64 | Complete |
| SECR-02 | Phase 64 | Complete |
| SECR-03 | Phase 64 | Complete |
| SECR-04 | Phase 64 | Complete |
| FRAG-01 | Phase 65 | Complete |
| FRAG-02 | Phase 65 | Complete |
| FRAG-03 | Phase 65 | Complete |
| INFR-01 | Phase 66 | Pending |
| INFR-02 | Phase 66 | Pending |
| INFR-03 | Phase 66 | Pending |
| INFR-04 | Phase 66 | Pending |

**Coverage:**
- v1.12 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-03-10*
*Last updated: 2026-03-10 after roadmap creation*
