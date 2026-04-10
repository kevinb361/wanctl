---
phase: 109-vm-infrastructure-bridges
plan: 02
subsystem: infra
tags: [proxmox, vm, vfio, pci-passthrough, debian, q35, ovmf]

requires:
  - phase: 109-01
    provides: "VFIO passthrough active on odin for 4 target NICs"
provides:
  - "VM 206 (cake-shaper) running Debian 13 with SSH at 10.10.110.223"
  - "4 VFIO passthrough NICs visible as ens16/ens17/ens27/ens28"
  - "Guest NIC-to-host PCI mapping documented with device ID confirmation"
affects: [109-03, 109-04, 110-production-cutover]

tech-stack:
  added: []
  patterns: [q35-ovmf-passthrough, hostpci-sequential-ordering]

key-files:
  created: []
  modified: [docs/VM_INFRASTRUCTURE.md]

key-decisions:
  - "QEMU guest PCI ordering matches hostpci index sequentially — deterministic mapping"
  - "Modem vs router role within each NIC pair deferred to physical cabling (Phase 110)"

patterns-established:
  - "Guest NIC discovery: readlink /sys/class/net/NAME/device + device ID confirmation"

requirements-completed: [INFR-02, INFR-06]

duration: ~30min
completed: 2026-03-25
---

# Plan 109-02: VM Creation & NIC Passthrough Summary

**VM 206 (cake-shaper) running Debian 13 with 4 VFIO passthrough NICs: ens16/ens17 (i210 Spectrum), ens27/ens28 (i350 ATT)**

## Performance

- **Duration:** ~30 min (includes Debian install)
- **Started:** 2026-03-25
- **Completed:** 2026-03-25
- **Tasks:** 3 (Task 1 done by user pre-plan, Tasks 2-3 executed inline)
- **Files modified:** 1

## Accomplishments
- VM 206 created with q35+OVMF, cpu=host, balloon=0, 32GB ZFS
- 4 VFIO passthrough NICs added via hostpci0-3
- Guest NIC names discovered: ens16, ens17 (i210), ens27, ens28 (i350)
- Device ID confirmation: 0x1533 = i210 (Spectrum), 0x1521 = i350 (ATT)
- NIC mapping and bridge membership documented in VM_INFRASTRUCTURE.md

## Task Commits

1. **Task 1: Create VM 206** - human-action (user created VM via Proxmox before plan start)
2. **Task 2: Add passthrough NICs and discover names** - human-action (verified via SSH)
3. **Task 3: Record NIC mapping** - inline (docs update)

## Files Created/Modified
- `docs/VM_INFRASTRUCTURE.md` - Section 2 added: VM specs, creation commands, NIC discovery results

## Decisions Made
- VM created by user before formal plan execution — Task 1 accepted as pre-completed
- Guest PCI ordering confirmed deterministic via hostpci index

## Deviations from Plan
- VM created before plan execution started (user preference — wanted to install Debian first)
- No functional impact — all acceptance criteria met

## Issues Encountered
- Initial NIC discovery command hung on Debian 13 (glob expansion in /sys) — resolved with explicit interface name list

## Next Phase Readiness
- NIC names known: ready for bridge configuration (Plan 109-03)
- br-spectrum: ens16 + ens17
- br-att: ens27 + ens28

---
*Phase: 109-vm-infrastructure-bridges*
*Completed: 2026-03-25*
