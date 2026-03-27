# Phase 119: Auto-Fusion Healing - Research

**Researched:** 2026-03-27
**Domain:** Rolling Pearson correlation, 3-state machine, fusion lifecycle management
**Confidence:** HIGH

## Summary

Phase 119 adds automatic fusion state management to replace the manual SIGUSR1 toggle workflow for ICMP/IRTT path divergence (the ATT production issue where correlation=0.74 causes permanent delta offset). The implementation involves: (1) an incremental rolling Pearson correlation computed per-cycle at ~3us overhead, (2) a 3-state machine (ACTIVE/SUSPENDED/RECOVERING) with asymmetric hysteresis, (3) AlertEngine integration for Discord notifications on state transitions, (4) tuning parameter locking via the existing `_parameter_locks` dict, and (5) health endpoint extensions.

All building blocks exist in the codebase. The AlertEngine fire/cooldown mechanism, the `is_parameter_locked`/`lock_parameter` functions, the health endpoint fusion section, and the SIGUSR1 reload handler are all ready for extension. No new dependencies. The Pearson correlation uses Python stdlib `math` only (incremental formula, not `statistics.correlation` -- that would be 90x slower per-cycle). The 50ms cycle budget is safe: incremental Pearson add+compute measured at 3.3 microseconds.

**Primary recommendation:** Implement a standalone `FusionHealer` class in a new `src/wanctl/fusion_healer.py` module, instantiated per-WAN in `WANController.__init__()`, with a `tick()` method called from the existing `_check_protocol_correlation()` site. Reuse `_parameter_locks` dict with a sentinel expiry (`float('inf')`) for event-based locking that the healer clears on recovery.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use rolling Pearson correlation between ICMP and IRTT signal deltas, NOT the existing simple ratio metric in `_check_protocol_correlation()`. Pearson catches the ATT scenario where the ratio looks "normal" (0.74) but signals disagree on directional trends.
- **D-02:** Sustained detection uses a 60-second time window average of Pearson correlation. At 20Hz, this is ~1,200 samples per window -- statistically robust. Threshold is configurable via YAML.
- **D-03:** 3-state machine: ACTIVE -> SUSPENDED -> RECOVERING -> ACTIVE.
- **D-04:** SUSPENDED triggers when 60-second rolling Pearson correlation drops below configurable threshold for sustained period.
- **D-05:** RECOVERING -> ACTIVE requires sustained good correlation above threshold for a longer window (e.g., 5 minutes). Asymmetric hysteresis: fast to suspend (~1 min), slow to recover (~5 min). This mirrors the controller's existing philosophy (rate decreases immediate, increases require sustained GREEN cycles).
- **D-06:** Operator overrides with healer pause. When operator sends SIGUSR1 to re-enable fusion while healer is in SUSPENDED state, fusion re-enables immediately AND the healer pauses monitoring for a configurable grace period (default 30 minutes). After grace expires, healer resumes -- if correlation is still bad, it re-suspends. If the operator's change fixed the path, correlation improves during grace and healer stays ACTIVE.

