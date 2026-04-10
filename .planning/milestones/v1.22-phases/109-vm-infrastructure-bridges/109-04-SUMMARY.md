---
phase: 109-vm-infrastructure-bridges
plan: 04
subsystem: infra
tags: [deployment, cake, tc, iproute2, systemd, pip3]

requires:
  - phase: 109-03
    provides: "Transparent L2 bridges (br-spectrum, br-att) with systemd-networkd"
provides:
  - "wanctl deployed to /opt/wanctl on cake-shaper (81 Python files)"
  - "CAKE qdisc verified on router-side bridge member ports (ens17, ens28)"
  - "JSON stats parsing verified via tc -s -j"
  - "systemd service with networkd ordering (After=systemd-networkd-wait-online)"
affects: [110-production-cutover]

tech-stack:
  added: [iproute2-6.15.0, sch_cake]
  patterns: [tc-qdisc-replace-idempotent, pip3-break-system-packages]

key-files:
  created: []
  modified: [docs/VM_INFRASTRUCTURE.md]

key-decisions:
  - "ecn keyword not supported by iproute2-6.15.0 tc — CAKE enables ECN by default, no keyword needed"
  - "tc binary at /usr/sbin/tc (not in user PATH) — wanctl runs as root via systemd so this is fine"
  - "install.sh run with --no-wizard (interactive wizard hangs in non-TTY SSH)"

patterns-established:
  - "CAKE init: tc qdisc replace on router-side NIC only (not modem-side)"
  - "Systemd ordering: networkd-wait-online must complete before wanctl starts"

requirements-completed: [INFR-04]

duration: ~20min
completed: 2026-03-25
---

# Plan 109-04: wanctl Deployment & CAKE Verification Summary

**wanctl deployed to cake-shaper with CAKE qdiscs verified on ens17 (Spectrum) and ens28 (ATT) — JSON stats parseable**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-25
- **Completed:** 2026-03-25
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments
- wanctl code deployed to /opt/wanctl (81 Python files)
- wanctl user and FHS directories created via install.sh --no-wizard
- Python dependencies installed: icmplib, requests, paramiko, pyyaml, tabulate, cryptography, pexpect
- iproute2 and curl installed
- systemd service installed with After=systemd-networkd-wait-online.service
- CAKE qdisc successfully attached to ens17 (Spectrum, ingress mode) and ens28 (ATT, ack-filter mode)
- JSON stats collection verified via tc -s -j qdisc show
- sch_cake kernel module loads successfully
- Test qdiscs cleaned up (daemon will re-create at startup)

## Task Commits

1. **Task 1: Deploy wanctl and install dependencies** - executed via SSH
2. **Task 2: Test CAKE initialization** - verified via SSH
3. **Task 3: Document deployment and CAKE verification** - inline (docs update)

## Files Created/Modified
- `docs/VM_INFRASTRUCTURE.md` - Sections 4 (deployment) and 5 (operational reference) added

## Decisions Made
- Dropped `ecn` keyword from CAKE commands — not supported by iproute2-6.15.0, ECN is default
- Used install.sh --no-wizard to avoid interactive TTY requirement
- Installed rsync on cake-shaper (missing from fresh Debian 13 minimal install)

## Deviations from Plan

### Auto-fixed Issues

**1. ecn keyword not supported**
- **Found during:** Task 2 (CAKE initialization test)
- **Issue:** tc qdisc replace rejected `ecn` keyword — not a valid parameter in iproute2-6.15.0
- **Fix:** Removed `ecn` from command — CAKE enables ECN by default on all tins
- **Verification:** tc qdisc replace succeeds without ecn, CAKE operates correctly

---

**Total deviations:** 1 auto-fixed (iproute2 version difference)
**Impact on plan:** No functional impact — ECN behavior is identical

## Issues Encountered
- install.sh wizard mode hangs on non-TTY SSH — resolved with --no-wizard flag
- rsync not installed on fresh Debian 13 — installed via apt
- tc binary at /usr/sbin/tc not in user PATH — wanctl systemd service runs with full PATH

## Next Phase Readiness
- Infrastructure complete: VM, bridges, CAKE all verified
- Ready for Phase 110: Production Cutover (staged migration)
- Remaining for production: config YAML files, secrets, physical cabling, daemon enable

---
*Phase: 109-vm-infrastructure-bridges*
*Completed: 2026-03-25*
