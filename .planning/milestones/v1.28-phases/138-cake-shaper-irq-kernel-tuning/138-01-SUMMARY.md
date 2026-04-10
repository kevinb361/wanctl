---
phase: 138-cake-shaper-irq-kernel-tuning
plan: 01
subsystem: infra
tags: [irq-affinity, sysctl, kernel-tuning, cake-shaper, igb, bridge]

# Dependency graph
requires:
  - phase: 125-reboot-resilience
    provides: wanctl-nic-tuning.sh oneshot pattern and systemd service
provides:
  - 3-core IRQ affinity distribution for Spectrum bridge (ens16=CPU0, ens17=CPU2)
  - Kernel network sysctl tuning (netdev_budget=600) via sysctl.d drop-in
  - deploy.sh integration for sysctl.d deployment
affects: [cake-shaper-vm, deploy-scripts, wanctl-performance]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      sysctl.d drop-in for persistent kernel tuning,
      per-NIC IRQ affinity instead of per-bridge-pair,
    ]

key-files:
  created:
    - deploy/sysctl/99-wanctl-network.conf
  modified:
    - deploy/scripts/wanctl-nic-tuning.sh
    - deploy/systemd/wanctl-nic-tuning.service
    - scripts/deploy.sh

key-decisions:
  - "netdev_budget_usecs cannot be lowered below 8000 on kernel 6.12.74+deb13 -- kept at default"
  - "IRQ distribution: ens16=CPU0 (DL), ens17=CPU2 (UL), ATT=CPU1 -- traffic-weighted split"
  - "Belt-and-suspenders: sysctls applied both at runtime (script) and at boot (sysctl.d)"

patterns-established:
  - "sysctl.d drop-in: deploy/sysctl/ directory with deploy_sysctl_tuning() in deploy.sh"
  - "Per-NIC IRQ affinity: individual pinning instead of bridge-pair loop for heterogeneous distribution"

requirements-completed: [VMOPT-02, VMOPT-03]

# Metrics
duration: 13min
completed: 2026-04-04
---

# Phase 138 Plan 01: IRQ & Kernel Tuning Summary

**3-core IRQ affinity splits Spectrum bridge across CPU0+CPU2, netdev_budget doubled to 600, RRUL load avg drops 23% (1.13 to 0.87)**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-04T21:19:04Z
- **Completed:** 2026-04-04T21:32:51Z
- **Tasks:** 2
- **Files modified:** 4 (+ 1 new file)

## Accomplishments

- Spectrum bridge IRQs split across 2 cores: ens16 (DL) on CPU0, ens17 (UL) moved to CPU2
- Kernel netdev_budget doubled from 300 to 600 for bridge+CAKE packet processing
- Persistent sysctl.d drop-in at /etc/sysctl.d/99-wanctl-network.conf survives reboot
- RRUL load average reduced 23%: 1.13 baseline to 0.87 after tuning
- CPU2 now handles 16.4% softirq (was 0% NIC IRQs before)
- All settings verified persistent across reboot (IRQ numbers change but script uses NIC name lookup)

## Task Commits

Each task was committed atomically:

1. **Task 1: Update tuning script with 3-core IRQ distribution, sysctl tuning, and sysctl.d drop-in** - `a0631fb` (feat)
2. **Task 2: Deploy to cake-shaper VM + netdev_budget_usecs kernel minimum fix** - `f22590b` (fix)

## Files Created/Modified

- `deploy/scripts/wanctl-nic-tuning.sh` - 3-core IRQ affinity (ens16=CPU0, ens17=CPU2, ATT=CPU1) + apply_sysctl()
- `deploy/sysctl/99-wanctl-network.conf` - Persistent kernel tuning: netdev_budget=600, budget_usecs=8000, max_backlog=10000
- `deploy/systemd/wanctl-nic-tuning.service` - Added ProtectKernelTunables=no + wanctl-bridge-qos.service ordering
- `scripts/deploy.sh` - Added deploy_sysctl_tuning() function for sysctl.d drop-in deployment

## Decisions Made

- **netdev_budget_usecs=8000 (not 4000):** Kernel 6.12.74+deb13 enforces minimum of 8000us. Values 1000-7000 all rejected with EINVAL. Kept at explicit default; netdev_budget=600 is the effective tuning knob.
- **Per-NIC pinning over loop:** Changed from `for nic in SPECTRUM_NICS` to individual ens16/ens17 calls to support different CPU targets.
- **Belt-and-suspenders sysctl:** Both runtime (sysctl -w in script) and boot-time (/etc/sysctl.d/) for reliability.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] netdev_budget_usecs kernel minimum prevents 4000us target**

- **Found during:** Task 2 (deployment to cake-shaper)
- **Issue:** Plan specified netdev_budget_usecs=4000, but kernel 6.12.74+deb13 rejects all values below 8000 with EINVAL
- **Fix:** Changed to 8000 (explicit default) in both wanctl-nic-tuning.sh and 99-wanctl-network.conf. Updated comments to document kernel constraint.
- **Files modified:** deploy/scripts/wanctl-nic-tuning.sh, deploy/sysctl/99-wanctl-network.conf
- **Verification:** All 3 sysctls apply cleanly with no warnings after service restart
- **Committed in:** f22590b

---

**Total deviations:** 1 auto-fixed (1 bug - kernel constraint)
**Impact on plan:** Minimal. The primary tuning win comes from netdev_budget=600 (doubled from default) and IRQ redistribution, not from budget_usecs.

## Issues Encountered

- IRQ numbers change between reboots (e.g., ens16 was 40/41/42 before reboot, became 31/32/33 after). Not a problem -- the script uses NIC name grep on /proc/interrupts, not hardcoded IRQ numbers.

## Measurement Results

### Before (baseline under RRUL)

- Load avg: 1.13
- CPU0: ~49% (34% softirq) -- all Spectrum IRQs
- CPU1: ~20%
- CPU2: ~24% (0% NIC softirq)

### After (with 3-core IRQ distribution)

- Load avg: 0.87 (**23% reduction**)
- CPU0: ~47% (36% softirq) -- ens16 DL only
- CPU1: ~25% (2% softirq) -- ATT only
- CPU2: ~37.5% (16.4% softirq) -- ens17 UL (was idle)

### Analysis

- CPU2 now actively shares Spectrum IRQ work (16.4% softirq vs 0% before)
- CPU0 softirq similar (36% vs 34%) because ens16 DL is the heavier NIC
- Overall load average dropped 23% due to better work distribution across cores
- No CPU is near saturation -- headroom for traffic bursts

## User Setup Required

None - all deployment was automated via SSH.

## Next Phase Readiness

- IRQ and sysctl tuning is live and verified on cake-shaper VM
- deploy.sh updated for future deployments to include sysctl.d
- Ready for additional infrastructure optimization phases

## Self-Check: PASSED

- All 5 files exist (4 modified + 1 created)
- Both commits verified: a0631fb, f22590b
- IRQ affinity verified on cake-shaper after reboot: ens16=CPU0, ens17=CPU2, ATT=CPU1
- Sysctls verified after reboot: netdev_budget=600, budget_usecs=8000, max_backlog=10000

---

_Phase: 138-cake-shaper-irq-kernel-tuning_
_Completed: 2026-04-04_
