# Phase 120: Adaptive Rate Step Tuning - Research

**Researched:** 2026-03-27
**Domain:** Tuning engine extension -- response parameter optimization (step_up_mbps, factor_down, green_cycles_required)
**Confidence:** HIGH

## Summary

Phase 120 extends the existing 4-layer tuning engine to learn optimal response parameters from production congestion/recovery episodes. The existing tuning infrastructure is mature (10+ strategies, safety revert, parameter locking, 4-layer rotation, exclude_params gating) -- this phase adds 3 new strategies following established patterns, a 5th rotation layer, oscillation lockout with Discord alerting, and controller attribute mapping for parameters that live on QueueController objects rather than WANController.

The highest-risk aspect is that response parameters directly control bandwidth allocation. A bad step_up_mbps causes link saturation (overshoot). A bad factor_down causes either bandwidth starvation (too aggressive) or prolonged congestion (too gentle). A bad green_required causes oscillation (too low) or underutilization (too high). The existing safety revert mechanism (1.5x congestion increase triggers 24h cooldown) applies, but the oscillation lockout (RTUN-04) adds a second safety layer specific to response parameter interactions.

**Primary recommendation:** Add a 5th RESPONSE_LAYER with 3 new pure-function strategies in a new `response.py` module. Use state transition counting in the 1m wanctl_state time series for episode detection. Implement oscillation lockout via the existing `_parameter_locks` dict with a long cooldown and a new `oscillation_lockout` alert type. Handle DL/UL as 6 separate parameters (3 per direction) for maximum flexibility, since the existing config already has distinct per-direction values. Ship disabled via exclude_params (RTUN-05).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation decisions are Claude's discretion.

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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RTUN-01 | Tuner learns optimal step_up_mbps from production recovery episode analysis | Recovery episode detection via state transitions in wanctl_state 1m time series; strategy measures recovery speed (time from RED/SOFT_RED to GREEN at ceiling) and adjusts step_up toward faster recovery without overshoot |
| RTUN-02 | Tuner learns optimal factor_down from congestion resolution speed | Congestion episode detection via state transitions; strategy measures resolution speed and severity, adjusts factor_down toward faster resolution without excessive bandwidth sacrifice |
| RTUN-03 | Tuner learns optimal green_cycles_required from step-up re-trigger rate | Counts how often step-up is followed by re-entry to RED/SOFT_RED within a short window; high re-trigger rate means green_required is too low |
| RTUN-04 | Oscillation lockout freezes all response parameters when transitions/minute exceeds threshold | State transition rate computed from wanctl_state time series; when rate exceeds configurable threshold, all 6 response parameters locked via _parameter_locks with long cooldown + Discord alert |
| RTUN-05 | Response tuning is opt-in via exclude_params (disabled by default) | 6 new parameter names added to default exclude_params; operator removes them from exclude_params to opt in |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (statistics) | 3.12 | mean, median, quantiles for episode analysis | Zero deps, matches all existing strategies |
| Python stdlib (time) | 3.12 | monotonic clock for parameter locks | Matches existing safety.py pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| wanctl.tuning.models | internal | SafetyBounds, TuningResult, TuningConfig, clamp_to_step | All strategy return types and config |
| wanctl.tuning.safety | internal | measure_congestion_rate, is_parameter_locked, lock_parameter | Oscillation detection and lockout |
| wanctl.tuning.analyzer | internal | run_tuning_analysis, StrategyFn | Strategy dispatch |
| wanctl.tuning.applier | internal | apply_tuning_results, persist_tuning_result | Bounds enforcement and persistence |
| wanctl.alert_engine | internal | AlertEngine.fire() | Oscillation lockout Discord alert |
| wanctl.storage.reader | internal | query_metrics | 1m metric time series access |

**Zero new Python dependencies.** All strategies use stdlib only, matching the existing pattern.

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/tuning/strategies/
    base.py                    # TuningStrategy protocol (existing)
    signal_processing.py       # SIGP-01/02/03 (existing)
    congestion_thresholds.py   # CALI-01/02 (existing)
    advanced.py                # ADVT-01/02/03 (existing)
    response.py                # NEW: RTUN-01/02/03 strategies

tests/
    test_response_tuning_strategies.py  # NEW: strategy unit tests
    test_response_tuning_wiring.py      # NEW: integration/wiring tests
