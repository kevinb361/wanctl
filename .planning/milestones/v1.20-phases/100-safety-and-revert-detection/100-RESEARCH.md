# Phase 100: Safety and Revert Detection - Research

**Researched:** 2026-03-19
**Domain:** Post-tuning congestion monitoring, automatic revert, hysteresis cooldown
**Confidence:** HIGH

## Summary

Phase 100 adds the safety net for adaptive tuning: after each parameter adjustment, the system measures congestion rate over a defined observation window, compares it to a pre-adjustment baseline, and automatically reverts if degradation is detected. A hysteresis cooldown then locks the parameter category from further tuning to prevent oscillation. This is the critical safety layer that Phases 101 and 102 depend on before they can safely tune more sensitive parameters (signal processing, fusion weights).

The implementation is straightforward because the existing infrastructure already provides everything needed. The `wanctl_state` metric (0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED) is persisted to SQLite every cycle at raw granularity and downsampled to 1m aggregates via MODE aggregation. The `tuning_params` table already has a `reverted INTEGER DEFAULT 0` column. The `_apply_tuning_to_controller()` function already maps parameter names to WANController attributes. The applier already persists every adjustment with old/new values. The only new components are: (1) a congestion rate measurement function, (2) revert logic in the tuning flow, and (3) a hysteresis lock tracker.

**Primary recommendation:** Define "congestion rate" as the fraction of 1m-aggregated samples where `wanctl_state >= 2` (SOFT_RED or RED) within the observation window. This is simple, already stored, and directly reflects what operators care about (time spent in congestion). Implement as a pure function in the tuning module, measure before and after each adjustment, and revert when the post/pre ratio exceeds a configurable threshold.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SAFE-01 | System monitors congestion rate after each parameter adjustment | Congestion rate = fraction of wanctl_state >= 2 in observation window; query via existing query_metrics() on 1m aggregates |
| SAFE-02 | Automatic revert to previous values when post-adjustment congestion rate increases | Revert uses TuningResult.old_value already stored in tuning_params; _apply_tuning_to_controller() reverses mapping; log at ERROR level |
| SAFE-03 | Hysteresis lock prevents revert oscillation (revert freezes category for configurable cooldown) | Per-parameter cooldown tracked on WANController via dict[str, float] mapping parameter -> lock_expiry; default 24h cooldown |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib statistics | 3.12 | mean() for congestion rate computation | Zero dependencies, already imported in strategies |
| SQLite (existing) | 3.12 | Query wanctl_state metrics for congestion rate | Already stores per-cycle state data at raw and 1m granularity |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| wanctl.storage.reader.query_metrics | existing | Read-only metric queries | Congestion rate measurement pre/post adjustment |
| wanctl.tuning.applier | existing | Persist revert records, logging | Extended to handle reverts |
| wanctl.tuning.models | existing | TuningResult for revert tracking | RevertRecord or extend TuningResult |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fraction of SOFT_RED+RED | State transitions/hour | Transitions count rapid flapping as bad, but fraction-based is simpler and more intuitive |
| Fraction of SOFT_RED+RED | Average state value (0-3) | Average is sensitive to GREEN/YELLOW distribution, fraction is binary "congested or not" |
| 1m aggregated query | Raw 20Hz query | Raw query on 30min window = 36,000 rows per metric; 1m = 30 rows. Performance difference is massive. |

**Installation:**
```bash
# No new dependencies
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/tuning/
    models.py           # Add RevertRecord (frozen dataclass)
    safety.py           # NEW: measure_congestion_rate(), check_for_revert(), RevertTracker
    applier.py          # Extend: persist_revert_record()
    analyzer.py         # Unchanged
    strategies/
        congestion_thresholds.py  # Unchanged
```

### Pattern 1: Congestion Rate Measurement (Pure Function)

**What:** Query wanctl_state from SQLite for a time window, compute fraction of samples in congestion (state >= 2).

**When to use:** Before applying tuning results (baseline) and at the next tuning cycle (observation).

**Example:**
```python
# Source: derived from existing query_metrics() pattern in storage/reader.py
def measure_congestion_rate(
    db_path: str,
    wan_name: str,
    start_ts: int,
    end_ts: int,
) -> float | None:
    """Fraction of 1m samples where state >= SOFT_RED in time window.

    Returns None if insufficient data (< 10 samples).
    State encoding: 0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED
    """
    from wanctl.storage.reader import query_metrics

    data = query_metrics(
        db_path=db_path,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=["wanctl_state"],
        wan=wan_name,
        granularity="1m",
    )
    if not data:
        return None

    state_values = [row["value"] for row in data if row["metric_name"] == "wanctl_state"]
    if len(state_values) < 10:
        return None

    congested = sum(1 for v in state_values if v >= 2.0)
    return congested / len(state_values)
```

