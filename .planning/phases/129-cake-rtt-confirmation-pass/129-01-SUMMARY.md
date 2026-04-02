---
phase: 129-cake-rtt-confirmation-pass
plan: 01
subsystem: tuning
tags:
  [cake, rtt, aqm, cobalt, confirmation-pass, rrul, flent, linux-cake, docsis]

requires:
  - phase: 127-dl-parameter-sweep
    provides: "9 DL parameter winners for linux-cake transport"
  - phase: 128-ul-parameter-sweep
    provides: "3 UL parameter winners for linux-cake transport"
provides:
  - "CAKE rtt=40ms validated (tested 25-100ms range)"
  - "Confirmation pass: 6/7 params confirmed, target_bloat_ms flipped 15->9"
  - "Final validated linux-cake configuration ready for production commit"
affects: [130-production-config-commit]

tech-stack:
  added: []
  patterns:
    [
      "CAKE rtt ~2x baseline RTT guideline",
      "confirmation pass catches CAKE rtt/target_bloat coupling",
    ]

key-files:
  created:
    - ".planning/phases/129-cake-rtt-confirmation-pass/129-CONFIRMATION-RESULTS.md"
  modified:
    - "docs/CABLE_TUNING.md"
    - ".planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md"

key-decisions:
  - "CAKE rtt=40ms optimal (~2x baseline RTT of 22-25ms)"
  - "target_bloat_ms reverted from 15 to 9 after confirmation pass (CAKE rtt interaction)"
  - "Confirmation pass methodology validated -- caught real interaction effect"

patterns-established:
  - "CAKE rtt and target_bloat_ms are coupled: always re-test target_bloat after changing rtt"
  - "Confirmation pass: re-test all changed params with full set active after any new parameter introduction"

requirements-completed: [TUNE-03, TUNE-04]

duration: 32min
completed: 2026-04-02
---

# Phase 129: CAKE RTT + Confirmation Pass Summary

**CAKE rtt=40ms validated (5-way test), confirmation pass caught target_bloat_ms interaction flip from 15 back to 9 -- final linux-cake config has 7 total changes from REST baseline**

## Performance

- **Duration:** 32 min (18:18-18:50 CDT)
- **Started:** 2026-04-02T23:18:00Z
- **Completed:** 2026-04-02T23:53:00Z
- **Tasks:** 10 (0-8 checkpoint, 9 auto)
- **Files modified:** 3

## Accomplishments

- CAKE rtt=40ms wins 5-way test (25/35/40/50/100ms) -- median -16%, p99 -39%, throughput +7% vs default 100ms
- Confirmation pass: 6 of 7 changed parameters confirmed with full winner set active
- Caught critical interaction: CAKE rtt=40ms restored target_bloat_ms=9 viability (was 15 under rtt=100ms)
- Complete documentation with CAKE rtt section, confirmation pass section in CABLE_TUNING.md
- Final validated linux-cake configuration ready for Phase 130 production commit

## Task Commits

Each task was committed atomically:

1. **Tasks 0-8: CAKE rtt test + 7 confirmation re-tests** - Human checkpoint tasks (no code commits, live A/B testing on production VM)
2. **Task 9: Document CAKE rtt + confirmation results** - `64eb414` (docs)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified

- `.planning/phases/129-cake-rtt-confirmation-pass/129-CONFIRMATION-RESULTS.md` - Complete test data: CAKE rtt 5-way + 7 confirmation results with metrics
- `docs/CABLE_TUNING.md` - Added CAKE rtt section, confirmation pass section, corrected target_bloat_ms in recommended config
- `.planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md` - Added Phase 129 cross-reference and post-confirmation correction

## Decisions Made

- **CAKE rtt=40ms:** Optimal is ~2x baseline RTT. Below 35ms starts dropping good packets. Above 50ms leaves too much queue slack. Guideline for other links: start at 2x baseline.
- **target_bloat_ms reverted to 9:** Phase 127 found 15 winning (with CAKE rtt=100ms). Phase 129 confirmation pass with rtt=40ms flipped back to 9. Per D-08 methodology, full-set result is authoritative.
- **Confirmation pass validated:** The methodology proved its value by catching a real parameter interaction. Without it, production would have run target_bloat=15 which is suboptimal with rtt=40ms.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Extended CAKE rtt test from 2-way to 5-way**

- **Found during:** Task 1
- **Issue:** Plan specified 50ms vs 100ms only. Baseline RTT of 22-25ms suggested optimal rtt might be below 50ms.
- **Fix:** Tested 5 values (25/35/40/50/100ms) to find true optimum at 40ms
- **Files modified:** 129-CONFIRMATION-RESULTS.md
- **Verification:** 40ms dominated all metrics across the range
- **Committed in:** 64eb414

---

**Total deviations:** 1 auto-fixed (Rule 2 - extended test range for better result)
**Impact on plan:** Positive -- found true optimum at 40ms instead of selecting between only 50ms and 100ms.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Final validated configuration documented and ready for Phase 130 production config commit
- All parameter winners confirmed or corrected via confirmation pass
- Production is currently running the confirmed values (applied during testing)
- Phase 130 needs to: update spectrum.yaml, update configs/spectrum-vm.yaml, restart service, verify health

## Self-Check: PASSED

- [x] 129-CONFIRMATION-RESULTS.md exists
- [x] 129-01-SUMMARY.md exists
- [x] docs/CABLE_TUNING.md exists
- [x] Commit 64eb414 exists
- [x] No stubs found

---

_Phase: 129-cake-rtt-confirmation-pass_
_Completed: 2026-04-02_
