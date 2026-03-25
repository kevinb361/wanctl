# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production. A TUI dashboard provides real-time operational visibility. Proactive alerting notifies operators of congestion, steering, connectivity, and anomaly events via Discord. Operator-facing CLI tools validate configs offline and audit router queue state. CAKE parameter optimization and bufferbloat benchmarking provide a complete operator feedback loop. RTT signal processing (Hampel filtering, jitter/variance EWMA, confidence scoring) and IRTT UDP measurements enrich the primary ICMP control loop. Dual-signal fusion combines weighted ICMP + IRTT RTT for congestion control input, with reflector quality scoring, OWD asymmetry detection, and IRTT loss alerting. Adaptive tuning self-optimizes controller parameters from production metrics via 4-layer rotation with safety revert detection.

## Domain Expertise

None

## Phases

- [x] **Phase 104: IOMMU Verification Gate** - Confirm PCIe passthrough feasibility for all 4 target NICs on odin (completed 2026-03-24)
- [x] **Phase 105: LinuxCakeBackend Core** - Drop-in backend using tc for bandwidth control and stats collection (completed 2026-03-24)
- [x] **Phase 106: CAKE Optimization Parameters** - Full CAKE feature set (split-gso, ECN, ack-filter, ingress, overhead, memlimit, rtt) (completed 2026-03-24)
- [x] **Phase 107: Config & Factory Wiring** - Transport selection, factory function, and config validation for linux-cake (completed 2026-03-25)
- [x] **Phase 108: Steering Dual-Backend & Observability** - Steering uses local CAKE stats + remote mangle rules, per-tin stats in health/history (completed 2026-03-25)
- [x] **Phase 109: VM Infrastructure & Bridges** - Proxmox VM with VFIO passthrough, transparent bridges, CAKE on member port egress, management VLAN (completed 2026-03-25)
- [x] **Phase 110: Production Cutover** - Staged migration (ATT first), rollback drill, benchmark validation (completed 2026-03-25)

## Phase Details

### Phase 104: IOMMU Verification Gate

**Goal**: Confirm the CAKE offload architecture is physically feasible before any code work begins
**Depends on**: Nothing (prerequisite gate)
**Requirements**: INFR-01
**Success Criteria** (what must be TRUE):

1. All 4 target NICs (2x i210, 2x i350) confirmed in separate IOMMU groups on odin
2. VFIO passthrough feasibility documented with exact PCI addresses and group numbers
   **Plans**: 1 plan
   Plans:
   - [x] 104-01-PLAN.md -- IOMMU verification documentation and human confirmation gate

### Phase 105: LinuxCakeBackend Core

**Goal**: A complete RouterBackend implementation that controls CAKE via local tc commands with verified parameter correctness
**Depends on**: Phase 104
**Requirements**: BACK-01, BACK-02, BACK-03, BACK-04
**Success Criteria** (what must be TRUE):

1. LinuxCakeBackend.set_bandwidth() changes CAKE rate limits via `tc qdisc change` and returns success/failure
2. LinuxCakeBackend.get_stats() returns parsed queue statistics (drops, delay, flows) from `tc -s -j qdisc show`
3. After `tc qdisc replace`, LinuxCakeBackend reads back params via `tc -j qdisc show` and verifies diffserv mode, overhead, and bandwidth match expectations
4. Per-tin statistics (Voice/Video/BE/Bulk -- drops, delays, flows per tin) are parsed and available from get_stats()
   **Plans**: 1 plan
   Plans:
   - [x] 105-01-PLAN.md -- LinuxCakeBackend implementation + comprehensive tests

### Phase 106: CAKE Optimization Parameters

**Goal**: CAKE qdiscs are configured with all performance-critical options per link type, incorporating ecosystem best practices
**Depends on**: Phase 105
**Requirements**: CAKE-01, CAKE-02, CAKE-03, CAKE-05, CAKE-06, CAKE-08, CAKE-09, CAKE-10
**Success Criteria** (what must be TRUE):

