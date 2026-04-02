---
phase: 126-pre-test-gate
plan: 01
subsystem: infra
tags: [bash, cake, gate-check, linux-cake, production-validation]

# Dependency graph
requires:
  - phase: 125-boot-resilience
    provides: NIC tuning script, systemd wiring, cake-shaper VM deployment
provides:
  - Reusable pre-tuning gate check script (scripts/check-tuning-gate.sh)
  - Production environment validated for linux-cake A/B testing
affects:
  [
    127-dl-parameter-sweep,
    128-ul-parameter-sweep,
    129-cake-rtt-confirmation,
    130-production-config-commit,
  ]

# Tech tracking
tech-stack:
  added: [jq (VM-side JSON parsing)]
  patterns:
    [SSH-from-dev gate check pattern, router REST API validation from VM]

key-files:
  created:
    - scripts/check-tuning-gate.sh
  modified: []

key-decisions:
  - "sudo required for tc and kill on cake-shaper VM (non-root user)"
  - "Mangle rule filtering by action type (mark-connection/mark-packet), not comment text -- comment matching produced false positives"
  - "Removed set -e from gate script -- individual check failures should not abort remaining checks"

patterns-established:
  - "Gate check pattern: SSH from dev machine to VM, VM reaches router REST API for cross-device validation"
  - "5-point pre-tuning validation: CAKE qdiscs, no router CAKE, rate visibility, transport config, health endpoint"

requirements-completed: [GATE-01, GATE-02, GATE-03]

# Metrics
duration: 30min
completed: 2026-04-02
---

# Phase 126 Plan 01: Pre-Test Gate Summary

**Reusable bash gate script validates 5 pre-tuning conditions on production cake-shaper VM -- all 5/5 pass, environment confirmed ready for linux-cake A/B testing**

## Performance

- **Duration:** ~30 min (including human verification on production)
- **Started:** 2026-04-02T21:30:00Z
- **Completed:** 2026-04-02T22:00:00Z
- **Tasks:** 2 (1 auto + 1 human checkpoint)
- **Files modified:** 1

## Accomplishments

- Created scripts/check-tuning-gate.sh (431 lines) -- reusable 5-point gate check for pre-tuning validation
- All 5 gate checks pass on production cake-shaper VM (10.10.110.223)
- Confirmed: CAKE qdiscs on all 4 bridge NICs (ens16, ens17, ens27, ens28), no router CAKE, 38Mbit active shaping, linux-cake transport, v1.25.0 health

## Task Commits

Each task was committed atomically:

1. **Task 1: Write reusable pre-tuning gate check script** - `96332c4` (feat)
2. **Task 2: Disable router CAKE and run gate checks** - `b9399a8` (fix -- sudo/mangle/set-e corrections after production testing)

## Files Created/Modified

- `scripts/check-tuning-gate.sh` - Self-contained bash gate check script: 5 checks (CAKE qdiscs, no router CAKE, rate visibility, transport config, health endpoint), runs from dev machine via SSH to VM

## Decisions Made

- **sudo for tc/kill:** cake-shaper VM requires sudo for `tc -s qdisc show` and `kill -0` process checks (non-root kevin user)
- **Mangle filter by action type:** Original script grepped mangle rule comments for "cake" which matched unrelated rules; switched to filtering by action field (mark-connection, mark-packet) which is the actual indicator of CAKE-related mangle rules
- **Removed set -e:** Gate script needs to run all 5 checks even if one fails, so individual check failures should report FAIL and continue rather than aborting the script

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] sudo required for tc and kill on VM**

- **Found during:** Task 2 (production gate check execution)
- **Issue:** `tc -s qdisc show` and `kill -0 $PID` require sudo on cake-shaper VM (non-root user)
- **Fix:** Added `sudo` prefix to all `tc` and `kill` commands in SSH sessions
- **Files modified:** scripts/check-tuning-gate.sh
- **Verification:** Gate script runs successfully with sudo, all 5 checks pass
- **Committed in:** b9399a8

**2. [Rule 1 - Bug] Mangle rule comment matching too aggressive**

- **Found during:** Task 2 (production gate check execution)
- **Issue:** Grepping mangle rule comments for "cake" matched unrelated rules, causing false FAIL on check 2
- **Fix:** Changed to filter mangle rules by action type (mark-connection, mark-packet) instead of comment text
- **Files modified:** scripts/check-tuning-gate.sh
- **Verification:** Check 2 correctly reports PASS -- no active CAKE mangle rules
- **Committed in:** b9399a8

**3. [Rule 1 - Bug] set -e caused premature script exit on check failures**

- **Found during:** Task 2 (production gate check execution)
- **Issue:** `set -e` caused the entire script to abort when a check's grep returned non-zero, preventing remaining checks from running
- **Fix:** Removed `set -e` from the script so all 5 checks always execute and report independently
- **Files modified:** scripts/check-tuning-gate.sh
- **Verification:** All 5 checks run to completion, final summary correctly tallies pass/fail
- **Committed in:** b9399a8

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** All fixes necessary for correct script operation on production. No scope creep.

## Issues Encountered

- Router CAKE was already disabled on MikroTik before checkpoint -- no manual disabling needed (Step 1 of checkpoint was a no-op)

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - gate script is fully functional with no placeholder logic.

## Next Phase Readiness

- Gate script confirms environment is ready for A/B tuning
- Phase 127 (DL Parameter Sweep) can begin immediately
- All 5 prerequisites satisfied: linux-cake transport, CAKE qdiscs active, no double-shaping, rate changes visible, health endpoint healthy

## Self-Check: PASSED

- FOUND: scripts/check-tuning-gate.sh
- FOUND: commit 96332c4 (Task 1)
- FOUND: commit b9399a8 (Task 2 fix)
- FOUND: 126-01-SUMMARY.md

---

_Phase: 126-pre-test-gate_
_Completed: 2026-04-02_
