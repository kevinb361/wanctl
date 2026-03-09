# Research Summary: WAN-Aware Steering Integration

**Domain:** Dual-WAN adaptive steering with secondary WAN RTT signal
**Researched:** 2026-03-08
**Overall confidence:** HIGH

## Executive Summary

The wanctl steering daemon currently makes failover decisions based on local CAKE queue signals (RTT delta, drops, queue depth) assessed via `assess_congestion_state()` and scored through the `ConfidenceController`. The autorate daemon running on the same container has a richer view of WAN health through its 4-state download zone (GREEN/YELLOW/SOFT_RED/RED) computed from EWMA-smoothed end-to-end RTT deltas, but this state is never persisted to the shared state file. The dl_zone is computed every 50ms cycle in `adjust_4state()` and logged, but only `ewma.baseline_rtt` and `ewma.load_rtt` are written to the state file.

The integration requires two changes: (1) autorate must write its congestion state to the state file, and (2) steering must read it and feed it into the confidence scoring model. The confidence model is the right injection point because it already aggregates multiple signals into a single score with temporal filtering (sustain timers, flap detection).

No new classes are needed. The existing `compute_confidence()` function already has a pattern for sustained state detection (`SOFT_RED_sustained` checks last 3 history entries). WAN state can follow this exact pattern: add `wan_state` and `wan_state_history` to `ConfidenceSignals`, add WAN weights to `ConfidenceWeights`, add a scoring block to `compute_confidence()`. All temporal filtering is handled by (a) history-based sustained detection in the score computation, and (b) the existing `TimerManager` sustain timers that gate the confidence score before it triggers routing changes.

Total estimated changes: ~60 lines production code across 5 existing files, ~150-200 lines tests. Zero new dependencies. Zero new files.

## Key Findings

**Stack:** Zero new dependencies. All patterns already exist in codebase.
**Architecture:** WAN state injected as secondary weighted signal in existing `compute_confidence()` function.
**Critical pitfall:** Autorate state file currently does NOT contain congestion state (dl_zone). It only has `ewma.baseline_rtt` and `ewma.load_rtt`. The zone string is computed locally in `WANController.run_cycle()` and never persisted. This is the first thing that must change.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Autorate State Extension** - Add congestion state to state file
   - Addresses: dl_zone/ul_zone persistence in WANControllerState schema
   - Avoids: Breaking existing state file consumers (new key, old readers ignore it)
   - Low risk: adds data that existing consumers silently skip

2. **Steering WAN State Integration** - Read WAN state and wire into confidence scoring
   - Addresses: AutorateStateLoader refactor, ConfidenceSignals extension, scoring weights, daemon wiring
   - Avoids: Modifying assess_congestion_state (single responsibility), creating hard gates
   - Depends on Phase 1 for real data (can develop/test with mocked state files)

3. **Observability and Configuration** - Health endpoint, config, logging
   - Addresses: WAN state visibility in health endpoint, configurable weights/hysteresis
   - Avoids: Over-engineering config (start with defaults, tune in production)
   - Depends on Phases 1-2 for data flow

**Phase ordering rationale:**
- Phase 1 must come first because steering needs data to read
- Phase 1 is independently deployable with zero risk (adds data, breaks nothing)
- Phase 2 is the core integration; can develop with mock state files before Phase 1 deploys
- Phase 3 is polish making the integration observable and tunable
- Phases 1-2 could potentially combine into a single phase (total ~40 lines production code)

**Research flags for phases:**
- Phase 1: Standard pattern, no research needed (follows existing save_state/load_state patterns exactly)
- Phase 2: Weight values (30/15/5/0) are educated estimates; need production validation via dry-run, not research
- Phase 3: Standard pattern, no research needed

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new deps, all patterns pre-existing |
| Features | HIGH | Single clear feature, well-defined scope |
| Architecture | HIGH | All integration points verified against actual source code |
| Pitfalls | HIGH | Well-understood domain, similar patterns already implemented |

## Gaps to Address

- **Weight calibration:** WAN_RED=30, WAN_SOFT_RED=15, WAN_YELLOW=5 are reasonable starting points based on existing CAKE weight ratios and threshold math, but optimal values require production observation with dry-run mode enabled.
- **Sustained cycle count:** 3-cycle sustained requirement for WAN RED mirrors existing SOFT_RED_sustained pattern but may need adjustment based on observed WAN state flicker frequency.
- **Steering interval mismatch:** Steering runs at 0.5s (from config `measurement.interval_seconds`) while autorate runs at 50ms. Each steering file read gets the latest of ~10 autorate cycles. This is fine (already temporally filtered by autorate's own hysteresis in adjust_4state), but worth noting.
- **State file naming:** Config says `cake_state_sources.primary: /run/wanctl/spectrum_state.json` but autorate derives state file from lock file path (`/run/wanctl/spectrum_state.json`). These match. Verified no mismatch.
