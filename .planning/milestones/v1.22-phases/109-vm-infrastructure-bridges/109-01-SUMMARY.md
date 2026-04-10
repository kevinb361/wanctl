---
phase: 109-vm-infrastructure-bridges
plan: 01
subsystem: infra
tags: [vfio, proxmox, pci-passthrough, iommu, nic]

requires:
  - phase: 104-iommu-verification-gate
    provides: "IOMMU group isolation verification for all 4 target NICs"
provides:
  - "VFIO passthrough active on odin for 4 NICs (2x i210, 2x i350)"
  - "docs/VM_INFRASTRUCTURE.md runbook with VFIO setup and verification"
affects: [109-02, 109-03, 109-04, 110-production-cutover]

tech-stack:
  added: []
  patterns: [vfio-pci-binding, softdep-module-ordering]

key-files:
  created: [docs/VM_INFRASTRUCTURE.md]
  modified: []

key-decisions:
  - "Skipped kernel pinning -- blocks security patches, VFIO works on 6.17.4-2-pve without pinning"
  - "VM ID changed from 106 to 206 to avoid Proxmox backup numbering conflicts across hosts"
  - "VM IP 10.10.110.223 instead of planned 10.10.110.106"
  - "VM created with q35 + OVMF (UEFI) for proper PCIe passthrough support"
  - "Debian 13 (trixie) instead of planned Debian 12 -- no functional differences for this use case"
  - "VM specs: 2 cores, 2GB RAM, 32GB ZFS, virtio-scsi-single + iothread, cpu=host, balloon=0"

patterns-established:
  - "VFIO binding via /etc/modprobe.d/vfio.conf with softdep igb pre: vfio-pci"

requirements-completed: [INFR-02]

duration: ~45min
completed: 2026-03-25
---

# Plan 109-01: VFIO Host Preparation Summary

**VFIO passthrough active on odin: 4 NICs (2x i210, 2x i350) bound to vfio-pci, management X552 unaffected**

## Performance

- **Duration:** ~45 min (includes odin reboot)
- **Started:** 2026-03-25
- **Completed:** 2026-03-25
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- VFIO modules loading at boot via /etc/modules
- All 4 target NICs bound to vfio-pci driver via modprobe.d/vfio.conf
- Management NIC (X552, 04:00.0) confirmed safe on ixgbe driver
- VM 206 (cake-shaper) created on odin with Debian 13, q35+OVMF, SSH at 10.10.110.223
- Complete VFIO setup runbook documented in docs/VM_INFRASTRUCTURE.md

## Task Commits

1. **Task 1: Generate VFIO setup runbook** - `6a8ed16` (docs)
2. **Task 2: Execute VFIO setup on odin** - human-action checkpoint (verified via SSH)

## Files Created/Modified
- `docs/VM_INFRASTRUCTURE.md` - VFIO setup runbook with NIC mapping, verification commands, safety warnings

## Decisions Made
- Skipped kernel pinning (user preference -- security patches > VFIO version lock)
- VM 206 instead of 106 (Proxmox backup numbering conflict avoidance)
- IP 10.10.110.223 instead of .106 (user assignment during Debian install)
- q35 + OVMF for native PCIe bus emulation with passthrough devices
- Debian 13 instead of 12 (current release, all required packages available)

## Deviations from Plan

### Plan Modifications

**1. No kernel pinning**
- Plan specified `proxmox-boot-tool kernel pin 6.17.2-1-pve`
- User opted out to avoid blocking kernel security patches
- VFIO verified working on 6.17.4-2-pve without pinning
- Runbook updated to document this as skipped

**2. VM ID 206, IP .223, Debian 13**
- Plan specified VM 106, IP .106, Debian 12
- User changed VM ID to 206 (backup numbering), chose IP .223, installed Debian 13
- All subsequent plans updated to use new values

---

**Total deviations:** 2 plan modifications (user preferences, no functional impact)
**Impact on plan:** All deviations are configuration choices. VFIO functionality is identical.

## Issues Encountered
- Heredoc with leading spaces failed on odin's shell -- resolved by pasting without indentation

## User Setup Required
None - VFIO setup complete on odin.

## Next Phase Readiness
- VFIO active, ready for Plan 109-02: add passthrough NICs to VM 206
- VM 206 running Debian 13 with SSH at 10.10.110.223
- 4 NICs available for qm set --hostpci passthrough

---
*Phase: 109-vm-infrastructure-bridges*
*Completed: 2026-03-25*