### Claude's Discretion
- Parameter lock mechanism (D-07)
- Pearson correlation implementation details (window management, sample buffer structure)
- Exact configurable threshold values and defaults
- Grace period default (30 minutes suggested, Claude may adjust)
- Where the healer state machine lives (new module vs integrated into autorate_continuous.py)
- Alert message content and severity levels for state transitions
- Health endpoint payload structure for heal state and correlation history
- Test structure and fixture design

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FUSE-01 | Controller auto-suspends fusion when protocol correlation drops below configurable threshold for sustained period | Incremental Pearson correlation (3.3us/cycle), 60s rolling window, `FusionHealer` state machine ACTIVE->SUSPENDED transition |
| FUSE-02 | Controller auto-re-enables fusion when protocol correlation recovers (3-state: ACTIVE/SUSPENDED/RECOVERING) | Asymmetric hysteresis: 60s suspend window, 300s recovery window, state machine SUSPENDED->RECOVERING->ACTIVE |
| FUSE-03 | Fusion state transitions trigger Discord alerts via AlertEngine | New alert types `fusion_suspended`/`fusion_recovering`/`fusion_recovered` with `rule_key="fusion_healing"` |
| FUSE-04 | TuningEngine locks fusion_icmp_weight parameter when fusion healer suspends fusion | Reuse `_parameter_locks` dict with `float('inf')` sentinel expiry; healer clears on recovery |
| FUSE-05 | Health endpoint exposes fusion heal state (active/suspended/recovering) and correlation history | Extend existing `wan_health["fusion"]` dict with `heal_state`, `pearson_correlation`, `correlation_window_avg` |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Production network control system -- change conservatively
- Priority: stability > safety > clarity > elegance
- Never refactor core logic, algorithms, thresholds, or timing without approval
- Portable Controller Architecture: all variability in config parameters (YAML)
- 50ms cycle interval -- all per-cycle additions must be sub-millisecond
- Tests use `.venv/bin/pytest tests/ -v`
- Python 3.12, modern type hints, absolute imports
- Zero new dependencies (stdlib only per project pattern)

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `math` | 3.12 | Incremental Pearson formula (sqrt) | Zero-dep, O(1) per-cycle |
| Python stdlib `collections.deque` | 3.12 | Rolling window buffers for ICMP/IRTT deltas | Established pattern in signal_processing.py |
| Python stdlib `time.monotonic` | 3.12 | Grace period tracking, state transition timestamps | Clock-drift immune, matches all existing timing |
| Python stdlib `enum.Enum` | 3.12 | HealState (ACTIVE/SUSPENDED/RECOVERING) | Type-safe state representation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `statistics.correlation` | 3.12 | Test validation only -- verify incremental Pearson matches exact | Not for production hot loop (298us vs 3.3us) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Incremental Pearson | `statistics.correlation` per-cycle | 90x slower (298us vs 3.3us), still within budget but wasteful |
| Incremental Pearson | numpy corrcoef | New dependency, overkill for single-pair correlation |
| `deque` buffers | Circular array | deque is established codebase pattern, no benefit from custom |

**Installation:**
```bash
# No installation needed -- all stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
    fusion_healer.py           # NEW: FusionHealer class + HealState enum
    autorate_continuous.py     # MODIFY: instantiate healer, hook tick(), SIGUSR1 grace
    health_check.py            # MODIFY: expose heal state
    alert_engine.py            # NO CHANGE (add alert rules in YAML config only)
    tuning/safety.py           # NO CHANGE (reuse is_parameter_locked/lock_parameter)
tests/
    test_fusion_healer.py      # NEW: healer state machine unit tests
    test_fusion_healer_integration.py  # NEW: healer + WANController wiring tests
```

### Pattern 1: Standalone Healer Module
**What:** `FusionHealer` as a single-responsibility class in its own module, following the `SignalProcessor` and `ReflectorScorer` patterns.
**When to use:** When a per-cycle state machine has enough logic to warrant its own module (~150-200 lines).
**Why not inline in autorate_continuous.py:** autorate_continuous.py is already 4200+ lines. The healer has its own state (buffers, running sums, state machine, grace timer). A dedicated module improves testability and follows the `signal_processing.py` / `reflector_scorer.py` precedent.

