# Phase 111: Auto-Tuning Production Hardening — Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Source:** Production analysis (live health endpoints, metrics DB queries, code review)

<domain>
## Phase Boundary

Harden v1.20 auto-tuning based on 6 days of production data (130 adjustments, 0 reverts). Two categories:
1. **Config bounds**: 4 YAML bound changes across both WANs to unlock parameters stuck at bounds
2. **Code fix**: SIGP-01 outlier rate calculation uses wrong denominator, underestimates by 60x

Scope: configs/spectrum.yaml, configs/att.yaml, src/wanctl/tuning/strategies/signal_processing.py, tests.
No changes to core control logic, state machine, or architectural spine.

</domain>

<decisions>
## Implementation Decisions

### Config: ATT Bounds
- hampel_window_size max: 15 -> 21 (tuner pegged at ceiling for 3+ days, jitter 0.34ms wants wider window, interpolation targets 15+ consistently)

### Config: Spectrum Bounds
- target_bloat_ms min: 10 -> 5 (currently pegged at floor, link may benefit from tighter threshold)
- warn_bloat_ms min: 25 -> 15 (currently pegged at floor)
- baseline_rtt_max min: 30 -> 25 (currently pegged at floor, p95 RTT ~24ms, 25ms gives margin)

### Code: SIGP-01 Rate Normalization Bug
- File: src/wanctl/tuning/strategies/signal_processing.py
- Bug: Line 123 divides counter delta by fixed SAMPLES_PER_MINUTE=1200, assuming consecutive DB records are 1 minute apart
- Reality: metrics are recorded every ~0.05s (68K records/hour), so counter deltas between records are tiny
- Effect: rate = delta / 1200 yields 0.2% when true rate is 11.9% (60x underestimate)
- Fix: replace `delta / SAMPLES_PER_MINUTE` with `delta / max(time_gap * 20, 1)` using actual time between consecutive timestamps
- SAMPLES_PER_MINUTE constant becomes unused, remove it
- The `20` comes from 20Hz cycle rate (50ms interval) — use existing CYCLE_INTERVAL constant if available
- Note: corrected rate (11.9%) is within target range, so sigma 2.8 is correct. Bug prevents future adaptation if recording density changes.

### Testing
- Unit tests for tune_hampel_sigma with various recording densities (1s, 5s, 60s gaps)
- Verify rate calculation produces consistent outlier rate regardless of recording interval
- Test edge cases: zero time gap, counter reset (negative delta), single sample

### Claude's Discretion
- Whether to add a dedicated constant for cycle rate (20) vs computing from CYCLE_INTERVAL
- Test fixture structure and parametrization approach
- Whether to log a warning when time_gap is 0 between records

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Signal Processing Strategy
- `src/wanctl/tuning/strategies/signal_processing.py` — Contains SIGP-01 (tune_hampel_sigma) with the bug at line 123, SAMPLES_PER_MINUTE constant at line 42

### Tuning Infrastructure
- `src/wanctl/tuning/applier.py` — Bounds enforcement and trivial-change filter
- `src/wanctl/tuning/models.py` — SafetyBounds, clamp_to_step

### Production Config
- `configs/spectrum.yaml` — Spectrum tuning bounds (lines ~122-155)
- `configs/att.yaml` — ATT tuning bounds

### Existing Tests
- `tests/` — Check for existing signal_processing strategy tests to extend

</canonical_refs>

<specifics>
## Specific Ideas

### Production Evidence
- Spectrum: 74 adjustments, 0 reverts, outlier_rate 27.3% cumulative but 11.9% hourly (corrected)
- ATT: 56 adjustments, 0 reverts, 100% GREEN, 1.1M consecutive green cycles
- ATT tuner stopped 32h ago — all params at bounds
- Alert flapping dropped 98% after tuning engaged (228/day to 2/day)

### Diagnostic Query (reproduces the bug)
```python
# Current (buggy): rate = delta / 1200 → 0.2%
# Corrected: rate = delta / (time_gap * 20) → 11.9%
# Underestimation factor: 60x
```

</specifics>

<deferred>
## Deferred Ideas

- Bound saturation detection (log when parameter hits bound repeatedly)
- ATT fusion/IRTT enablement (separate concern, link is stable without it)
- Tuning frequency reduction when all params converged (optimization, not needed)

</deferred>

---

*Phase: 111-auto-tuning-production-hardening-config-bounds-sigp-01-rate-fix*
*Context gathered: 2026-03-25 via production analysis*
