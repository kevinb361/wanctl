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
- v1.27 Performance & QoS: Phases 131-136 (shipped 2026-04-03)
- v1.28 Infrastructure Optimization: Phases 137-140 (in progress)

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

<details>
<summary>v1.27 Performance & QoS (Phases 131-136) -- SHIPPED 2026-04-03</summary>

- [x] Phase 131: Cycle Budget Profiling -- per-subsystem timing under RRUL
- [x] Phase 132: Cycle Budget Optimization -- BackgroundRTTThread, cycle util 102%->27%
- [x] Phase 133: Diffserv Bridge Audit -- 3-point DSCP capture audit
- [x] Phase 134: Diffserv Tin Separation -- MikroTik prerouting DSCP + wanctl-check-cake
- [x] Phase 135: Upload Recovery Tuning -- A/B tested, +17.6% UL throughput
- [x] Phase 136: Hysteresis Observability -- suppression rate monitoring + alerting

</details>

### v1.28 Infrastructure Optimization (Phases 137-141)

- [ ] **Phase 137: cake-shaper vCPU Expansion** - Add 3rd vCPU to cake-shaper VM on odin, verify operational
- [ ] **Phase 138: cake-shaper IRQ & Kernel Tuning** - NIC IRQ affinity balancing + kernel network sysctl optimization
- [ ] **Phase 139: RB5009 Queue & IRQ Optimization** - SFP+ multi-queue + switch IRQ redistribution
- [ ] **Phase 140: WireGuard Error Investigation** - Diagnose 821K tx-errors, identify root cause, apply fix
- [x] **Phase 141: Bridge Download DSCP Classification** - nftables bridge rules to classify download traffic into CAKE tins (completed 2026-04-04)

## Phase Details

### Phase 137: cake-shaper vCPU Expansion

**Goal**: cake-shaper VM runs with 3 vCPUs, providing headroom for CAKE + wanctl under sustained load
**Depends on**: Nothing (first phase of v1.28)
**Requirements**: VMOPT-01
**Success Criteria** (what must be TRUE):

1. Proxmox VM 206 config shows 3 cores allocated
2. cake-shaper VM boots and all 4 passthrough NICs are operational (br-spectrum, br-att forwarding)
3. wanctl@spectrum and wanctl@att services running with no errors after vCPU change
4. `nproc` on cake-shaper returns 3
   **Plans**: TBD

### Phase 138: cake-shaper IRQ & Kernel Tuning

**Goal**: NIC interrupt processing is balanced across cores and kernel network stack is tuned for bridge+CAKE workload
**Depends on**: Phase 137 (3rd core must be available for IRQ distribution)
**Requirements**: VMOPT-02, VMOPT-03
**Success Criteria** (what must be TRUE):

1. Spectrum bridge IRQs (ens16/ens17) and ATT bridge IRQs (ens27/ens28) are distributed across at least 2 cores (not all Spectrum on CPU0)
2. IRQ affinity persists across reboot (systemd unit or udev rule)
3. `net.core.netdev_budget`, `net.core.netdev_budget_usecs`, and `net.core.netdev_max_backlog` are tuned and persisted via sysctl.d
4. Load average under equivalent traffic is measurably lower than pre-optimization baseline
   **Plans**: TBD

### Phase 139: RB5009 Queue & IRQ Optimization

**Goal**: SFP+ TX queue drops eliminated and CPU core utilization balanced across all 4 cores
**Depends on**: Nothing (independent of VM phases)
**Requirements**: RTOPT-01, RTOPT-02
**Success Criteria** (what must be TRUE):

1. SFP+ interface queue type is `multi-queue-ethernet-default` (mq-pfifo, limit=2000)
2. TX queue drop counter resets to 0 and stays near-zero under normal traffic
3. Switch IRQ 34 (SFP+ processing) reassigned away from cpu2 to a less-loaded core
4. Per-core CPU utilization is more evenly distributed (no single core >35% under normal load)
   **Plans**: TBD

### Phase 140: WireGuard Error Investigation

**Goal**: Root cause of 821K WireGuard TX errors identified and resolved
**Depends on**: Nothing (independent investigation)
**Requirements**: RTOPT-04
**Success Criteria** (what must be TRUE):

1. Root cause documented (MTU, MSS clamping, crypto bottleneck, or client-side)
2. Fix applied (MTU adjustment, MSS clamp rule, or other)
3. TX error rate drops to <100/day after fix (from ~3,400/day baseline)
4. WireGuard VPN connectivity confirmed functional after changes
   **Plans**: TBD

### Phase 141: Bridge Download DSCP Classification

**Goal**: Download traffic classified into correct CAKE diffserv4 tins via nftables bridge rules, closing the bridge-before-router DSCP gap
**Depends on**: Nothing (independent, but benefits from Phase 138 kernel tuning)
**Requirements**: VMOPT-04
**Success Criteria** (what must be TRUE):

1. nftables bridge forward rules classify download packets by port/protocol into Voice, Bulk, and Best Effort tins
2. CAKE ens17 (Spectrum DL) and ens28 (ATT DL) show non-trivial Voice and Bulk tin traffic during normal usage (not just Best Effort)
3. Endpoint-set DSCP (VoIP EF) still works — bridge rules do not override trusted endpoint marks
4. nftables rules persist across reboot (systemd unit or /etc/nftables.conf)
5. Rules are direction-specific (iif modem-side, oif router-side) — upload path unaffected
6. RRUL test confirms download tin separation with Voice latency < Best Effort latency under load
   **Plans:** 2/2 plans complete

Plans:
- [x] 141-01-PLAN.md — Create nftables rules, loader script, systemd service, deploy.sh integration
- [x] 141-02-PLAN.md — Deploy to both bridges, verify tin separation, RRUL validation, reboot persistence