```python
# src/wanctl/fusion_healer.py
import enum
import logging
import math
import time
from collections import deque

logger = logging.getLogger(__name__)


class HealState(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RECOVERING = "recovering"


class FusionHealer:
    """Automatic fusion state management based on rolling Pearson correlation.

    Monitors ICMP/IRTT signal delta correlation and manages a 3-state machine:
    ACTIVE -> SUSPENDED (correlation degraded) -> RECOVERING -> ACTIVE (correlation recovered).

    Instantiated per-WAN in WANController.__init__(). Called via tick() from
    the existing _check_protocol_correlation() site each cycle.
    """

    def __init__(
        self,
        wan_name: str,
        *,
        suspend_threshold: float = 0.3,
        recover_threshold: float = 0.5,
        suspend_window_sec: float = 60.0,
        recover_window_sec: float = 300.0,
        grace_period_sec: float = 1800.0,
        cycle_interval_sec: float = 0.05,
    ) -> None:
        self._wan_name = wan_name
        self._state = HealState.ACTIVE
        self._suspend_threshold = suspend_threshold
        self._recover_threshold = recover_threshold
        self._suspend_window_samples = int(suspend_window_sec / cycle_interval_sec)
        self._recover_window_samples = int(recover_window_sec / cycle_interval_sec)
        self._grace_period_sec = grace_period_sec
        self._grace_until: float = 0.0  # monotonic expiry

        # Rolling Pearson correlation via incremental running sums
        self._window_size = self._suspend_window_samples  # 1200 at 20Hz
        self._x_buf: deque[float] = deque(maxlen=self._window_size)
        self._y_buf: deque[float] = deque(maxlen=self._window_size)
        self._sum_x = 0.0
        self._sum_y = 0.0
        self._sum_xy = 0.0
        self._sum_x2 = 0.0
        self._sum_y2 = 0.0
        self._n = 0

        # State transition tracking
        self._sustained_below_count = 0
        self._sustained_above_count = 0
        self._last_transition_ts: float | None = None

    def tick(self, icmp_delta: float, irtt_delta: float) -> HealState:
        """Process one cycle of ICMP/IRTT deltas. Returns current state."""
        ...  # Implementation details in plan

    @property
    def state(self) -> HealState:
        return self._state

    @property
    def pearson_r(self) -> float | None:
        """Current rolling Pearson correlation, or None if warming up."""
        ...
```

### Pattern 2: Reuse Existing Parameter Lock Mechanism (D-07 Resolution)
**What:** Use the existing `_parameter_locks` dict with `lock_parameter(locks, "fusion_icmp_weight", float('inf'))` for event-based locking. The healer calls `lock_parameter` when transitioning to SUSPENDED and `del locks["fusion_icmp_weight"]` when transitioning to ACTIVE.
**Why this over a new `healer_locked_params` set:**
1. The tuning engine already checks `is_parameter_locked(wc._parameter_locks, pname)` at line 4158. Zero changes needed in the tuning hot path.
2. The `float('inf')` sentinel means the lock never time-expires -- only the healer can clear it (event-based semantics with time-based infrastructure).
3. The existing `is_parameter_locked()` function already handles expiry checks, so the sentinel works naturally.
4. Separation of concerns is maintained: the healer *creates* the lock (with infinite duration), the tuning engine *checks* it (unchanged), and the healer *clears* it on recovery.

```python
# In FusionHealer.tick() when transitioning to SUSPENDED:
from wanctl.tuning.safety import lock_parameter
lock_parameter(self._parameter_locks_ref, "fusion_icmp_weight", float('inf'))

# In FusionHealer.tick() when transitioning to ACTIVE:
self._parameter_locks_ref.pop("fusion_icmp_weight", None)
```

### Pattern 3: Incremental Rolling Pearson Correlation
**What:** O(1) per-cycle Pearson computation using running sums (sum_x, sum_y, sum_xy, sum_x2, sum_y2) with deque-based windowing.
**Performance:** 3.3 microseconds per cycle (benchmarked on dev machine).
**Numerical stability:** Drift of 2e-14 after 1 million cycles (14 hours at 20Hz). No recalibration needed.

