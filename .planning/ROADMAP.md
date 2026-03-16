# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production. A TUI dashboard provides real-time operational visibility. Proactive alerting notifies operators of congestion, steering, connectivity, and anomaly events via Discord. Operator-facing CLI tools validate configs offline and audit router queue state. CAKE parameter optimization and bufferbloat benchmarking provide a complete operator feedback loop.

## Domain Expertise

None

## Milestones

### Active

- **v1.18 Measurement Quality** (Phases 88-92) - IN PROGRESS

### Completed

- [v1.17 CAKE Optimization & Benchmarking](milestones/v1.17-ROADMAP.md) (Phases 84-87) - SHIPPED 2026-03-16
- [v1.16 Validation & Operational Confidence](milestones/v1.16-ROADMAP.md) (Phases 81-83) - SHIPPED 2026-03-13
- [v1.15 Alerting & Notifications](milestones/v1.15-ROADMAP.md) (Phases 76-80) - SHIPPED 2026-03-12
- [v1.14 Operational Visibility](milestones/v1.14-ROADMAP.md) (Phases 73-75) - SHIPPED 2026-03-11
- [v1.13 Legacy Cleanup & Feature Graduation](milestones/v1.13-ROADMAP.md) (Phases 67-72) - SHIPPED 2026-03-11
- [v1.12 Deployment & Code Health](milestones/v1.12-ROADMAP.md) (Phases 62-66) - SHIPPED 2026-03-11
- [v1.11 WAN-Aware Steering](milestones/v1.11-ROADMAP.md) (Phases 58-61) - SHIPPED 2026-03-10
- [v1.10 Architectural Review Fixes](milestones/v1.10-ROADMAP.md) (Phases 50-57) - SHIPPED 2026-03-09
- [v1.9 Performance & Efficiency](milestones/v1.9-ROADMAP.md) (Phases 47-49) - SHIPPED 2026-03-07
- [v1.8 Resilience & Robustness](milestones/v1.8-ROADMAP.md) (Phases 43-46) - SHIPPED 2026-03-06
- [v1.7 Metrics History](milestones/v1.7-ROADMAP.md) (Phases 38-42) - SHIPPED 2026-01-25
- [v1.6 Test Coverage 90%](milestones/v1.6-ROADMAP.md) (Phases 31-37) - SHIPPED 2026-01-25
- [v1.5 Quality & Hygiene](milestones/v1.5-ROADMAP.md) (Phases 27-30) - SHIPPED 2026-01-24
- [v1.4 Observability](milestones/v1.4-ROADMAP.md) (Phases 25-26) - SHIPPED 2026-01-24
- [v1.3 Reliability & Hardening](milestones/v1.3-ROADMAP.md) (Phases 21-24) - SHIPPED 2026-01-21
- [v1.2 Configuration & Polish](milestones/v1.2-ROADMAP.md) (Phases 16-20) - SHIPPED 2026-01-14
- [v1.1 Code Quality](milestones/v1.1-ROADMAP.md) (Phases 6-15) - SHIPPED 2026-01-14
- [v1.0 Performance Optimization](milestones/v1.0-ROADMAP.md) (Phases 1-5) - SHIPPED 2026-01-13

## Phases

**v1.18 Measurement Quality** (Phases 88-92)

**Milestone Goal:** Improve RTT measurement accuracy and signal quality through smarter signal processing, IRTT as a supplemental UDP RTT source, and container networking latency characterization. All new capabilities ship in observation mode -- metrics and logs only, no congestion control input changes. Dual-signal fusion deferred to v1.19+.

- [ ] **Phase 88: Signal Processing Core** - Hampel filter, jitter tracker, confidence interval, and variance EWMA for RTT signal quality
- [ ] **Phase 89: IRTT Foundation** - IRTT client wrapper, JSON parsing, YAML config, container install, and graceful fallback
- [ ] **Phase 90: IRTT Daemon Integration** - Background measurement thread wired into autorate daemon with cached results and loss direction tracking
- [ ] **Phase 91: Container Networking Audit** - Measure and document veth/bridge overhead and jitter contribution to RTT measurements
- [ ] **Phase 92: Observability** - Health endpoint signal quality and IRTT sections, SQLite persistence for both

## Phase Details

### Phase 88: Signal Processing Core
**Goal**: RTT measurements are filtered, tracked, and annotated with quality metadata before reaching the control loop
**Depends on**: Nothing (first phase -- pure Python, zero external dependencies)
**Requirements**: SIGP-01, SIGP-02, SIGP-03, SIGP-04, SIGP-05, SIGP-06
**Success Criteria** (what must be TRUE):
  1. Outlier RTT samples are detected and replaced by the Hampel filter using a rolling window of recent measurements, with outlier events logged at DEBUG level
  2. Per-cycle jitter value is computed from consecutive RTT samples using RFC 3550 EWMA and is available as a named attribute on the signal processor
  3. Measurement confidence interval is computed each cycle, reflecting how reliable the current RTT reading is relative to recent variance
  4. RTT variance is tracked via EWMA alongside existing load_rtt smoothing, accessible for downstream consumers
  5. All signal processing runs in observation mode only -- it produces metrics and logs but does not alter congestion state transitions or rate adjustments