```

### Pattern 1: Pure Function Strategy (StrategyFn)
**What:** Each strategy is a pure function matching `Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]`.
**When to use:** All 3 new response strategies follow this.
**Example (from existing codebase):**
```python
# Source: src/wanctl/tuning/strategies/signal_processing.py
def tune_hampel_sigma(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    # Extract relevant metrics from metrics_data
    # Analyze and compute candidate value
    # Return TuningResult or None if no change warranted
```

### Pattern 2: Episode Detection via State Transition Counting
**What:** Parse the wanctl_state 1m time series to identify discrete episodes (congestion onset, recovery completion) by detecting state transitions.
**When to use:** RTUN-01 (recovery episodes), RTUN-02 (congestion episodes), RTUN-03 (re-trigger detection).
**Key insight:** The 1m granularity uses MODE aggregation for wanctl_state. State values: GREEN=0, YELLOW=1, SOFT_RED=2, RED=3. A transition from state >= 2 to state 0 marks a recovery episode. A transition from state 0 to state >= 2 marks congestion onset. Consecutive state values build a timeline of episodes.

**Algorithm sketch for episode detection:**
```python
def _detect_episodes(metrics_data: list[dict]) -> list[Episode]:
    """Detect congestion/recovery episodes from state time series."""
    state_by_ts: dict[int, float] = {}
    rate_by_ts: dict[int, float] = {}
    for row in metrics_data:
        ts = row["timestamp"]
        if row["metric_name"] == "wanctl_state":
            state_by_ts[ts] = row["value"]
        elif row["metric_name"] == "wanctl_rate_download_mbps":
            rate_by_ts[ts] = row["value"]

    # Walk sorted timestamps, detect transitions
    sorted_ts = sorted(state_by_ts.keys())
    episodes = []
    in_congestion = False
    congestion_start = None
    for i, ts in enumerate(sorted_ts):
        state = state_by_ts[ts]
        if not in_congestion and state >= 2.0:
            in_congestion = True
            congestion_start = ts
        elif in_congestion and state == 0.0:
            in_congestion = False
            episodes.append(Episode(
                congestion_start=congestion_start,
                recovery_end=ts,
                duration_sec=ts - congestion_start,
                # ... rate data for overshoot/undershoot analysis
            ))
    return episodes
```

### Pattern 3: Per-Direction Parameter Naming
**What:** Use direction-prefixed parameter names to handle DL/UL separately.
**When to use:** All 6 response parameters.
**Convention:**
- `dl_step_up_mbps`, `ul_step_up_mbps`
- `dl_factor_down`, `ul_factor_down`
- `dl_green_required`, `ul_green_required`

This matches the existing config structure where `continuous_monitoring.download.step_up_mbps` and `continuous_monitoring.upload.step_up_mbps` are distinct values.

### Pattern 4: 5th Rotation Layer
**What:** Add RESPONSE_LAYER as 5th element in ALL_LAYERS list, extending the rotation cycle from 4 hours to 5 hours.
**Why:** Clean separation of concerns. Response strategies have the highest blast radius and deserve their own analysis cycle. Mixing with ADVANCED_LAYER would crowd it (currently 4 strategies, adding 6 more would make 10).

```python
RESPONSE_LAYER = [
    ("dl_step_up_mbps", tune_step_up),
    ("ul_step_up_mbps", tune_step_up),
    ("dl_factor_down", tune_factor_down),
    ("ul_factor_down", tune_factor_down),
    ("dl_green_required", tune_green_required),
    ("ul_green_required", tune_green_required),
]
ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER, ADVANCED_LAYER, RESPONSE_LAYER]
```

**NOTE:** The same strategy function handles both DL and UL -- it's parameterized via the metrics_data which already contains direction-specific state data. The wanctl_state metric recorded in `_encode_state` is for the download direction (line 2961). Upload state is recorded separately (line 3088) with `{"direction": "upload"}` in labels. The strategy will need to filter by direction label or use separate metrics.

### Pattern 5: Controller Attribute Mapping for QueueController
**What:** Response parameters live on `wc.download` and `wc.upload` QueueController objects, not directly on WANController.
**Critical difference from existing strategies:** All current tunable parameters (thresholds, alpha, sigma, etc.) are WANController attributes. Response parameters are QueueController attributes:
- `wc.download.step_up_bps` (stored in bps, tuned in Mbps -- needs conversion like MBPS_TO_BPS = 1_000_000)
- `wc.download.factor_down` (ratio 0.0-1.0, no conversion)
- `wc.download.green_required` (integer, needs rounding)
- Same for `wc.upload.*`

The `_apply_tuning_to_controller` function must be extended:
```python
elif r.parameter == "dl_step_up_mbps":
    wc.download.step_up_bps = int(r.new_value * 1_000_000)
