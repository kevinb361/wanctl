# Roadmap: wanctl

## Overview

wanctl v1.24 adds state machine hysteresis to eliminate GREEN/YELLOW flapping at the EWMA threshold boundary during prime-time DOCSIS load. Production data (2026-03-30) shows 30 GREEN<->YELLOW transitions per 120s window during evening peak -- the spike detector confirmation counter (v1.23.1) solved single-sample jitter, but EWMA oscillation at the exact `baseline + target_bloat_ms` boundary persists. Four phases: core hysteresis logic first (dwell timer + deadband on both DL and UL state machines), then configuration wiring (YAML + SIGUSR1 hot-reload + sensible defaults), then observability (health endpoint state + suppression logging), and finally production validation (deploy, confirm zero flapping alerts, verify genuine congestion still detected within latency budget).

## Domain Expertise

None

## Milestones

- v1.0 through v1.22: See MILESTONES.md (shipped)
- v1.23 Self-Optimizing Controller: Phases 117-120 (shipped 2026-03-27)
- v1.24 EWMA Boundary Hysteresis: Phases 121-124 (current)

## Phases

### v1.23 Self-Optimizing Controller (shipped)

- [x] **Phase 117: pyroute2 Netlink Backend** - Replace subprocess tc with pyroute2 netlink for CAKE bandwidth changes and per-tin stats readback
- [x] **Phase 118: Metrics Retention Strategy** - Configurable retention thresholds with tuner data availability validation
- [x] **Phase 119: Auto-Fusion Healing** - Automatic fusion suspend/recovery based on protocol correlation with Discord alerts
- [x] **Phase 120: Adaptive Rate Step Tuning** - Tuner learns optimal step_up, factor_down, green_cycles_required with oscillation lockout

### v1.24 EWMA Boundary Hysteresis

- [ ] **Phase 121: Core Hysteresis Logic** - Dwell timer and deadband margin on GREEN/YELLOW state transitions for both download and upload
- [ ] **Phase 122: Hysteresis Configuration** - YAML config, sensible defaults, and SIGUSR1 hot-reload for hysteresis parameters
- [ ] **Phase 123: Hysteresis Observability** - Health endpoint state exposure and transition suppression logging
- [ ] **Phase 124: Production Validation** - Deploy, confirm zero flapping, verify genuine congestion detection latency

## Phase Details

### Phase 121: Core Hysteresis Logic
**Goal**: The controller absorbs transient EWMA threshold crossings without triggering state transitions, so only sustained congestion causes GREEN->YELLOW
**Depends on**: Nothing (first phase of v1.24)
**Requirements**: HYST-01, HYST-02, HYST-03, HYST-04
**Success Criteria** (what must be TRUE):
  1. Controller remains in GREEN when delta briefly exceeds target_bloat_ms for fewer than N consecutive cycles (dwell timer absorbs transients)
  2. Controller transitions from YELLOW back to GREEN only when delta drops below (target_bloat_ms - deadband_ms), not at the exact threshold (split threshold prevents boundary oscillation)
  3. Dwell counter resets to zero whenever delta drops below threshold mid-dwell, so only uninterrupted above-threshold runs trigger YELLOW
  4. Upload state machine applies identical dwell timer and deadband logic as download (both directions protected from flapping)
**Plans:** 1 plan

Plans:
- [x] 121-01-PLAN.md -- TDD: Dwell timer + deadband margin in QueueController (adjust + adjust_4state)

### Phase 122: Hysteresis Configuration
**Goal**: Operators can tune hysteresis behavior via YAML config with sensible defaults that work without changes, and update parameters at runtime via SIGUSR1
**Depends on**: Phase 121
**Requirements**: CONF-01, CONF-02, CONF-03
**Success Criteria** (what must be TRUE):
  1. Operator can set dwell_cycles and deadband_ms under continuous_monitoring.thresholds in YAML and the controller applies them
  2. Sending SIGUSR1 to the daemon reloads hysteresis parameters from disk without service restart (consistent with existing dry_run/fusion/wan_state reload chain)
  3. A fresh install with no hysteresis config uses sensible defaults (dwell_cycles=3, deadband_ms=3.0) that eliminate flapping without masking genuine congestion
**Plans:** 2 plans

Plans:
- [ ] 122-01-PLAN.md -- Config parsing, SCHEMA validation, KNOWN_KEYS, WANController wiring, defaults
- [ ] 122-02-PLAN.md -- SIGUSR1 hot-reload method and main loop integration

### Phase 123: Hysteresis Observability
**Goal**: Operators can see hysteresis state in the health endpoint and identify suppressed transitions in logs without adding overhead to the control loop
**Depends on**: Phase 121
**Requirements**: OBSV-01, OBSV-02
**Success Criteria** (what must be TRUE):
  1. Health endpoint JSON includes hysteresis section with current dwell_counter value, configured deadband_margins, and cumulative transitions_suppressed count
  2. When the dwell timer absorbs a would-be GREEN->YELLOW transition, a log message appears indicating "transition suppressed, dwell N/M" (showing current count vs required)
  3. Suppressed transition count is visible in health endpoint for monitoring without log parsing
**Plans**: TBD

### Phase 124: Production Validation
**Goal**: Hysteresis is proven effective in production -- flapping is eliminated and genuine congestion detection latency remains acceptable
**Depends on**: Phase 121, Phase 122, Phase 123
**Requirements**: VALN-01, VALN-02
**Success Criteria** (what must be TRUE):
  1. During a prime-time evening window (7pm-11pm), zero flapping alerts fire (vs baseline of 1-3 alert pairs per evening)
  2. An RRUL stress test triggers YELLOW within 500ms of the no-hysteresis baseline (dwell_cycles=3 at 50ms = 150ms additional latency, well within budget)
  3. Health endpoint transitions_suppressed counter is non-zero, confirming hysteresis is actively absorbing transients
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 121 -> 122 -> 123 -> 124

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 121. Core Hysteresis Logic | 1/1 | Complete   | 2026-03-31 |
| 122. Hysteresis Configuration | 0/2 | Not started | - |
| 123. Hysteresis Observability | 0/TBD | Not started | - |
| 124. Production Validation | 0/TBD | Not started | - |

<details>
<summary>Previous Milestones (v1.0-v1.23)</summary>

| Milestone                            | Phases  | Plans | Status   | Completed  |
| ------------------------------------ | ------- | ----- | -------- | ---------- |
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

### Phase 111: Auto-Tuning Production Hardening -- Config bounds + SIGP-01 rate fix

**Goal:** Widen 4 tuning bounds stuck at limits and fix SIGP-01 outlier rate 60x underestimate from wrong denominator
**Requirements**: SIGP-01-FIX, BOUNDS-SPECTRUM, BOUNDS-ATT
**Depends on:** None (standalone hardening, applies to current production v1.20)
**Plans:** 4/4 plans complete

Plans:

- [x] 111-01-PLAN.md -- Config bounds update + SIGP-01 rate normalization fix with density-aware tests

</details>
