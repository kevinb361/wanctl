---
phase: 135
plan: 02
status: complete
started: 2026-04-03
completed: 2026-04-03
---

# Plan 135-02: Analysis + Deploy — Summary

## One-liner

Winner B3 (step_up=5, factor_down=0.90) deployed to production — +17.6% UL throughput, -7% latency, no DL regression

## What Was Built

Analyzed 21 flent runs, selected B3 as winner (exceeds 15% throughput threshold), deployed to production, updated repo config.

## Key Decisions

- B3 over B2: B3 exceeds 15% threshold (+17.6%), B2 narrowly misses (+13.4%). B2 has better latency but throughput was the primary objective.
- factor_down=0.90 consistently beat 0.80 across all step_up values — gentler decay is better for UL on DOCSIS
- step_up=5 (13% of ceiling) shows no oscillation — could test higher in future

## Key Files

### Modified
- `configs/spectrum-vm.yaml` — UL step_up=5, factor_down=0.90 with Phase 135 validation dates

## Self-Check: PASSED

- [x] Winner selected with data-backed rationale
- [x] Exceeds 15% threshold (17.6% UL throughput improvement)
- [x] Deployed to production with SIGUSR1 reload
- [x] Repo config updated with validation dates
- [x] Health status confirmed healthy after deploy
