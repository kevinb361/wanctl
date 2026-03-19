# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production. A TUI dashboard provides real-time operational visibility. Proactive alerting notifies operators of congestion, steering, connectivity, and anomaly events via Discord. Operator-facing CLI tools validate configs offline and audit router queue state. CAKE parameter optimization and bufferbloat benchmarking provide a complete operator feedback loop. RTT signal processing (Hampel filtering, jitter/variance EWMA, confidence scoring) and IRTT UDP measurements enrich the primary ICMP control loop. Dual-signal fusion combines weighted ICMP + IRTT RTT for congestion control input, with reflector quality scoring, OWD asymmetry detection, and IRTT loss alerting.

## Domain Expertise

None

## Milestones

### Active

- **v1.20 Adaptive Tuning** - Phases 98-102 (in progress)

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

## v1.20 Adaptive Tuning

**Milestone Goal:** Make wanctl a self-optimizing controller that learns optimal parameters from its own production metrics, with conservative safety bounds. Zero new dependencies -- stdlib statistics + existing SQLite infrastructure.

### Phases

- [ ] **Phase 98: Tuning Foundation** - Framework, models, config, enable/disable, health endpoint, SQLite persistence
- [ ] **Phase 99: Congestion Threshold Calibration** - Derive target_bloat_ms and warn_bloat_ms from RTT delta percentiles
- [ ] **Phase 100: Safety and Revert Detection** - Monitor post-adjustment congestion rate and auto-revert on degradation
- [x] **Phase 101: Signal Processing Tuning** - Optimize Hampel sigma/window and EWMA alpha per-WAN from metrics
- [ ] **Phase 102: Advanced Tuning** - Adapt fusion weights, reflector scoring, baseline bounds, and expose tuning history

### Phase Details

### Phase 98: Tuning Foundation

**Goal**: Operators can enable a tuning engine that safely analyzes per-WAN metrics on an hourly cadence with full observability
**Depends on**: Nothing (first phase of v1.20)
**Requirements**: TUNE-01, TUNE-02, TUNE-03, TUNE-04, TUNE-05, TUNE-06, TUNE-07, TUNE-08, TUNE-09, TUNE-10
**Success Criteria** (what must be TRUE):

1. Operator can set `tuning.enabled: false` in YAML and the daemon starts with zero tuning behavior; toggling to true via SIGUSR1 activates tuning without restart
2. Health endpoint `/health` shows a `tuning` section with enabled state, last_run timestamp, parameter names with current values and safety bounds, and recent adjustment history
3. Tuning runs once per hourly maintenance window (not per-cycle), analyzes each WAN independently, and skips analysis when less than 1 hour of metrics data is available
4. Every adjustment is clamped to 10% max change from current value, logged with old/new/rationale, and persisted to SQLite for historical review
5. Each tunable parameter has operator-configurable min/max safety bounds in YAML that the engine never exceeds
   **Plans:** 3 plans
   Plans:

- [ ] 098-01-PLAN.md -- Models, config parsing, SQLite schema, strategy protocol
- [ ] 098-02-PLAN.md -- Analyzer (per-WAN query), applier (bounds, persist, log)
- [ ] 098-03-PLAN.md -- Daemon wiring (maintenance window, SIGUSR1, health endpoint, example configs)

### Phase 99: Congestion Threshold Calibration

**Goal**: Controller automatically derives congestion thresholds from observed RTT delta distributions rather than static config values
**Depends on**: Phase 98
**Requirements**: CALI-01, CALI-02, CALI-03, CALI-04
**Success Criteria** (what must be TRUE):

1. `target_bloat_ms` converges toward the p75 of GREEN-state RTT delta distribution over successive hourly tuning cycles
2. `warn_bloat_ms` converges toward the p90 of GREEN-state RTT delta distribution over successive hourly tuning cycles
3. Threshold derivation uses a 24-hour lookback window that captures full diurnal patterns (day/evening/night traffic)
4. When a parameter's coefficient of variation drops below a configurable threshold, the engine detects convergence and stops adjusting that parameter
   **Plans:** 2 plans
   Plans:

- [ ] 099-01-PLAN.md -- Strategy functions (calibrate_target_bloat, calibrate_warn_bloat) + convergence detection + tests (TDD)
- [ ] 099-02-PLAN.md -- Wire strategies into maintenance loop + integration tests

### Phase 100: Safety and Revert Detection

**Goal**: Controller automatically detects when a tuning adjustment causes degradation and reverts to previous values
**Depends on**: Phase 98
**Requirements**: SAFE-01, SAFE-02, SAFE-03
**Success Criteria** (what must be TRUE):

1. After each parameter adjustment, the system monitors congestion rate over a defined observation window and compares to pre-adjustment baseline
2. When post-adjustment congestion rate increases beyond a threshold, the system automatically reverts to the previous parameter values and logs the revert with reason
3. After a revert, a configurable hysteresis cooldown locks that parameter category from further tuning attempts, preventing revert oscillation
   **Plans:** 2 plans
   Plans:

- [ ] 100-01-PLAN.md -- Safety module (congestion rate, revert detection, hysteresis lock) + revert persistence (TDD)
- [ ] 100-02-PLAN.md -- Daemon wiring (maintenance loop, WANController state, health endpoint)

### Phase 101: Signal Processing Tuning

**Goal**: Signal processing parameters (Hampel filter, EWMA) are optimized per-WAN from actual noise characteristics
**Depends on**: Phase 98, Phase 100
**Requirements**: SIGP-01, SIGP-02, SIGP-03, SIGP-04
**Success Criteria** (what must be TRUE):

