---
phase: 135
plan: 01
status: complete
started: 2026-04-03
completed: 2026-04-03
---

# Plan 135-01: UL A/B Test Matrix — Summary

## One-liner

21 RRUL flent runs completed: baseline (step_up=1/fd=0.85) + 6 configs (step_up 3/4/5 x factor_down 0.80/0.90), winner is B3 (step_up=5, factor_down=0.90) at +17.6% UL throughput

## What Was Built

Ran the full UL parameter A/B test matrix via flent RRUL against Dallas netperf. Results documented in 135-UL-RESULTS.md with per-run metrics and comparison table.

## Key Decisions

- Used actual production baseline (step_up=1, not 2 as plan assumed — config had diverged)
- Redid A1 runs after DL step_up corruption from scoped sed (switched to line-number sed)
- All configs restored to baseline between rows

## Key Files

### Created
- `.planning/phases/135-upload-recovery-tuning/135-UL-RESULTS.md`

## Issues Encountered

- Scoped sed corrupted DL step_up (15->35) during A1 setup. Fixed immediately, switched to line-number sed for remainder. A1 runs redone with correct DL.

## Self-Check: PASSED

- [x] 3 baseline runs completed
- [x] 18 matrix runs completed (6 configs x 3 runs)
- [x] DL params verified unchanged after fix
- [x] Production restored to baseline after testing
