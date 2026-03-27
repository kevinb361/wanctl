# Phase 120: Adaptive Rate Step Tuning - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the tuning engine to learn optimal response parameters (step_up_mbps, factor_down, green_cycles_required) from production congestion/recovery episodes. Add oscillation lockout that freezes all response parameters when transition frequency exceeds a threshold. Response tuning ships disabled by default via exclude_params, matching the existing tuning graduation pattern. Completes the self-optimizing controller vision by closing the detection→response loop.

</domain>

<decisions>
## Implementation Decisions

### Episode Detection
- **D-01:** Claude's discretion on episode detection approach. Options: state transition parsing from wanctl_state 1m time series (identify discrete recovery/congestion episodes), rate-based aggregate heuristics (measure recovery speed and overshoot rates without per-episode granularity), or a hybrid. Choose based on what the existing 1m metric stream supports and strategy implementation complexity.

### Oscillation Lockout
- **D-02:** Claude's discretion on oscillation lockout mechanism (RTUN-04). Options: reuse existing `_parameter_locks` dict with long cooldown (like Phase 119 healer's `float('inf')` pattern), new oscillation freeze state with stability-based recovery, or other. Choose based on code fit and whether unfreeze should be time-based or condition-based. Hard constraint: must fire a Discord alert via AlertEngine when triggered.

### Layer Placement
- **D-03:** Claude's discretion on where response strategies sit in the 4-layer rotation. Options: new 5th RESPONSE_LAYER (clean separation, 5-hour cycle), extend ADVANCED_LAYER (keeps 4-hour cycle, more crowded), or other arrangement. Choose based on tuning cadence impact and separation of concerns.

### Per-Direction Handling
- **D-04:** Claude's discretion on how to handle separate DL/UL values for step_up_mbps (1.0 DL, 0.5 UL), factor_down (0.85 DL, 0.90 UL), and green_required (5 both). Options: 6 separate parameters (max flexibility, double parameter space), 3 paired with fixed ratio, DL-only tuning (reduced scope), or other. Choose based on blast radius management and existing per-direction config structure.

### Claude's Discretion
- Episode detection approach (D-01)
- Oscillation lockout mechanism and unfreeze logic (D-02)
- Layer placement in 4-layer rotation (D-03)
- Per-direction parameter handling (D-04)
- Strategy implementation internals (metric queries, analysis algorithms)
- Oscillation threshold default value and configurability
- How strategies consume episode data from the 1m metric stream
- Test structure and fixture design
- Whether new strategies go in existing files or new ones

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tuning Engine Core
- `src/wanctl/tuning/analyzer.py` -- `run_tuning_analysis()` orchestration, metric query, strategy dispatch
- `src/wanctl/tuning/models.py` -- `TuningConfig` (exclude_params frozenset, bounds), `TuningResult`, `PendingObservation`
- `src/wanctl/tuning/applier.py` -- Bounds enforcement, max_step_pct clamping, SQLite persistence
- `src/wanctl/tuning/safety.py` -- `check_and_revert()`, `measure_congestion_rate()`, `is_parameter_locked()`/`lock_parameter()`

### Existing Strategies (patterns to follow)
- `src/wanctl/tuning/strategies/base.py` -- `TuningStrategy` protocol with `analyze()` signature
- `src/wanctl/tuning/strategies/signal_processing.py` -- Signal strategies (hampel, EWMA) as reference implementation
- `src/wanctl/tuning/strategies/congestion_thresholds.py` -- Threshold calibration strategies
- `src/wanctl/tuning/strategies/advanced.py` -- Advanced strategies (fusion, reflector, baseline)

### Response Parameters (modification targets)
- `src/wanctl/autorate_continuous.py` lines 157-200 -- step_up_mbps, factor_down config schema
- `src/wanctl/autorate_continuous.py` lines 317-356 -- QueueController init (download_step_up, download_factor_down, green_required)
- `src/wanctl/autorate_continuous.py` lines 1370-1520 -- 3/4-zone state machine where response parameters are applied
- `src/wanctl/autorate_continuous.py` lines 1553-1627 -- `_apply_tuning_to_controller()` parameter mapping