elif r.parameter == "ul_step_up_mbps":
    wc.upload.step_up_bps = int(r.new_value * 1_000_000)
elif r.parameter == "dl_factor_down":
    wc.download.factor_down = r.new_value
elif r.parameter == "ul_factor_down":
    wc.upload.factor_down = r.new_value
elif r.parameter == "dl_green_required":
    wc.download.green_required = round(r.new_value)
elif r.parameter == "ul_green_required":
    wc.upload.green_required = round(r.new_value)
```

The `current_params` dict in the maintenance loop must also be extended:
```python
"dl_step_up_mbps": wc.download.step_up_bps / 1e6,
"ul_step_up_mbps": wc.upload.step_up_bps / 1e6,
"dl_factor_down": wc.download.factor_down,
"ul_factor_down": wc.upload.factor_down,
"dl_green_required": float(wc.download.green_required),
"ul_green_required": float(wc.upload.green_required),
```

### Anti-Patterns to Avoid
- **Tuning in bps domain:** step_up_bps values are 1,000,000+ (1Mbps = 1,000,000 bps). clamp_to_step rounds to 1 decimal -- this is fine for Mbps (e.g., 15.0 -> 15.5) but useless for bps. Always tune in Mbps, convert at apply time. This mirrors the load_time_constant_sec pattern (tune in tc domain, convert to alpha at apply).
- **Tuning green_required as float:** green_required is an integer (cycle count). The TuningResult/clamp_to_step pipeline works with floats and rounds to 1 decimal. Must round to int at apply time. Set bounds as integers (e.g., min=2, max=10) to keep the float representation lossless.
- **Single direction analysis for per-direction params:** Download and upload have fundamentally different characteristics (Spectrum DL: 15 Mbps step, 0.85 factor vs UL: 1 Mbps step, 0.85 factor). The strategy must analyze the correct direction's state/rate data.
- **Ignoring the upload state metric difference:** Download state is the primary wanctl_state metric (recorded every cycle). Upload state is recorded separately with `{"direction": "upload"}` label. Strategies analyzing upload episodes must filter appropriately.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parameter bounds enforcement | Custom clamping logic | `clamp_to_step()` from `tuning.models` | Already handles two-phase clamping (bounds + max_step_pct), rounding, floor for small values |
| Safety revert after bad adjustment | Custom monitoring | `check_and_revert()` + `PendingObservation` from `tuning.safety` | Already wired in maintenance loop, handles all tunable parameters equally |
| Parameter cooldown after revert | Custom timer | `lock_parameter()` / `is_parameter_locked()` from `tuning.safety` | Already integrated with the strategy filtering in the maintenance loop |
| Metrics query | Custom SQL | `query_metrics()` from `storage.reader` | Already handles read-only connections, filtering by wan/granularity/time |
| Alert delivery | Custom webhook code | `AlertEngine.fire()` | Already handles cooldown suppression, SQLite persistence, Discord delivery callback |
| Persistence of tuning results | Custom SQLite code | `persist_tuning_result()` from `tuning.applier` | Already handles the tuning_params table schema |

## Common Pitfalls

### Pitfall 1: Unit Domain Mismatch (step_up)
**What goes wrong:** step_up_bps on QueueController is in bits/sec (integer, e.g., 15,000,000). Tuning operates on floats with 1-decimal rounding. If you tune in bps, clamp_to_step's round(1) makes changes meaningless (15000000.0 -> 15000000.0, no change).
**Why it happens:** All existing tunable params are naturally in "small float" domains (ms, ratios, sigma). step_up_mbps is the first param where the controller stores a different unit than the config.
**How to avoid:** Tune in Mbps domain (parameter name: `dl_step_up_mbps`). Convert to bps at apply time: `wc.download.step_up_bps = int(r.new_value * 1_000_000)`. Bounds in Mbps (e.g., min=0.5, max=30.0).
**Warning signs:** Trivial change filter (abs < 0.1) always triggers, no adjustments ever applied.

### Pitfall 2: green_required Integer Truncation
**What goes wrong:** green_required is an integer on QueueController. TuningResult stores floats. clamp_to_step rounds to 1 decimal. If a strategy proposes 4.5, it gets clamped to 4.5, then applied as round(4.5) = 4 -- but 4 might be the current value, making the change invisible.
**Why it happens:** The tuning pipeline was designed for continuous parameters.
**How to avoid:** Strategy should propose integer candidates directly (e.g., current + 1 or current - 1). Use integer bounds. The 1-decimal round won't hurt integer values (5.0 stays 5.0). At apply time: `wc.download.green_required = round(r.new_value)`.
**Warning signs:** green_required oscillates between N and N+1 every cycle.

### Pitfall 3: Mode Aggregation Masks Rapid Transitions
**What goes wrong:** wanctl_state at 1m granularity uses MODE aggregation (most common state in the minute). If the controller oscillates rapidly between GREEN and RED within a minute, MODE picks the most frequent one -- potentially GREEN even though the link was congested for 40% of the minute.
**Why it happens:** MODE is correct for state metrics in general (you want the dominant state) but it underreports oscillation.
**How to avoid:** For oscillation detection (RTUN-04), count transitions between consecutive 1m buckets rather than counting time in congested state. A transition rate of > N transitions/hour is the signal, not the fraction of time in each state. Additionally, the raw wanctl_rate_download_mbps metric (AVG aggregated at 1m) shows rate volatility that complements state transition counting.
**Warning signs:** Oscillation lockout never triggers despite visible bandwidth swings in logs.

### Pitfall 4: Overshoot Detection Requires Rate + State Correlation
**What goes wrong:** Measuring only "how fast did the rate recover to ceiling" misses overshoot -- where the rate reaches ceiling but immediately re-enters congestion because the step was too aggressive.
**Why it happens:** Fast recovery is good, but too-fast recovery with overshoot is worse than slower recovery without overshoot.
**How to avoid:** step_up strategy must combine recovery speed with re-trigger rate. If recovery is fast AND re-trigger rate is low, step_up is too conservative (increase). If recovery is fast AND re-trigger rate is high, step_up is too aggressive (decrease).
**Warning signs:** step_up keeps increasing but congestion rate also increases.

### Pitfall 5: Upload State Metric Filtering
**What goes wrong:** Upload state is recorded with `{"direction": "upload"}` in labels, but `query_metrics()` returns all metrics for a WAN without label filtering. If the strategy doesn't filter by direction, it mixes DL and UL state data.
**Why it happens:** The primary wanctl_state is download (recorded in metrics_batch every cycle). Upload state is recorded separately only on transitions. The 1m MODE aggregate may be dominated by download state records.
**How to avoid:** For upload strategies, use a separate upload state metric or filter by labels. For the initial implementation, consider tuning upload parameters based on the download state proxy (since UL congestion typically correlates with DL congestion in CAKE queuing scenarios) -- but document this as a simplification.
**Warning signs:** Upload strategy proposes changes based on download congestion patterns.

### Pitfall 6: Oscillation Lockout Must Freeze ALL Response Params Atomically
**What goes wrong:** If oscillation lockout only freezes the currently-being-tuned parameters, the next rotation cycle could still adjust other response parameters, defeating the purpose.
**Why it happens:** The existing lock_parameter() mechanism is per-parameter. Oscillation is a system-level condition requiring system-level freeze.
**How to avoid:** When oscillation is detected, lock ALL 6 response parameter names (dl_step_up_mbps, ul_step_up_mbps, dl_factor_down, ul_factor_down, dl_green_required, ul_green_required) simultaneously with a long cooldown. This uses the existing is_parameter_locked() check in the strategy filtering step to skip all response strategies.
**Warning signs:** One response parameter frozen but others still changing, oscillation continues.

## Code Examples

### Example 1: Recovery Episode Detection (RTUN-01 strategy core)
```python
# Pattern: Detect recovery episodes from 1m wanctl_state time series
@dataclass(frozen=True, slots=True)
class RecoveryEpisode:
    """A single congestion->recovery cycle."""
    congestion_start_ts: int
    recovery_end_ts: int
    duration_sec: int
    peak_severity: float  # Max state value during episode
    pre_rate_mbps: float | None  # Rate before congestion
    post_rate_mbps: float | None  # Rate after recovery

