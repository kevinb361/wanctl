---
phase: 125-boot-resilience
plan: 01
subsystem: infra
tags: [systemd, bash, ethtool, nic-tuning, irq-affinity, boot-resilience]

# Dependency graph
requires: []
provides:
  - "Idempotent NIC tuning shell script with journal logging and graceful error handling"
  - "Updated systemd oneshot calling script instead of raw ExecStart lines"
affects: [125-02, deploy.sh]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      logger-t-journal-pattern,
      per-nic-error-handling,
      always-exit-0-boot-safety,
    ]

key-files:
  created:
    - deploy/scripts/wanctl-nic-tuning.sh
  modified:
    - deploy/systemd/wanctl-nic-tuning.service

key-decisions:
  - "Script always exits 0 -- missing NICs or failed ethtool warn but never block boot chain (D-01)"
  - "Uses $TAG variable with logger -t for consistent journal tagging (follows wanctl-recovery.sh pattern)"
  - "Ring buffer constants (RING_RX/RING_TX=4096) parameterized for clarity and future adjustability"

patterns-established:
  - "Boot-critical scripts exit 0 unconditionally -- availability over correctness"
  - "NIC tuning uses logger -t wanctl-nic-tuning for all journal output"

requirements-completed: [BOOT-01, BOOT-02]

# Metrics
duration: 2min
completed: 2026-04-02
---

# Phase 125 Plan 01: NIC Tuning Script Summary

**Idempotent NIC tuning shell script with ring buffers (4096), rx-udp-gro-forwarding, and IRQ affinity for 4 bridge NICs, called by updated systemd oneshot**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-02T14:46:56Z
- **Completed:** 2026-04-02T14:49:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created deploy/scripts/wanctl-nic-tuning.sh with per-NIC error handling, journal logging (9 logger calls), and graceful missing-NIC skip
- Replaced 10 fragile ExecStart ethtool lines in systemd service with single ExecStart calling the script
- All 4 bridge NICs covered: ens16/ens17 (Spectrum i210) and ens27/ens28 (ATT i350)
- IRQ affinity pinning: Spectrum -> CPU 0, ATT -> CPU 1

## Task Commits

Each task was committed atomically:

1. **Task 1: Create wanctl-nic-tuning.sh script** - `6cb1ae7` (feat)
2. **Task 2: Update wanctl-nic-tuning.service to call script** - `c1f64cf` (feat)

## Files Created/Modified

- `deploy/scripts/wanctl-nic-tuning.sh` - Idempotent NIC tuning: ring buffers, GRO forwarding, IRQ affinity with journal logging
- `deploy/systemd/wanctl-nic-tuning.service` - Simplified to single ExecStart calling the shell script, hardening preserved

## Decisions Made

- Script always exits 0 per D-01 (availability over correctness -- wanctl with suboptimal NICs better than no wanctl)
- Followed wanctl-recovery.sh pattern (logger -t for journal output) per D-02
- Ring buffer values parameterized as constants (RING_RX=4096, RING_TX=4096) rather than inline literals

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - both files are complete and production-ready.

## Next Phase Readiness

- NIC tuning script ready for deploy.sh integration (Plan 02 scope)
- systemd service ready for dependency wiring (Plan 02: wanctl@.service After= ordering)
- Script deployed to /usr/local/bin/ on target via deploy.sh (Plan 02 will add to SCRIPTS array)

## Self-Check: PASSED

All created files exist. All commit hashes verified in git log.

---

_Phase: 125-boot-resilience_
_Completed: 2026-04-02_
