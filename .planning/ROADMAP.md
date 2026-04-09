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
- v1.28 Infrastructure Optimization: Phases 137-141 (shipped 2026-04-05)
- v1.29 Code Health & Cleanup: Phases 142-150 (shipped 2026-04-08)
- v1.30 Burst Detection: Phases 151-153 (shipped 2026-04-09)

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

<details>
<summary>v1.28 Infrastructure Optimization (Phases 137-141) -- SHIPPED 2026-04-05</summary>

- [x] Phase 137: cake-shaper vCPU Expansion -- 3rd vCPU added (manual Proxmox task, completed 2026-04-04)
- [x] Phase 138: cake-shaper IRQ & Kernel Tuning -- 3-core IRQ affinity + sysctl tuning (completed 2026-04-04)
- [x] Phase 139: RB5009 Queue & IRQ Optimization -- SFP+ multi-queue + switch IRQ redistribution (completed 2026-04-04)
- [x] Phase 140: WireGuard Error Investigation -- ZeroTier binding root cause, fix applied (completed 2026-04-05)
- [x] Phase 141: Bridge Download DSCP Classification -- nftables bridge DSCP into CAKE tins (completed 2026-04-04)

</details>

<details>
<summary>v1.29 Code Health & Cleanup (Phases 142-150) -- SHIPPED 2026-04-08</summary>

- [x] **Phase 142: Dead Code Removal** - Remove unused imports, dead functions/methods, and orphaned modules (completed 2026-04-05)
- [x] **Phase 143: Dependency & Cruft Cleanup** - Remove unused pip deps, stale TODOs, dead config references (completed 2026-04-05)
- [x] **Phase 144: Module Splitting** - Break up files over 500 LOC into focused single-responsibility modules (completed 2026-04-06)
- [x] **Phase 145: Method Extraction & Simplification** - Extract long methods and flatten high cyclomatic complexity (completed 2026-04-06)
- [x] **Phase 146: Test Cleanup & Organization** - Remove redundant tests, restructure directories, consolidate fixtures (completed 2026-04-06)
- [x] **Phase 147: Interface Decoupling** - Reduce tight coupling between modules with cleaner interfaces (completed 2026-04-08)
- [x] **Phase 148: Test Robustness & Performance** - Replace brittle mocks, profile and speed up slow tests (completed 2026-04-08)
- [x] **Phase 149: Type Annotations & Protocols** - Add missing type annotations, use Protocol/ABC patterns (completed 2026-04-08)
- [x] **Phase 150: Linting Strictness** - Enable stricter mypy rules and additional ruff rules (completed 2026-04-08)

</details>

<details>
<summary>v1.30 Burst Detection (Phases 151-153) -- SHIPPED 2026-04-09</summary>

- [x] **Phase 151: Burst Detection** - RTT acceleration detector with false-trigger filtering (completed 2026-04-09)
- [x] **Phase 152: Fast-Path Response** - Direct floor jump on burst ramp with anti-oscillation safety (completed 2026-04-09)
- [x] **Phase 153: Validation & Soak** - Flent regression tests and 24h production soak (completed 2026-04-09)

</details>

### v1.31 Linux-CAKE Optimization

**Milestone Goal:** Remove legacy router-era constraints and optimize the controller for local CAKE management -- netlink rate updates, deferred I/O, asymmetry-aware upload control, and post-DSCP parameter re-validation.

- [ ] **Phase 154: Netlink Backend Wiring** - Wire LinuxCakeAdapter to NetlinkCakeBackend with FD leak fix and CAKE parameter readback validation
- [ ] **Phase 155: Deferred I/O Worker** - Background thread for SQLite metrics writes, fdatasync for state files, coalesced state writes
- [ ] **Phase 156: Asymmetry-Aware Upload** - Attenuated upload rate control using IRTT directional congestion detection
- [ ] **Phase 157: Hysteresis Re-Tuning** - Measure and tune post-DSCP hysteresis suppression rate via A/B testing
- [ ] **Phase 158: Parameter Re-Validation** - A/B re-validate step_up, bloat thresholds on linux-cake post-DSCP post-netlink

## Phase Details