### Pattern 2: Snapshot-Compare-Revert Flow

**What:** At tuning time, snapshot the congestion rate from the previous hour. After applying new parameters, store the snapshot. At the NEXT tuning cycle, measure congestion rate for the observation window and compare.

**When to use:** Every tuning cycle where adjustments were made.

**Flow:**
```
Tuning Cycle N:
  1. Check pending observations from Cycle N-1
     - For each observed adjustment: measure post-congestion rate
     - If post_rate / pre_rate > revert_threshold: REVERT
  2. Measure pre-adjustment congestion rate (baseline)
  3. Run strategies, apply results
  4. Store pre_rate + applied results as "pending observation"

Tuning Cycle N+1:
  1. Check pending observations from Cycle N
     - Measure post-adjustment congestion rate (observation window = since last tuning)
     - Compare to stored pre_rate
  ...
```

**Why deferred observation:** Tuning runs hourly. We need at least 30-60 minutes of post-adjustment data to measure congestion rate meaningfully. Checking immediately after applying would have zero post-adjustment data.

### Pattern 3: Hysteresis Lock (Per-Parameter Cooldown)

**What:** After a revert, lock the parameter from further tuning for a configurable period (default 24h). Track as `dict[str, float]` mapping parameter name to lock expiry timestamp.

**When to use:** After every revert to prevent oscillation.

**Example:**
```python
# On WANController or in safety module state
_parameter_locks: dict[str, float] = {}  # param -> monotonic expiry

def is_locked(parameter: str) -> bool:
    expiry = _parameter_locks.get(parameter)
    if expiry is None:
        return False
    if time.monotonic() >= expiry:
        del _parameter_locks[parameter]
        return False
    return True

def lock_parameter(parameter: str, cooldown_sec: float) -> None:
    _parameter_locks[parameter] = time.monotonic() + cooldown_sec
```

### Pattern 4: Revert as Inverse TuningResult

**What:** A revert is just applying a TuningResult where new_value = original old_value. Reuse existing `_apply_tuning_to_controller()` and `persist_tuning_result()` with the `reverted` column set to 1.

**When to use:** When congestion rate increase exceeds threshold.

### Anti-Patterns to Avoid

- **Per-cycle revert checking:** Checking congestion rate every 50ms cycle would be both wasteful (same SQLite query 72,000 times/hour) and statistically meaningless (single-cycle noise). Check only at tuning cadence.
- **Immediate post-apply measurement:** Measuring congestion rate immediately after `_apply_tuning_to_controller()` returns meaningless data -- zero post-adjustment time has elapsed.
- **Reverting all parameters on any degradation:** If two parameters were adjusted and congestion increases, revert BOTH, not just the most recent. Attribution of which parameter caused degradation is not possible with the current round-robin approach. Revert the entire batch.
- **Complex statistical significance tests:** A simple ratio threshold (post/pre > 1.2) is sufficient. The 1-hour observation window already smooths noise. Adding t-tests or Mann-Whitney U adds complexity for marginal accuracy gain in a system that already has slow cadence and small steps as primary safeguards.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Congestion rate query | Custom SQL direct to sqlite3 | `query_metrics()` from storage/reader.py | Read-only connection, error handling, granularity filtering all built in |
| Parameter revert application | Custom WANController mutation | `_apply_tuning_to_controller()` with inverse TuningResult | Already maps all parameter names to attributes, updates TuningState |
| Revert persistence | New table | Existing `tuning_params` table with `reverted=1` column | Schema already has the column, just use it |
| Revert logging | Custom log format | Existing WARNING/ERROR log pattern from applier | Consistent with TUNING log prefix convention |

## Common Pitfalls

### Pitfall 1: Revert Oscillation (Pitfall 7 from PITFALLS.md)

**What goes wrong:** Tuning adjusts parameter, congestion rate increases slightly (22%, above 20% threshold), system reverts. Next cycle, same data produces same adjustment, same revert. Infinite loop.

**Why it happens:** The revert threshold is too close to normal variation. Without hysteresis, the same analysis produces the same result every cycle.

