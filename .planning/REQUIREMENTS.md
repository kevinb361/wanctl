# Requirements: wanctl v1.22 Full System Audit

**Defined:** 2026-03-26
**Core Value:** Sub-second congestion detection with 50ms control loops — now audited for production hardening

## v1.22 Requirements

Comprehensive audit from network engineering, Linux sysadmin, and Python development perspectives. No new features — cleanup, hardening, and documentation only.

### Foundation Scan

- [x] **FSCAN-01**: All Python dependencies scanned for CVEs with pip-audit (zero critical/high)
- [x] **FSCAN-02**: Unused dependencies identified and removed via deptry
- [x] **FSCAN-03**: Dead code inventory produced via vulture (identification only, no removal)
- [x] **FSCAN-04**: File permissions verified (/etc/wanctl/secrets 0640, state/log dirs 0750)
- [x] **FSCAN-05**: systemd-analyze security score assessed for all 3 service units
- [x] **FSCAN-06**: Ruff rule expansion (C901/SIM/PERF/RET/PT/TRY/ARG/ERA) applied and findings triaged
- [x] **FSCAN-07**: Orphaned test fixtures identified via pytest-deadfixtures
- [x] **FSCAN-08**: Log rotation verified (RotatingFileHandler active, retention appropriate)

### Network Engineering

- [x] **NETENG-01**: CAKE parameters verified per WAN (overhead, diffserv4, ack-filter, split-gso, memlimit)
- [x] **NETENG-02**: DSCP end-to-end trace completed (MikroTik mangle -> CAKE tins -> verify EF/AF/CS1 mapping)
- [x] **NETENG-03**: Steering logic correctness audited (confidence scoring, degrade timers, CAKE-primary invariant)
- [x] **NETENG-04**: Measurement methodology validated (reflector selection, signal chain, IRTT vs ICMP paths)
- [x] **NETENG-05**: Queue depth and memory pressure baseline documented from production CAKE stats

### Code Quality

- [ ] **CQUAL-01**: All broad `except Exception` catches triaged (legitimate safety vs bug-swallowing)
- [ ] **CQUAL-02**: Bug-swallowing exception catches fixed with appropriate error handling
- [ ] **CQUAL-03**: MyPy strictness probed module-by-module with fix/suppress strategy per module
- [x] **CQUAL-04**: Thread safety audit completed (threaded files, shared mutable state, race conditions)
- [ ] **CQUAL-05**: Complexity hotspots analyzed (5 largest files) with extraction recommendations documented
- [x] **CQUAL-06**: SIGUSR1 reload chain fully cataloged with E2E test coverage verified
- [ ] **CQUAL-07**: Import graph analyzed for circular dependencies

### Operational Hardening

- [ ] **OPSEC-01**: systemd units hardened (ProtectKernelTunables, SystemCallFilter, etc.) verified on production VM
- [ ] **OPSEC-02**: NIC/bridge tuning made persistent across reboot (rx-udp-gro-forwarding, ring buffers)
- [ ] **OPSEC-03**: Resource limits set on service units (MemoryMax, TasksMax, LimitNOFILE)
- [ ] **OPSEC-04**: Backup/recovery procedure documented (configs, metrics.db, VM snapshots, rollback)
- [ ] **OPSEC-05**: Production dependency lock file created (requirements-production.txt)
- [ ] **OPSEC-06**: Circuit breaker config consistent across all 3 service units

### Test & Documentation

- [ ] **TDOC-01**: Test quality audit completed (assertion-free, over-mocked, tautological tests identified)
- [ ] **TDOC-02**: Highest-risk test quality issues fixed
- [ ] **TDOC-03**: All docs/\* reviewed for accuracy against current architecture (post-v1.21)
- [ ] **TDOC-04**: Container-era scripts archived to .archive/ with manifest
- [ ] **TDOC-05**: CONFIG_SCHEMA.md aligned with config_validation_utils.py and accepted params
- [ ] **TDOC-06**: Audit findings summary with remaining debt inventory produced

## Future Requirements

### Deferred to v1.23+

- **REFAC-01**: autorate_continuous.py extraction into separate modules (4,282 LOC, 4 responsibilities)
- **REFAC-02**: Global strict mypy migration (module-by-module probe in v1.22, full migration later)
- **OBSRV-01**: Prometheus/Grafana integration (document metric naming readiness only in v1.22)
- **TEST-01**: Mutation testing with mutmut on critical modules (hours-long runtime, scope TBD)
- **ARCH-01**: import-linter architectural boundary enforcement (post-audit contracts)

## Out of Scope

| Feature                               | Reason                                                                                |
| ------------------------------------- | ------------------------------------------------------------------------------------- |
| Rewriting autorate_continuous.py      | Behavioral regressions in 50ms control loop take days to surface — separate milestone |
| Global strict mypy                    | Produces unreviewable changeset — module-by-module probe only in v1.22                |
| Removing all mocking from tests       | Makes tests environment-dependent and slow                                            |
| Performance optimization of 50ms loop | Already within budget; premature optimization causes instability                      |
| Prometheus/Grafana implementation     | Document readiness only — implementation is scope creep                               |
| New features of any kind              | This is an audit milestone — hardening and cleanup only                               |

## Traceability

| Requirement | Phase     | Status   |
| ----------- | --------- | -------- |
| FSCAN-01    | Phase 112 | Complete |
| FSCAN-02    | Phase 112 | Complete |
| FSCAN-03    | Phase 112 | Complete |
| FSCAN-04    | Phase 112 | Complete |
| FSCAN-05    | Phase 112 | Complete |
| FSCAN-06    | Phase 112 | Complete |
| FSCAN-07    | Phase 112 | Complete |
| FSCAN-08    | Phase 112 | Complete |
| NETENG-01   | Phase 113 | Complete |
| NETENG-02   | Phase 113 | Complete |
| NETENG-03   | Phase 113 | Complete |
| NETENG-04   | Phase 113 | Complete |
| NETENG-05   | Phase 113 | Complete |
| CQUAL-01    | Phase 114 | Pending  |
| CQUAL-02    | Phase 114 | Pending  |
| CQUAL-03    | Phase 114 | Pending  |
| CQUAL-04    | Phase 114 | Complete |
| CQUAL-05    | Phase 114 | Pending  |
| CQUAL-06    | Phase 114 | Complete |
| CQUAL-07    | Phase 114 | Pending  |
| OPSEC-01    | Phase 115 | Pending  |
| OPSEC-02    | Phase 115 | Pending  |
| OPSEC-03    | Phase 115 | Pending  |
| OPSEC-04    | Phase 115 | Pending  |
| OPSEC-05    | Phase 115 | Pending  |
| OPSEC-06    | Phase 115 | Pending  |
| TDOC-01     | Phase 116 | Pending  |
| TDOC-02     | Phase 116 | Pending  |
| TDOC-03     | Phase 116 | Pending  |
| TDOC-04     | Phase 116 | Pending  |
| TDOC-05     | Phase 116 | Pending  |
| TDOC-06     | Phase 116 | Pending  |

**Coverage:**

- v1.22 requirements: 32 total
- Mapped to phases: 32/32
- Unmapped: 0

---

_Requirements defined: 2026-03-26_
_Last updated: 2026-03-26 after roadmap creation_
