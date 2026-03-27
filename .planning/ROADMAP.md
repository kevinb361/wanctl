# Roadmap: wanctl

## Overview

wanctl v1.23 completes the self-optimizing controller vision by extending adaptive tuning to response parameters (step_up, factor_down, green_cycles), automating fusion healing for ICMP/IRTT path divergence, replacing subprocess tc calls with pyroute2 netlink for 10x latency reduction, adding Prometheus/Grafana observability, and making metrics.db retention configurable. Five phases ordered by technical uncertainty and dependency: netlink backend first (highest uncertainty, fully independent), retention second (prerequisite for Prometheus aggressive mode), fusion healing third (addresses known ATT production issue), adaptive rate steps fourth (highest blast radius, needs stable foundation), Prometheus last (purely additive, benefits from all prior phases).

## Domain Expertise

None

## Milestones

- v1.0 through v1.22: See MILESTONES.md (shipped)
- v1.23 Self-Optimizing Controller: Phases 117-121 (current)

## Phases

### v1.22 Remaining (Full System Audit)

- [x] **Phase 116: Test & Documentation Hygiene** - Test quality audit and fixes, docs freshness review, container script archival, audit findings summary

### v1.23 Self-Optimizing Controller

- [ ] **Phase 117: pyroute2 Netlink Backend** - Replace subprocess tc with pyroute2 netlink for CAKE bandwidth changes and per-tin stats readback
- [ ] **Phase 118: Metrics Retention Strategy** - Configurable retention thresholds with tuner data availability validation
- [ ] **Phase 119: Auto-Fusion Healing** - Automatic fusion suspend/recovery based on protocol correlation with Discord alerts
- [ ] **Phase 120: Adaptive Rate Step Tuning** - Tuner learns optimal step_up, factor_down, green_cycles_required with oscillation lockout
- [ ] **Phase 121: Prometheus/Grafana Export** - Prometheus metrics on port 9103 with Grafana dashboard and per-tin CAKE labels

## Phase Details

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
   **Plans**: 3 plans

Plans:

- [x] 116-01-PLAN.md -- Test quality audit scan + fix assertion-free and tautological tests
- [x] 116-02-PLAN.md -- CONFIG_SCHEMA.md alignment, docs VM updates, container script archival
- [x] 116-03-PLAN.md -- Capstone v1.22 audit findings summary (aggregates all phases 112-116)

### Phase 117: pyroute2 Netlink Backend

**Goal**: tc calls in the 50ms hot loop use kernel netlink instead of subprocess fork/exec, reclaiming ~5ms/cycle
**Depends on**: Nothing (first phase, fully independent)
**Requirements**: NLNK-01, NLNK-02, NLNK-03, NLNK-04, NLNK-05
**Success Criteria** (what must be TRUE):

1. Operator can set `transport: "linux-cake-netlink"` in YAML and the controller uses pyroute2 for all tc operations
2. CAKE bandwidth changes via netlink produce identical queue state to subprocess tc (verified by tc -j readback)
3. Per-tin CAKE stats (bytes, packets, drops per tin) are available via netlink without subprocess tc -j qdisc show
4. If pyroute2 netlink fails, the controller falls back to subprocess tc and logs a warning (no service interruption)
5. The IPRoute connection persists for daemon lifetime and automatically reconnects on socket death without cycle disruption
   **Plans**: TBD

### Phase 118: Metrics Retention Strategy

**Goal**: Operators can configure metrics.db retention thresholds and the system enforces that tuner data availability is never silently broken
**Depends on**: Nothing (independent, but ships before Prometheus for config design coordination)
**Requirements**: RETN-01, RETN-02, RETN-03
**Success Criteria** (what must be TRUE):

1. Operator can configure retention thresholds (raw_age_seconds, aggregate_1m_age_seconds, aggregate_5m_age_seconds) via storage.retention YAML section
2. Config validation rejects any retention config where aggregate_1m_age_seconds is less than tuning.lookback_hours \* 3600, with a clear error message
3. Operator can enable prometheus_compensated mode for aggressive local retention (24-48h) when long-term TSDB is available
   **Plans**: 2 plans

