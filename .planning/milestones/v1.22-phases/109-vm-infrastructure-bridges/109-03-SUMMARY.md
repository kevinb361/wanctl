---
phase: 109-vm-infrastructure-bridges
plan: 03
subsystem: infra
tags: [systemd-networkd, bridge, l2-forwarding, stp, transparent-bridge]

requires:
  - phase: 109-02
    provides: "VM 206 with 4 passthrough NICs (ens16/ens17/ens27/ens28)"
provides:
  - "br-spectrum bridge (ens16 + ens17) with STP disabled"
  - "br-att bridge (ens27 + ens28) with STP disabled"
  - "systemd-networkd persistence across reboot"
  - "Management IP 10.10.110.223/24 on ens18"
affects: [109-04, 110-production-cutover]

tech-stack:
  added: []
  patterns: [systemd-networkd-bridge, RequiredForOnline-carrier]

key-files:
  created: []
  modified: [docs/VM_INFRASTRUCTURE.md]

key-decisions:
  - "RequiredForOnline=carrier for bridges (not routable) — prevents wait-online hang on IP-less bridges"
  - "RequiredForOnline=enslaved for member ports — correct bridge member state"
  - "CAKE NOT in systemd-networkd — wanctl daemon handles via tc qdisc replace"
  - "ifupdown fully replaced by systemd-networkd (interfaces.bak preserved)"

patterns-established:
  - "systemd-networkd numbering: 10-*.netdev, 20-member.network, 30-bridge.network, 40-mgmt.network"

requirements-completed: [INFR-03, INFR-05, INFR-06]

duration: ~15min
completed: 2026-03-25
---

# Plan 109-03: Bridge Configuration Summary

**Two transparent L2 bridges (br-spectrum, br-att) configured via systemd-networkd with STP disabled, verified across reboot**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-25
- **Completed:** 2026-03-25
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments
- br-spectrum: ens16 + ens17 enslaved, STP disabled, forward_delay=0, no IP
- br-att: ens27 + ens28 enslaved, STP disabled, forward_delay=0, no IP
- Management: ens18 static 10.10.110.223/24 via systemd-networkd
- 9 systemd-networkd config files created and verified
- ifupdown fully replaced (backup preserved at interfaces.bak)
- Configuration survives reboot — verified via SSH reconnect
- systemd-networkd-wait-online does not hang (carrier-based, not routable)

## Task Commits

1. **Task 1: Create systemd-networkd configs** - executed via SSH (9 files created, reboot verified)
2. **Task 2: Verify bridges** - full verification suite passed
3. **Task 3: Document bridge configuration** - inline (docs update)

## Files Created/Modified
- `docs/VM_INFRASTRUCTURE.md` - Section 3: bridge topology, systemd-networkd files, verification, troubleshooting

## Decisions Made
- Used RequiredForOnline=carrier for bridges (not routable) to prevent wait-online timeout on IP-less bridges
- Documented that CAKE must NOT be configured in systemd-networkd (race condition per systemd #31226)

## Deviations from Plan
None — plan executed as written, with Claude executing SSH commands directly.

## Issues Encountered
- NIC state shows "no-carrier" for all passthrough NICs — expected since no cables are connected yet

## Next Phase Readiness
- Bridges ready for CAKE qdisc attachment (Plan 109-04)
- CAKE targets: ens17 (br-spectrum router-side), ens28 (br-att router-side)
- Infrastructure ready for wanctl deployment

---
*Phase: 109-vm-infrastructure-bridges*
*Completed: 2026-03-25*
