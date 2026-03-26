# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on a Proxmox VM with PCIe passthrough NICs, transparent bridges, and dual-WAN steering. After 21 feature milestones and a CAKE offload migration, the system has accumulated technical debt across 28,629 LOC and 3,723 tests. v1.22 is a comprehensive audit from network engineering, Linux sysadmin, and Python development perspectives -- no new features, only cleanup, hardening, and documentation.

## Domain Expertise

None

## Milestones

- v1.0 through v1.21: See MILESTONES.md (shipped)
- v1.22 Full System Audit: Phases 112-116 (current)

## Phases

- [ ] **Phase 112: Foundation Scan** - Mechanical tool-driven scanning (CVEs, dead code, permissions, linting) that produces findings for all later phases
- [ ] **Phase 113: Network Engineering Audit** - CAKE parameter verification, DSCP end-to-end trace, steering logic correctness, measurement methodology validation
- [ ] **Phase 114: Code Quality & Safety** - Exception handling triage, type safety probe, thread safety audit, complexity analysis, SIGUSR1 chain catalog
- [ ] **Phase 115: Operational Hardening** - systemd unit hardening, NIC persistence, resource limits, backup/recovery procedures, dependency locking
- [ ] **Phase 116: Test & Documentation Hygiene** - Test quality audit and fixes, docs freshness review, container script archival, audit findings summary

## Phase Details

### Phase 112: Foundation Scan

**Goal**: All mechanical scanning tools have run and produced actionable inventories that unblock later phases
**Depends on**: Nothing (first phase)
**Requirements**: FSCAN-01, FSCAN-02, FSCAN-03, FSCAN-04, FSCAN-05, FSCAN-06, FSCAN-07, FSCAN-08
**Success Criteria** (what must be TRUE):

1. pip-audit reports zero critical/high CVEs in all Python dependencies
2. Unused dependencies identified by deptry and removed from pyproject.toml
3. Dead code inventory from vulture exists as a structured report (identification only, no removals)
4. File permissions on /etc/wanctl/secrets (0600), state dirs (0750), and log dirs (0750) verified on production VM
5. Ruff expanded rule set (C901/SIM/PERF/RET/PT/TRY/ARG/ERA) enabled with findings triaged (fix, suppress, or defer)
   **Plans:** 4 plans

Plans:

- [x] 112-01-PLAN.md -- Dependency hygiene scan (pip-audit, deptry, deadfixtures, log rotation)
- [x] 112-02-PLAN.md -- Production VM security audit (file permissions, systemd security scores)
- [x] 112-03-PLAN.md -- Ruff rule expansion with autofix and triage
- [x] 112-04-PLAN.md -- Vulture dead code inventory with false positive validation

### Phase 113: Network Engineering Audit

**Goal**: CAKE configuration, DSCP mapping, steering logic, and measurement methodology are verified correct on the production VM
**Depends on**: Phase 112
**Requirements**: NETENG-01, NETENG-02, NETENG-03, NETENG-04, NETENG-05
**Success Criteria** (what must be TRUE):

1. CAKE parameters per WAN verified via `tc -j qdisc show` readback (overhead, diffserv4, ack-filter, split-gso, memlimit match expected values)
2. DSCP end-to-end trace documented showing MikroTik mangle rules produce correct CAKE tin classification (EF=Voice, AF41=Video, CS1=Bulk)
3. Steering logic audit confirms confidence scoring weights, degrade timers, and CAKE-primary invariant are correct
4. Measurement methodology validated: reflector selection, signal chain (Hampel/Fusion/EWMA), IRTT vs ICMP paths documented with correctness rationale
5. Queue depth and memory pressure baseline documented from production `tc -s qdisc show` statistics
   **Plans:** 3 plans

Plans:

- [x] 113-01-PLAN.md -- CAKE parameter verification + DSCP end-to-end trace
- [x] 113-02-PLAN.md -- Steering logic audit + measurement methodology validation
- [ ] 113-03-PLAN.md -- Queue depth and memory pressure baseline

### Phase 114: Code Quality & Safety

**Goal**: Exception handling, type safety, thread safety, and complexity hotspots are audited with dispositions documented and highest-risk issues fixed
**Depends on**: Phase 112
**Requirements**: CQUAL-01, CQUAL-02, CQUAL-03, CQUAL-04, CQUAL-05, CQUAL-06, CQUAL-07
**Success Criteria** (what must be TRUE):

1. All broad `except Exception` catches have documented dispositions (legitimate safety net vs. bug-swallowing) and bug-swallowing catches are fixed
2. MyPy strictness probed on at least 5 leaf modules with per-module fix/suppress strategy documented
3. Thread safety audit completed for all threaded files with shared mutable state and race conditions cataloged
4. Top 5 complexity hotspots analyzed with extraction recommendations documented (no execution -- deferred to v1.23)
5. SIGUSR1 reload chain fully cataloged (all targets across both daemons) with E2E test coverage verified or added
   **Plans**: TBD

### Phase 115: Operational Hardening