**How to avoid:** Hysteresis cooldown lock (SAFE-03). After revert, lock the parameter for configurable period (default 24h). Also consider: if a parameter is reverted 3+ times, escalate lock to 72h.

**Warning signs:** tuning_params table shows same parameter alternating between two values with reverted=1.

### Pitfall 2: Observation Window Too Short

**What goes wrong:** Tuning runs hourly. Observation window is 30 minutes. But 30 minutes might be entirely night-time quiet period. The congestion rate is "0" both before and after adjustment, so the system never detects problems that only manifest during peak hours.

**Why it happens:** Congestion is load-dependent. A threshold change that is too aggressive only manifests when load arrives.

**How to avoid:** Use the full inter-tuning-cycle window (1 hour) as the observation period. This provides 60 data points at 1m granularity -- sufficient for rate measurement. For the very first observation after enabling tuning, accept that the window may be suboptimal.

**Warning signs:** Pre-adjustment and post-adjustment congestion rates are both near 0.0 (no load during either window).

### Pitfall 3: Congestion Rate Baseline Contaminated by Natural Traffic Variation

**What goes wrong:** Pre-adjustment congestion rate was measured during a quiet period (0.05). Post-adjustment window happens during peak usage (0.15). System reverts a perfectly good parameter change because natural traffic variation increased congestion, not the parameter change.

**Why it happens:** Network traffic is non-stationary. Congestion rate varies with time of day, day of week, user activity patterns.

**How to avoid:**
1. Set revert threshold conservatively high (default 50% increase, not 20%). A small increase is likely noise; a large increase is likely parameter-caused.
2. Consider absolute congestion rate too: only revert if post_rate > some minimum (e.g., 0.10 = 10% of time congested). Reverting from 0.02 to 0.03 (50% increase) is pointless -- both are healthy.
3. The 10% max step per cycle already limits how much damage a single adjustment can do.

**Warning signs:** Reverts cluster at specific times of day (load transition periods).

### Pitfall 4: State Metric Aggregation Mismatch

**What goes wrong:** `wanctl_state` uses MODE aggregation at 1m granularity. A minute with 50% GREEN and 50% RED reports as one of them (mode). If RED barely wins, the minute counts as fully congested.

**Why it happens:** MODE aggregation is discrete -- it picks the most common value, not a weighted average.

**How to avoid:** Accept this as a reasonable approximation. At 20Hz (1200 cycles/minute), MODE reflects the dominant state. A minute where RED barely wins (601/1200 cycles) is arguably congested. The systematic bias is small and affects both pre and post measurements equally.

**Warning signs:** None needed -- this is acceptable behavior.

### Pitfall 5: MagicMock Truthy Trap in Lock State

**What goes wrong:** Tests use MagicMock for WANController. `if wc._parameter_locks:` is truthy on MagicMock, causing test code to enter lock-checking branches unexpectedly.

**How to avoid:** Initialize `_parameter_locks = {}` explicitly on WANController (empty dict is falsy). In test mocks, set `mock_wc._parameter_locks = {}` explicitly.

## Code Examples

### Measuring Congestion Rate from Existing Metrics

```python
# Source: derived from storage/reader.py query_metrics() and congestion_thresholds.py state filtering
def measure_congestion_rate(
    db_path: str,
    wan_name: str,
    start_ts: int,
    end_ts: int,
) -> float | None:
    """Fraction of 1m samples in SOFT_RED or RED state.

    Returns None if fewer than 10 samples in the window (insufficient data).
    State encoding from _encode_state(): 0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED
    """
    data = query_metrics(
        db_path=db_path,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=["wanctl_state"],
        wan=wan_name,
        granularity="1m",
    )

    state_values = [row["value"] for row in data if row["metric_name"] == "wanctl_state"]
    if len(state_values) < 10:
        return None

    congested_count = sum(1 for v in state_values if v >= 2.0)
    return congested_count / len(state_values)
```

### Revert Check at Tuning Time