def _detect_recovery_episodes(
    metrics_data: list[dict],
    direction: str = "download",
) -> list[RecoveryEpisode]:
    """Detect recovery episodes from state transitions."""
    state_by_ts: dict[int, float] = {}
    rate_metric = f"wanctl_rate_{direction}_mbps"
    rate_by_ts: dict[int, float] = {}

    for row in metrics_data:
        ts = row["timestamp"]
        if row["metric_name"] == "wanctl_state":
            state_by_ts[ts] = row["value"]
        elif row["metric_name"] == rate_metric:
            rate_by_ts[ts] = row["value"]

    sorted_ts = sorted(state_by_ts.keys())
    episodes: list[RecoveryEpisode] = []
    in_congestion = False
    congestion_start = 0
    peak_severity = 0.0

    for ts in sorted_ts:
        state = state_by_ts[ts]
        if not in_congestion and state >= 2.0:
            in_congestion = True
            congestion_start = ts
            peak_severity = state
        elif in_congestion:
            peak_severity = max(peak_severity, state)
            if state == 0.0:
                in_congestion = False
                episodes.append(RecoveryEpisode(
                    congestion_start_ts=congestion_start,
                    recovery_end_ts=ts,
                    duration_sec=ts - congestion_start,
                    peak_severity=peak_severity,
                    pre_rate_mbps=rate_by_ts.get(congestion_start),
                    post_rate_mbps=rate_by_ts.get(ts),
                ))
                peak_severity = 0.0

    return episodes
