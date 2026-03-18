# Domain Pitfalls: v1.20 Adaptive Tuning

**Domain:** Self-optimizing parameter tuning for production dual-WAN CAKE controller
**Researched:** 2026-03-18
**Confidence:** HIGH (grounded in codebase analysis, control theory fundamentals, and production experience from 20 milestones)

## Critical Pitfalls

Mistakes that could cause production network degradation, rewrite of the tuning system, or loss of operator trust.

### Pitfall 1: Identifier-Controller Interaction (Feedback Oscillation)

**What goes wrong:** Tuning adjusts a parameter (e.g., target_bloat_ms from 15 to 12). This changes the congestion state distribution (more YELLOW/RED transitions). The next tuning cycle sees a "different" RTT distribution and adjusts the parameter again. The system oscillates between parameter values, never converging.

**Why it happens:** The tuning system modifies the very system whose output it measures. This is the classic "identifier-controller interaction" problem in adaptive control theory. The measurement (RTT delta distribution) is not independent of the control (congestion thresholds).

**Consequences:** Oscillating parameters cause oscillating bandwidth limits. Users experience alternating fast/slow network. The dashboard shows constant state transitions. AlertEngine fires congestion_flapping alerts.

**Prevention:**
1. **Slow cadence**: Tune hourly, not per-cycle. Allow 1 hour of data collection after each adjustment before analyzing again.
2. **Small steps**: Max 10% parameter change per cycle. Multiple cycles to reach the target value.
3. **Convergence detection**: If a parameter has changed < 1% in the last 3 cycles, mark it converged and stop adjusting.
4. **Revert trigger**: If congestion rate increases > 20% after adjustment, revert immediately.
5. **Round-robin**: Tune one parameter category per cycle. Never change correlated parameters simultaneously.

**Detection:** Monitor the tuning_params table for the same parameter ping-ponging between values. Log consecutive adjustments in opposite directions as a WARNING.

### Pitfall 2: Insufficient Data Leading to Bad Parameters

**What goes wrong:** System starts up or metrics.db is rebuilt. Tuning runs on 30 minutes of data, derives thresholds from a non-representative sample (e.g., only night-time low-load data). Parameters are set for quiet conditions. When peak-hour load arrives, the thresholds are too tight, causing excessive congestion state transitions.

**Why it happens:** Short data windows do not capture diurnal patterns. A 1-hour sample might be all GREEN or all RED depending on when it was collected. Percentile analysis on non-representative data produces non-representative parameters.

**Consequences:** Parameters are "optimized" for the wrong conditions. Peak-hour performance degrades. Operator must manually revert or disable tuning.

**Prevention:**
1. **Minimum data requirement**: Require >= 1 hour of metrics before first tuning cycle (configurable via `min_data_hours`).
2. **Prefer 24h lookback**: Always analyze 24 hours of data to capture full diurnal cycle. Fall back to available data only on fresh install.
3. **Confidence score**: Scale confidence by `min(1.0, data_hours / 24)`. Low-confidence adjustments are smaller (multiply max_change_pct by confidence).
4. **State filtering**: Only use GREEN-period data for threshold calibration. Filter out periods already in congestion to avoid circular reasoning.

**Detection:** Log the data_hours and confidence for every tuning decision. Alert if confidence < 0.5.

### Pitfall 3: Tuning Signal Processing Parameters While Signal Processing is Active

**What goes wrong:** Tuning changes Hampel sigma_threshold from 3.0 to 2.5. Immediately, the outlier rate changes from 14% to 25%. The next tuning cycle sees the new (higher) outlier rate and adjusts sigma back up. But the outlier rate metric now reflects the transition period, not the steady-state behavior of sigma=2.5.

**Why it happens:** Signal processing parameters affect the very metrics used to evaluate them. Changing Hampel sigma changes the outlier rate. Changing EWMA alpha changes the jitter and variance values. The system must wait for the new parameter to reach steady state before evaluating its effect.

**Consequences:** Signal processing parameters oscillate. Outlier rate bounces between high and low values. The filtered_rtt signal becomes noisy due to parameter changes.

**Prevention:**
1. **Settling period**: After changing a signal processing parameter, wait at least 1 hour before re-evaluating (one full tuning cycle).
2. **Pre-change metrics**: Store the outlier rate, jitter, and variance BEFORE the change. Compare to post-change steady-state (not transitional data).
3. **Separate from threshold tuning**: Never tune signal processing and congestion thresholds in the same cycle. Signal processing parameters affect the data that threshold tuning consumes.
4. **Target-based tuning**: Tune Hampel sigma to achieve a TARGET outlier rate (5-15%), not to minimize a metric. The target is set in config, not derived from data.