```python
# Source: derived from applier.py pattern and tuning wiring in autorate_continuous.py
def check_and_revert(
    pending_observation: PendingObservation | None,
    db_path: str,
    wan_name: str,
    revert_threshold: float,
    min_congestion_rate: float,
    writer: Any | None,
) -> list[TuningResult]:
    """Check pending observation; return revert TuningResults if degradation detected.

    Returns empty list if no revert needed.
    """
    if pending_observation is None:
        return []

    now_ts = int(time.time())
    post_rate = measure_congestion_rate(
        db_path, wan_name,
        start_ts=pending_observation.applied_ts,
        end_ts=now_ts,
    )

    if post_rate is None:
        return []  # Insufficient post-adjustment data

    pre_rate = pending_observation.pre_congestion_rate

    # Skip revert check if both rates are negligibly low
    if post_rate < min_congestion_rate:
        return []

    # Check if congestion increased beyond threshold
    if pre_rate > 0.001:
        ratio = post_rate / pre_rate
    else:
        # Pre-rate was near zero, use absolute threshold
        ratio = post_rate / min_congestion_rate if min_congestion_rate > 0 else 0.0

    if ratio <= revert_threshold:
        return []  # No degradation detected

    # Build revert TuningResults (reverse old/new)
    reverts = []
    for original in pending_observation.applied_results:
        reverts.append(TuningResult(
            parameter=original.parameter,
            old_value=original.new_value,  # Current (bad) value
            new_value=original.old_value,  # Revert to previous (good) value
            confidence=1.0,
            rationale=f"REVERT: congestion rate {pre_rate:.2%}->{post_rate:.2%} (ratio {ratio:.1f}x > {revert_threshold}x)",
            data_points=0,
            wan_name=wan_name,
        ))

    return reverts
```

### Hysteresis Lock on WANController

```python
# Source: follows _tuning_enabled / _tuning_state pattern on WANController
# In WANController.__init__:
self._parameter_locks: dict[str, float] = {}  # param_name -> monotonic lock expiry

def _is_parameter_locked(self, parameter: str) -> bool:
    """Check if a parameter is locked after revert."""
    expiry = self._parameter_locks.get(parameter)
    if expiry is None:
        return False
    if time.monotonic() >= expiry:
        del self._parameter_locks[parameter]
        return False
    return True

def _lock_parameter(self, parameter: str, cooldown_sec: float) -> None:
    """Lock a parameter from tuning after revert."""
    self._parameter_locks[parameter] = time.monotonic() + cooldown_sec
    self.logger.warning(
        "[TUNING] %s: locked %s for %ds after revert",
        self.wan_name, parameter, int(cooldown_sec),
    )
```

### Persisting a Revert Record