```

### Example 2: Oscillation Detection and Lockout (RTUN-04)
```python
# Pattern: Count state transitions per minute from 1m time series
def _count_transitions_per_minute(
    metrics_data: list[dict],
    lookback_minutes: int = 60,
) -> float:
    """Count state transitions per minute over recent window."""
    state_by_ts: dict[int, float] = {}
    for row in metrics_data:
        if row["metric_name"] == "wanctl_state":
            state_by_ts[row["timestamp"]] = row["value"]

    sorted_ts = sorted(state_by_ts.keys())
    if len(sorted_ts) < 2:
        return 0.0

    # Only look at recent window
    cutoff = sorted_ts[-1] - (lookback_minutes * 60)
    recent_ts = [ts for ts in sorted_ts if ts >= cutoff]

    transitions = 0
    for i in range(1, len(recent_ts)):
        if state_by_ts[recent_ts[i]] != state_by_ts[recent_ts[i - 1]]:
            transitions += 1

    span_minutes = max(1, (recent_ts[-1] - recent_ts[0]) / 60)
    return transitions / span_minutes

# Lockout: freeze all 6 response params
RESPONSE_PARAMS = [
    "dl_step_up_mbps", "ul_step_up_mbps",
    "dl_factor_down", "ul_factor_down",
    "dl_green_required", "ul_green_required",
]
OSCILLATION_LOCKOUT_SEC = 7200  # 2 hours

def _apply_oscillation_lockout(
    locks: dict[str, float],
    alert_engine: AlertEngine | None,
    wan_name: str,
) -> None:
    """Freeze all response parameters and fire Discord alert."""
    for param in RESPONSE_PARAMS:
        lock_parameter(locks, param, OSCILLATION_LOCKOUT_SEC)
    if alert_engine is not None:
        alert_engine.fire(
            alert_type="oscillation_lockout",
            severity="warning",
            wan_name=wan_name,
            details={
                "locked_params": RESPONSE_PARAMS,
                "lockout_sec": OSCILLATION_LOCKOUT_SEC,
            },
        )
```

### Example 3: _apply_tuning_to_controller Extension
```python
# Source: extends existing _apply_tuning_to_controller in autorate_continuous.py
# New elif branches for response parameters:
elif r.parameter == "dl_step_up_mbps":
    wc.download.step_up_bps = int(r.new_value * 1_000_000)
elif r.parameter == "ul_step_up_mbps":
    wc.upload.step_up_bps = int(r.new_value * 1_000_000)
elif r.parameter == "dl_factor_down":
    wc.download.factor_down = r.new_value
elif r.parameter == "ul_factor_down":
    wc.upload.factor_down = r.new_value
elif r.parameter == "dl_green_required":
    wc.download.green_required = round(r.new_value)
elif r.parameter == "ul_green_required":
    wc.upload.green_required = round(r.new_value)
