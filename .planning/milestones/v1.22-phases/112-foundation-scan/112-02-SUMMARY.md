---
phase: 112-foundation-scan
plan: 02
subsystem: infra
tags: [systemd, permissions, security-audit, production-vm, hardening]

# Dependency graph
requires:
  - phase: none
    provides: none
provides:
  - "Production VM file permission inventory (31 items audited)"
  - "systemd security exposure scores for all 4 service units"
  - "Prioritized hardening opportunity catalog with CAP_NET_RAW compatibility"
  - "Complete unit file captures for Phase 115 reference"
affects: [115-ops-security, 116-doc-debt]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - ".planning/phases/112-foundation-scan/112-02-findings.md"
  modified: []

key-decisions:
  - "secrets file 0640 is correct (not 0600) -- wanctl group needs read access"
  - "Steering service is named steering.service not wanctl-steering.service"
  - "NIC tuning service (9.6 UNSAFE) is acceptable for root oneshot boot service"
  - "High-priority hardening could reduce scores from 8.4 to ~3.5-4.5"

patterns-established: []

requirements-completed: [FSCAN-04, FSCAN-05]

# Metrics
duration: 4min
completed: 2026-03-26
---

# Phase 112 Plan 02: Production VM Security Audit Summary

**File permissions verified (31 items, 0 FAIL) and systemd exposure scores documented (8.4 EXPOSED for 3 runtime services) with prioritized hardening roadmap for Phase 115**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-26T17:20:06Z
- **Completed:** 2026-03-26T17:24:06Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Audited 31 file permission items across 4 directories -- all critical security permissions correct (0 FAIL)
- Documented systemd-analyze security scores: 8.4 EXPOSED for all 3 runtime services, 9.6 UNSAFE for NIC tuning oneshot
- Cataloged 20+ hardening opportunities with CAP_NET_RAW compatibility notes and estimated post-hardening score of 3.5-4.5
- Captured all 3 unit file contents for Phase 115 (OPSEC-01) reference

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit file permissions on production VM** - `2f2508c` (docs)
2. **Task 2: Run systemd-analyze security on all 3 service units** - `23ee529` (docs)

## Files Created/Modified

- `.planning/phases/112-foundation-scan/112-02-findings.md` - Complete security audit with permissions table, systemd analysis, hardening opportunities

## Decisions Made

- `/etc/wanctl/secrets` at 0640 (not 0600) is correct -- the wanctl group must read it; 0600 would break the service
- The steering service is `steering.service` (not `wanctl-steering.service` as the plan assumed)
- `wanctl-nic-tuning.service` at 9.6 UNSAFE is acceptable -- runs as root, oneshot at boot, needs device access
- Estimated 4+ point reduction achievable with safe hardening (8.4 -> ~3.5-4.5)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected steering service unit name**

- **Found during:** Task 2 (systemd security analysis)
- **Issue:** Plan referenced `wanctl-steering.service` but production uses `steering.service`
- **Fix:** Used correct service name `steering.service` for systemd-analyze and unit file capture
- **Files modified:** `.planning/phases/112-foundation-scan/112-02-findings.md`
- **Verification:** `systemctl list-units --type=service | grep wanctl` confirms name
- **Committed in:** `23ee529` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Service name correction necessary to complete analysis. No scope creep.

## Issues Encountered

- SSH glob expansion: `stat /etc/wanctl/*.yaml` failed with single-quote SSH -- resolved by using `bash -c` for glob expansion on remote
- `/opt/wanctl/src/` does not exist on production VM -- code is deployed flat in `/opt/wanctl/` (no src subdirectory)

## Cleanup Opportunities Identified (Not In Scope)

- `metrics.db.corrupt` (284MB) in `/var/lib/wanctl/` -- dead weight
- `autorate_continuous.py.bak` (178KB) in `/opt/wanctl/` -- dead weight
- `spectrum.yaml.bak.*` (2 files) in `/etc/wanctl/` -- dead weight

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Hardening opportunities fully cataloged for Phase 115 (OPSEC-01)
- Unit file contents captured to enable local development of hardened unit files
- Cleanup items documented for Phase 116 (TDOC) or separate maintenance

## Self-Check: PASSED

- FOUND: `.planning/phases/112-foundation-scan/112-02-findings.md`
- FOUND: `.planning/phases/112-foundation-scan/112-02-SUMMARY.md`
- FOUND: commit `2f2508c` (Task 1)
- FOUND: commit `23ee529` (Task 2)

---

_Phase: 112-foundation-scan_
_Completed: 2026-03-26_
