---
gsd_state_version: 1.0
milestone: v1.20
milestone_name: Adaptive Tuning
status: completed
last_updated: "2026-03-19T21:37:32.914Z"
last_activity: "2026-03-19 - Completed quick task 260319-lk3: Fix state file persistence + tuning param restore"
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 13
  completed_plans: 13
  percent: 92
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Phase 102 — advanced-tuning

## Position

**Milestone:** v1.20 Adaptive Tuning
**Phase:** 102 of 103 (Advanced Tuning)
**Plan:** 3 of 3 complete
**Status:** v1.20 milestone complete
**Last activity:** 2026-03-19 - Completed quick task 260319-lk3: Fix state file persistence + tuning param restore

Progress: [█████████░] 92%

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
- Inline load EWMA in run_cycle preserves update_ewma() for ~32 test call sites (Phase 103)
- Freeze gate delta uses icmp_rtt - baseline_rtt (Hampel-filtered, no second EWMA needed) (Phase 103)
- Baseline is ICMP-derived concept -- never contaminate with fused/IRTT signals (Phase 103)
- --tuning handler placed before --alerts in main() for priority ordering (Phase 102)
- Signal confidence used as proxy for reflector quality (per-host success rates not in SQLite) (Phase 102)
- Reliability-ratio pattern: ICMP=1/(1+variance), IRTT=(1-loss_fraction)/(1+jitter), weight=ICMP_rel/(ICMP_rel+IRTT_rel) (Phase 102)
- Baseline bounds: p5*0.9 for min (hard floor 1.0ms), p95*1.1 for max, from wanctl_rtt_baseline_ms history (Phase 102)
- ADVANCED_LAYER placed 4th (last) in ALL_LAYERS -- meta-parameters run after core signal chain stabilizes (Phase 102)
- Lazy import of advanced strategies inside isinstance(TuningConfig) guard matches existing pattern (Phase 102)

### Known Issues

- Hampel filter default sigma=3.0/window=7 may need per-WAN tuning from production data
- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- Target outlier rate for Hampel is empirical (5-15% range), needs experimentation in Phase 101
- "Congestion rate" metric definition resolved in Phase 100: fraction of wanctl_state >= 2.0 (SOFT_RED/RED) in time window

### Roadmap Evolution

- Phase 103 added: Fix fusion baseline deadlock (IRTT path divergence freezes baseline via permanent delta > threshold)

### Blockers

None.

### Quick Tasks Completed

| #          | Description                                       | Date       | Commit  | Directory                                                                  |
| ---------- | ------------------------------------------------- | ---------- | ------- | -------------------------------------------------------------------------- |
| 260319-lk3 | Fix state file persistence + tuning param restore | 2026-03-19 | 6cbbd80 | [260319-lk3](./quick/260319-lk3-fix-state-file-persistence-and-tuning-pa/) |

### Pending Todos

5 todos in `.planning/todos/pending/`
