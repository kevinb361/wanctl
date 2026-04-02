# Roadmap: wanctl

## Overview

wanctl adaptive dual-WAN CAKE controller for MikroTik. Eliminates bufferbloat via queue tuning + intelligent WAN steering.

## Domain Expertise

None

## Milestones

- v1.0 through v1.23: See MILESTONES.md (shipped)
- v1.24 EWMA Boundary Hysteresis: Phases 121-124 (shipped 2026-04-02)
- v1.25 Reboot Resilience: Phase 125 (shipped 2026-04-02)
- v1.26 Tuning Validation: Phases 126-130 (in progress)

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

**Known gaps (deferred to v1.26):**

- Phase 126 (Boot Validation CLI) moved to v1.26
- BOOT-04 (full reboot E2E test) requires physical access

</details>

### v1.26 Tuning Validation (Phases 126-130)

**Milestone Goal:** Re-test all tuning parameters on linux-cake transport to validate or re-tune production values after REST-to-linux-cake backend switch.

- [ ] **Phase 126: Pre-Test Gate** - Verify linux-cake transport active, CAKE qdiscs on VM, no double-shaping from MikroTik
- [x] **Phase 127: DL Parameter Sweep** - A/B test 9 download parameters sequentially with RRUL methodology
- [ ] **Phase 128: UL Parameter Sweep** - A/B test 3 upload parameters sequentially with RRUL methodology
- [ ] **Phase 129: CAKE RTT + Confirmation Pass** - Test CAKE rtt parameter, then re-test response group for interaction effects
- [ ] **Phase 130: Production Config Commit** - Update spectrum.yaml with full validated parameter set

## Phase Details

### Phase 126: Pre-Test Gate

**Goal**: Confirm the test environment is correct before any tuning begins -- linux-cake transport active, CAKE qdiscs on all 4 bridge NICs, and no double-shaping from MikroTik router
**Depends on**: Nothing (first phase of v1.26)
**Requirements**: GATE-01, GATE-02, GATE-03
**Success Criteria** (what must be TRUE):

1. `tc -s qdisc show` on cake-shaper VM reports CAKE qdiscs on ens16, ens17, ens27, ens28
2. MikroTik `/queue/type` and `/queue/tree` show no active CAKE queues on Spectrum WAN
3. A wanctl rate change (e.g., SIGUSR1 or manual config edit) produces a visible bandwidth change in `tc -s qdisc show` output
   **Plans**: 1 plan

Plans:

- [x] 126-01-PLAN.md -- Gate script + production validation

### Phase 127: DL Parameter Sweep

**Goal**: Determine optimal download parameters on linux-cake transport by A/B testing each of the 9 DL tunables one at a time
**Depends on**: Phase 126
**Requirements**: TUNE-01, RSLT-01
**Success Criteria** (what must be TRUE):

1. Each of the 9 DL parameters has been tested with at least 2 values (current vs candidate) using RRUL flent against Dallas netperf server
2. Each test has a documented winner with metrics delta (throughput, latency percentiles) and test conditions (time of day, cable plant load)
3. Winners are applied cumulatively -- each new test runs with all prior winners in place
4. All 9 DL results recorded in a findings doc under `.planning/`
   **Plans**: 1 plan

Plans:

- [x] 127-01-PLAN.md -- Sequential A/B test of 9 DL parameters with RRUL flent

### Phase 128: UL Parameter Sweep

**Goal**: Determine optimal upload parameters on linux-cake transport by A/B testing each of the 3 UL tunables one at a time
**Depends on**: Phase 127
**Requirements**: TUNE-02
**Success Criteria** (what must be TRUE):

1. Each of the 3 UL parameters has been tested with at least 2 values using RRUL flent against Dallas netperf server
2. Each test has a documented winner with metrics delta and test conditions
3. All 3 UL results recorded alongside DL results in the findings doc
   **Plans**: TBD

### Phase 129: CAKE RTT + Confirmation Pass

**Goal**: Test CAKE rtt parameter and re-test the response group (factor_down_yellow, factor_down, step_up_mbps) with all winners in place to check for interaction effects
**Depends on**: Phase 128
**Requirements**: TUNE-03, TUNE-04
**Success Criteria** (what must be TRUE):

1. CAKE rtt tested (50ms vs 100ms) with RRUL flent and winner documented
2. Response group (factor_down_yellow, factor_down, step_up_mbps) re-tested with full winner set to confirm no interaction regressions
3. Confirmation results match or improve upon Phase 127 individual winners -- any regressions investigated and resolved
   **Plans**: TBD

### Phase 130: Production Config Commit

**Goal**: Update production spectrum.yaml with the complete validated parameter set from all testing phases
**Depends on**: Phase 129
**Requirements**: RSLT-02
**Success Criteria** (what must be TRUE):

1. spectrum.yaml on cake-shaper updated with all validated winners from Phases 127-129
2. Config diff reviewed -- every changed value traceable to a specific A/B test result
3. wanctl service restarted and confirmed healthy with new config (health endpoint returns 200, no error logs)
   **Plans**: TBD

## Progress

**Execution Order:** Phases 126 -> 127 -> 128 -> 129 -> 130

| Phase                             | Plans Complete | Status      | Completed  |
| --------------------------------- | -------------- | ----------- | ---------- |
| 126. Pre-Test Gate                | 1/1            | Complete    | 2026-04-02 |
| 127. DL Parameter Sweep           | 1/1            | Complete    | 2026-04-02 |
| 128. UL Parameter Sweep           | 0/TBD          | Not started | -          |
| 129. CAKE RTT + Confirmation Pass | 0/TBD          | Not started | -          |
| 130. Production Config Commit     | 0/TBD          | Not started | -          |

<details>
<summary>Previous Milestones (v1.0-v1.25)</summary>

| Milestone                            | Phases  | Plans | Status   | Completed  |
| ------------------------------------ | ------- | ----- | -------- | ---------- |
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
