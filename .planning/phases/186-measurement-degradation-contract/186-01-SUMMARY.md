---
phase: 186-measurement-degradation-contract
plan: 01
subsystem: health
tags: [measurement, health, contract, audit]
requires: []
provides:
  - "Inline collapse-path audit for raw RTT, reflector-host, cadence, and stale-reuse call sites"
  - "Locked v1.38 measurement-health contract for downstream implementation and test plans"
affects: [186-02-PLAN.md, 186-03-PLAN.md, wan_health.measurement]
tech-stack:
  added: []
  patterns: [inline plan contract, version-pinned code-path audit]
key-files:
  created:
    - .planning/phases/186-measurement-degradation-contract/186-01-SUMMARY.md
  modified:
    - .planning/phases/186-measurement-degradation-contract/186-01-PLAN.md
key-decisions:
  - "Locked the measurement contract in the plan itself so 186-02 and 186-03 quote one source of truth."
  - "Kept the phase documentation-only: no src/wanctl code changed."
patterns-established:
  - "Contract phases can pin exact file:line anchors inline in PLAN.md instead of separate audit artifacts."
  - "Measurement contract terminology is locked to 6 legal cross-product combinations plus a boundary partition."
requirements-completed: []
duration: 8 min
completed: 2026-04-15
---

# Phase 186 Plan 01: Measurement Collapse Audit And Locked Health Contract Summary

**Inline measurement-collapse audit with anchored stale-reuse sites and a locked `wan_health.measurement` contract for Phase 186 follow-on plans**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-15T09:19:52Z
- **Completed:** 2026-04-15T09:27:30Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added the in-plan `## Collapse Path Audit` section with anchored write, read, cadence, stale-reuse, and consumer-surface bullets.
- Added the in-plan `## Locked Contract (v1.38 Phase 186)` section with literal field, state, cadence, staleness, and requirement-trace rules for downstream plans.
- Kept the plan scoped to planning artifacts only; no `src/wanctl/` files were changed by this plan.

## Task Commits

1. **Task 1: Produce Collapse Path Audit section inline in this PLAN (strictly descriptive)** - `767a709` (`feat`)
2. **Task 2: Lock the v1.38 Phase 186 measurement-health contract inline** - `be508da` (`feat`)
3. **Rule 1 follow-up fix: remove expanded cross-product wording** - `223067f` (`fix`)

## Files Created/Modified

- `.planning/phases/186-measurement-degradation-contract/186-01-PLAN.md` - Stores the new audit and locked contract sections used by Plans 186-02 and 186-03.
- `.planning/phases/186-measurement-degradation-contract/186-01-SUMMARY.md` - Records plan outcomes, deviations, and readiness for the next plans.

## Decisions Made

- Locked the contract directly in `186-01-PLAN.md` rather than a separate audit file so downstream plans consume one version-pinned source.
- Preserved the existing section boundary: `measurement` is the only contract surface touched by this plan, while `reflector_quality` remains orthogonal.
- Kept requirement status unchanged in `REQUIREMENTS.md` because this contract-only plan does not yet satisfy the runtime behavior described by `MEAS-01` and `MEAS-03`.

## Audit Counts

- `write site`: 3 bullets
- `read site`: 4 bullets
- `cadence site`: 3 bullets
- `stale reuse site`: 4 bullets
- `consumer surface`: 2 bullets

## Locked Contract Surface

- New fields: `state`, `successful_count`, `stale`
- State mapping: `3 -> healthy`, `2 -> reduced`, `<=1 -> collapsed`
- Staleness rule: `stale = True` when cadence is missing/non-positive or `staleness_sec` is missing; otherwise `stale = staleness_sec > 3 * cadence_sec`
- Cardinality framing: `3 x 2 = 6` legal cross-product combinations plus a separate `successful_count` boundary partition
- Existing fields preserved: `available`, `raw_rtt_ms`, `staleness_sec`, `active_reflector_hosts`, `successful_reflector_hosts`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tightened the audit-section verification snippet**
- **Found during:** Task 1
- **Issue:** The original `awk '/## Collapse Path Audit/,/^## /'` acceptance snippet could match the task text earlier in the same plan file and falsely fail the descriptive-wording check.
- **Fix:** Replaced it with a section-scoped `awk` expression that starts only at the literal heading line.
- **Files modified:** `.planning/phases/186-measurement-degradation-contract/186-01-PLAN.md`
- **Verification:** The section-scoped wording check exits cleanly against the completed audit section.
- **Committed in:** `767a709`

**2. [Rule 1 - Bug] Removed prohibited expanded-cardinality wording from the locked contract**
- **Found during:** Task 2 verification
- **Issue:** The locked contract prose still contained explicit expanded-cardinality wording even though the plan requires the contract to use only the `6 legal cross-product combinations + boundary partition` framing.
- **Fix:** Reworded the sentence so the contract keeps the required framing without the prohibited terminology.
- **Files modified:** `.planning/phases/186-measurement-degradation-contract/186-01-PLAN.md`
- **Verification:** Section-scoped grep confirms the locked contract contains `3 x 2 = 6` and no prohibited expanded-cardinality phrase.
- **Committed in:** `223067f`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes were documentation-only and kept the plan’s contract and verification semantics internally consistent. No runtime scope creep.

## Issues Encountered

- `.planning/` is gitignored in this worktree, so plan artifacts required `git add -f` for each commit.
- The worktree already contained unrelated dirty `src/` and `tests/` changes; this plan stayed scoped to the phase planning files only.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 186-02 can implement the locked `measurement` contract against the anchored controller and health-check call sites.
- Plan 186-03 can build contract tests from the pinned field list, state boundaries, staleness formula, and cardinality language.
- No blockers remain for the next plan.

## Known Stubs

None.

## Self-Check: PASSED

- Found `.planning/phases/186-measurement-degradation-contract/186-01-PLAN.md`
- Found `.planning/phases/186-measurement-degradation-contract/186-01-SUMMARY.md`
- Verified commits `767a709`, `be508da`, and `223067f` exist in git history

---
*Phase: 186-measurement-degradation-contract*
*Completed: 2026-04-15*
