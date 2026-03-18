# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production. A TUI dashboard provides real-time operational visibility. Proactive alerting notifies operators of congestion, steering, connectivity, and anomaly events via Discord. Operator-facing CLI tools validate configs offline and audit router queue state. CAKE parameter optimization and bufferbloat benchmarking provide a complete operator feedback loop. RTT signal processing (Hampel filtering, jitter/variance EWMA, confidence scoring) and IRTT UDP measurements enrich the primary ICMP control loop. Dual-signal fusion combines weighted ICMP + IRTT RTT for congestion control input, with reflector quality scoring, OWD asymmetry detection, and IRTT loss alerting.

## Domain Expertise

None

## Milestones

### Active

(None — planning next milestone)

### Completed

- [v1.19 Signal Fusion](milestones/v1.19-ROADMAP.md) (Phases 93-97) - SHIPPED 2026-03-18
- [v1.18 Measurement Quality](milestones/v1.18-ROADMAP.md) (Phases 88-92) - SHIPPED 2026-03-17
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

## Completed Milestone Details

<details>
<summary>v1.19 Signal Fusion (Phases 93-97) - SHIPPED 2026-03-18</summary>

**Milestone Goal:** Graduate observation-mode signals (IRTT, signal quality) into active congestion control inputs through weighted dual-signal fusion, OWD-based asymmetric congestion detection, reflector quality scoring, and IRTT loss alerting.

- [x] Phase 93: Reflector Quality Scoring (2/2 plans) -- completed 2026-03-17
- [x] Phase 94: OWD Asymmetric Detection (2/2 plans) -- completed 2026-03-18
- [x] Phase 95: IRTT Loss Alerts (1/1 plan) -- completed 2026-03-18
- [x] Phase 96: Dual-Signal Fusion Core (2/2 plans) -- completed 2026-03-18
- [x] Phase 97: Fusion Safety & Observability (2/2 plans) -- completed 2026-03-18

**Key Results:** Reflector quality scoring with graceful degradation. OWD asymmetric detection (no NTP dependency). IRTT sustained loss alerting via AlertEngine. Weighted ICMP+IRTT fusion with multi-gate fallback. Ships disabled with SIGUSR1 toggle. Health endpoint fusion section. ~202 new tests (3,256 to ~3,458), 15/15 requirements satisfied.

See [milestones/v1.19-ROADMAP.md](milestones/v1.19-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.18 Measurement Quality (Phases 88-92) - SHIPPED 2026-03-17</summary>

**Milestone Goal:** Improve RTT measurement accuracy and signal quality through smarter signal processing, IRTT as a supplemental UDP RTT source, and container networking latency characterization. All new capabilities ship in observation mode.

- [x] Phase 88: Signal Processing Core (2/2 plans) -- completed 2026-03-16
- [x] Phase 89: IRTT Foundation (2/2 plans) -- completed 2026-03-16
- [x] Phase 90: IRTT Daemon Integration (2/2 plans) -- completed 2026-03-16
- [x] Phase 91: Container Networking Audit (2/2 plans) -- completed 2026-03-17
- [x] Phase 92: Observability (2/2 plans) -- completed 2026-03-17

**Key Results:** Hampel outlier filter, jitter/variance EWMA, confidence scoring (observation mode). IRTT UDP RTT via background thread with lock-free caching. ICMP/UDP protocol correlation. Container networking 0.17ms overhead (negligible). Health endpoint signal_quality + irtt sections. SQLite persistence for both. 363 new tests (2,893 to 3,256), 21/21 requirements satisfied. Deployed and production-verified.

See [milestones/v1.18-ROADMAP.md](milestones/v1.18-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.17 and earlier (Phases 1-87) - SHIPPED 2026-01-13 to 2026-03-16</summary>

See individual milestone archives in `milestones/` for details:

- [v1.17 CAKE Optimization & Benchmarking](milestones/v1.17-ROADMAP.md) - CAKE auto-fix, bufferbloat benchmarking
- [v1.16 Validation & Operational Confidence](milestones/v1.16-ROADMAP.md) - Config validation, CAKE audit
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

## Progress

**Total:** 97 phases complete, 197 plans across 20 milestones

| Milestone                            | Phases | Plans | Status   | Shipped    |
| ------------------------------------ | ------ | ----- | -------- | ---------- |
| v1.19 Signal Fusion                  | 93-97  | 9     | Complete | 2026-03-18 |
| v1.18 Measurement Quality            | 88-92  | 10    | Complete | 2026-03-17 |
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
