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

### v1.30 Burst Detection

**Milestone Goal:** Detect and respond to multi-flow congestion bursts that overwhelm gradual floor descent, cutting p99 latency from 3,200ms to under 500ms during worst-case scenarios (tcp_12down).

- [ ] **Phase 151: Burst Detection** - RTT acceleration detector with false-trigger filtering
- [ ] **Phase 152: Fast-Path Response** - Direct floor jump on burst ramp with anti-oscillation safety
- [ ] **Phase 153: Validation & Soak** - Flent regression tests and 24h production soak

## Phase Details

### Phase 151: Burst Detection
**Goal**: Controller can detect multi-flow burst ramps within 200ms by measuring RTT acceleration (second derivative), without false-triggering on normal single-flow congestion
**Depends on**: Nothing (first phase of v1.30)
**Requirements**: DET-01, DET-02
**Success Criteria** (what must be TRUE):
  1. RTT acceleration (second derivative) is computed each cycle and exposed in health endpoint or logs
  2. A flent tcp_12down test triggers a burst detection event within 200ms of flow onset
  3. A flent rrul_be test (single-flow normal congestion) does NOT trigger a burst detection event
  4. Burst detection threshold is configurable in YAML and reloadable via SIGUSR1
**Plans:** 2 plans
Plans:
- [ ] 151-01-PLAN.md -- BurstDetector module and unit tests
- [ ] 151-02-PLAN.md -- WANController integration, config, health, metrics, SIGUSR1

### Phase 152: Fast-Path Response
**Goal**: When a burst ramp is detected, the controller immediately jumps to SOFT_RED or RED floor instead of descending gradually, without causing rate oscillation
**Depends on**: Phase 151
**Requirements**: RSP-01, RSP-02
**Success Criteria** (what must be TRUE):
  1. On burst detection, rate drops to SOFT_RED floor within one cycle (50ms) instead of gradual descent through YELLOW
  2. After a fast-path floor jump, the controller does not immediately recover and re-drop (no oscillation loop within 5s)
  3. Normal congestion (non-burst) still follows the existing gradual descent path unchanged
  4. Fast-path response parameters (target floor, holdoff duration) are configurable in YAML
**Plans**: TBD

### Phase 153: Validation & Soak
**Goal**: Burst detection delivers measurable latency improvement under worst-case load and causes no regression under normal traffic patterns or extended production use
**Depends on**: Phase 152
**Requirements**: VAL-01, VAL-02, VAL-03
**Success Criteria** (what must be TRUE):
  1. Flent tcp_12down p99 latency is below 500ms (down from 800-3200ms baseline)
  2. Flent RRUL and rrul_be median and p99 latency remain within 10% of pre-burst-detection baseline
  3. 24h production soak shows zero false burst detection triggers during normal household usage
  4. All existing unit tests pass with no regressions
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 151 through 153.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 151. Burst Detection | v1.30 | 0/2 | Planned | - |
| 152. Fast-Path Response | v1.30 | 0/0 | Not started | - |
| 153. Validation & Soak | v1.30 | 0/0 | Not started | - |
