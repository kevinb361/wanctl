# Phase 182: ATT Footprint Closure - Research

**Researched:** 2026-04-14
**Domain:** ATT-specific metrics DB footprint reduction, production-safe compaction, milestone closeout
**Confidence:** HIGH

## Summary

Phase 182 exists because `STOR-06` is still open after Phase 181. The production-safe reduction path worked for Spectrum but did not materially shrink ATT. This phase should stay narrow:

1. explain the ATT-specific non-reduction using direct production evidence
2. apply only the storage-side reduction step needed to shrink ATT
3. re-prove the production outcome against the fixed `2026-04-13` baseline

This should remain a storage/operations phase. Do not change congestion logic, thresholds, timing, or safety behavior.

## What Phase 181 Already Proved

### 1. The reduction mechanism is real

Phase 181 demonstrated that the offline reduction path can materially shrink a live per-WAN DB without changing control logic. Spectrum dropped by roughly `366 MB` against baseline.

### 2. The startup regression is fixed

The earlier watchdog failure was caused by pre-health startup storage work, not by the history-reader changes. That recovery is already complete and should not be reopened here except as a regression check.

### 3. The operator story is now explicit

- CLI is the authoritative merged cross-WAN history proof path.
- `/metrics/history` is endpoint-local and exposes `metadata.source`.

Phase 182 should preserve that story, not redesign it.

## Most Likely Reasons ATT Did Not Shrink

The current evidence suggests one or more of these ATT-specific conditions:

1. ATT did not go through the same effective offline compaction path that Spectrum did.
2. ATT still holds a larger live retained set at the moment compaction was attempted, so pruning did not create enough reclaimable space before rewrite.
3. ATT compaction was interrupted or not completed, leaving the file effectively unchanged.
4. ATT may have higher write churn during the verification window, so post-compaction growth masked a small reduction.

The phase should verify these directly instead of assuming config drift or schema differences.

## Recommended Plan Split

### Plan 01: ATT reduction precheck and exact operator procedure

Goal: prove why ATT stayed flat and capture the exact ATT-only procedure that should shrink it safely.

Expected focus:
- compare ATT vs Spectrum reduction path execution
- inspect ATT DB inventory, retention shape, and live service state
- write the ATT-specific operator runbook/evidence note

### Plan 02: Execute the ATT-only reduction path and preserve operator safety

Goal: make the smallest repo-side or script-side change needed to support a reliable ATT reduction, then run the ATT procedure.

Expected focus:
- only adjust storage-maintenance or operator helper surfaces if needed
- avoid any control-loop or timing changes
- ensure restart/health/canary/soak still remain valid

### Plan 03: Capture final production evidence and close STOR-06

Goal: compare ATT and Spectrum against the fixed baseline and close the milestone only if both active per-WAN DBs are now materially smaller.

Expected focus:
- final stat comparison to `2026-04-13`
- current `storage.status`, canary, soak, and history proof path
- explicit satisfied/unsatisfied decision for `STOR-06`

## Risks And Boundaries

- Do not treat `storage.status: ok` as proof of reduction.
- Do not broaden `/metrics/history` back into a merged cross-WAN proof path.
- Do not claim success from repo-side plausibility alone; Phase 182 is production-evidence-driven.
- Do not change retention semantics unless the ATT evidence shows the existing reduction path is genuinely insufficient.

## Evidence Required To Close STOR-06

The phase should not close the requirement without all of the following:

1. direct `stat` evidence showing `metrics-att.db` is materially smaller than the fixed `2026-04-13` baseline
2. confirmation that Spectrum remains materially smaller too
3. `soak-monitor` and canary results showing no operator workflow regression
4. a fresh CLI and endpoint-local HTTP proof check showing the supported history-reader story still holds

## Repo-Side Preparation Expectation

This phase is likely mostly operational. Repo changes should only happen if the current reduction helper or docs are insufficient to run the ATT reduction safely or repeatably.