1. Upload CAKE includes split-gso and ack-filter; download CAKE includes split-gso, ingress keyword, and ecn
2. Per-link overhead is configured correctly (docsis for Spectrum, bridged-ptm for ATT) with explicit MPU
3. Memory limits are bounded via memlimit parameter on all CAKE instances
4. CAKE rtt parameter is configured per-link with a tunable default (candidate for adaptive tuning integration)
5. `tc qdisc replace` command strings match the ecosystem-validated patterns (no nat, no wash, no autorate-ingress)
   **Plans**: 2 plans
   Plans:
   - [x] 106-01-PLAN.md -- CakeParamsBuilder module with direction-aware defaults and config overrides
   - [x] 106-02-PLAN.md -- Extend initialize_cake for overhead_keyword support + integration tests

### Phase 107: Config & Factory Wiring

**Goal**: Operators can select linux-cake transport in YAML config and the system wires the correct backend
**Depends on**: Phase 105
**Requirements**: CONF-01, CONF-02, CONF-04
**Success Criteria** (what must be TRUE):

1. Setting `transport: "linux-cake"` in YAML config with bridge interface names creates a LinuxCakeBackend
2. Factory function selects LinuxCakeBackend vs RouterOS based on transport config without WANController changes
3. `wanctl-check-config` validates linux-cake transport settings and checks that specified interfaces exist
   **Plans**: 2 plans
   Plans:
   - [x] 107-01-PLAN.md -- Factory wiring: from_config direction parameter + get_backend linux-cake branch
   - [x] 107-02-PLAN.md -- check-config: validate_linux_cake validator + KNOWN_AUTORATE_PATHS update

### Phase 108: Steering Dual-Backend & Observability

**Goal**: Steering daemon operates with split data sources (local CAKE stats, remote mangle rules) and per-tin stats are operator-visible
**Depends on**: Phase 105, Phase 107
**Requirements**: CONF-03, CAKE-07
**Success Criteria** (what must be TRUE):

1. Steering daemon reads CAKE stats from LinuxCakeBackend (local tc) while controlling mangle rules via REST on MikroTik
2. Per-tin statistics (Voice/Video/BE/Bulk drops, delays, flows) are visible in the health endpoint
3. Per-tin statistics are queryable via `wanctl-history` CLI
   **Plans**: 2 plans
   Plans:
   - [x] 108-01-PLAN.md -- Dual-backend CakeStatsReader + per-tin health endpoint
   - [x] 108-02-PLAN.md -- Per-tin metrics storage + wanctl-history --tins CLI

### Phase 109: VM Infrastructure & Bridges

**Goal**: A production-ready Debian 12 VM on odin with passthrough NICs, transparent bridges, and CAKE initialized on bridge member port egress
**Depends on**: Phase 104
**Requirements**: INFR-02, INFR-03, INFR-04, INFR-05, INFR-06
**Success Criteria** (what must be TRUE):

1. Proxmox VM runs Debian 12 with 4 VFIO-passthrough NICs (2x i210, 2x i350) visible inside the guest
2. Transparent L2 bridges (br-spectrum, br-att) forward traffic with STP disabled and forward_delay=0
3. CAKE qdisc is attached and shaping traffic on bridge member port egress via `tc qdisc replace` (not systemd-networkd CAKE section)
4. systemd-networkd configuration persists bridges and interfaces across reboots (CAKE setup owned by wanctl startup, not systemd)
5. VLAN 110 management interface provides SSH, health endpoint, ICMP, and IRTT connectivity
   **Plans**: 4 plans
   Plans:
   - [x] 109-01-PLAN.md -- VFIO host prep: kernel pin, modules, modprobe, reboot verification
   - [x] 109-02-PLAN.md -- VM creation, Debian 12 install, NIC passthrough, interface discovery
   - [x] 109-03-PLAN.md -- Bridge configuration with systemd-networkd, reboot persistence
   - [x] 109-04-PLAN.md -- wanctl deployment, CAKE initialization verification

### Phase 110: Production Cutover

**Goal**: Both WAN links are shaped by the Linux VM with validated performance improvement and tested rollback
**Depends on**: Phase 106, Phase 107, Phase 108, Phase 109
**Requirements**: CUTR-01, CUTR-02, CUTR-03, CUTR-04, CUTR-05
**Success Criteria** (what must be TRUE):