**Detection:** Log outlier rate before and after sigma changes. Flag if rate changes > 50% -- indicates parameter is too sensitive.

### Pitfall 4: Tuning During Network Events

**What goes wrong:** ISP maintenance window, DDOS attack, or router firmware update causes anomalous RTT. Tuning cycle runs during or shortly after the event. Parameters are adjusted based on non-representative data.

**Why it happens:** Tuning has no awareness of external events. It sees high RTT data and adjusts thresholds upward, which then allows more congestion before triggering control actions.

**Consequences:** After the event, thresholds are too permissive. Real congestion goes undetected until the next tuning cycle corrects.

**Prevention:**
1. **Exclude anomalous periods**: If > 50% of the lookback window is in RED/SOFT_RED state, skip tuning for this cycle. Log "skipping tuning: sustained congestion detected".
2. **Robust statistics**: Use median and IQR instead of mean and stdev for parameter derivation. Median is resistant to outlier contamination.
3. **State-filtered analysis**: Only analyze data from GREEN periods for threshold calibration. Congested periods tell you "congestion happened" but not where the threshold should be.

**Detection:** Log the percentage of each congestion state in the analysis window. If RED > 25%, flag the tuning cycle as potentially contaminated.

## Moderate Pitfalls

### Pitfall 5: MagicMock Truthy Trap in Tuning Code

**What goes wrong:** Test uses `MagicMock()` for a WANController. Tuning code checks `if controller.tuning_enabled:` and MagicMock is truthy. Tuning runs against mock data and either crashes on missing attributes or produces nonsensical results.

**Prevention:** Follow the established pattern from v1.18/v1.19: use explicit None/False for boolean-checked attributes on mock WANControllers.

```python
# In test fixtures:
mock_controller._tuning_enabled = False  # Explicit, not MagicMock()
mock_controller._last_tuning_ts = None   # Explicit None
mock_controller._tuning_state = None     # Explicit None
```

### Pitfall 6: SQLite Query Performance on Raw Data

**What goes wrong:** Tuning analyzer queries 24 hours of RAW granularity data (24h x 20Hz = 1.7M rows per metric per WAN). Query takes seconds, blocking the maintenance window and potentially triggering the watchdog.

**Prevention:**
1. **Always query aggregated data**: Use 1m granularity for tuning (24h = 1440 rows). Never query raw data for analysis.
2. **Use existing select_granularity()**: The reader.py function already selects optimal granularity based on time range.
3. **Limit query scope**: Query specific metric names, not all metrics. Each strategy queries only the metrics it needs.
4. **Budget-aware**: Check elapsed time during tuning. If approaching maintenance window limit, skip remaining strategies.

### Pitfall 7: Revert Logic Triggering on Normal Variation

**What goes wrong:** Tuning adjusts target_bloat_ms from 15 to 14. Normal network variation causes congestion rate to increase by 22% (just above the 20% revert threshold). System reverts the perfectly good parameter change. Next cycle, derives 14 again, applies, reverts again -- revert oscillation.

**Prevention:**
1. **Statistical significance**: Revert only if congestion rate increase is statistically significant (not just > threshold). Use at least 30 minutes of post-change data.
2. **Hysteresis on revert**: After a revert, mark the parameter as "locked" for 24 hours. Do not attempt to tune it again until lock expires.
3. **Revert count tracking**: If a parameter is reverted > 3 times, raise its revert threshold or mark it as not-tunable for this WAN.
4. **Directional awareness**: Distinguish between "parameter too aggressive" (threshold lowered, more false RED) and "parameter too permissive" (threshold raised, missed congestion). Only revert the direction that caused the problem.

### Pitfall 8: Tuning Config Bounds Too Tight

**What goes wrong:** Operator sets `bounds.target_bloat_ms: {min: 14, max: 16}`. Actual optimal value is 12ms. Tuning repeatedly hits the lower bound and logs "clamped to min". Parameters never reach optimal.