**Goal**: Production VM services are hardened, persistent across reboot, resource-limited, and recoverable from disaster
**Depends on**: Phase 114
**Requirements**: OPSEC-01, OPSEC-02, OPSEC-03, OPSEC-04, OPSEC-05, OPSEC-06
**Success Criteria** (what must be TRUE):

1. systemd units pass `systemd-analyze security` with improved scores and ProtectKernelTunables/SystemCallFilter/RestrictNamespaces applied where compatible with CAP_NET_RAW
2. NIC tuning (rx-udp-gro-forwarding, ring buffers) persists across VM reboot without manual intervention
3. Resource limits (MemoryMax, TasksMax, LimitNOFILE) set on all 3 service units and verified under load
4. Backup/recovery procedure documented covering configs, metrics.db, VM snapshots, and rollback to previous state
5. Production dependency lock file (requirements-production.txt) created from running VM and circuit breaker config verified consistent across all 3 units
   **Plans**: TBD

### Phase 116: Test & Documentation Hygiene

**Goal**: Test suite quality issues are identified and fixed, all documentation reflects current architecture, and a complete audit findings summary exists
**Depends on**: Phase 115
**Requirements**: TDOC-01, TDOC-02, TDOC-03, TDOC-04, TDOC-05, TDOC-06
**Success Criteria** (what must be TRUE):

1. Test quality audit completed with assertion-free, over-mocked, and tautological tests identified and highest-risk cases fixed
2. All files in docs/\* reviewed and updated to reflect post-v1.21 architecture (container references removed, VM architecture documented)
3. Container-era scripts archived to .archive/ with a manifest documenting what each script was and why it was archived
4. CONFIG_SCHEMA.md aligned with config_validation_utils.py (all accepted params documented, no stale entries)
5. Audit findings summary produced with remaining debt inventory categorized by severity and recommended milestone
   **Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 112 -> 113 -> 114 -> 115 -> 116

| Phase                             | Plans Complete | Status      | Completed  |
| --------------------------------- | -------------- | ----------- | ---------- |
| 112. Foundation Scan              | 4/4            | Complete    | 2026-03-26 |
| 113. Network Engineering Audit    | 2/3            | In Progress |            |
| 114. Code Quality & Safety        | 0/TBD          | Not started | -          |
| 115. Operational Hardening        | 0/TBD          | Not started | -          |
| 116. Test & Documentation Hygiene | 1/3            | In Progress | -          |

<details>
<summary>Previous Milestones (v1.0-v1.21)</summary>

| Milestone                            | Phases  | Plans | Status   | Completed  |
| ------------------------------------ | ------- | ----- | -------- | ---------- |
| v1.21 CAKE Offload                   | 104-110 | 14    | Complete | 2026-03-25 |
| v1.20 Adaptive Tuning                | 98-103  | 13    | Complete | 2026-03-19 |
| v1.19 Signal Fusion                  | 93-97   | 9     | Complete | 2026-03-18 |
| v1.18 Measurement Quality            | 88-92   | 10    | Complete | 2026-03-17 |
| v1.17 CAKE Optimization              | 84-87   | 8     | Complete | 2026-03-16 |
| v1.16 Validation & Operational Conf. | 81-83   | 4     | Complete | 2026-03-13 |
| v1.15 Alerting & Notifications       | 76-80   | 10    | Complete | 2026-03-12 |
| v1.14 Operational Visibility         | 73-75   | 7     | Complete | 2026-03-11 |
| v1.13 Legacy Cleanup & Feature Grad. | 67-72   | 10    | Complete | 2026-03-11 |
| v1.12 Deployment & Code Health       | 62-66   | 7     | Complete | 2026-03-11 |
| v1.11 WAN-Aware Steering             | 58-61   | 8     | Complete | 2026-03-10 |
| v1.10 Architectural Review Fixes     | 50-57   | 15    | Complete | 2026-03-09 |
| v1.9 Performance & Efficiency        | 47-49   | 6     | Complete | 2026-03-07 |
| v1.8 Resilience & Robustness         | 43-46   | 8     | Complete | 2026-03-06 |
| v1.7 Metrics History                 | 38-42   | 8     | Complete | 2026-01-25 |
| v1.6 Test Coverage 90%               | 31-37   | 17    | Complete | 2026-01-25 |
| v1.5 Quality & Hygiene               | 27-30   | 8     | Complete | 2026-01-24 |
| v1.4 Observability                   | 25-26   | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening         | 21-24   | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish          | 16-20   | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality                    | 6-15    | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization        | 1-5     | 8     | Complete | 2026-01-13 |

### Phase 111: Auto-Tuning Production Hardening -- Config bounds + SIGP-01 rate fix

**Goal:** Widen 4 tuning bounds stuck at limits and fix SIGP-01 outlier rate 60x underestimate from wrong denominator
**Requirements**: SIGP-01-FIX, BOUNDS-SPECTRUM, BOUNDS-ATT
**Depends on:** None (standalone hardening, applies to current production v1.20)
**Plans:** 4/4 plans complete

Plans:

- [x] 111-01-PLAN.md -- Config bounds update + SIGP-01 rate normalization fix with density-aware tests

</details>
