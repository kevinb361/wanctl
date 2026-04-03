# Roadmap: wanctl

## Overview

wanctl adaptive dual-WAN CAKE controller for MikroTik. Eliminates bufferbloat via queue tuning + intelligent WAN steering.

## Domain Expertise

None

## Milestones

- v1.0 through v1.23: See MILESTONES.md (shipped)
- v1.24 EWMA Boundary Hysteresis: Phases 121-124 (shipped 2026-04-02)
- v1.25 Reboot Resilience: Phase 125 (shipped 2026-04-02)
- v1.26 Tuning Validation: Phases 126-130 (shipped 2026-04-02)
- v1.27 Performance & QoS: Phases 131-136 (in progress)

## Phases

<details>
<summary>v1.24 EWMA Boundary Hysteresis (Phases 121-124) -- SHIPPED 2026-04-02</summary>

- [x] Phase 121: Core Hysteresis Logic -- dwell timer + deadband margin
- [x] Phase 122: Hysteresis Configuration -- YAML config, defaults, SIGUSR1 hot-reload
- [x] Phase 123: Hysteresis Observability -- health endpoint, transition suppression logging
- [x] Phase 124: Production Validation -- deploy, confirm zero flapping

</details>

<details>
<summary>v1.25 Reboot Resilience (Phase 125) -- SHIPPED 2026-04-02</summary>

- [x] Phase 125: Boot Resilience -- NIC tuning script, systemd dependency wiring, deploy.sh, dry-run validated

</details>

<details>
<summary>v1.26 Tuning Validation (Phases 126-130) -- SHIPPED 2026-04-02</summary>

- [x] Phase 126: Pre-Test Gate -- 5-point environment verification script
- [x] Phase 127: DL Parameter Sweep -- 9 DL params A/B tested, 6 changed
- [x] Phase 128: UL Parameter Sweep -- 3 UL params tested, 1 changed
- [x] Phase 129: CAKE RTT + Confirmation Pass -- rtt=40ms, 1 interaction flip caught
- [x] Phase 130: Production Config Commit -- config verified, docs updated

</details>

### v1.27 Performance & QoS (Phases 131-136)

- [x] **Phase 131: Cycle Budget Profiling** - Profile hot path under RRUL to identify subsystem bottlenecks
- [ ] **Phase 132: Cycle Budget Optimization** - Optimize hot path or adjust interval + regression indicator
- [ ] **Phase 133: Diffserv Bridge Audit** - Trace DSCP marks through L2 bridge path to diagnose tin separation failure
- [ ] **Phase 134: Diffserv Tin Separation** - Fix DSCP survival and automate bridge path validation
- [ ] **Phase 135: Upload Recovery Tuning** - A/B test UL step_up/factor_down on linux-cake and deploy winners
- [ ] **Phase 136: Hysteresis Observability** - Suppression rate monitoring, logging, and alerting for real congestion

## Phase Details

### Phase 131: Cycle Budget Profiling

**Goal**: Operator can pinpoint which subsystems cause 138% cycle budget overruns under RRUL load
**Depends on**: Nothing (first phase of v1.27)
**Requirements**: PERF-01
**Success Criteria** (what must be TRUE):

1. Operator can run profiling under RRUL load and see per-subsystem timing breakdown
2. The top 3 cycle-time consumers are identified with measured durations
3. A clear recommendation exists: optimize specific subsystem(s) or adjust cycle interval
   **Plans:** 2 plans
   Plans:

- [x] 131-01-PLAN.md -- Sub-timer instrumentation + health endpoint subsystem breakdown
- [x] 131-02-PLAN.md -- Production profiling runs, py-spy flamegraph, analysis document

### Phase 132: Cycle Budget Optimization

**Goal**: Controller runs within target cycle budget under sustained RRUL load with regression detection
**Depends on**: Phase 131
**Requirements**: PERF-02, PERF-03
**Success Criteria** (what must be TRUE):

1. Controller completes cycles within 50ms budget under RRUL load (or interval is adjusted with documented rationale)
2. Health endpoint shows cycle utilization percentage with configurable warning threshold
3. Operator is alerted (via health endpoint or logs) when utilization exceeds the configured threshold
   **Plans:** 2 plans
   Plans:

- [x] 132-01-PLAN.md -- Background RTT thread + persistent ThreadPoolExecutor + non-blocking measure_rtt()
- [x] 132-02-PLAN.md -- Health endpoint status field + cycle_budget_warning alert + SIGUSR1 reload

### Phase 133: Diffserv Bridge Audit

**Goal**: Operator knows exactly where DSCP marks are lost or preserved in the MikroTik-to-CAKE bridge path
**Depends on**: Nothing (independent of PERF work)
**Requirements**: QOS-01
**Success Criteria** (what must be TRUE):

1. Each hop in the DSCP path (MikroTik mangle -> bridge interface -> CAKE qdisc) has been tested with marked packets
2. The exact point where DSCP marks are lost or preserved is documented
3. A fix strategy is identified (bridge config, ethtool, tc filter, or other)
   **Plans:** 1 plan
   Plans:

- [x] 133-01-PLAN.md -- 3-point DSCP capture audit (tcpdump + tc tin stats) + analysis document

### Phase 134: Diffserv Tin Separation

**Goal**: CAKE tins correctly separate traffic by DSCP class and wanctl-check-cake validates it automatically
**Depends on**: Phase 133
**Requirements**: QOS-02, QOS-03
**Success Criteria** (what must be TRUE):

1. Download traffic shows differentiated tin distribution (not 100% BestEffort) via MikroTik prerouting DSCP marking or documented acceptance of current architecture
2. Per-tin CAKE stats (via health endpoint or wanctl-history --tins) show differentiated traffic distribution for upload direction
3. `wanctl-check-cake` includes a DSCP tin distribution check that validates non-trivial tin usage
   **Plans:** 2 plans
   Plans:

- [ ] 134-01-PLAN.md -- MikroTik prerouting DSCP SET DL rules via REST API + tin separation validation
- [ ] 134-02-PLAN.md -- wanctl-check-cake tin distribution check (TDD, unit tests)

**Phase 133 findings (scope input):**

- Upload DSCP path works correctly (tins separate). Download has architectural gap: CAKE on ens17 sees packets BEFORE MikroTik marks them.
- Key options: MikroTik prerouting DSCP for download (medium), accept download BestEffort (low), wanctl-check-cake extension (low, QOS-03).
- iperf3 --dscp works on data stream (not control); use Python sockets or filter data stream for testing.
- Full analysis: `.planning/phases/133-diffserv-bridge-audit/133-ANALYSIS.md`

### Phase 135: Upload Recovery Tuning

**Goal**: UL parameters are A/B validated on linux-cake transport for faster recovery under bidirectional load
**Depends on**: Nothing (independent, but uses same flent methodology as v1.26)
**Requirements**: TUNE-01, TUNE-02
**Success Criteria** (what must be TRUE):

1. UL step_up and factor_down have been A/B tested via RRUL flent with documented per-test metrics
2. Winning UL parameters are deployed to production config with validation dates
3. UL throughput under RRUL is improved relative to v1.26 baseline (10% of ceiling target exceeded)
   **Plans:** 2 plans
   Plans:

- [x] 135-01-PLAN.md -- Gate check, baseline, and full matrix testing (3 step_up x 2 factor_down = 18 flent runs)
- [x] 135-02-PLAN.md -- Analysis, winner selection, production deploy, and documentation

### Phase 136: Hysteresis Observability

**Goal**: Operator can monitor dwell/deadband suppression rates during real congestion to detect potential false negatives
**Depends on**: Nothing (builds on v1.24 hysteresis infrastructure)
**Requirements**: HYST-01, HYST-02, HYST-03
**Success Criteria** (what must be TRUE):

1. Health endpoint exposes per-minute suppression rate with windowed counters (not just cumulative total)
2. Controller logs periodic suppression rate at INFO level during active congestion events
3. Discord alert fires when suppression rate exceeds configurable threshold
4. Operator can distinguish healthy suppression (jitter filtering) from excessive suppression (missed congestion)
   **Plans:** 2 plans
   Plans:

- [x] 136-01-PLAN.md -- Windowed suppression counter + health endpoint fields + periodic congestion logging
- [x] 136-02-PLAN.md -- hysteresis_suppression alert via AlertEngine + SIGUSR1 threshold reload

## Progress

| Phase                          | Plans Complete | Status      | Completed  |
| ------------------------------ | -------------- | ----------- | ---------- |
| 131. Cycle Budget Profiling    | 2/2            | Complete    | 2026-04-03 |
| 132. Cycle Budget Optimization | 2/2            | Complete    | 2026-04-03 |
| 133. Diffserv Bridge Audit     | 1/1            | Complete    | 2026-04-03 |
| 134. Diffserv Tin Separation   | 0/2            | Complete    | 2026-04-03 |
| 135. Upload Recovery Tuning    | 2/2 | Complete    | 2026-04-03 |
| 136. Hysteresis Observability  | 2/2 | Complete   | 2026-04-03 |

<details>
<summary>Previous Milestones (v1.0-v1.26)</summary>

| Milestone                            | Phases  | Plans | Status   | Completed  |
| ------------------------------------ | ------- | ----- | -------- | ---------- |
| v1.26 Tuning Validation              | 126-130 | 5     | Complete | 2026-04-02 |
| v1.25 Reboot Resilience              | 125     | 2     | Complete | 2026-04-02 |
| v1.24 EWMA Boundary Hysteresis       | 121-124 | 6     | Complete | 2026-04-02 |
| v1.23 Self-Optimizing Controller     | 117-120 | 8     | Complete | 2026-03-27 |
| v1.22 Full System Audit              | 112-116 | 16+   | Complete | 2026-03-26 |
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

</details>
