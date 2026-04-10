# Phase 88: Signal Processing Core - Research

**Researched:** 2026-03-16
**Domain:** RTT signal processing (Hampel filter, EWMA jitter/variance, confidence scoring)
**Confidence:** HIGH

## Summary

Phase 88 introduces a pre-EWMA signal processing stage into the autorate daemon's hot path. The SignalProcessor class sits between `measure_rtt()` and `update_ewma()`, performing outlier detection via Hampel filter, jitter tracking, variance tracking, and confidence scoring. All algorithms use Python 3.12 stdlib only (`statistics.median`, `math`, `collections.deque`). The implementation is a single new module (`signal_processing.py`) with a frozen dataclass result type, following established wanctl patterns.

The primary technical challenge is the Hampel filter's MAD (Median Absolute Deviation) calculation within a rolling window, which requires careful handling of the warm-up period (first 7 cycles = 350ms). The jitter and variance EWMAs follow the existing `alpha = cycle_interval / time_constant` pattern already proven in autorate_continuous.py. The confidence formula is a simple variance-based 0-1 score that requires access to the current baseline RTT.

**Primary recommendation:** Implement as a single `signal_processing.py` module with `SignalProcessor` class and `SignalResult` frozen dataclass. Follow the existing per-WAN instance pattern (one SignalProcessor per WANController). Config loading follows the alerting section pattern (optional YAML section with defaults, warn+disable on invalid config).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Outlier RTT samples are replaced with rolling window median before passing to EWMA
- Both raw and filtered RTT values stored in SignalResult for metrics/logging
- YAML-configurable parameters under `signal_processing.hampel:` section (window_size: 7, sigma_threshold: 3.0 as defaults)
- Rolling outlier rate tracked: outlier_rate (percentage of recent window), total_outliers (lifetime count), consecutive_outliers
- Warm-up period: pass through raw RTT unfiltered until window has enough samples (7 cycles = 350ms), log at DEBUG
- Pre-EWMA filter position: raw RTT -> SignalProcessor.process() -> filtered_rtt -> existing update_ewma()
- SignalResult frozen dataclass (slots=True) returned from process(): filtered_rtt, raw_rtt, jitter_ms, variance_ms2, confidence, is_outlier, outlier_rate, warming_up
- Per-WAN SignalProcessor instance, instantiated in WANController.__init__() with its own independent state
- No state persistence across daemon restarts -- warm-up is 350ms, negligible
- New module: `src/wanctl/signal_processing.py` (standalone, imported by autorate_continuous.py)
- Configurable EWMA alpha via time_constant_sec (matching existing load_rtt pattern), not strict RFC 3550 fixed alpha
- Default time constants: jitter 2.0s (alpha=0.025), variance 5.0s (alpha=0.01)
- Jitter computed from RAW RTT samples (not filtered) -- reflects true network behavior including spikes
- Variance computed from RAW RTT samples -- squared deviation of raw_rtt from load_rtt EWMA mean
- Confidence score: variance-based 0-1 scale: `1.0 / (1.0 + variance / baseline^2)` -- high=stable, low=noisy
- Filtered RTT DOES feed into EWMA (Hampel replacement is the value of signal processing)
- Signal processing DOES NOT alter congestion state transitions, rate adjustments, or alerting
- Confidence, jitter, variance are computed and logged but do not gate any control decisions
- Always active -- no enable/disable flag. Zero config change needed to activate on deploy
- SQLite persistence and health endpoint exposure deferred to Phase 92 (Observability)
- Per-cycle signal results logged at DEBUG; outlier events logged at INFO with raw/replaced values and outlier_rate