Plans:

- [ ] 118-01-PLAN.md -- Config schema, get_storage_config() retention section, cross-section validation, config-driven downsampler thresholds
- [ ] 118-02-PLAN.md -- Daemon wiring (autorate + steering), per-granularity cleanup, SIGUSR1 reload, example configs

### Phase 119: Auto-Fusion Healing

**Goal**: The controller automatically manages fusion state based on protocol correlation, eliminating manual SIGUSR1 toggle for ICMP/IRTT path divergence
**Depends on**: Nothing (independent, ships after Phase 117 for sequential validation)
**Requirements**: FUSE-01, FUSE-02, FUSE-03, FUSE-04, FUSE-05
**Success Criteria** (what must be TRUE):

1. When ICMP/IRTT protocol correlation drops below threshold for a sustained period, the controller auto-suspends fusion and sends a Discord alert
2. When protocol correlation recovers, the controller transitions through RECOVERING to ACTIVE and sends a Discord alert
3. The health endpoint shows current fusion heal state (ACTIVE/SUSPENDED/RECOVERING) and recent correlation history
4. While fusion is suspended by the healer, the TuningEngine cannot modify fusion_icmp_weight (parameter is locked)
   **Plans**: TBD

### Phase 120: Adaptive Rate Step Tuning

**Goal**: The tuning engine learns optimal response parameters from production episodes, completing the self-optimizing controller vision
**Depends on**: Phase 118 (retention must guarantee 1m data availability for strategy lookback)
**Requirements**: RTUN-01, RTUN-02, RTUN-03, RTUN-04, RTUN-05
**Success Criteria** (what must be TRUE):

1. The tuner analyzes production recovery episodes and adjusts step_up_mbps toward faster recovery without overshoot
2. The tuner analyzes congestion resolution speed and adjusts factor_down toward faster resolution without excessive bandwidth sacrifice
3. The tuner analyzes step-up re-trigger rates and adjusts green_cycles_required to prevent premature recovery
4. When transitions/minute exceeds the oscillation threshold, all response parameters are frozen and a Discord alert fires
5. Response tuning is disabled by default via exclude_params and must be explicitly opted in (matching existing tuning graduation pattern)
   **Plans**: TBD

### Phase 121: Prometheus/Grafana Export

**Goal**: Operators can view live wanctl metrics in Grafana dashboards backed by Prometheus, with zero overhead added to the 50ms control loop
**Depends on**: Phase 118 (prometheus_compensated retention mode depends on retention config design)
**Requirements**: OBSV-01, OBSV-02, OBSV-03, OBSV-04
**Success Criteria** (what must be TRUE):

1. Prometheus can scrape wanctl metrics from port 9103 and display them in Grafana using the committed dashboard JSON
2. Per-tin CAKE metrics are exported with stable labels (wan, direction, tin) enabling per-traffic-class Grafana panels
3. The core wanctl daemon starts and operates normally without prometheus_client installed (optional dependency)
4. The /metrics endpoint adds zero overhead to the 50ms control loop (CustomCollector reads state on scrape, not push from cycle)
   **Plans**: TBD
   **UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 116 -> 117 -> 118 -> 119 -> 120 -> 121

| Phase                             | Plans Complete | Status      | Completed  |
| --------------------------------- | -------------- | ----------- | ---------- |
| 116. Test & Documentation Hygiene | 3/3            | Complete    | 2026-03-26 |
| 117. pyroute2 Netlink Backend     | 2/2 | Complete    | 2026-03-27 |
| 118. Metrics Retention Strategy   | 0/2            | Not started | -          |
| 119. Auto-Fusion Healing          | 0/TBD          | Not started | -          |
| 120. Adaptive Rate Step Tuning    | 0/TBD          | Not started | -          |
| 121. Prometheus/Grafana Export    | 0/TBD          | Not started | -          |

<details>
<summary>Previous Milestones (v1.0-v1.22)</summary>

| Milestone                            | Phases  | Plans | Status   | Completed  |
| ------------------------------------ | ------- | ----- | -------- | ---------- |
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
