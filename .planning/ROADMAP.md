# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production. A TUI dashboard provides real-time operational visibility. Proactive alerting notifies operators of congestion, steering, connectivity, and anomaly events via Discord. Operator-facing CLI tools validate configs offline and audit router queue state. CAKE parameter optimization and bufferbloat benchmarking provide a complete operator feedback loop. RTT signal processing (Hampel filtering, jitter/variance EWMA, confidence scoring) and IRTT UDP measurements run in observation mode alongside the primary ICMP control loop. v1.19 graduates these observation-mode signals into active congestion control inputs through weighted fusion, OWD asymmetry detection, reflector quality scoring, and IRTT loss alerting.

## Domain Expertise

None

## Milestones

### Active

- **v1.19 Signal Fusion** (Phases 93-97) - IN PROGRESS

### Completed

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

## v1.19 Signal Fusion

**Milestone Goal:** Graduate observation-mode signals (IRTT, signal quality) into active congestion control inputs through weighted dual-signal fusion, OWD-based asymmetric congestion detection, reflector quality scoring, and IRTT loss alerting.

## Phases

- [ ] **Phase 93: Reflector Quality Scoring** - Rolling quality scores for ping_host reflectors with deprioritization and recovery
- [ ] **Phase 94: OWD Asymmetric Detection** - Upstream vs downstream congestion detection from IRTT burst-internal delays
- [ ] **Phase 95: IRTT Loss Alerts** - Sustained upstream/downstream packet loss alerts via existing AlertEngine
- [ ] **Phase 96: Dual-Signal Fusion Core** - Weighted IRTT + icmplib combination for congestion control input with config and fallback
- [ ] **Phase 97: Fusion Safety & Observability** - Ships disabled with SIGUSR1 toggle, health endpoint fusion visibility

## Phase Details

### Phase 93: Reflector Quality Scoring
**Goal**: Unreliable ping_host reflectors are automatically deprioritized based on measured quality, with periodic recovery checks
**Depends on**: Nothing (uses existing icmplib infrastructure)
**Requirements**: REFL-01, REFL-02, REFL-03, REFL-04
**Success Criteria** (what must be TRUE):
  1. Each configured ping_host reflector has a rolling quality score visible in the health endpoint
  2. A reflector with high timeout frequency or excessive jitter is automatically skipped during RTT measurement
  3. A deprioritized reflector is re-checked on a configurable interval and restored when quality improves
  4. Reflector quality scores persist across measurement cycles (not reset each cycle)
**Plans:** 2 plans
Plans:
- [ ] 93-01-PLAN.md -- ReflectorScorer module, RTTMeasurement extension, config loader, schema
- [ ] 93-02-PLAN.md -- WANController integration, health endpoint, SQLite persistence

### Phase 94: OWD Asymmetric Detection
**Goal**: The controller can distinguish upstream-only from downstream-only congestion using IRTT burst-internal send_delay vs receive_delay
**Depends on**: Nothing (uses existing IRTTThread/IRTTMeasurement infrastructure from v1.18)
**Requirements**: ASYM-01, ASYM-02, ASYM-03
**Success Criteria** (what must be TRUE):
  1. IRTT burst results are analyzed for send_delay vs receive_delay divergence to detect directional congestion
  2. Asymmetric congestion direction is exposed as a named attribute (e.g., "upstream", "downstream", "symmetric", "unknown") for downstream consumers
  3. Asymmetric congestion events are persisted in SQLite with direction and magnitude for trend analysis
**Plans:** 2 plans
Plans:
- [ ] 94-01-PLAN.md -- IRTTResult OWD extension, AsymmetryAnalyzer module, config loader
- [ ] 94-02-PLAN.md -- WANController integration, health endpoint, SQLite persistence

### Phase 95: IRTT Loss Alerts
**Goal**: Operators receive Discord notifications when sustained upstream or downstream packet loss is detected via IRTT
**Depends on**: Nothing (uses existing AlertEngine from v1.15 and IRTTThread from v1.18)
**Requirements**: ALRT-01, ALRT-02, ALRT-03
**Success Criteria** (what must be TRUE):
  1. Sustained upstream packet loss above a configurable threshold triggers a Discord alert with loss percentage and direction
  2. Sustained downstream packet loss above a configurable threshold triggers a separate Discord alert
  3. IRTT loss alerts respect per-event cooldown suppression consistent with existing alert types (no alert storms)
**Plans**: TBD

### Phase 96: Dual-Signal Fusion Core
**Goal**: IRTT and icmplib RTT measurements are combined via weighted average to produce a fused congestion signal that is more robust than either signal alone
**Depends on**: Phase 93 (improved icmplib signal quality), Phase 94 (IRTT data enrichment)
**Requirements**: FUSE-01, FUSE-03, FUSE-04
**Success Criteria** (what must be TRUE):
  1. A weighted average of IRTT UDP RTT and icmplib ICMP RTT is computed and usable as congestion control input
  2. Fusion weights are configurable via YAML with warn+default validation (invalid values produce warnings and fall back to defaults)
  3. When IRTT is unavailable or stale (thread not running, measurement too old), the controller operates on icmplib-only with zero behavioral change from pre-fusion behavior
**Plans**: TBD

### Phase 97: Fusion Safety & Observability
**Goal**: Fusion ships safely disabled with zero-downtime toggle and full operational visibility
**Depends on**: Phase 96 (fusion engine must exist to gate and observe)
**Requirements**: FUSE-02, FUSE-05
**Success Criteria** (what must be TRUE):
  1. Fusion is disabled by default on fresh deploy -- the controller behaves identically to pre-v1.19 until explicitly enabled
  2. SIGUSR1 toggles fusion enabled/disabled without daemon restart (zero-downtime, proven pattern from v1.13)
  3. Health endpoint shows fusion state (enabled/disabled, active weights, which signal sources are contributing, fused RTT value)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 93 -> 94 -> 95 -> 96 -> 97

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 93. Reflector Quality Scoring | 0/2 | Not started | - |
| 94. OWD Asymmetric Detection | 0/2 | Not started | - |
| 95. IRTT Loss Alerts | 0/TBD | Not started | - |
| 96. Dual-Signal Fusion Core | 0/TBD | Not started | - |
| 97. Fusion Safety & Observability | 0/TBD | Not started | - |

### Completed Milestones

| Milestone                            | Phases | Plans | Status   | Shipped    |
| ------------------------------------ | ------ | ----- | -------- | ---------- |
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
| v1.5 Quality & Hygiene              | 27-30  | 8     | Complete | 2026-01-24 |
| v1.4 Observability                   | 25-26  | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening         | 21-24  | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish          | 16-20  | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality                    | 6-15   | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization        | 1-5    | 8     | Complete | 2026-01-13 |

**Total:** 92 phases complete, 188 plans across 19 milestones

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