```python
def _add_sample(self, x: float, y: float) -> None:
    """Add a sample pair, evicting oldest if window full."""
    if len(self._x_buf) == self._window_size:
        old_x = self._x_buf[0]
        old_y = self._y_buf[0]
        self._sum_x -= old_x
        self._sum_y -= old_y
        self._sum_xy -= old_x * old_y
        self._sum_x2 -= old_x * old_x
        self._sum_y2 -= old_y * old_y
        self._n -= 1
    self._x_buf.append(x)
    self._y_buf.append(y)
    self._sum_x += x
    self._sum_y += y
    self._sum_xy += x * y
    self._sum_x2 += x * x
    self._sum_y2 += y * y
    self._n += 1

def _compute_pearson(self) -> float | None:
    """Compute Pearson r from running sums. Returns None if < 2 samples."""
    if self._n < 2:
        return None
    numerator = self._n * self._sum_xy - self._sum_x * self._sum_y
    denom_sq = (self._n * self._sum_x2 - self._sum_x ** 2) * (
        self._n * self._sum_y2 - self._sum_y ** 2
    )
    if denom_sq <= 0.0:
        return 0.0
    return numerator / math.sqrt(denom_sq)
```

### Pattern 4: SIGUSR1 Grace Period Integration
**What:** When `_reload_fusion_config()` detects fusion being re-enabled while healer is SUSPENDED, it calls `healer.start_grace_period()`. During grace, healer continues collecting samples but does not suspend.

```python
# In _reload_fusion_config() -- after setting self._fusion_enabled = new_enabled:
if new_enabled and not old_enabled and self._fusion_healer is not None:
    if self._fusion_healer.state == HealState.SUSPENDED:
        self._fusion_healer.start_grace_period()
        self.logger.warning(
            "[FUSION] Operator override: healer paused for %ds grace period",
            self._fusion_healer._grace_period_sec,
        )
```

### Pattern 5: Alert Integration
**What:** New alert types use the existing `rule_key` mechanism so all fusion healing alerts share one YAML config block.

```yaml
# YAML config pattern:
alerting:
  rules:
    fusion_healing:
      enabled: true
      cooldown_sec: 300
      severity: warning
```

```python
# In FusionHealer, after state transition:
self._alert_engine.fire(
    alert_type="fusion_suspended",
    severity="warning",
    wan_name=self._wan_name,
    details={
        "pearson_r": round(r, 4),
        "threshold": self._suspend_threshold,
        "window_sec": 60,
    },
    rule_key="fusion_healing",
)
```

### Anti-Patterns to Avoid
- **Computing Pearson on full list each cycle:** `statistics.correlation(list(x_buf), list(y_buf))` is 90x slower. Use incremental running sums.
- **Using absolute RTT values for correlation:** Decision D-01 specifies signal *deltas* (cycle-over-cycle changes), not absolute RTT. Absolute values would correlate on magnitude, not direction.
- **Separate locking mechanism for healer:** Adding a new `_healer_locked_params` set means the tuning engine needs to check two places. Reuse `_parameter_locks` with `float('inf')`.
- **Putting healer state machine in autorate_continuous.py:** Already 4200+ lines. Healer is a self-contained module like `signal_processing.py`.
- **Stateful alerting in the healer:** Healer calls `AlertEngine.fire()`, which handles cooldowns and dedup. Don't build custom cooldown logic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Alert dedup/cooldown | Custom per-transition cooldown logic | `AlertEngine.fire()` with `rule_key="fusion_healing"` | Already handles (type,wan) cooldown, persistence, delivery |
| Parameter locking | New `healer_locked_params` set | `lock_parameter(locks, param, float('inf'))` | Tuning engine already checks `is_parameter_locked()` -- zero integration cost |
| Config validation | Custom validator for healing config | Extend `_load_fusion_config()` pattern | Same warn+default pattern used for all config sections |
| Webhook delivery | Custom Discord POST | `webhook_delivery.py` callback via AlertEngine | Handles rate limiting, retry, mention_role_id |

**Key insight:** The codebase has mature, battle-tested infrastructure for alerting, parameter locking, config loading, and health endpoints. Every integration point for this phase is an extension of existing patterns, not a new subsystem.

## Common Pitfalls