1. Hampel sigma threshold converges toward a per-WAN optimum derived from outlier rate analysis (targeting a noise-appropriate outlier rejection rate)
2. Hampel window size is tuned per-WAN based on autocorrelation analysis of RTT samples
3. Load EWMA alpha is tuned from settling time analysis to match each WAN's latency dynamics
4. Signal chain parameters are tuned bottom-up (signal processing first, then EWMA, then thresholds) with one layer per tuning cycle to isolate effects
   **Plans:** 2 plans
   Plans:

- [x] 101-01-PLAN.md -- Signal processing strategy functions (hampel sigma, hampel window, EWMA alpha) + unit tests
- [x] 101-02-PLAN.md -- Layer rotation wiring, applier extension, maintenance loop integration

### Phase 102: Advanced Tuning

**Goal**: Cross-signal parameters and operational bounds are self-adjusted, and operators can review all tuning history
**Depends on**: Phase 98, Phase 100, Phase 101
**Requirements**: ADVT-01, ADVT-02, ADVT-03, ADVT-04
**Success Criteria** (what must be TRUE):

1. Fusion ICMP/IRTT weight is adapted based on per-signal reliability scoring (signals with lower variance or fewer anomalies get higher weight)
2. Reflector `min_score` threshold is tuned from observed success rate distribution so deprioritization matches actual reflector reliability
3. Baseline RTT bounds are auto-adjusted from p5/p95 of observed baseline history, preventing false baseline drift alerts
4. `wanctl-history --tuning` displays tuning adjustment history with WAN name, parameter, old/new values, rationale, and time-range filtering
   **Plans:** 3 plans
   Plans:

- [ ] 102-01-PLAN.md -- Advanced strategy functions (fusion weight, reflector min_score, baseline bounds) + unit tests (TDD)
- [ ] 102-02-PLAN.md -- CLI query_tuning_params reader + --tuning flag/formatters in history.py (TDD)
- [ ] 102-03-PLAN.md -- Wiring: ADVANCED_LAYER in rotation, applier extension, current_params extension

### Phase 103: Fix fusion baseline deadlock

**Goal**: Baseline EWMA uses ICMP-only signal (not fused RTT) to prevent IRTT path divergence from freezing or corrupting baseline
**Requirements**: FBLK-01, FBLK-02, FBLK-03, FBLK-04, FBLK-05
**Depends on:** Phase 96 (introduced the bug), independent of Phase 102
**Plans:** 1 plan
**Success Criteria** (what must be TRUE):

1. Baseline EWMA receives ICMP-only filtered_rtt, never the fused signal
2. Load EWMA receives fused RTT for enhanced congestion detection
3. When IRTT diverges from ICMP (ATT: 43ms vs 29ms), baseline still updates during idle
4. Fusion-disabled behavior is identical to pre-fix
5. Baseline freeze gate uses icmp_filtered_rtt vs baseline_rtt delta

Plans:

- [ ] 103-01-PLAN.md -- TDD: Tests for FBLK-01..05 + signal path split fix in autorate_continuous.py

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

| Milestone                            | Phases | Plans | Status      | Shipped    |
| ------------------------------------ | ------ | ----- | ----------- | ---------- |
| v1.20 Adaptive Tuning                | 98-102 | TBD   | In progress | -          |
| v1.19 Signal Fusion                  | 93-97  | 9     | Complete    | 2026-03-18 |
| v1.18 Measurement Quality            | 88-92  | 10    | Complete    | 2026-03-17 |
| v1.17 CAKE Optimization & Bench.     | 84-87  | 8     | Complete    | 2026-03-16 |
| v1.16 Validation & Op. Confidence    | 81-83  | 4     | Complete    | 2026-03-13 |
| v1.15 Alerting & Notifications       | 76-80  | 10    | Complete    | 2026-03-12 |
| v1.14 Operational Visibility         | 73-75  | 7     | Complete    | 2026-03-11 |
| v1.13 Legacy Cleanup & Feature Grad. | 67-72  | 10    | Complete    | 2026-03-11 |
| v1.12 Deployment & Code Health       | 62-66  | 7     | Complete    | 2026-03-11 |
| v1.11 WAN-Aware Steering             | 58-61  | 8     | Complete    | 2026-03-10 |
| v1.10 Architectural Review Fixes     | 50-57  | 15    | Complete    | 2026-03-09 |
| v1.9 Performance & Efficiency        | 47-49  | 6     | Complete    | 2026-03-07 |
| v1.8 Resilience & Robustness         | 43-46  | 8     | Complete    | 2026-03-06 |
| v1.7 Metrics History                 | 38-42  | 8     | Complete    | 2026-01-25 |
| v1.6 Test Coverage 90%               | 31-37  | 17    | Complete    | 2026-01-25 |
| v1.5 Quality & Hygiene               | 27-30  | 8     | Complete    | 2026-01-24 |
| v1.4 Observability                   | 25-26  | 4     | Complete    | 2026-01-24 |
| v1.3 Reliability & Hardening         | 21-24  | 5     | Complete    | 2026-01-21 |
| v1.2 Configuration & Polish          | 16-20  | 5     | Complete    | 2026-01-14 |
| v1.1 Code Quality                    | 6-15   | 30    | Complete    | 2026-01-14 |
| v1.0 Performance Optimization        | 1-5    | 8     | Complete    | 2026-01-13 |
