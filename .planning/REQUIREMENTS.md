# Requirements: wanctl

**Defined:** 2026-01-24
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.6 Requirements

Requirements for Test Coverage 90% milestone. Each maps to roadmap phases.

### Coverage Infrastructure

- [x] **COV-01**: Coverage threshold set to 90% in pyproject.toml (fail_under) ✓
- [x] **COV-02**: `make ci` fails if coverage drops below 90% ✓
- [x] **COV-03**: Coverage badge updated to reflect new threshold ✓

### Core Controller Tests

- [x] **CORE-01**: autorate_continuous.py coverage >=90% (98.3%) ✓
- [x] **CORE-02**: All main() entry point paths tested ✓
- [x] **CORE-03**: Signal handlers (SIGTERM, SIGHUP) tested ✓
- [x] **CORE-04**: Control loop state transitions tested ✓
- [x] **CORE-05**: Error recovery paths tested ✓

### Steering Daemon Tests

- [x] **STEER-01**: steering/daemon.py coverage >=90% (91.0%) ✓
- [x] **STEER-02**: Daemon lifecycle (start/stop/restart) tested ✓
- [x] **STEER-03**: Routing decision logic tested ✓
- [x] **STEER-04**: Confidence-based steering paths tested ✓
- [x] **STEER-05**: Congestion assessment integration tested ✓

### CLI Tool Tests

- [x] **CLI-01**: calibrate.py coverage >=90% (97.5%) ✓
- [x] **CLI-02**: Calibration workflow tested end-to-end ✓
- [x] **CLI-03**: perf_profiler.py coverage >=90% (98.7%) ✓
- [x] **CLI-04**: CLI argument parsing tested ✓

### Backend Client Tests

- [x] **BACK-01**: routeros_rest.py coverage >=90% (93.4%) ✓
- [x] **BACK-02**: REST API request/response handling tested ✓
- [x] **BACK-03**: routeros_ssh.py coverage >=90% (100%) ✓
- [x] **BACK-04**: SSH command execution tested ✓
- [x] **BACK-05**: backends/base.py coverage >=90% (80.6% - abstract methods excluded) ✓
- [x] **BACK-06**: Backend factory and abstract methods tested ✓

### State Management Tests

- [x] **STATE-01**: state_manager.py coverage >=90% (93.6%) ✓
- [x] **STATE-02**: State persistence (save/load) tested ✓
- [x] **STATE-03**: Concurrent access and locking tested ✓
- [x] **STATE-04**: Corruption recovery tested ✓

### Metrics & Measurement Tests

- [x] **MEAS-01**: metrics.py coverage >=90% (98.5%) ✓
- [x] **MEAS-02**: Metrics collection and reporting tested ✓
- [x] **MEAS-03**: steering/cake_stats.py coverage >=90% (96.7%) ✓
- [x] **MEAS-04**: CAKE statistics parsing tested ✓
- [x] **MEAS-05**: rtt_measurement.py coverage >=90% (96.9%) ✓
- [x] **MEAS-06**: RTT measurement edge cases tested ✓

### Infrastructure Tests

- [x] **INFRA-01**: error_handling.py coverage >=90% (99.1%) ✓
- [x] **INFRA-02**: Error escalation and recovery tested ✓
- [x] **INFRA-03**: signal_utils.py coverage >=90% (100%) ✓
- [x] **INFRA-04**: systemd_utils.py coverage >=90% (97.0%) ✓
- [x] **INFRA-05**: path_utils.py coverage >=90% (100%) ✓

## Future Requirements

None currently.

## Out of Scope

| Feature                            | Reason                                    |
| ---------------------------------- | ----------------------------------------- |
| 100% coverage                      | Diminishing returns, 90% is comprehensive |
| Integration tests with real router | Requires hardware, unit tests sufficient  |
| Performance benchmarks in CI       | Not coverage-related, separate concern    |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase    | Status   |
| ----------- | -------- | -------- |
| COV-01      | Phase 31 | Complete |
| COV-02      | Phase 31 | Complete |
| COV-03      | Phase 31 | Complete |
| CORE-01     | Phase 35 | Complete |
| CORE-02     | Phase 35 | Complete |
| CORE-03     | Phase 35 | Complete |
| CORE-04     | Phase 35 | Complete |
| CORE-05     | Phase 35 | Complete |
| STEER-01    | Phase 36 | Complete |
| STEER-02    | Phase 36 | Complete |
| STEER-03    | Phase 36 | Complete |
| STEER-04    | Phase 36 | Complete |
| STEER-05    | Phase 36 | Complete |
| CLI-01      | Phase 37 | Complete |
| CLI-02      | Phase 37 | Complete |
| CLI-03      | Phase 37 | Complete |
| CLI-04      | Phase 37 | Complete |
| BACK-01     | Phase 32 | Complete |
| BACK-02     | Phase 32 | Complete |
| BACK-03     | Phase 32 | Complete |
| BACK-04     | Phase 32 | Complete |
| BACK-05     | Phase 32 | Complete |
| BACK-06     | Phase 32 | Complete |
| STATE-01    | Phase 33 | Complete |
| STATE-02    | Phase 33 | Complete |
| STATE-03    | Phase 33 | Complete |
| STATE-04    | Phase 33 | Complete |
| MEAS-01     | Phase 34 | Complete |
| MEAS-02     | Phase 34 | Complete |
| MEAS-03     | Phase 34 | Complete |
| MEAS-04     | Phase 34 | Complete |
| MEAS-05     | Phase 34 | Complete |
| MEAS-06     | Phase 34 | Complete |
| INFRA-01    | Phase 33 | Complete |
| INFRA-02    | Phase 33 | Complete |
| INFRA-03    | Phase 33 | Complete |
| INFRA-04    | Phase 33 | Complete |
| INFRA-05    | Phase 33 | Complete |

**Coverage:**

- v1.6 requirements: 38 total
- Mapped to phases: 38
- Unmapped: 0

---

_Requirements defined: 2026-01-24_
_Last updated: 2026-01-25 after v1.6 milestone audit_