### Claude's Discretion
- Exact SignalResult field naming beyond the core fields discussed
- Internal data structure choices (deque sizing, EWMA initialization values)
- Test organization and fixture design
- DEBUG log message formatting details
- Alpha calculation implementation (reuse existing utility or inline)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SIGP-01 | Outlier RTT samples identified and replaced using rolling Hampel filter before EWMA update | Hampel filter algorithm verified: rolling median + MAD * 1.4826 * sigma_threshold. Python stdlib `statistics.median` available. Warm-up passthrough during first window_size cycles. |
| SIGP-02 | Jitter tracked per cycle using RFC 3550 EWMA from consecutive RTT measurements | RFC 3550 formula adapted: `J(i) = J(i-1) + alpha * (|D(i-1,i)| - J(i-1))` where D = difference between consecutive raw RTTs. Alpha from time_constant (2.0s default). |
| SIGP-03 | Measurement confidence interval computed per cycle indicating RTT reading reliability | Formula: `1.0 / (1.0 + variance / baseline^2)`. Requires baseline_rtt from WANController. Returns 0-1 float (1.0 = perfectly stable). |
| SIGP-04 | RTT variance tracked via EWMA alongside existing load_rtt smoothing | EWMA variance: `var = (1-alpha)*var + alpha*(raw_rtt - load_rtt)^2`. Alpha from time_constant (5.0s default). Uses squared deviation of raw_rtt from load_rtt mean. |
| SIGP-05 | Signal processing uses only Python stdlib (zero new package dependencies) | Verified: `statistics.median`, `collections.deque`, `math.isnan/isinf`, `dataclasses.dataclass` -- all stdlib. No numpy/scipy needed. |
| SIGP-06 | Signal processing operates in observation mode -- metrics and logs only, no congestion control input changes | Filtered RTT feeds EWMA (this IS the value), but confidence/jitter/variance are observational only. No gating of state transitions or rate adjustments. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| statistics (stdlib) | Python 3.12 | `statistics.median` for Hampel window median | Available in stdlib, no dependency needed |
| collections (stdlib) | Python 3.12 | `deque(maxlen=N)` for rolling windows | Bounded, O(1) append, automatic eviction |
| math (stdlib) | Python 3.12 | `math.isnan`, `math.isinf` for numeric guards | Required for NaN/Inf protection pattern |
| dataclasses (stdlib) | Python 3.12 | `@dataclass(frozen=True, slots=True)` for SignalResult | Project pattern (CommandResult in router_command_utils.py) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging (stdlib) | Python 3.12 | DEBUG per-cycle, INFO on outlier events | All signal processing logging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| statistics.median | sorted(window)[len//2] | statistics.median handles edge cases (even/odd lengths), cleaner |
| Manual MAD | scipy.stats.median_abs_deviation | scipy is 30MB+ dep, explicitly out of scope (REQUIREMENTS.md) |
| collections.deque | list with manual slicing | deque(maxlen=N) auto-evicts, no manual bookkeeping |

**Installation:**
```bash
# No installation needed -- all stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
├── signal_processing.py    # NEW: SignalProcessor + SignalResult (standalone module)
├── autorate_continuous.py  # MODIFIED: import SignalProcessor, wire into WANController
└── ...                     # Everything else untouched
```

### Pattern 1: Pre-EWMA Filter Chain
**What:** SignalProcessor sits between measure_rtt() and update_ewma() in the hot path
**When to use:** Every cycle where measured_rtt is not None
**Example:**
```python
# In WANController.run_cycle(), after RTT measurement, before state management:
# Current (line 1647):
#   self.update_ewma(measured_rtt)
# New:
#   signal_result = self.signal_processor.process(measured_rtt, self.load_rtt, self.baseline_rtt)
#   self.update_ewma(signal_result.filtered_rtt)
```

### Pattern 2: Frozen Dataclass Result
**What:** SignalResult is immutable, lightweight, slot-based
**When to use:** Returned from every process() call for downstream consumption
**Example:**
```python
# Source: Follows router_command_utils.py CommandResult pattern
@dataclass(frozen=True, slots=True)
class SignalResult:
    filtered_rtt: float    # Post-Hampel RTT (or raw if warming up)
    raw_rtt: float         # Original measured RTT (always preserved)
    jitter_ms: float       # EWMA jitter from consecutive raw RTT deltas
    variance_ms2: float    # EWMA variance of raw RTT around load_rtt
    confidence: float      # 0-1 score: 1.0/(1.0 + variance/baseline^2)
    is_outlier: bool       # True if Hampel detected this sample as outlier
    outlier_rate: float    # Fraction of recent window that were outliers
    warming_up: bool       # True if Hampel window not yet full
```

### Pattern 3: Config Section with Defaults (Alerting Pattern)
**What:** Optional YAML section, all defaults work without config changes
**When to use:** signal_processing section in autorate config
**Example:**
```python
# Follows _load_alerting_config() pattern in autorate_continuous.py
# Config._load_signal_processing_config() reads optional YAML section
# Invalid values warn and fall back to defaults (never crash)
# Config.signal_processing_config stores dict or uses defaults dict
```

### Pattern 4: Per-WAN Instance (WANController owns all state)
**What:** Each WANController creates its own SignalProcessor in __init__
**When to use:** Signal processing state is per-WAN (independent Hampel windows, jitter history)
**Example:**
```python
# In WANController.__init__():
#   self.signal_processor = SignalProcessor(
#       wan_name=wan_name,
#       config=config.signal_processing_config,  # dict with defaults
#       logger=logger,
#   )
```

### Anti-Patterns to Avoid
- **Shared SignalProcessor across WANs:** Each WAN has different RTT characteristics; shared rolling windows would corrupt detection
- **Filtering jitter/variance input:** Jitter and variance MUST use raw RTT, not filtered -- they reflect true network quality
- **Gating control decisions on confidence:** Phase 88 is observation mode only. Confidence does NOT influence state transitions
- **Persisting signal state to disk:** 350ms warm-up is negligible; state persistence adds complexity for zero value
- **Using numpy/scipy:** Explicitly out of scope per REQUIREMENTS.md. All math is trivially implementable with stdlib

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Median calculation | Manual sorted+index | `statistics.median()` | Handles even/odd lengths, edge cases, consistent with codebase |
| Rolling window | list with manual pop(0) | `collections.deque(maxlen=N)` | O(1) append + auto-eviction vs O(N) pop(0) |
| NaN/Inf guard | Ad-hoc checks | Follow `congestion_assessment.py` ewma_update pattern | Proven pattern, consistent error handling |
| Alpha from time constant | Inline math | Reuse the `alpha = cycle_interval / time_constant` pattern from autorate_continuous.py:365-415 | Interval-independent, human-readable, already validated |

**Key insight:** Every algorithm in this phase has a trivial stdlib implementation. The complexity is in correct wiring and edge case handling, not in the math itself.

## Common Pitfalls

### Pitfall 1: MAD of Zero (Constant Window)
**What goes wrong:** When all values in the Hampel window are identical, MAD = 0.0, making the threshold `0 * sigma = 0`. Any non-identical value becomes an "outlier."
**Why it happens:** Stable networks can produce identical RTT measurements for multiple consecutive cycles (especially at low latencies where ICMP precision rounds to same value).
**How to avoid:** Guard against MAD = 0: if MAD == 0.0, skip outlier detection for that cycle (no sample is an outlier when variance is zero). This is the mathematically correct interpretation: if the distribution has zero spread, any deviation is just a new value, not an outlier.
**Warning signs:** Outlier rate spikes to near 100% during stable periods.

### Pitfall 2: Warm-Up Period Edge Cases
**What goes wrong:** During the first 7 cycles (350ms), the Hampel window is not full. Attempting to compute median on < window_size samples produces unreliable outlier detection.
**Why it happens:** deque starts empty and fills gradually.
**How to avoid:** Track sample count. While `len(window) < window_size`, set `warming_up=True`, return raw_rtt as filtered_rtt, set is_outlier=False. Jitter and variance EWMAs initialize naturally (first sample sets the value).
**Warning signs:** False outlier detection in the first 350ms after daemon start.

### Pitfall 3: Confidence Requires Non-Zero Baseline
**What goes wrong:** Division by zero in `1.0 / (1.0 + variance / baseline^2)` when baseline_rtt is 0.
**Why it happens:** baseline_rtt initializes from config (typically 25-40ms), but edge cases or corrupted state could produce 0.
**How to avoid:** Guard: `if baseline_rtt <= 0: return 1.0` (assume confidence is high when baseline is unknown/invalid). This is safe because confidence is observational only.
**Warning signs:** NaN or Inf in confidence field.

### Pitfall 4: Jitter Requires Previous RTT
**What goes wrong:** First cycle has no previous raw_rtt to compute jitter delta.
**Why it happens:** Jitter = abs(current_raw - previous_raw). On first call, previous does not exist.
**How to avoid:** Initialize `_previous_raw_rtt = None`. On first call, set jitter_ms = 0.0 and store current as previous. Second cycle onward computes normally.
**Warning signs:** Crash or NaN on first cycle.

### Pitfall 5: EWMA Initialization (Zero Start)
**What goes wrong:** EWMA starting at 0.0 takes many cycles to converge to true value.
**Why it happens:** Standard EWMA formula `(1-a)*current + a*new` with current=0 underestimates for many cycles.
**How to avoid:** Follow existing pattern from `congestion_assessment.py:145-147`: if current == 0.0, initialize with the new value directly. Both jitter and variance EWMAs should use this pattern.
**Warning signs:** Jitter/variance reads as near-zero for the first several seconds.

### Pitfall 6: Performance Impact in 50ms Hot Path
**What goes wrong:** Signal processing adds latency to every cycle (currently 30-40ms of 50ms budget used).
**Why it happens:** statistics.median on a 7-element deque is O(N log N) which is trivial, but unnecessary allocations or copies could add up at 20Hz.
**How to avoid:** Use `statistics.median(list(window))` -- deque must be converted to list for statistics.median. For 7 elements this is ~100ns. Avoid creating intermediate data structures. The entire signal processing should add < 0.1ms per cycle.
**Warning signs:** Cycle overrun rate increases after deployment.

## Code Examples

Verified patterns from existing codebase:

### Hampel Filter Core Algorithm
```python
# stdlib only implementation
import statistics
from collections import deque

# MAD scale factor for Gaussian consistency
# 1 / Phi^-1(3/4) where Phi^-1 is the quantile function of standard normal
MAD_SCALE_FACTOR = 1.4826

def _hampel_check(window: deque, new_value: float, sigma_threshold: float) -> tuple[bool, float]:
    """Check if new_value is an outlier relative to window.

    Returns (is_outlier, replacement_value).
    replacement_value is median if outlier, else new_value.
    """
    values = list(window)  # deque -> list for statistics.median
    med = statistics.median(values)

    # MAD = median of absolute deviations from median
    abs_devs = [abs(v - med) for v in values]
    mad = statistics.median(abs_devs)

    # Threshold: MAD * scale_factor * sigma
    threshold = mad * MAD_SCALE_FACTOR * sigma_threshold

    if threshold == 0.0:
        # All values identical -- no outlier possible
        return False, new_value

    if abs(new_value - med) > threshold:
        return True, med  # Replace outlier with median

    return False, new_value
```

### Alpha from Time Constant (Existing Pattern)
```python
# Source: autorate_continuous.py lines 365-415
# Formula: alpha = cycle_interval / time_constant
CYCLE_INTERVAL_SECONDS = 0.05  # 50ms

# Jitter: 2.0s time constant -> alpha = 0.05/2.0 = 0.025
jitter_alpha = CYCLE_INTERVAL_SECONDS / jitter_time_constant_sec

# Variance: 5.0s time constant -> alpha = 0.05/5.0 = 0.01
variance_alpha = CYCLE_INTERVAL_SECONDS / variance_time_constant_sec
```

### EWMA Update with Zero-Start Guard
```python
# Source: congestion_assessment.py lines 100-155
def _ewma_update(current: float, new_value: float, alpha: float) -> float:
    """EWMA update with first-sample initialization."""
    if current == 0.0:
        return new_value  # Initialize with first measurement
    return (1.0 - alpha) * current + alpha * new_value
```

### Confidence Score Calculation
```python
# Variance-based confidence: 1.0 = stable, 0.0 = noisy
# Formula chosen for interpretability: >0.8 stable, 0.5-0.8 moderate, <0.5 unreliable
def _compute_confidence(variance_ms2: float, baseline_rtt: float) -> float:
    if baseline_rtt <= 0.0:
        return 1.0  # Unknown baseline -> assume confident (observational only)
    return 1.0 / (1.0 + variance_ms2 / (baseline_rtt ** 2))
```

### Config Loading Pattern (Following Alerting)
```python
# Source: autorate_continuous.py _load_alerting_config() pattern
# Optional YAML section, warn+default on invalid values, never crash
def _load_signal_processing_config(self) -> None:
    sp = self.data.get("signal_processing", {})
    # Hampel defaults
    hampel = sp.get("hampel", {})
    window_size = hampel.get("window_size", 7)
    sigma_threshold = hampel.get("sigma_threshold", 3.0)
    # Validate with warn+default
    if not isinstance(window_size, int) or window_size < 3:
        logger.warning(f"signal_processing.hampel.window_size invalid; defaulting to 7")
        window_size = 7
    # ... similar for other fields
    self.signal_processing_config = {
        "hampel_window_size": window_size,
        "hampel_sigma_threshold": sigma_threshold,
        "jitter_time_constant_sec": jitter_tc,
        "variance_time_constant_sec": variance_tc,
    }
```

### Integration Point in run_cycle()
```python
# Source: autorate_continuous.py line 1643-1647
# Current:
#   self.update_ewma(measured_rtt)
# After signal processing integration:
#   signal_result = self.signal_processor.process(
#       raw_rtt=measured_rtt,
#       load_rtt=self.load_rtt,
#       baseline_rtt=self.baseline_rtt,
#   )
#   self._last_signal_result = signal_result  # Store for Phase 92 metrics
#   self.update_ewma(signal_result.filtered_rtt)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw RTT -> EWMA (no filtering) | Hampel filter -> EWMA | Phase 88 (new) | Outlier spikes no longer poison EWMA |
| No jitter tracking | EWMA jitter from consecutive RTT deltas | Phase 88 (new) | Network stability metric available |
| No variance tracking | EWMA variance of raw RTT around load_rtt | Phase 88 (new) | Measurement reliability quantified |
| No confidence scoring | Variance-based 0-1 confidence | Phase 88 (new) | Future phases can use for fusion/gating |

**Deprecated/outdated:**
- Acceleration detection (autorate_continuous.py:1649-1661) still uses `load_rtt - previous_load_rtt` for spike detection. This remains unchanged -- signal processing Hampel filter operates on raw RTT before EWMA, while accel detection operates on load_rtt after EWMA. They are complementary, not redundant.

## Open Questions

1. **Outlier rate window vs Hampel window**
   - What we know: CONTEXT.md specifies "outlier_rate (percentage of recent window)" -- the Hampel window itself is the natural choice
   - What's unclear: Whether outlier_rate should use a separate, potentially larger, tracking window
   - Recommendation: Use the Hampel window size (7) as the outlier rate denominator. Track `_recent_outlier_count` as count of outliers in the current window. Rate = count / window_size. This is simple and avoids a second deque.

2. **Confidence score when baseline is initial value**
   - What we know: baseline_rtt starts at config value (e.g., 25.0ms) before converging to true value
   - What's unclear: Whether confidence should account for baseline not yet being converged
   - Recommendation: Use current baseline as-is. The initial config baseline is a reasonable estimate, and confidence is observational only. After ~60s of idle time, baseline converges naturally.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_signal_processing.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIGP-01 | Hampel filter detects and replaces outliers | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestHampelFilter -x` | Wave 0 |
| SIGP-01 | Warm-up period passes raw RTT through | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestWarmUp -x` | Wave 0 |
| SIGP-01 | MAD=0 guard (constant window) | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestHampelFilter::test_constant_window -x` | Wave 0 |
| SIGP-02 | Jitter computed from consecutive raw RTTs | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestJitter -x` | Wave 0 |
| SIGP-02 | First cycle jitter is 0.0 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestJitter::test_first_cycle -x` | Wave 0 |
| SIGP-03 | Confidence computed from variance and baseline | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestConfidence -x` | Wave 0 |
| SIGP-03 | Confidence handles baseline=0 gracefully | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestConfidence::test_zero_baseline -x` | Wave 0 |
| SIGP-04 | Variance EWMA tracks raw RTT deviation | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestVariance -x` | Wave 0 |
| SIGP-05 | No new dependencies added | unit | `.venv/bin/pytest tests/test_signal_processing.py::test_stdlib_only -x` | Wave 0 |
| SIGP-06 | Observation mode: filtered_rtt feeds EWMA, no state/rate changes | integration | `.venv/bin/pytest tests/test_signal_processing.py::TestObservationMode -x` | Wave 0 |
| -- | Config loading with defaults and validation | unit | `.venv/bin/pytest tests/test_signal_processing_config.py -x` | Wave 0 |
| -- | Integration with WANController.run_cycle() | integration | `.venv/bin/pytest tests/test_autorate_continuous.py -x -k signal` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_signal_processing.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_signal_processing.py` -- covers SIGP-01, SIGP-02, SIGP-03, SIGP-04, SIGP-05, SIGP-06
- [ ] `tests/test_signal_processing_config.py` -- covers config loading, validation, defaults
- [ ] No new framework install needed -- existing pytest infrastructure covers all requirements

## Sources

### Primary (HIGH confidence)
- `/home/kevin/projects/wanctl/src/wanctl/autorate_continuous.py` -- WANController, update_ewma(), run_cycle(), Config class, alpha calculation pattern
- `/home/kevin/projects/wanctl/src/wanctl/steering/congestion_assessment.py` -- ewma_update() with NaN/Inf guards, zero-start initialization
- `/home/kevin/projects/wanctl/src/wanctl/router_command_utils.py` -- `@dataclass(frozen=True, slots=True)` CommandResult pattern
- `/home/kevin/projects/wanctl/src/wanctl/baseline_rtt_manager.py` -- BaselineRTTManager EWMA pattern, baseline freeze logic
- `/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py` -- RTTMeasurement class, ping_host() return type
- `/home/kevin/projects/wanctl/tests/conftest.py` -- mock_autorate_config fixture pattern
- Python 3.12 stdlib verification -- `statistics.median`, `collections.deque`, `math.isnan/isinf` all available
- `.planning/phases/88-signal-processing-core/88-CONTEXT.md` -- locked implementation decisions

### Secondary (MEDIUM confidence)
- [Wikipedia: MAD](https://en.wikipedia.org/wiki/Median_absolute_deviation) -- MAD_SCALE_FACTOR = 1.4826 = 1/quantile(normal, 3/4)
- [RFC 3550](https://www.ietf.org/rfc/rfc3550.txt) -- Jitter EWMA formula J(i) = J(i-1) + (|D(i-1,i)| - J(i-1))/16, adapted with configurable alpha
- [Towards Data Science: Hampel Filter](https://towardsdatascience.com/outlier-detection-with-hampel-filter-85ddf523c73d/) -- Algorithm verification: rolling median + MAD * scale * sigma threshold

### Tertiary (LOW confidence)
- None -- all findings verified against codebase and official references

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, verified against Python 3.12
- Architecture: HIGH -- follows 6 established wanctl patterns (frozen dataclass, per-WAN instance, config section, EWMA alpha, deque window, warn+default validation)
- Pitfalls: HIGH -- derived from algorithm properties and verified against existing codebase guards
- Integration points: HIGH -- exact line numbers identified in autorate_continuous.py

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stdlib-only, no external dependency drift risk)