```

## Architecture Decisions (Claude's Discretion Recommendations)

### D-01: Episode Detection Approach
**Recommendation:** State transition parsing from wanctl_state 1m time series.

**Rationale:** The wanctl_state metric at 1m granularity directly encodes GREEN=0, YELLOW=1, SOFT_RED=2, RED=3. State transitions are observable as consecutive samples with different values. This is simpler and more reliable than rate-based heuristics because:
1. State is the authoritative indicator of controller decisions (rate is a consequence).
2. The 1m MODE aggregation gives the dominant state per minute, filtering out sub-minute noise.
3. Recovery episodes = consecutive minutes where state goes from >= 2 back to 0.
4. Congestion episodes = consecutive minutes where state goes from 0 to >= 2.

Complementary rate data (wanctl_rate_download_mbps, wanctl_rate_upload_mbps) is used for overshoot detection but not as the primary episode signal.

### D-02: Oscillation Lockout Mechanism
**Recommendation:** Reuse existing `_parameter_locks` dict with a long cooldown (2 hours default). No new freeze state needed.

**Rationale:**
1. The existing `lock_parameter()` / `is_parameter_locked()` mechanism is already integrated into the maintenance loop's strategy filtering (line 4335). Adding response params to these locks automatically prevents their strategies from running.
2. A 2-hour cooldown is appropriate because: the tuning cadence is 1 hour, so 2 hours means at least 1 full rotation cycle is skipped. This is enough time for the operator to notice and adjust.
3. The oscillation check runs at the start of the RESPONSE_LAYER cycle, before any response strategies execute. If transitions/minute exceeds the threshold, all 6 params are locked and a Discord alert fires.
4. Recovery is time-based (cooldown expiry), which is simpler and more predictable than condition-based recovery. The operator can always override via config change + SIGUSR1 reload.
5. Using `float('inf')` for permanent lock (like the healer) is too aggressive for oscillation -- oscillation may be transient.

**Oscillation threshold default:** 6 transitions/hour (configurable via `tuning.oscillation_threshold`). Rationale: normal operation has ~2-4 transitions/hour during peak usage. 6/hour (one every 10 minutes on average) indicates the response parameters are fighting each other.

### D-03: Layer Placement
**Recommendation:** New 5th RESPONSE_LAYER (5-hour rotation cycle).

**Rationale:**
1. Clean separation: response params have the highest blast radius and deserve dedicated analysis time.
2. The ADVANCED_LAYER already has 4 strategies (fusion weight, reflector min_score, baseline min/max). Adding 6 more would make 10 -- too crowded.
3. A 5-hour cycle is acceptable: response parameters change slowly in production (operator manually adjusts them every few weeks at most). Hourly analysis is already conservative.
4. The rotation index is already modular (`wc._tuning_layer_index % len(ALL_LAYERS)`), so adding a 5th layer requires only appending to the list.

### D-04: Per-Direction Parameter Handling
**Recommendation:** 6 separate parameters (dl_step_up_mbps, ul_step_up_mbps, dl_factor_down, ul_factor_down, dl_green_required, ul_green_required).

**Rationale:**
1. The existing config already has distinct per-direction values: DL step_up=15 vs UL step_up=1, DL factor_down=0.85 vs UL factor_down=0.85.
2. Download and upload have fundamentally different bandwidth envelopes (Spectrum: ~400Mbps DL vs ~23Mbps UL). A fixed ratio would be an arbitrary constraint.
3. The parameter space increase (3 -> 6) is manageable because each param has independent bounds and the exclude_params mechanism lets the operator opt in to specific directions first.
4. The wanctl_state metric already records DL and UL states separately (DL in main batch, UL only on transitions with direction label). The strategy can use direction-appropriate data.
5. All 6 params start in exclude_params (RTUN-05), so the blast radius is zero until explicitly opted in.

**Simplification for initial implementation:** Both DL and UL strategies can share the same analysis function, differentiated by the direction parameter and which QueueController attributes they target.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual step_up/factor_down tuning | Same (manual) | n/a | Phase 120 automates this |
| 4-layer rotation (4h cycle) | 5-layer rotation (5h cycle) | Phase 120 | One additional hour per full rotation |
| No oscillation protection | Oscillation lockout + alert | Phase 120 | Prevents response parameter interactions from destabilizing the link |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_response_tuning_strategies.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RTUN-01 | tune_step_up returns TuningResult adjusting step_up from recovery episodes | unit | `.venv/bin/pytest tests/test_response_tuning_strategies.py::TestTuneStepUp -x` | Wave 0 |
| RTUN-02 | tune_factor_down returns TuningResult adjusting factor_down from congestion resolution | unit | `.venv/bin/pytest tests/test_response_tuning_strategies.py::TestTuneFactorDown -x` | Wave 0 |
| RTUN-03 | tune_green_required returns TuningResult adjusting green_required from re-trigger rate | unit | `.venv/bin/pytest tests/test_response_tuning_strategies.py::TestTuneGreenRequired -x` | Wave 0 |
| RTUN-04 | oscillation lockout freezes all 6 params and fires Discord alert when transition rate exceeds threshold | unit | `.venv/bin/pytest tests/test_response_tuning_wiring.py::TestOscillationLockout -x` | Wave 0 |
| RTUN-05 | response params excluded by default, opt-in via removing from exclude_params | unit | `.venv/bin/pytest tests/test_response_tuning_wiring.py::TestExcludeParamsDefault -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_response_tuning_strategies.py tests/test_response_tuning_wiring.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_response_tuning_strategies.py` -- covers RTUN-01, RTUN-02, RTUN-03
- [ ] `tests/test_response_tuning_wiring.py` -- covers RTUN-04, RTUN-05, _apply_tuning_to_controller extension, current_params extension, RESPONSE_LAYER wiring

## Open Questions

1. **Upload state metric granularity in 1m data**
   - What we know: Download wanctl_state is recorded every cycle (in metrics_batch). Upload state is recorded only on transitions (lines 3083-3091) with a direction label.
   - What's unclear: After 1m MODE aggregation, will there be enough upload state data points for meaningful episode analysis? In quiet periods, upload may have very few state records.
   - Recommendation: For the initial implementation, analyze download-direction episodes for both DL and UL params. Upload congestion almost always co-occurs with download congestion (CAKE queues on same link). Document this as a simplification; per-direction state analysis can be added later if the operator has distinct UL congestion patterns.

2. **Optimal oscillation threshold**
   - What we know: Normal operation has ~2-4 state transitions/hour during peak usage. The proposed default is 6/hour.
   - What's unclear: The right threshold depends on traffic patterns that vary by deployment.
   - Recommendation: Make it configurable via `tuning.oscillation_threshold` (default 6). Log the measured transition rate periodically so operators can tune the threshold based on their deployment's baseline.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/tuning/strategies/base.py` -- StrategyFn protocol definition
