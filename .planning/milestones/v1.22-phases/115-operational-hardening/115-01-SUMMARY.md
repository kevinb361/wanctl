---
phase: 115-operational-hardening
plan: 01
subsystem: infra
tags:
  [systemd, hardening, security, capabilities, syscall-filter, circuit-breaker]

# Dependency graph
requires:
  - phase: 112-foundation-scan
    provides: "Baseline systemd security scores (8.4 EXPOSED) and hardening catalog from 112-02-findings.md"
provides:
  - "Hardened systemd unit files for wanctl@, steering, and wanctl-nic-tuning"
  - "Security exposure reduced from 8.4 EXPOSED to 2.1/1.9 OK for runtime services"
  - "Consistent circuit breaker config across all 3 runtime units (OPSEC-06)"
  - "deploy/systemd/ directory with version-controlled unit files"
affects: [115-operational-hardening, 116-test-documentation-hygiene]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "systemd hardening: ProtectKernelTunables + CapabilityBoundingSet + SystemCallFilter + RestrictNamespaces"
    - "Unit file source of truth in deploy/systemd/ with scp to production VM"

key-files:
  created:
    - deploy/systemd/wanctl@.service
    - deploy/systemd/steering.service
    - deploy/systemd/wanctl-nic-tuning.service
  modified: []

key-decisions:
  - "CAP_NET_ADMIN required for wanctl@ (tc commands), NOT for steering (ICMP only)"
  - "SystemCallFilter blocks 8 dangerous classes; preserves @privileged, @raw-io, @resources"
  - "NIC tuning service gets limited hardening (runs as root, needs /proc/irq and ethtool device access)"
  - "Unit file backups (.bak.pre115) created on VM before any changes"

patterns-established:
  - "deploy/systemd/ directory as version-controlled source of truth for production unit files"
  - "Capability bounding: AmbientCapabilities + CapabilityBoundingSet together for defense in depth"

requirements-completed: [OPSEC-01, OPSEC-06]

# Metrics
duration: 5min
completed: 2026-03-26
---

# Phase 115 Plan 01: Systemd Hardening Summary

**Hardened all 4 systemd units on production VM -- wanctl@ scored 2.1 OK and steering 1.9 OK (down from 8.4 EXPOSED), with circuit breaker config made consistent across all 3 runtime services**

## Performance

- **Duration:** ~5 min (continuation after checkpoint approval)
- **Started:** 2026-03-26T22:47:02Z
- **Completed:** 2026-03-26T22:48:00Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments

- wanctl@.service hardened: 8.4 EXPOSED to 2.1 OK (kernel protection, capability bounding, syscall filtering, namespace restrictions)
- steering.service hardened: 8.4 EXPOSED to 1.9 OK (same hardening, CAP_NET_RAW only -- no CAP_NET_ADMIN)
- wanctl-nic-tuning.service hardened: 9.6 UNSAFE to 7.5 EXPOSED (limited hardening for root oneshot needing ethtool/IRQ access)
- OPSEC-06 fix: steering.service now has StartLimitBurst=5/StartLimitIntervalSec=300 (was missing)
- Circuit breaker config identical across all 3 runtime units (Restart=on-failure, RestartSec=5s, WatchdogSec=30s)
- Unit file backups (.bak.pre115) created on VM for rollback

## Task Commits

Each task was committed atomically:

1. **Task 1: Take VM snapshot and harden all 4 systemd unit files** - `2162112` (feat)
2. **Task 2: Verify hardened services are functioning correctly** - checkpoint:human-verify (approved, no commit needed)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified

- `deploy/systemd/wanctl@.service` - Hardened template unit for spectrum/att WAN controllers (ProtectKernelTunables, CapabilityBoundingSet, SystemCallFilter, etc.)
- `deploy/systemd/steering.service` - Hardened steering daemon unit (CAP_NET_RAW only, StartLimitBurst added for OPSEC-06)
- `deploy/systemd/wanctl-nic-tuning.service` - Hardened NIC tuning oneshot (limited hardening for root service)

## Decisions Made

- CAP_NET_ADMIN is required for wanctl@ (tc commands for CAKE rate changes) but NOT for steering (only needs CAP_NET_RAW for ICMP)
- SystemCallFilter blocks @clock @cpu-emulation @debug @module @mount @obsolete @reboot @swap; preserves @privileged (cap_net_raw), @raw-io (ICMP sockets), @resources (process mgmt)
- NIC tuning service gets limited hardening because it runs as root and needs /proc/irq for IRQ affinity and device access for ethtool
- PrivateUsers not applied (conflicts with AmbientCapabilities), PrivateNetwork not applied (needs network), @raw-io not filtered (would break ICMP)

## Verification Results (Human-Verified Checkpoint)

User verified on production VM:

- All 3 services: **active (running)**, GREEN/GREEN on both WANs
- Health endpoint: healthy, uptime 187s, 0 failures, 60.5% utilization
- wanctl@spectrum security score: **2.1 OK** (was 8.4 EXPOSED)
- steering security score: **1.9 OK** (was 8.4 EXPOSED)
- No EPERM/EACCES errors in journals
- Fusion active, tuning active, IRTT available
- Circuit breaker config now consistent across all 3 units

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Runtime services hardened and verified healthy
- NIC persistence (OPSEC-02) and resource limits (OPSEC-03) ready for Plan 03
- Backup/recovery runbook (Plan 02) can proceed in parallel

## Self-Check: PASSED

- FOUND: 115-01-SUMMARY.md
- FOUND: commit 2162112

---

_Phase: 115-operational-hardening_
_Completed: 2026-03-26_