### Phase 154: Netlink Backend Wiring
**Goal**: CAKE bandwidth changes use kernel netlink instead of subprocess tc, recovering ~5ms/cycle and eliminating fork overhead from the hot path
**Depends on**: Nothing (first phase of v1.31)
**Requirements**: XPORT-01, XPORT-02, XPORT-03
**Success Criteria** (what must be TRUE):
  1. LinuxCakeAdapter uses NetlinkCakeBackend for all bandwidth changes in production -- no subprocess tc on the hot path
  2. After 100 consecutive set_bandwidth() calls, netlink FD count has not increased (FD leak in _reset_ipr() is fixed)
  3. After a bandwidth-only netlink change, CAKE diffserv mode, overhead, and rtt remain unchanged (validated by readback)
  4. Health endpoint reports netlink as the active transport backend
**Plans:** 2 plans
Plans:
- [ ] 154-01-PLAN.md -- FD leak fix + adapter factory swap to NetlinkCakeBackend
- [ ] 154-02-PLAN.md -- Periodic readback validation + health endpoint transport reporting

### Phase 155: Deferred I/O Worker
**Goal**: Per-cycle disk I/O is off the control loop hot path, dropping cycle p99 from 51ms to within the 50ms budget
**Depends on**: Phase 154
**Requirements**: CYCLE-01, CYCLE-02, CYCLE-03
**Success Criteria** (what must be TRUE):
  1. SQLite metrics writes happen on a background thread -- control loop enqueues data and returns without blocking
  2. State JSON writes use fdatasync (not fsync), remain synchronous, and only flush when state has actually changed and minimum interval has elapsed
  3. Cycle p99 under RRUL load is below 50ms (measured via health endpoint or cycle timing logs)
  4. Graceful shutdown drains all queued writes before process exit -- no data loss on systemctl stop
**Plans**: TBD

### Phase 156: Asymmetry-Aware Upload
**Goal**: Upload rate is preserved during download-only congestion, keeping VoIP and video quality stable during bulk downloads
**Depends on**: Phase 155
**Requirements**: ASYM-01, ASYM-02, ASYM-03
**Success Criteria** (what must be TRUE):
  1. During a download-only Usenet load, upload rate stays above 20Mbps instead of dropping to 8Mbps floor
  2. Asymmetry suppression requires N consecutive asymmetric IRTT readings before activating (no single-sample trigger)
  3. When IRTT data is stale (>30s old), asymmetry gate disables automatically and upload rate control reverts to current behavior
  4. Asymmetry gate is configurable in YAML and toggleable via SIGUSR1 hot-reload
  5. During bidirectional congestion (both DL and UL RTT elevated), upload rate reduction is NOT suppressed -- override prevents feedback loop
**Plans**: TBD

### Phase 157: Hysteresis Re-Tuning
**Goal**: Hysteresis suppression rate is validated against the post-DSCP, post-netlink, post-async jitter profile and tuned below the 20/min alert threshold
**Depends on**: Phase 156
**Requirements**: TUNE-01
**Success Criteria** (what must be TRUE):
  1. Post-v1.31 hysteresis suppression rate is measured and documented (baseline measurement under RRUL)
  2. If suppression rate exceeds 20/min, dwell_cycles and/or deadband_ms are A/B tested and updated to bring rate below threshold
  3. If suppression rate is already below 20/min after Phases 154-156, current values are confirmed correct and documented
**Plans**: TBD

### Phase 158: Parameter Re-Validation
**Goal**: Controller tuning parameters are confirmed optimal for the final v1.31 system behavior via A/B testing
**Depends on**: Phase 157
**Requirements**: TUNE-02
**Success Criteria** (what must be TRUE):
  1. step_up_mbps is A/B tested (current value vs alternatives) under RRUL on the post-v1.31 system and confirmed or updated
  2. warn_bloat_ms and hard_red_bloat_ms are A/B tested and confirmed or updated for the post-DSCP linux-cake profile
  3. All parameter changes (if any) are deployed and stable in production for 24h before milestone is marked complete
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 154 through 158.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 154. Netlink Backend Wiring | v1.31 | 0/2 | Not started | - |
| 155. Deferred I/O Worker | v1.31 | 0/? | Not started | - |
| 156. Asymmetry-Aware Upload | v1.31 | 0/? | Not started | - |
| 157. Hysteresis Re-Tuning | v1.31 | 0/? | Not started | - |
| 158. Parameter Re-Validation | v1.31 | 0/? | Not started | - |