### 4-Layer Rotation
- `src/wanctl/autorate_continuous.py` lines 4269-4399 -- Layer definitions, round-robin, strategy filtering, revert check

### Alert System
- `src/wanctl/alert_engine.py` -- AlertEngine `fire()` method for oscillation lockout Discord alert

### State Metrics
- `src/wanctl/autorate_continuous.py` lines 3585-3591 -- `_encode_state()` (GREEN=0, YELLOW=1, SOFT_RED=2, RED=3)
- `src/wanctl/storage/reader.py` -- `query_metrics()` for wanctl_state 1m time series

### Existing Tests
- `tests/test_tuning_safety_wiring.py` -- Safety/revert/locking tests
- `tests/test_advanced_tuning_strategies.py` -- Advanced strategy tests
- `tests/test_signal_tuning_strategies.py` -- Signal strategy tests
- `tests/test_threshold_tuning_strategies.py` -- Threshold strategy tests

### Prior Phase Context
- `.planning/phases/118-metrics-retention-strategy/118-CONTEXT.md` -- Retention config (Phase 118 guarantees 1m data availability for lookback)
- `.planning/phases/119-auto-fusion-healing/119-CONTEXT.md` -- FusionHealer pattern (standalone module, parameter locking via float('inf'))

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TuningStrategy` protocol in `strategies/base.py` -- New response strategies follow this exact pattern
- `measure_congestion_rate()` in `safety.py` -- Queries wanctl_state 1m data, counts SOFT_RED/RED fraction. Can be extended or reused for episode detection.
- `_encode_state()` -- State encoding (0-3) already in the metric stream at 1m granularity
- `check_and_revert()` + `PendingObservation` -- Safety pattern applies to response parameters too
- `AlertEngine.fire()` -- Ready for oscillation lockout alert (add new `oscillation_lockout` alert type)
- `lock_parameter()` / `is_parameter_locked()` -- Existing lock mechanism, used by healer (Phase 119) with `float('inf')` sentinel

### Established Patterns
- Strategies return `TuningResult | None` -- None means no change warranted
- `SafetyBounds` dataclass constrains each parameter's min/max/max_step_pct
- Applier clamps to bounds and filters trivial changes (< 0.1 delta)
- Layer rotation via `_tuning_layer_index % len(ALL_LAYERS)`
- exclude_params checked before strategy dispatch (not inside strategy)
- `load_time_constant_sec` domain: strategies output time constants, applier converts to alpha

### Integration Points
- `ALL_LAYERS` list in `autorate_continuous.py` line 4286 -- Add response strategies here
- `_apply_tuning_to_controller()` -- Add mapping for step_up_mbps, factor_down, green_required
- `TuningConfig.bounds` -- Add SafetyBounds for new parameters
- Config schema -- Add `tuning.bounds.step_up_mbps`, `tuning.bounds.factor_down`, `tuning.bounds.green_required`
- `exclude_params` default -- Response params excluded by default (RTUN-05)

### Key Constraint: Highest Blast Radius
Response parameters directly control bandwidth allocation. A bad step_up_mbps causes overshoot (saturated link). A bad factor_down causes either excessive sacrifice (too aggressive) or prolonged congestion (too gentle). A bad green_required causes premature recovery (oscillation) or delayed recovery (underutilization). Safety mechanisms must be robust.

</code_context>

<specifics>
## Specific Ideas

- Production defaults: step_up_mbps 1.0 DL / 0.5 UL, factor_down 0.85 DL / 0.90 UL, green_required 5 both directions
- The wanctl_state metric at 1m granularity encodes GREEN=0, YELLOW=1, SOFT_RED=2, RED=3 -- state transitions are directly observable in this time series
- The tuner's existing safety revert (1.5x congestion increase → 24h cooldown) applies to response parameters too
- RTUN-05 matches the existing graduation pattern: new params start in exclude_params, operator opts in when ready
- Phase 118 guarantees 1m data is retained for at least lookback_hours -- response strategies can rely on this

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 120-adaptive-rate-step-tuning*
*Context gathered: 2026-03-27*