**Prevention:**
1. **Default bounds that are generous**: Default bounds should span the reasonable range for each parameter type, not be tight around the current value.
2. **Log when clamped**: Log at INFO when a derived parameter is clamped to a bound. This tells the operator the bounds may need widening.
3. **Document bounds rationale**: Each default bound should have a comment explaining the physical meaning. "min: 5 # Below 5ms, even idle links trigger YELLOW."

### Pitfall 9: Per-WAN Tuning Cadence Interaction

**What goes wrong:** Both WANs tune simultaneously in the same maintenance window. Spectrum tuning queries data that includes periods when ATT was congested (which affected Spectrum via the steering daemon). Spectrum's threshold is set based on data contaminated by ATT's behavior.

**Prevention:**
1. **Independent analysis**: Each WAN's tuning queries only its own metrics (the existing `wan` filter in query_metrics()).
2. **No cross-WAN state**: The steering daemon's WAN-aware signals should be excluded from autorate tuning data. Use only autorate metrics per WAN.
3. **Sequential tuning**: Tune one WAN per maintenance window (alternate). This provides 2 hours between any WAN's successive adjustments.

## Minor Pitfalls

### Pitfall 10: Tuning Params Table Bloat

**What goes wrong:** Every hourly cycle writes 8 parameter decisions per WAN to tuning_params. Over months, table grows. No cleanup or retention policy.

**Prevention:** Add tuning_params to the existing retention/cleanup system in storage/retention.py. Default retention: 30 days (matches alerts pattern).

### Pitfall 11: SIGUSR1 Reload During Tuning Analysis

**What goes wrong:** Operator sends SIGUSR1 while tuning analysis is in progress. Fusion config and tuning config are both reloaded. The tuning cycle that was computing parameters based on old config now applies them under new config (e.g., new bounds).

**Prevention:** Check for reload flag at the START of tuning analysis, not during. If reload happened mid-analysis, discard results and re-analyze with new config in the next cycle.

### Pitfall 12: Float Precision in Parameter Comparison

**What goes wrong:** Tuning derives target_bloat_ms = 14.999999999. Current value is 15.0. The "trivial change" filter (< 1% difference) does not catch this because 14.999... rounds differently. Parameter is "changed" every cycle with no meaningful effect, generating noise in logs and tuning_params.

**Prevention:** Round all derived parameters to 1 decimal place before comparison. Use `round(value, 1)` consistently. The codebase already uses `:.1f` formatting in log messages.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Foundation + config | Pitfall 5: MagicMock truthy trap | Use explicit None/False on mock tuning attributes |
| Foundation + config | Config validation not following warn+disable | Copy exact pattern from _load_fusion_config |
| Threshold calibration | Pitfall 1: oscillation on first deploy | Ship with max_change_pct=5 (extra conservative) |
| Threshold calibration | Pitfall 2: insufficient data | Enforce min_data_hours=1, log confidence |
| Threshold calibration | Pitfall 4: anomalous data contamination | State-filter to GREEN periods only |
| Revert detection | Pitfall 7: revert oscillation | Require statistical significance + hysteresis lock |
| Hampel tuning | Pitfall 3: outlier rate feedback loop | Target-based approach with settling period |
| EWMA tuning | Pitfall 1: alpha changes affect jitter metrics | Settle for 1 hour before re-evaluating |
| Fusion weight tuning | Pitfall 9: cross-signal contamination | Independent per-WAN analysis, WAN filter |
| Reflector scoring | Pitfall 2: short window with all reflectors active | Need sustained deprioritization data to tune |
| Baseline bounds | Pitfall 4: ISP maintenance shifts baseline | Use p5/p95 over 7 days, not 24h |
| SQLite integration | Pitfall 6: raw data query performance | Always use 1m aggregated data |
| Persistence | Pitfall 10: table bloat | Add retention policy to existing cleanup |

## Sources

- [Self-tuning controller theory](https://en.wikipedia.org/wiki/Self-tuning) -- identifier-controller interaction
- [Stability-preserving PID tuning](https://www.oaepublish.com/articles/ces.2021.15) -- conservative adaptation pattern
- [Stability and Convergence Analysis](https://link.springer.com/chapter/10.1007/978-981-15-5538-1_2) -- convergence conditions
- Codebase: v1.18 MEMORY.md MagicMock truthy trap pattern
- Codebase: v1.19 _reload_fusion_config SIGUSR1 chain pattern
- Codebase: storage/downsampler.py aggregation tiers and retention
- Production: Spectrum 14% outlier rate vs ATT 0% (validates per-WAN tuning need)