**Plans:** 2 plans

Plans:
- [ ] 88-01-PLAN.md -- TDD: SignalProcessor + SignalResult (Hampel, jitter, variance, confidence algorithms)
- [ ] 88-02-PLAN.md -- Config loading, WANController wiring, integration tests, CONFIG_SCHEMA docs

### Phase 89: IRTT Foundation
**Goal**: IRTT binary is installed, wrapped, and configurable so that IRTT measurements can be invoked and parsed reliably
**Depends on**: Nothing (independent of Phase 88 -- could run in parallel)
**Requirements**: IRTT-01, IRTT-04, IRTT-05, IRTT-08
**Success Criteria** (what must be TRUE):
  1. IRTT client subprocess is invoked with configurable server/port and returns parsed RTT, loss, and IPDV values from JSON output
  2. IRTT is configurable via a YAML `irtt:` section (server, port, cadence, enabled) and is disabled by default
  3. When IRTT binary is missing or server is unreachable, the controller continues operating with zero behavioral change -- no errors, no degradation
  4. IRTT binary is installed on production containers (cake-spectrum, cake-att) via apt
**Plans**: TBD

### Phase 90: IRTT Daemon Integration
**Goal**: IRTT measurements run continuously in the background and are consumed by the autorate daemon each cycle without blocking
**Depends on**: Phase 89
**Requirements**: IRTT-02, IRTT-03, IRTT-06, IRTT-07
**Success Criteria** (what must be TRUE):
  1. IRTT measurements execute in a background daemon thread on a configurable cadence (default 10s), independent of the 50ms control loop
  2. The main control loop reads the latest cached IRTT result each cycle in constant time with zero blocking -- even if a measurement is in-flight
  3. Upstream vs downstream packet loss direction is tracked per IRTT measurement burst and available in the cached result
  4. ICMP vs UDP RTT correlation is computed per measurement, detecting protocol-specific deprioritization when both signals are available
**Plans**: TBD

### Phase 91: Container Networking Audit
**Goal**: The latency contribution of container networking (veth pairs, Linux bridge) to RTT measurements is measured, quantified, and documented
**Depends on**: Nothing (independent -- measurement and documentation task)
**Requirements**: CNTR-01, CNTR-02, CNTR-03
**Success Criteria** (what must be TRUE):
  1. Container veth/bridge networking overhead is measured with quantified round-trip latency added by the network path from container to host
  2. Jitter contribution from container networking is characterized separately from WAN jitter, showing whether container networking adds meaningful variance
  3. An audit report documents the measurement floor -- the minimum RTT noise attributable to container infrastructure rather than actual WAN conditions
**Plans**: TBD

### Phase 92: Observability
**Goal**: Signal quality and IRTT data are visible in health endpoints and persisted in SQLite for trend analysis
**Depends on**: Phase 88, Phase 90
**Requirements**: OBSV-01, OBSV-02, OBSV-03, OBSV-04
**Success Criteria** (what must be TRUE):
  1. Health endpoint includes a signal_quality section showing current jitter, confidence, variance, and outlier count
  2. Health endpoint includes an irtt section showing latest RTT, loss direction, IPDV, and server connection status
  3. Signal quality metrics (jitter, confidence, variance, outlier_count) are written to SQLite each cycle for historical trend analysis
  4. IRTT metrics (rtt, loss_up, loss_down, ipdv, server) are written to SQLite per measurement for historical trend analysis
**Plans**: TBD

## Progress

### v1.18 Measurement Quality

**Execution Order:** 88 -> 89 -> 90 -> 91 -> 92
(Note: Phase 89 is independent of 88 and could run in parallel. Phase 91 is independent of all others.)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 88. Signal Processing Core | 0/2 | In progress | - |
| 89. IRTT Foundation | 0/TBD | Not started | - |
| 90. IRTT Daemon Integration | 0/TBD | Not started | - |
| 91. Container Networking Audit | 0/TBD | Not started | - |
| 92. Observability | 0/TBD | Not started | - |

### Completed Milestones

| Milestone                            | Phases | Plans | Status   | Shipped    |
| ------------------------------------ | ------ | ----- | -------- | ---------- |
| v1.17 CAKE Optimization & Bench.     | 84-87  | 8     | Complete | 2026-03-16 |
| v1.16 Validation & Op. Confidence    | 81-83  | 4     | Complete | 2026-03-13 |
| v1.15 Alerting & Notifications       | 76-80  | 10    | Complete | 2026-03-12 |
| v1.14 Operational Visibility         | 73-75  | 7     | Complete | 2026-03-11 |
| v1.13 Legacy Cleanup & Feature Grad. | 67-72  | 10    | Complete | 2026-03-11 |
| v1.12 Deployment & Code Health       | 62-66  | 7     | Complete | 2026-03-11 |
| v1.11 WAN-Aware Steering             | 58-61  | 8     | Complete | 2026-03-10 |
| v1.10 Architectural Review Fixes     | 50-57  | 15    | Complete | 2026-03-09 |
| v1.9 Performance & Efficiency        | 47-49  | 6     | Complete | 2026-03-07 |
| v1.8 Resilience & Robustness         | 43-46  | 8     | Complete | 2026-03-06 |
| v1.7 Metrics History                 | 38-42  | 8     | Complete | 2026-01-25 |
| v1.6 Test Coverage 90%               | 31-37  | 17    | Complete | 2026-01-25 |
| v1.5 Quality & Hygiene               | 27-30  | 8     | Complete | 2026-01-24 |
| v1.4 Observability                   | 25-26  | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening         | 21-24  | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish          | 16-20  | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality                    | 6-15   | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization        | 1-5    | 8     | Complete | 2026-01-13 |