### Pitfall 1: Using Absolute RTT Instead of Deltas for Pearson Input
**What goes wrong:** Pearson on absolute ICMP/IRTT RTT values would show high correlation whenever both signals have similar magnitudes, even if they trend in opposite directions (the exact ATT production scenario).
**Why it happens:** Confusing "values are similar" with "values move together."
**How to avoid:** Feed cycle-over-cycle deltas (`current_rtt - previous_rtt`) into the Pearson computation. This measures directional agreement, which is what D-01 specifies.
**Warning signs:** Pearson stays high (>0.7) even when one signal rises while the other falls.

### Pitfall 2: Forgetting to Handle Warmup Period
**What goes wrong:** Healer triggers SUSPENDED transition on first few cycles when correlation is undefined or noisy.
**Why it happens:** The 60-second window needs ~1,200 samples to be statistically meaningful. With fewer than ~100 samples, Pearson can swing wildly.
**How to avoid:** Return `None` from `_compute_pearson()` when `n < min_samples` (e.g., 100). State machine stays ACTIVE during warmup. Log warmup progress.
**Warning signs:** Spurious suspension alerts within 60 seconds of daemon startup.

### Pitfall 3: Grace Period Not Clearing Sustained Counters
**What goes wrong:** Operator sends SIGUSR1, grace starts, but the healer's `_sustained_below_count` carries over from before grace. When grace expires, healer immediately re-suspends from stale counter state.
**Why it happens:** Grace period only pauses state transitions, but doesn't reset the counters.
**How to avoid:** `start_grace_period()` must reset `_sustained_below_count = 0` and `_sustained_above_count = 0` and transition to ACTIVE.
**Warning signs:** Suspension fires within seconds of grace expiry instead of requiring a full 60s window.

### Pitfall 4: MagicMock Safety in Health Endpoint
**What goes wrong:** Health endpoint accesses `wan_controller._fusion_healer.state` but in tests, `_fusion_healer` might be a MagicMock that doesn't have the expected `.value` attribute.
**Why it happens:** Established pattern in the codebase -- health endpoint uses `getattr()` guards.
**How to avoid:** Use `getattr(wan_controller, "_fusion_healer", None)` and check `is not None` before accessing `.state`.
**Warning signs:** `AttributeError` in health check during tests.

