# Requirements: wanctl

**Defined:** 2026-01-24
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.6 Requirements

Requirements for Test Coverage 90% milestone. Each maps to roadmap phases.

### Coverage Infrastructure

- [ ] **COV-01**: Coverage threshold set to 90% in pyproject.toml (fail_under)
- [ ] **COV-02**: `make ci` fails if coverage drops below 90%
- [ ] **COV-03**: Coverage badge updated to reflect new threshold

### Core Controller Tests

- [ ] **CORE-01**: autorate_continuous.py coverage >=90% (currently 33%)
- [ ] **CORE-02**: All main() entry point paths tested
- [ ] **CORE-03**: Signal handlers (SIGTERM, SIGHUP) tested
- [ ] **CORE-04**: Control loop state transitions tested
- [ ] **CORE-05**: Error recovery paths tested

### Steering Daemon Tests

- [ ] **STEER-01**: steering/daemon.py coverage >=90% (currently 44%)
- [ ] **STEER-02**: Daemon lifecycle (start/stop/restart) tested
- [ ] **STEER-03**: Routing decision logic tested
- [ ] **STEER-04**: Confidence-based steering paths tested
- [ ] **STEER-05**: Congestion assessment integration tested

### CLI Tool Tests

- [ ] **CLI-01**: calibrate.py coverage >=90% (currently 0%)
- [ ] **CLI-02**: Calibration workflow tested end-to-end
- [ ] **CLI-03**: perf_profiler.py coverage >=90% (currently 0%)
- [ ] **CLI-04**: CLI argument parsing tested

### Backend Client Tests

- [ ] **BACK-01**: routeros_rest.py coverage >=90% (currently 9%)
- [ ] **BACK-02**: REST API request/response handling tested
- [ ] **BACK-03**: routeros_ssh.py coverage >=90% (currently 18%)
- [ ] **BACK-04**: SSH command execution tested
- [ ] **BACK-05**: backends/base.py coverage >=90% (currently 0%)
- [ ] **BACK-06**: Backend factory and abstract methods tested

### State Management Tests

- [ ] **STATE-01**: state_manager.py coverage >=90% (currently 39%)
- [ ] **STATE-02**: State persistence (save/load) tested
- [ ] **STATE-03**: Concurrent access and locking tested
- [ ] **STATE-04**: Corruption recovery tested

### Metrics & Measurement Tests

- [ ] **MEAS-01**: metrics.py coverage >=90% (currently 26%)
- [ ] **MEAS-02**: Metrics collection and reporting tested
- [ ] **MEAS-03**: steering/cake_stats.py coverage >=90% (currently 24%)
- [ ] **MEAS-04**: CAKE statistics parsing tested
- [ ] **MEAS-05**: rtt_measurement.py coverage >=90% (currently 67%)
- [ ] **MEAS-06**: RTT measurement edge cases tested

### Infrastructure Tests

- [ ] **INFRA-01**: error_handling.py coverage >=90% (currently 21%)
- [ ] **INFRA-02**: Error escalation and recovery tested
- [ ] **INFRA-03**: signal_utils.py coverage >=90% (currently 50%)
- [ ] **INFRA-04**: systemd_utils.py coverage >=90% (currently 33%)
- [ ] **INFRA-05**: path_utils.py coverage >=90% (currently 71%)

## Future Requirements

None currently.

## Out of Scope

| Feature | Reason |
|---------|--------|
| 100% coverage | Diminishing returns, 90% is comprehensive |
| Integration tests with real router | Requires hardware, unit tests sufficient |
| Performance benchmarks in CI | Not coverage-related, separate concern |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| COV-01 | Phase 31 | Pending |
| COV-02 | Phase 31 | Pending |
| COV-03 | Phase 31 | Pending |
| CORE-01 | Phase 35 | Pending |
| CORE-02 | Phase 35 | Pending |
| CORE-03 | Phase 35 | Pending |
| CORE-04 | Phase 35 | Pending |
| CORE-05 | Phase 35 | Pending |
| STEER-01 | Phase 36 | Pending |
| STEER-02 | Phase 36 | Pending |
| STEER-03 | Phase 36 | Pending |
| STEER-04 | Phase 36 | Pending |
| STEER-05 | Phase 36 | Pending |
| CLI-01 | Phase 37 | Pending |
| CLI-02 | Phase 37 | Pending |
| CLI-03 | Phase 37 | Pending |
| CLI-04 | Phase 37 | Pending |
| BACK-01 | Phase 32 | Pending |
| BACK-02 | Phase 32 | Pending |
| BACK-03 | Phase 32 | Pending |
| BACK-04 | Phase 32 | Pending |
| BACK-05 | Phase 32 | Pending |
| BACK-06 | Phase 32 | Pending |
| STATE-01 | Phase 33 | Pending |
| STATE-02 | Phase 33 | Pending |
| STATE-03 | Phase 33 | Pending |
| STATE-04 | Phase 33 | Pending |
| MEAS-01 | Phase 34 | Pending |
| MEAS-02 | Phase 34 | Pending |
| MEAS-03 | Phase 34 | Pending |
| MEAS-04 | Phase 34 | Pending |
| MEAS-05 | Phase 34 | Pending |
| MEAS-06 | Phase 34 | Pending |
| INFRA-01 | Phase 33 | Pending |
| INFRA-02 | Phase 33 | Pending |
| INFRA-03 | Phase 33 | Pending |
| INFRA-04 | Phase 33 | Pending |
| INFRA-05 | Phase 33 | Pending |

**Coverage:**
- v1.6 requirements: 38 total
- Mapped to phases: 38
- Unmapped: 0

---
*Requirements defined: 2026-01-24*
*Last updated: 2026-01-24 after roadmap creation*