- `src/wanctl/tuning/models.py` -- TuningResult, SafetyBounds, TuningConfig, clamp_to_step
- `src/wanctl/tuning/analyzer.py` -- run_tuning_analysis dispatch, StrategyFn type alias
- `src/wanctl/tuning/safety.py` -- measure_congestion_rate, check_and_revert, lock_parameter, is_parameter_locked
- `src/wanctl/tuning/applier.py` -- apply_tuning_results, persist_tuning_result
- `src/wanctl/tuning/strategies/signal_processing.py` -- Reference strategy implementations
- `src/wanctl/tuning/strategies/advanced.py` -- Reference strategy implementations
- `src/wanctl/tuning/strategies/congestion_thresholds.py` -- GREEN-state delta extraction pattern
- `src/wanctl/autorate_continuous.py` lines 1310-1344 -- QueueController init (step_up_bps, factor_down, green_required)
- `src/wanctl/autorate_continuous.py` lines 1553-1627 -- _apply_tuning_to_controller
- `src/wanctl/autorate_continuous.py` lines 4269-4399 -- Layer definitions and maintenance loop
- `src/wanctl/autorate_continuous.py` lines 2950-2965 -- Metric recording (wanctl_state, rates)
- `src/wanctl/alert_engine.py` -- AlertEngine.fire() signature and delivery callback
- `configs/spectrum-vm.yaml` -- Production tuning config with bounds
- `tests/test_advanced_tuning_strategies.py` -- Test patterns (_make_metrics, _make_multi_metrics helpers)
- `tests/test_tuning_layer_rotation.py` -- Layer rotation and _apply_tuning_to_controller test patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new deps, all existing internal libraries
- Architecture: HIGH - follows established patterns exactly, all 4 extension points verified in source
- Pitfalls: HIGH - all pitfalls identified from direct code reading (unit domain, integer truncation, mode aggregation, QueueController indirection)
- Strategies: MEDIUM - episode detection algorithm is novel for this codebase; the approach is sound but exact thresholds will need production tuning

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable internal codebase, no external deps)