1. MikroTik queue tree entries are disabled (not deleted) and can be re-enabled for rollback
2. Physical cabling routes both modems through the VM NICs to the router
3. ATT (lower risk) is migrated first and validated before Spectrum cutover
4. Rollback procedure is documented and has been drill-tested successfully before production cutover
5. RRUL benchmark before/after comparison shows throughput improvement (target: Spectrum exceeds 740Mbps ceiling)
   **Plans**: 4 plans
   Plans:
   - [x] 110-01-PLAN.md -- Config YAML creation + baseline benchmarks
   - [x] 110-02-PLAN.md -- ATT cutover: cabling, daemon start, MikroTik queue disable
   - [x] 110-03-PLAN.md -- Rollback drill (Level 1 + Level 2) on ATT
   - [x] 110-04-PLAN.md -- Spectrum cutover, steering start, after-benchmarks

## Milestones

### Active

- **v1.21 CAKE Offload** - [Roadmap](milestones/v1.21-ROADMAP.md) (Phases 104-110) - In progress

### Completed

- [v1.20 Adaptive Tuning](milestones/v1.20-ROADMAP.md) (Phases 98-103) - SHIPPED 2026-03-19
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

## Progress

**Total:** 103 phases complete, 210 plans across 21 milestones + 7 phases planned (v1.21)

| Milestone                            | Phases  | Plans | Status      | Shipped    |
| ------------------------------------ | ------- | ----- | ----------- | ---------- |
| v1.21 CAKE Offload                   | 104-110 | TBD   | In progress | -          |
| v1.20 Adaptive Tuning                | 98-103  | 13    | Complete    | 2026-03-19 |
| v1.19 Signal Fusion                  | 93-97   | 9     | Complete    | 2026-03-18 |
| v1.18 Measurement Quality            | 88-92   | 10    | Complete    | 2026-03-17 |
| v1.17 CAKE Optimization & Bench.     | 84-87   | 8     | Complete    | 2026-03-16 |
| v1.16 Validation & Op. Confidence    | 81-83   | 4     | Complete    | 2026-03-13 |
| v1.15 Alerting & Notifications       | 76-80   | 10    | Complete    | 2026-03-12 |
| v1.14 Operational Visibility         | 73-75   | 7     | Complete    | 2026-03-11 |
| v1.13 Legacy Cleanup & Feature Grad. | 67-72   | 10    | Complete    | 2026-03-11 |
| v1.12 Deployment & Code Health       | 62-66   | 7     | Complete    | 2026-03-11 |
| v1.11 WAN-Aware Steering             | 58-61   | 8     | Complete    | 2026-03-10 |
| v1.10 Architectural Review Fixes     | 50-57   | 15    | Complete    | 2026-03-09 |
| v1.9 Performance & Efficiency        | 47-49   | 6     | Complete    | 2026-03-07 |
| v1.8 Resilience & Robustness         | 43-46   | 8     | Complete    | 2026-03-06 |
| v1.7 Metrics History                 | 38-42   | 8     | Complete    | 2026-01-25 |
| v1.6 Test Coverage 90%               | 31-37   | 17    | Complete    | 2026-01-25 |
| v1.5 Quality & Hygiene               | 27-30   | 8     | Complete    | 2026-01-24 |
| v1.4 Observability                   | 25-26   | 4     | Complete    | 2026-01-24 |
| v1.3 Reliability & Hardening         | 21-24   | 5     | Complete    | 2026-01-21 |
| v1.2 Configuration & Polish          | 16-20   | 5     | Complete    | 2026-01-14 |
| v1.1 Code Quality                    | 6-15    | 30    | Complete    | 2026-01-14 |
| v1.0 Performance Optimization        | 1-5     | 8     | Complete    | 2026-01-13 |

### Phase 111: Auto-Tuning Production Hardening -- Config bounds + SIGP-01 rate fix

**Goal:** Widen 4 tuning bounds stuck at limits and fix SIGP-01 outlier rate 60x underestimate from wrong denominator
**Requirements**: SIGP-01-FIX, BOUNDS-SPECTRUM, BOUNDS-ATT
**Depends on:** None (standalone hardening, applies to current production v1.20)
**Plans:** 4/4 plans complete

Plans:

- [x] 111-01-PLAN.md -- Config bounds update + SIGP-01 rate normalization fix with density-aware tests