```python
# Source: extends existing persist_tuning_result() in applier.py
def persist_revert_record(
    result: TuningResult,
    writer: Any | None,
) -> int | None:
    """Persist a revert to tuning_params table with reverted=1."""
    if writer is None:
        return None
    try:
        ts = int(time.time())
        cursor = writer.connection.execute(
            "INSERT INTO tuning_params "
            "(timestamp, wan_name, parameter, old_value, new_value, "
            "confidence, rationale, data_points, reverted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (ts, result.wan_name, result.parameter,
             result.old_value, result.new_value,
             result.confidence, result.rationale, result.data_points),
        )
        return cursor.lastrowid
    except Exception:
        logger.warning("Failed to persist revert for %s", result.parameter, exc_info=True)
        return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static config values | Phase 99 data-driven calibration | v1.20 Phase 99 | Thresholds derived from real RTT data |
| No safety net | Phase 100 revert detection | v1.20 Phase 100 (this phase) | Auto-revert on degradation |
| reverted column unused | reverted=1 on revert records | v1.20 Phase 100 | Audit trail for reverts |

**Already in place:**
- `tuning_params.reverted INTEGER DEFAULT 0` -- column exists, never set to 1 yet
- `wanctl_state` metric stored every cycle with state encoding 0-3
- MODE aggregation at 1m granularity for state metric
- `_apply_tuning_to_controller()` maps parameter names to WANController attributes bidirectionally

## Open Questions

1. **Revert threshold value**
   - What we know: Research suggests 20% (PITFALLS.md) but Pitfall 3 analysis suggests 50% may be more robust against natural traffic variation
   - What's unclear: Optimal threshold depends on production traffic variance, which varies per WAN
   - Recommendation: Default to 1.5 (50% increase). Make configurable as `tuning.safety.revert_threshold` (already in example YAML as `revert_threshold_pct: 20`). Start conservative.

2. **Minimum congestion rate for revert trigger**
   - What we know: Reverting when both pre and post rates are near zero (0.01 vs 0.02) is pointless noise
   - What's unclear: What floor constitutes "meaningful congestion"
   - Recommendation: Default 0.05 (5% of observation window in congestion). Below this, skip revert check.

3. **Lock cooldown duration**
   - What we know: Must be long enough to prevent oscillation, short enough to allow recovery
   - What's unclear: Whether 24h is too long for rapidly-changing network conditions
   - Recommendation: Default 24h (one full diurnal cycle). Configurable as `tuning.safety.revert_cooldown_sec: 86400`.

4. **Per-parameter vs batch revert**
   - What we know: Current tuning adjusts multiple parameters per cycle (target_bloat_ms + warn_bloat_ms). Cannot attribute congestion to a specific parameter.
   - What's unclear: Whether to revert all applied parameters or attempt individual attribution
   - Recommendation: Revert the entire batch. Lock all parameters in the batch. Simpler, safer, and correct given the inability to isolate attribution.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml (existing) |
| Quick run command | `.venv/bin/pytest tests/test_tuning_safety.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFE-01 | measure_congestion_rate returns correct fraction from wanctl_state data | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestMeasureCongestionRate -x` | Wave 0 |
| SAFE-01 | Observation window stored after adjustment, checked at next cycle | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestPendingObservation -x` | Wave 0 |
| SAFE-02 | Revert triggered when post/pre ratio exceeds threshold | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestCheckAndRevert -x` | Wave 0 |
| SAFE-02 | Revert applies old_value back to WANController attributes | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestRevertApplication -x` | Wave 0 |
| SAFE-02 | Revert persisted with reverted=1 in tuning_params | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestRevertPersistence -x` | Wave 0 |
| SAFE-02 | Revert logged at ERROR level with reason | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestRevertLogging -x` | Wave 0 |
| SAFE-03 | Lock applied to parameter after revert, blocks next tuning cycle | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestHysteresisLock -x` | Wave 0 |
| SAFE-03 | Lock expires after cooldown_sec, parameter becomes tunable again | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestLockExpiry -x` | Wave 0 |
| SAFE-03 | Locked parameters skipped by tuning analysis | unit | `.venv/bin/pytest tests/test_tuning_safety.py::TestLockedParameterSkip -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_tuning_safety.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tuning_safety.py` -- covers SAFE-01, SAFE-02, SAFE-03
- Framework install: None needed (pytest already configured)

## Sources

### Primary (HIGH confidence)
- Direct analysis: `src/wanctl/tuning/models.py` -- TuningResult, TuningConfig, TuningState, SafetyBounds, clamp_to_step
- Direct analysis: `src/wanctl/tuning/analyzer.py` -- run_tuning_analysis(), StrategyFn type alias, per-WAN query pattern
- Direct analysis: `src/wanctl/tuning/applier.py` -- apply_tuning_results(), persist_tuning_result(), clamp-then-skip pattern
- Direct analysis: `src/wanctl/tuning/strategies/congestion_thresholds.py` -- _extract_green_deltas(), state encoding (STATE_GREEN=0.0)
- Direct analysis: `src/wanctl/autorate_continuous.py` lines 1474-1516 -- _apply_tuning_to_controller() parameter mapping
- Direct analysis: `src/wanctl/autorate_continuous.py` lines 3835-3892 -- maintenance loop tuning wiring
- Direct analysis: `src/wanctl/autorate_continuous.py` lines 3241-3247 -- _encode_state() (GREEN=0, YELLOW=1, SOFT_RED=2, RED=3)
- Direct analysis: `src/wanctl/autorate_continuous.py` lines 2680-2687 -- wanctl_state metric persisted every cycle
- Direct analysis: `src/wanctl/storage/schema.py` lines 141-163 -- tuning_params table with reverted column
- Direct analysis: `src/wanctl/storage/reader.py` lines 19-99 -- query_metrics() read-only pattern
- Direct analysis: `src/wanctl/storage/downsampler.py` lines 45-49 -- wanctl_state uses MODE aggregation

### Secondary (MEDIUM confidence)
- `.planning/research/PITFALLS.md` -- Pitfall 7 (revert oscillation), Pitfall 1 (feedback oscillation)
- `.planning/research/ARCHITECTURE.md` -- tuning architecture, YAML config, health endpoint patterns
- `.planning/research/SUMMARY.md` -- revert detection architecture overview

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all infrastructure exists
- Architecture: HIGH -- direct code analysis of all integration points, clear flow
- Pitfalls: HIGH -- grounded in existing PITFALLS.md research + production patterns from 20 milestones

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable domain, no external dependencies)
