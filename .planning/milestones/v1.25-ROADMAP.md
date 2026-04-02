# Roadmap: wanctl

## Overview

wanctl v1.25 ensures the cake-shaper VM fully self-heals after reboot. Today, NIC optimizations (rx-udp-gro-forwarding on 4 bridge NICs) are lost on reboot and require manual reapplication. CAKE qdiscs are already handled by wanctl's initialize_cake, but there is no guarantee NIC tuning completes before wanctl starts, and no automated way to verify the full boot chain. Two phases: first, build and wire a systemd oneshot that persists NIC tuning with correct startup ordering; second, build a validation tool that confirms the entire chain (NIC tuning + CAKE qdiscs + wanctl health) both at boot and on-demand.

## Domain Expertise

None

## Milestones

- v1.0 through v1.23: See MILESTONES.md (shipped)
- v1.24 EWMA Boundary Hysteresis: Phases 121-124 (shipped 2026-04-02)
- v1.25 Reboot Resilience: Phases 125-126 (current)

## Phases

### v1.24 EWMA Boundary Hysteresis (shipped)

- [x] **Phase 121: Core Hysteresis Logic** - Dwell timer and deadband margin on GREEN/YELLOW state transitions
- [x] **Phase 122: Hysteresis Configuration** - YAML config, defaults, and SIGUSR1 hot-reload for hysteresis parameters
- [x] **Phase 123: Hysteresis Observability** - Health endpoint state exposure and transition suppression logging
- [x] **Phase 124: Production Validation** - Deploy, confirm zero flapping, verify genuine congestion detection latency

### v1.25 Reboot Resilience

- [ ] **Phase 125: Boot Resilience** - systemd oneshot for NIC tuning persistence with correct startup ordering and end-to-end boot chain
- [ ] **Phase 126: Boot Validation** - Post-boot health check and on-demand CLI tool confirming NIC tuning, CAKE qdiscs, and wanctl health

## Phase Details

### Phase 125: Boot Resilience

**Goal**: cake-shaper VM fully self-configures after reboot -- NIC optimizations are applied automatically before wanctl starts, with correct systemd dependency ordering across the entire boot chain
**Depends on**: Nothing (first phase of v1.25)
**Requirements**: BOOT-01, BOOT-02, BOOT-03, BOOT-04
**Success Criteria** (what must be TRUE):

1. After a VM reboot, all 4 bridge NICs (ens16, ens17, ens27, ens28) have rx-udp-gro-forwarding enabled without manual intervention
2. The NIC tuning oneshot is idempotent (safe to re-run), logs each optimization it applies, and exits cleanly if a NIC is missing rather than failing the boot chain
3. wanctl@spectrum and wanctl@att do not start until the NIC tuning oneshot reports success (systemd After/Requires dependency)
4. A full VM reboot produces the complete chain -- bridges up, NIC tuning applied, wanctl starts with CAKE qdiscs initialized, recovery timer active -- all verified via systemctl status
   **Plans:** 2 plans

Plans:

- [x] 125-01-PLAN.md -- NIC tuning shell script with logging, idempotency, and graceful error handling
- [x] 125-02-PLAN.md -- systemd dependency wiring, deploy.sh update, directory reconciliation, dry-run validation

### Phase 126: Boot Validation

**Goal**: Operator can verify the entire boot chain worked correctly, both automatically after boot and on-demand at any time
**Depends on**: Phase 125
**Requirements**: VALN-01, VALN-02
**Success Criteria** (what must be TRUE):

1. A post-boot validation step confirms all 3 layers: NIC tuning applied (rx-udp-gro-forwarding on all 4 NICs), CAKE qdiscs active on bridge interfaces (ens17, ens28), and wanctl services healthy (health endpoint returns 200)
2. The validation is available as an on-demand CLI command (e.g., wanctl-check-boot) that an operator can run at any time, not only at boot
3. Validation output clearly reports pass/fail per check with actionable messages for any failures
   **Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 125 -> 126

| Phase                | Plans Complete | Status      | Completed |
| -------------------- | -------------- | ----------- | --------- |
| 125. Boot Resilience | 2/2 | Complete    | 2026-04-02 |
| 126. Boot Validation | 0/?            | Not started | -         |

<details>
<summary>Previous Milestones (v1.0-v1.24)</summary>

| Milestone                            | Phases  | Plans | Status   | Completed  |
| ------------------------------------ | ------- | ----- | -------- | ---------- |
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