**Total:** 87 phases complete, 178 plans across 18 milestones

<details>
<summary>v1.17 CAKE Optimization & Benchmarking (Phases 84-87) - SHIPPED 2026-03-16</summary>

**Milestone Goal:** Automated CAKE queue type parameter optimization via `--fix` flag and bufferbloat benchmarking with A-F grading and before/after comparison.

- [x] Phase 84: CAKE Detection & Optimizer Foundation (2/2 plans) -- completed 2026-03-13
- [x] Phase 85: Auto-Fix CLI Integration (2/2 plans) -- completed 2026-03-13
- [x] Phase 86: Bufferbloat Benchmarking (2/2 plans) -- completed 2026-03-13
- [x] Phase 87: Benchmark Storage & Comparison (2/2 plans) -- completed 2026-03-15

**Key Results:** CAKE parameter detection and auto-fix via REST API, RRUL bufferbloat benchmarking with A+-F grading, SQLite storage with before/after comparison. 70 new tests (2,823 to 2,893), 23/23 requirements satisfied. Production tested on both Spectrum and ATT WANs.

See [milestones/v1.17-ROADMAP.md](milestones/v1.17-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.16 Validation & Operational Confidence (Phases 81-83) - SHIPPED 2026-03-13</summary>

**Milestone Goal:** Operator-facing CLI tools that catch misconfigurations before runtime and verify router queue state matches expectations.

- [x] Phase 81: Config Validation Foundation (1/1 plans) -- completed 2026-03-12
- [x] Phase 82: Steering Config + Output Modes (2/2 plans) -- completed 2026-03-13
- [x] Phase 83: CAKE Qdisc Audit (1/1 plans) -- completed 2026-03-13

**Key Results:** `wanctl-check-config` CLI tool with auto-detection (autorate/steering), 6 validation categories, cross-config topology checks, JSON output mode. `wanctl-check-cake` CLI for live router CAKE queue audit (connectivity, queue tree, CAKE type, max-limit diff, mangle rules). 157 new tests (2,666 to 2,823), 16/16 requirements satisfied.

See [milestones/v1.16-ROADMAP.md](milestones/v1.16-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.15 and earlier (Phases 1-80) - SHIPPED 2026-01-13 to 2026-03-12</summary>

See individual milestone archives in `milestones/` for details:

- [v1.15 Alerting & Notifications](milestones/v1.15-ROADMAP.md) - Discord webhooks, 7 alert types
- [v1.14 Operational Visibility](milestones/v1.14-ROADMAP.md) - TUI dashboard, live monitoring, sparklines
- [v1.13 Legacy Cleanup & Feature Graduation](milestones/v1.13-ROADMAP.md) - Legacy cleanup, feature graduation
- [v1.12 Deployment & Code Health](milestones/v1.12-ROADMAP.md) - Deployment alignment, security, config consolidation
- [v1.11 WAN-Aware Steering](milestones/v1.11-ROADMAP.md) - WAN zone fusion, confidence scoring
- [v1.10 Architectural Review Fixes](milestones/v1.10-ROADMAP.md) - Hot-loop, failover, test quality
- [v1.9 Performance & Efficiency](milestones/v1.9-ROADMAP.md) - icmplib, profiling, telemetry
- [v1.8 Resilience & Robustness](milestones/v1.8-ROADMAP.md) - Error recovery, fail-safe, shutdown
- [v1.7 Metrics History](milestones/v1.7-ROADMAP.md) - SQLite storage, CLI, HTTP API
- [v1.6 Test Coverage 90%](milestones/v1.6-ROADMAP.md) - 743 tests, CI enforcement
- [v1.5 Quality & Hygiene](milestones/v1.5-ROADMAP.md) - Coverage infra, security audit
- [v1.4 Observability](milestones/v1.4-ROADMAP.md) - Steering health endpoint
- [v1.3 Reliability & Hardening](milestones/v1.3-ROADMAP.md) - Failover, safety tests
- [v1.2 Configuration & Polish](milestones/v1.2-ROADMAP.md) - Phase2B dry-run, config docs
- [v1.1 Code Quality](milestones/v1.1-ROADMAP.md) - Refactoring, shared modules
- [v1.0 Performance Optimization](milestones/v1.0-ROADMAP.md) - 40x speed improvement

</details>