### Pitfall 5: Locking Fusion Weight During RECOVERING State
**What goes wrong:** Tuner modifies `fusion_icmp_weight` during RECOVERING (healer hasn't fully cleared), causing the recovering fusion to oscillate.
**Why it happens:** Lock only held during SUSPENDED, cleared at ACTIVE. RECOVERING is an intermediate state.
**How to avoid:** Keep the lock through both SUSPENDED and RECOVERING. Only clear when fully transitioning to ACTIVE.
**Warning signs:** Tuning adjustments to fusion_icmp_weight during RECOVERING state.

### Pitfall 6: IRTT Thread Not Running When Healer Expects Data
**What goes wrong:** Healer instantiated but IRTT thread is None (IRTT disabled). No deltas to feed into Pearson.
**Why it happens:** Fusion can be enabled in config without IRTT.
**How to avoid:** Only instantiate `FusionHealer` when both `fusion.enabled` AND `irtt.enabled`. The existing `_compute_fused_rtt()` already handles IRTT-not-running as pure passthrough.
**Warning signs:** Healer stuck in warmup forever with 0 samples.

## Code Examples

### Verified: AlertEngine fire() with rule_key
```python
# Source: src/wanctl/alert_engine.py lines 76-135
# Existing pattern used by congestion alerts with sustained_sec sub-types:
alert_engine.fire(
    alert_type="fusion_suspended",
    severity="warning",
    wan_name="att",
    details={"pearson_r": 0.15, "threshold": 0.3},
    rule_key="fusion_healing",  # Shares config block
)
```

### Verified: Parameter Lock with Infinite Duration
```python
# Source: src/wanctl/tuning/safety.py lines 159-190
# Existing functions with sentinel value:
from wanctl.tuning.safety import is_parameter_locked, lock_parameter

# Lock (healer suspends fusion):
lock_parameter(wc._parameter_locks, "fusion_icmp_weight", float('inf'))
# Infinite expiry means time.monotonic() never >= float('inf')

# Check (tuning engine, line 4158 -- NO CHANGE NEEDED):
if not is_parameter_locked(wc._parameter_locks, pname):
    # ... run strategy

# Unlock (healer recovers):
wc._parameter_locks.pop("fusion_icmp_weight", None)
```

### Verified: Health Endpoint Extension Pattern
```python
# Source: src/wanctl/health_check.py lines 278-320
# Existing fusion section -- extend with heal state:
wan_health["fusion"] = {
    "enabled": True,
    "icmp_weight": wan_controller._fusion_icmp_weight,
    # ... existing fields ...
    # NEW fields:
    "heal_state": healer.state.value if healer else "disabled",
    "pearson_correlation": round(healer.pearson_r, 4) if healer and healer.pearson_r is not None else None,
    "correlation_window_avg": round(healer.window_avg, 4) if healer and healer.window_avg is not None else None,
}
```

### Verified: SIGUSR1 Reload Hook Point
```python
# Source: src/wanctl/autorate_continuous.py lines 4224-4248
# Existing handler -- add healer grace after _reload_fusion_config():
if is_reload_requested():
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info("SIGUSR1 received, reloading config")
        wan_info["controller"]._reload_fusion_config()
        wan_info["controller"]._reload_tuning_config()
        # NEW: healer grace period check (added inside _reload_fusion_config)
```

### Verified: Existing Correlation Call Site
```python
# Source: src/wanctl/autorate_continuous.py lines 2724-2727
# This is where healer.tick() hooks in:
if age <= cadence * 3 and irtt_result.rtt_mean_ms > 0 and self.load_rtt > 0:
    ratio = self.load_rtt / irtt_result.rtt_mean_ms
    self._check_protocol_correlation(ratio)
    # NEW: feed deltas to healer
    # icmp_delta = self.load_rtt - self._prev_load_rtt (or similar)
    # irtt_delta = irtt_result.rtt_mean_ms - self._prev_irtt_rtt
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual SIGUSR1 toggle | Auto-healing state machine | Phase 119 (this phase) | Eliminates manual intervention for path divergence |
| Simple ICMP/UDP ratio | Rolling Pearson correlation | Phase 119 (this phase) | Catches directional disagreement that ratio misses |
| No parameter protection | Tuner lock during suspension | Phase 119 (this phase) | Prevents tuner from adjusting fusion_icmp_weight during known-bad state |

**Deprecated/outdated after this phase:**
- Manual SIGUSR1 workflow for fusion toggle during path divergence (still functional, now augmented with grace period)
- Simple ratio threshold (0.67-1.5) for protocol deprioritization detection (still runs, healer uses Pearson alongside)

## Open Questions

1. **What RTT values to use as Pearson inputs?**
   - What we know: D-01 says "signal deltas" -- cycle-over-cycle changes in ICMP vs IRTT RTT
   - What's unclear: Should we use `filtered_rtt` (post-Hampel) or `load_rtt` (post-EWMA) for ICMP delta? Should IRTT delta use `rtt_mean_ms` directly?
   - Recommendation: Use `filtered_rtt` for ICMP (post-Hampel, pre-EWMA -- cleanest signal without smoothing lag) and `irtt_result.rtt_mean_ms` for IRTT. Both are per-cycle raw-ish signals. The deltas then capture directional agreement. Planner should confirm this in the plan.

2. **Default threshold values**
   - What we know: D-02 says "configurable via YAML," no specific defaults given. ATT production correlation was 0.74 (ratio-based) which looked normal.
   - Recommendation: `suspend_threshold: 0.3` (Pearson below 0.3 = weak/no linear relationship), `recover_threshold: 0.5` (moderate positive correlation). These provide hysteresis gap of 0.2. Conservative -- better to not suspend than to flap.

3. **Should the healer also gate `_compute_fused_rtt()` directly?**
   - What we know: When healer suspends, it disables `_fusion_enabled`, which causes `_compute_fused_rtt()` to return `filtered_rtt` unchanged (line 2442-2443).
   - What's unclear: Should the healer set `_fusion_enabled = False` directly, or should `_compute_fused_rtt()` check `healer.state`?
   - Recommendation: Healer sets `_fusion_enabled = False` on SUSPENDED transition and `True` on ACTIVE transition. This is the simplest integration -- `_compute_fused_rtt()` needs zero changes. The healer owns the lifecycle of `_fusion_enabled` when healing is active.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (via .venv) |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_fusion_healer.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUSE-01 | Auto-suspend on low Pearson correlation for sustained period | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestSuspension -x` | Wave 0 |
| FUSE-01 | Pearson incremental matches statistics.correlation (cross-verify) | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestPearsonAccuracy -x` | Wave 0 |
| FUSE-02 | 3-state ACTIVE->SUSPENDED->RECOVERING->ACTIVE transitions | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestRecovery -x` | Wave 0 |
| FUSE-02 | Asymmetric hysteresis timing (fast suspend, slow recover) | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestHysteresis -x` | Wave 0 |
| FUSE-03 | Discord alerts on state transitions via AlertEngine | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestAlerts -x` | Wave 0 |
| FUSE-04 | fusion_icmp_weight locked in _parameter_locks during SUSPENDED | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestParameterLock -x` | Wave 0 |
| FUSE-04 | Lock persists through RECOVERING, cleared only at ACTIVE | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestParameterLock -x` | Wave 0 |
| FUSE-05 | Health endpoint shows heal_state and correlation data | unit | `.venv/bin/pytest tests/test_fusion_healer_integration.py::TestHealthEndpoint -x` | Wave 0 |
| D-06 | SIGUSR1 grace period pauses healer for 30 min | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestGracePeriod -x` | Wave 0 |
| D-06 | Grace period resets sustained counters | unit | `.venv/bin/pytest tests/test_fusion_healer.py::TestGracePeriod -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_fusion_healer.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fusion_healer.py` -- covers FUSE-01, FUSE-02, FUSE-03, FUSE-04, D-06
- [ ] `tests/test_fusion_healer_integration.py` -- covers FUSE-05 (health endpoint) and WANController wiring
- [ ] No framework install needed -- pytest already configured in pyproject.toml

## Sources

### Primary (HIGH confidence)
- `src/wanctl/autorate_continuous.py` lines 2389-2530 -- existing fusion core, correlation check, SIGUSR1 reload
- `src/wanctl/tuning/safety.py` lines 159-190 -- parameter lock mechanism (verified code)
- `src/wanctl/alert_engine.py` lines 76-135 -- fire() with rule_key mechanism (verified code)
- `src/wanctl/health_check.py` lines 278-320 -- health endpoint fusion section (verified code)
- `src/wanctl/signal_processing.py` -- deque-based windowed processing pattern (verified code)
- Python 3.12 `statistics.correlation` -- verified available for test validation
- Benchmark: incremental Pearson 3.3us/cycle, statistics.correlation 298us/cycle (measured locally)
- Benchmark: numerical drift 2e-14 after 1M cycles (measured locally)

### Secondary (MEDIUM confidence)
- Incremental Pearson formula: standard statistical identity `r = (n*sum_xy - sum_x*sum_y) / sqrt((n*sum_x2 - sum_x^2)(n*sum_y2 - sum_y^2))` -- textbook formula, well-established

### Tertiary (LOW confidence)
- Default threshold values (0.3 suspend, 0.5 recover) -- reasonable defaults based on Pearson interpretation (0.3 = weak correlation, 0.5 = moderate), but production validation needed

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, no new dependencies, patterns verified in codebase
- Architecture: HIGH -- every integration point verified in source, patterns match existing modules
- Pitfalls: HIGH -- derived from code review of actual integration points and production scenario
- Thresholds: LOW -- default values need production validation (configurable per YAML)

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable domain, no external dependencies)
