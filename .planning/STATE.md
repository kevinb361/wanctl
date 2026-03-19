---
gsd_state_version: 1.0
milestone: v1.20
milestone_name: Adaptive Tuning
status: planning
last_updated: "2026-03-19T12:49:04.358Z"
last_activity: 2026-03-19
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 9
  completed_plans: 9
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Phase 101 — signal-processing-tuning

## Position

**Milestone:** v1.20 Adaptive Tuning
**Phase:** 101 of 102 (Signal Processing Tuning)
**Plan:** 2 of 2 complete
**Status:** Ready to plan
**Last activity:** 2026-03-19

Progress: [██████████] 100%

## Accumulated Context

### Key Decisions

- clamp_to_step uses two-phase clamping: bounds first, then max step percentage
- TuningStrategy is a Protocol (structural subtyping) not an ABC
- Cadence minimum 600 seconds (10 minutes) to prevent tuning abuse
- max_delta floor of 0.001 prevents zero-delta trap for small values
- StrategyFn is a Callable type alias, not Protocol -- strategies are pure functions
- Confidence scaling: min(1.0, data_hours / 24.0) penalizes short data spans
- Trivial change threshold: abs(clamped - old) < 0.1 skips at DEBUG level
- query_metrics import at module level for analyzer simplicity
- isinstance(tuning_config, TuningConfig) guard in maintenance loop prevents MagicMock truthy trap
- getattr is not True pattern for health endpoint MagicMock safety
- Separate last_tuning timer from last_maintenance (independent cadences)
- Strategy confidence = min(1.0, green_count / 1440.0) penalizes non-GREEN data spans
- Sub-window CoV convergence is stateless (no tuning_params query needed)
- MIN_GREEN_SAMPLES = 60 prevents unreliable percentiles from sparse GREEN data
- Test data needs inter-sub-window variance to avoid false convergence detection
- Lazy import of congestion_thresholds inside tuning enabled guard (matches existing analyzer/applier pattern)
- Lock functions are stateless (operate on caller-provided dict) so WANController owns state
- Near-zero pre_rate uses min_congestion_rate as denominator to avoid division-by-zero
- Revert TuningResults: confidence=1.0 (authoritative), data_points=0 (not data-driven)
- Lazy import of safety functions inside isinstance(TuningConfig) guard matches existing pattern
- Clear \_pending_observation regardless of revert check outcome to prevent stale re-check
- Health safety section only in active tuning state (omitted when disabled or awaiting_data)
- tune_alpha_load outputs load_time_constant_sec (0.5-10s), NOT alpha_load, to survive clamp_to_step rounding and trivial change filter
- Outlier rate from counter deltas / 1200 samples-per-minute; negative deltas discarded (counter reset)
- Step detection threshold = max(2x median_jitter, 2.0ms); settling = 20% move toward target tc per cycle
- Layer rotation via modular index (wc.\_tuning_layer_index % 3): signal->EWMA->threshold per tuning cycle
- EWMA layer parameter name is load_time_constant_sec (NOT alpha_load); tc-to-alpha conversion at apply time only
- Deque resize: deque(existing, maxlen=new) preserves rightmost elements when shrinking window
- Layer definitions inside isinstance(TuningConfig) guard, outside per-WAN loop (define once, use for all WANs)

### Known Issues

- Hampel filter default sigma=3.0/window=7 may need per-WAN tuning from production data
- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- Target outlier rate for Hampel is empirical (5-15% range), needs experimentation in Phase 101
- "Congestion rate" metric definition resolved in Phase 100: fraction of wanctl_state >= 2.0 (SOFT_RED/RED) in time window

### Roadmap Evolution

- Phase 103 added: Fix fusion baseline deadlock (IRTT path divergence freezes baseline via permanent delta > threshold)

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/` (carried from v1.18)
