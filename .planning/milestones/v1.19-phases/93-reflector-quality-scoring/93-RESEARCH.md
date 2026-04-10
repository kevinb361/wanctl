# Phase 93: Reflector Quality Scoring - Research

**Researched:** 2026-03-17
**Domain:** ICMP reflector health tracking, rolling quality scoring, automatic deprioritization/recovery
**Confidence:** HIGH

## Summary

Phase 93 adds per-reflector quality tracking to the autorate daemon's RTT measurement path. Each configured `ping_host` reflector accumulates a rolling success rate. When a reflector's score drops below a configurable threshold, it is removed from the active measurement set. Deprioritized reflectors receive periodic recovery probes and are restored when quality improves.

The implementation maps cleanly onto existing codebase patterns. SignalProcessor (Phase 88) provides the template: per-WAN instantiation, deque-based rolling window, frozen dataclass result, config-with-defaults loading. AlertEngine (Phase 76) provides the SQLite event persistence pattern. The health endpoint (Phase 92) already has per-WAN sections with `available`/`reason` patterns to follow.

**Primary recommendation:** Create a standalone `ReflectorScorer` class (new module `reflector_scorer.py`) instantiated per-WAN in `WANController.__init__()`, with `measure_rtt()` calling through the scorer to filter the active reflector set and record per-host success/failure after each measurement cycle.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Quality score is **success rate** (0.0-1.0) -- fraction of successful pings over a rolling window
- Only signal is success/failure of each ping attempt -- no per-reflector jitter or RTT deviation tracking
- Rolling window is **count-based** (e.g., last 50 measurement attempts per reflector) using a deque
- Score is raw ratio (success_count / window_size), not mapped to discrete grades
- Single **global threshold** configurable via YAML (e.g., `reflector_quality.min_score: 0.8`)
- No per-reflector threshold overrides
- Deprioritized reflectors are **skipped entirely** -- removed from the active set for `measure_rtt()`
- If **all reflectors** are deprioritized, **force-use the best-scoring one** (never have zero targets)
- Forced-use logs a WARNING (matches ICMP blackout resilience pattern from v1.1)
- **Graceful degradation** for median-of-three mode: 3 healthy = median-of-3, 2 healthy = average-of-2, 1 healthy = single ping, 0 healthy = force best-scoring
- Deprioritization transitions logged at **WARNING** level
- Recovery transitions logged at **INFO** level
- **Periodic probe pings** to deprioritized reflectors on a configurable interval (default 30 seconds)
- Probe is a single ICMP ping via existing `RTTMeasurement.ping_host()`
- Recovery requires **sustained improvement**: N consecutive successful probes (configurable, default 3)
- Probe results update the reflector's score normally
- YAML config: `reflector_quality.probe_interval_sec` (default 30), `reflector_quality.recovery_count` (default 3)
- New **top-level `reflector_quality` section** in health response (peer to `signal_quality` and `irtt`)
- **Per-host detail**: each reflector gets an entry with score, status (active/deprioritized), and measurement count
- Section is **always present** regardless of reflector count (matches signal_quality always-present pattern)
- Includes `available: true` and standard availability pattern from v1.18
- **Event-based** SQLite writes: one row per deprioritization or recovery event (not per-cycle)

### Claude's Discretion
- Exact deque size for rolling window (50 suggested, Claude can adjust based on measurement frequency analysis)
- Internal class/module structure for ReflectorScorer or similar
- How probe timer integrates with the 50ms cycle loop (monotonic clock check vs separate timer)
- Whether to add a `reflector_quality` YAML section or extend `continuous_monitoring`

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REFL-01 | Each ping_host reflector has a rolling quality score based on success rate | ReflectorScorer class with per-host deque tracking success/failure, score = sum(deque) / len(deque) |
| REFL-02 | Low-scoring reflectors are deprioritized (skipped) when score falls below configurable threshold | `get_active_hosts()` method filters by min_score threshold, graceful degradation logic for median-of-three |
| REFL-03 | Deprioritized reflectors are periodically re-checked for recovery | Monotonic clock probe timer in run_cycle(), consecutive success counter, recovery via sustained probes |
| REFL-04 | Reflector quality scores are visible in health endpoint | New `reflector_quality` section in health response, per-host detail with score/status/measurements |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| collections.deque | stdlib | Per-host rolling window of success/failure booleans | Already used by SignalProcessor for Hampel window; maxlen gives automatic eviction |
| dataclasses (frozen) | stdlib | ReflectorStatus snapshot for health endpoint | Matches SignalResult pattern -- frozen for thread safety, slots for memory |
| time.monotonic | stdlib | Probe interval timer | Standard in codebase for all timing (IRTT staleness, alerting cooldowns) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | stdlib | WARNING for deprioritization, INFO for recovery | Follows established alert log patterns |
| json | stdlib | Serialize event details for SQLite persistence | Matches AlertEngine._persist_alert pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate YAML section | Extend continuous_monitoring | Separate `reflector_quality:` section is cleaner, follows irtt/alerting pattern of top-level feature config |
| EWMA score | Raw ratio | User locked raw ratio; EWMA would add smoothing but user wants direct interpretability |

**Installation:**
```bash
# No new dependencies -- 100% Python stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  reflector_scorer.py      # NEW: ReflectorScorer class + ReflectorStatus dataclass
  autorate_continuous.py   # MODIFY: config loading, WANController init, measure_rtt, run_cycle, health
  health_check.py          # MODIFY: add reflector_quality section to health response
  storage/schema.py        # MODIFY: add reflector_events table schema
```

### Pattern 1: ReflectorScorer Class
**What:** Standalone module with per-host state tracking, active host filtering, and probe scheduling.
**When to use:** Instantiated once per WANController in `__init__()`, called every cycle.
**Example:**
```python
# Source: Modeled on SignalProcessor pattern from signal_processing.py
from collections import deque
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ReflectorStatus:
    """Per-reflector quality snapshot for health endpoint."""
    host: str
    score: float          # 0.0-1.0 success rate
    status: str           # "active" or "deprioritized"
    measurements: int     # total measurements in window (may be < window_size during warmup)
    consecutive_successes: int  # for recovery tracking

class ReflectorScorer:
    """Per-WAN reflector quality tracking and deprioritization."""

    def __init__(
        self,
        hosts: list[str],
        min_score: float = 0.8,
        window_size: int = 50,
        probe_interval_sec: float = 30.0,
        recovery_count: int = 3,
        logger: logging.Logger = ...,
        wan_name: str = "",
    ) -> None:
        # Per-host state
        self._windows: dict[str, deque[bool]] = {
            h: deque(maxlen=window_size) for h in hosts
        }
        self._consecutive_successes: dict[str, int] = {h: 0 for h in hosts}
        self._deprioritized: set[str] = set()
        self._last_probe_time: dict[str, float] = {}
        # Config
        self._min_score = min_score
        self._probe_interval_sec = probe_interval_sec
        self._recovery_count = recovery_count
```

### Pattern 2: measure_rtt Integration
**What:** measure_rtt() calls through ReflectorScorer to get active hosts, then reports results back.
**When to use:** Every measurement cycle.
**Key insight:** Current `ping_hosts_concurrent()` returns `list[float]` without host attribution. Must change approach for per-host tracking.

**Critical finding:** `ping_hosts_concurrent()` drops host identity -- it returns a flat list of RTT floats. For reflector scoring, we need to know which host succeeded and which failed. Two approaches:

1. **Add a new method** `ping_hosts_concurrent_with_attribution()` that returns `dict[str, float | None]` (host -> RTT or None on failure). This is the cleanest approach.
2. **Ping hosts individually** within the scorer, sequentially or with manual ThreadPoolExecutor. This would duplicate the concurrency logic.

**Recommendation:** Add `ping_hosts_with_results()` to RTTMeasurement that returns `dict[str, float | None]`. This gives ReflectorScorer the per-host success/failure data it needs without duplicating concurrency code. The existing `ping_hosts_concurrent()` remains unchanged for backward compatibility.

```python
# In rtt_measurement.py
def ping_hosts_with_results(
    self, hosts: list[str], count: int = 1, timeout: float = 3.0
) -> dict[str, float | None]:
    """Ping multiple hosts concurrently, return per-host results.

    Returns:
        Dict mapping host -> RTT in ms (or None if ping failed).
    """
    if not hosts:
        return {}
    results: dict[str, float | None] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(hosts)) as executor:
        future_to_host = {executor.submit(self.ping_host, host, count): host for host in hosts}
        try:
            for future in concurrent.futures.as_completed(future_to_host, timeout=timeout):
                host = future_to_host[future]
                try:
                    results[host] = future.result()
                except Exception:
                    results[host] = None
        except concurrent.futures.TimeoutError:
            # Mark remaining hosts as failed
            for future, host in future_to_host.items():
                if host not in results:
                    results[host] = None
    return results
```

### Pattern 3: Probe Timer in run_cycle
**What:** Check monotonic clock in run_cycle() to determine if deprioritized reflectors need probing.
**When to use:** Every cycle, but probe fires only when interval elapsed (typically every 30s = 600 cycles at 50ms).
**Key insight:** At 50ms cycles, 30-second probe interval = 600 cycles between probes. The monotonic clock comparison is negligible overhead (~0.05us). This is identical to how IRTT staleness is checked in run_cycle().

```python
# In WANController.run_cycle(), after measure_rtt():
now = time.monotonic()
probed = self._reflector_scorer.maybe_probe(now, self.rtt_measurement)
# probed is list of (host, success) for any probes that ran
```

### Pattern 4: Graceful Degradation for Median-of-Three
**What:** Adapt RTT aggregation strategy based on how many healthy reflectors remain.
**When to use:** In the modified measure_rtt() method.

```python
active = self._reflector_scorer.get_active_hosts()
n = len(active)
if n >= 3:
    # Standard median-of-three
    results = self.rtt_measurement.ping_hosts_with_results(active[:3])
    # ... record success/failure per host ...
    rtts = [v for v in results.values() if v is not None]
    return statistics.median(rtts) if len(rtts) >= 2 else (rtts[0] if rtts else None)
elif n == 2:
    # Average of two
    results = self.rtt_measurement.ping_hosts_with_results(active[:2])
    rtts = [v for v in results.values() if v is not None]
    return statistics.mean(rtts) if rtts else None
elif n == 1:
    return self.rtt_measurement.ping_host(active[0], count=1)
else:
    # All deprioritized -- force best-scoring
    best = self._reflector_scorer.get_best_host()
    self.logger.warning(f"{self.wan_name}: All reflectors deprioritized, forcing {best}")
    return self.rtt_measurement.ping_host(best, count=1)
```

### Anti-Patterns to Avoid
- **Modifying `ping_hosts_concurrent()` return type:** Would break existing consumers. Add new method instead.
- **Storing ReflectorScorer state in the state file:** Reflector quality is transient (resets on restart is fine). State file is for rate/baseline persistence.
- **Probing inside measure_rtt():** Probes should run at their own cadence, not tied to measurement cycle. Keep probe logic in run_cycle() with its own timing.
- **Per-cycle SQLite writes:** Only write on deprioritization/recovery transitions. At 20Hz, per-cycle writes would be 72K rows/hour.
- **Locking for ReflectorScorer state:** All access is single-threaded within run_cycle(). No lock needed (same as SignalProcessor).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rolling window | Custom circular buffer | `collections.deque(maxlen=N)` | Automatic eviction, O(1) append, stdlib |
| Concurrent pings | Manual threading | Extend RTTMeasurement with attributed results | Reuses existing ThreadPoolExecutor pattern |
| SQLite event persistence | Raw SQL in scorer | MetricsWriter + AlertEngine pattern (INSERT into reflector_events) | Consistent error handling, never crashes daemon |
| Config validation | Manual type checks | Follow `_load_irtt_config()` pattern exactly | Warn+default, never crash |

**Key insight:** Every component of this feature has a direct analog in the existing codebase. The novel part is the measure_rtt() integration and the graceful degradation logic.

## Common Pitfalls

### Pitfall 1: ping_hosts_concurrent Drops Host Identity
**What goes wrong:** The existing method returns `list[float]` -- you cannot tell which host produced which RTT, or which hosts failed.
**Why it happens:** Original design only needed aggregate RTT, not per-host tracking.
**How to avoid:** Add `ping_hosts_with_results()` that returns `dict[str, float | None]`. Use this in the modified measure_rtt() when reflector scoring is active.
**Warning signs:** Tests pass but reflector scores never change (because success/failure not being recorded).

### Pitfall 2: MagicMock Truthy Trap for ReflectorScorer
**What goes wrong:** In tests with MagicMock config, `if self._reflector_scorer:` would be True for MagicMock, causing AttributeError.
**Why it happens:** MagicMock is always truthy. Known trap documented in MEMORY.md.
**How to avoid:** Use explicit `None` initialization and `isinstance()` guard, or always instantiate ReflectorScorer (since it's always active per CONTEXT.md).
**Warning signs:** Test failures with AttributeError on MagicMock.

### Pitfall 3: Window Size vs Measurement Frequency
**What goes wrong:** Window of 50 at 20Hz = 2.5 seconds of history. Too short for meaningful quality assessment.
**Why it happens:** 50ms cycle interval means reflector measurements are very frequent.
**How to avoid:** Window size of 50 is per-reflector, and with median-of-three, each reflector is pinged once per cycle. At 20Hz, 50 measurements = 2.5 seconds. This is actually reasonable because: (a) reflector failures tend to come in bursts (ISP route change, server maintenance), and (b) a 2.5s window with 0.8 threshold means 10+ failures in 2.5s triggers deprioritization, which is appropriate for detecting genuine issues. However, the planner should consider **100** for a 5-second window if operators want more stability.
**Recommendation:** Use 50 (as suggested) -- it captures burst failures while being responsive. The 0.8 threshold (40 of 50 successful) provides good noise margin.

### Pitfall 4: Probe Pings Adding to Cycle Time
**What goes wrong:** Probe pings to deprioritized reflectors add 1-2 seconds to cycle time, causing overruns.
**Why it happens:** `ping_host()` with timeout_ping=1 can block for up to 1 second on failure.
**How to avoid:** Run probes in a separate thread or only probe one host per cycle. Since probes happen every 30 seconds and there are at most 2-3 deprioritized hosts, a simple approach: probe one host per cycle when the probe timer fires, cycling through deprioritized hosts round-robin.
**Warning signs:** cycle_time_ms p95 spikes when reflectors are deprioritized.

### Pitfall 5: Score During Warmup Period
**What goes wrong:** With a fresh deque, 1 failure out of 2 measurements gives score 0.5, immediately deprioritizing.
**Why it happens:** Small sample size amplifies individual failures.
**How to avoid:** During warmup (measurements < window_size), either: (a) require minimum measurements before deprioritization (e.g., min 10 samples), or (b) treat score as 1.0 until warmup complete. Option (a) is safer and more explicit.
**Warning signs:** Reflectors getting deprioritized immediately after daemon restart.

### Pitfall 6: All Reflectors Deprioritized on Daemon Start
**What goes wrong:** If the network is briefly down at daemon startup, all reflectors quickly accumulate failures.
**Why it happens:** Empty deques fill with failures during the outage.
**How to avoid:** The "force best-scoring" fallback handles this. Additionally, the warmup minimum prevents premature deprioritization. Combined, these ensure the daemon always has measurement targets.

## Code Examples

### Config Loading Pattern
```python
# Source: Follows _load_irtt_config() pattern in autorate_continuous.py L711-790
def _load_reflector_quality_config(self) -> None:
    """Load reflector quality configuration."""
    logger = logging.getLogger(__name__)
    rq = self.data.get("reflector_quality", {})

    if not isinstance(rq, dict):
        logger.warning(
            f"reflector_quality config must be dict, got {type(rq).__name__}; "
            "using defaults"
        )
        rq = {}

    min_score = rq.get("min_score", 0.8)
    if not isinstance(min_score, (int, float)) or isinstance(min_score, bool):
        logger.warning(f"reflector_quality.min_score must be number, got {min_score!r}; defaulting to 0.8")
        min_score = 0.8
    min_score = max(0.0, min(1.0, float(min_score)))

    window_size = rq.get("window_size", 50)
    if not isinstance(window_size, int) or isinstance(window_size, bool) or window_size < 10:
        logger.warning(f"reflector_quality.window_size must be int >= 10, got {window_size!r}; defaulting to 50")
        window_size = 50

    probe_interval_sec = rq.get("probe_interval_sec", 30)
    if not isinstance(probe_interval_sec, (int, float)) or isinstance(probe_interval_sec, bool) or probe_interval_sec < 1:
        logger.warning(f"reflector_quality.probe_interval_sec must be number >= 1, got {probe_interval_sec!r}; defaulting to 30")
        probe_interval_sec = 30

    recovery_count = rq.get("recovery_count", 3)
    if not isinstance(recovery_count, int) or isinstance(recovery_count, bool) or recovery_count < 1:
        logger.warning(f"reflector_quality.recovery_count must be int >= 1, got {recovery_count!r}; defaulting to 3")
        recovery_count = 3

    self.reflector_quality_config = {
        "min_score": float(min_score),
        "window_size": window_size,
        "probe_interval_sec": float(probe_interval_sec),
        "recovery_count": recovery_count,
    }
```

### SQLite Event Persistence Pattern
```python
# Source: Follows AlertEngine._persist_alert() pattern in alert_engine.py L165-201
def _persist_reflector_event(
    self,
    event_type: str,  # "deprioritized" or "recovered"
    host: str,
    score: float,
    wan_name: str,
    writer: MetricsWriter | None,
) -> None:
    """Persist reflector quality transition to SQLite. Never raises."""
    if writer is None:
        return
    try:
        timestamp = int(time.time())
        details = json.dumps({"host": host, "score": round(score, 3), "event": event_type})
        writer.connection.execute(
            "INSERT INTO reflector_events (timestamp, event_type, host, wan_name, score, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, event_type, host, wan_name, round(score, 3), details),
        )
    except Exception:
        self._logger.warning(
            "Failed to persist reflector event %s for %s", event_type, host, exc_info=True
        )
```

### Health Endpoint Section Pattern
```python
# Source: Follows signal_quality/irtt pattern in health_check.py L192-241
# In _get_health_status(), after IRTT section:
scorer = wan_controller._reflector_scorer
if scorer is not None:
    statuses = scorer.get_all_statuses()
    wan_health["reflector_quality"] = {
        "available": True,
        "hosts": {
            s.host: {
                "score": round(s.score, 3),
                "status": s.status,
                "measurements": s.measurements,
            }
            for s in statuses
        },
    }
else:
    wan_health["reflector_quality"] = {
        "available": True,
        "hosts": {},
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All reflectors always used | Reflectors filtered by quality score | Phase 93 | Bad reflectors auto-excluded, better RTT signal quality |
| ping_hosts_concurrent returns flat list | New attributed method returns dict[host, rtt] | Phase 93 | Per-host success/failure tracking becomes possible |
| No reflector health visibility | Per-reflector scores in health endpoint | Phase 93 | Operators can see which reflectors are performing well |

**Deprecated/outdated:**
- None; this is greenfield functionality within the existing measurement infrastructure.

## Open Questions

1. **Deque window size: 50 vs 100**
   - What we know: At 20Hz with 3 reflectors, each reflector gets ~20 pings/second (one per cycle). Window of 50 = ~2.5s history. Window of 100 = ~5s history.
   - What's unclear: Whether 2.5s is sufficient for production noise tolerance.
   - Recommendation: Start with 50 (user suggested). It catches burst failures while being responsive. Can be tuned via YAML without code changes.

2. **Separate YAML section vs extend continuous_monitoring**
   - What we know: irtt, alerting, signal_processing all use top-level YAML sections. continuous_monitoring already has ping_hosts.
   - What's unclear: Whether operators prefer reflector_quality as a sub-key of continuous_monitoring or standalone.
   - Recommendation: **Top-level `reflector_quality:` section** -- matches irtt/alerting/signal_processing pattern. Reflector quality is a distinct feature with its own enable/disable semantics (it could be disabled while ping_hosts remain configured).

3. **Probe execution within cycle budget**
   - What we know: Probes are ICMP pings with 1s timeout. At 50ms cycles, a blocking probe would cause massive overrun.
   - What's unclear: Whether to use the existing RTTMeasurement.ping_host() synchronously (accepting rare overruns every 30s) or run probes asynchronously.
   - Recommendation: Run probes via the same concurrent pinging infrastructure used for measurement, but only when the probe timer fires. One probe per deprioritized host, concurrent with the main measurement. This adds at most the timeout of a single ping (~1s worst case) but only every 30 seconds. If overrun is unacceptable, probes can be moved to a separate thread.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` (pytest section) |
| Quick run command | `.venv/bin/pytest tests/test_reflector_scorer.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REFL-01 | Rolling quality score per reflector | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestReflectorScoring -x` | No - Wave 0 |
| REFL-01 | Score calculation (success_count / window_size) | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestScoreCalculation -x` | No - Wave 0 |
| REFL-01 | Window warmup behavior (min measurements) | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestWarmup -x` | No - Wave 0 |
| REFL-02 | Deprioritization below threshold | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestDeprioritization -x` | No - Wave 0 |
| REFL-02 | Graceful degradation (3->2->1->0 healthy) | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestGracefulDegradation -x` | No - Wave 0 |
| REFL-02 | Force best-scoring when all deprioritized | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestForceBestScoring -x` | No - Wave 0 |
| REFL-03 | Periodic probe scheduling | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestProbeScheduling -x` | No - Wave 0 |
| REFL-03 | Recovery after N consecutive successes | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestRecovery -x` | No - Wave 0 |
| REFL-04 | Health endpoint reflector_quality section | unit | `.venv/bin/pytest tests/test_health_check.py::TestReflectorQualityHealth -x` | No - Wave 0 |
| REFL-04 | SQLite event persistence | unit | `.venv/bin/pytest tests/test_reflector_scorer.py::TestEventPersistence -x` | No - Wave 0 |
| REFL-01-04 | Config loading and validation | unit | `.venv/bin/pytest tests/test_reflector_quality_config.py -x` | No - Wave 0 |
| REFL-02 | measure_rtt integration with scorer | unit | `.venv/bin/pytest tests/test_autorate_continuous.py::TestMeasureRTTReflectorScoring -x` | No - Wave 0 |
| REFL-01 | ping_hosts_with_results attributed method | unit | `.venv/bin/pytest tests/test_rtt_measurement.py::TestPingHostsWithResults -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_reflector_scorer.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_reflector_scorer.py` -- covers REFL-01, REFL-02, REFL-03, REFL-04 (scorer class tests)
- [ ] `tests/test_reflector_quality_config.py` -- covers config loading, validation, warn+default
- [ ] New test classes in `tests/test_health_check.py` -- covers REFL-04 (health endpoint)
- [ ] New test class in `tests/test_rtt_measurement.py` -- covers ping_hosts_with_results
- [ ] New test class in `tests/test_autorate_continuous.py` -- covers measure_rtt integration

## Sources

### Primary (HIGH confidence)
- `src/wanctl/rtt_measurement.py` -- RTTMeasurement class, ping_host(), ping_hosts_concurrent() signatures and return types
- `src/wanctl/signal_processing.py` -- SignalProcessor pattern: deque, frozen dataclass, per-WAN instantiation
- `src/wanctl/alert_engine.py` -- AlertEngine SQLite event persistence pattern
- `src/wanctl/health_check.py` -- Health endpoint structure, signal_quality/irtt section patterns
- `src/wanctl/autorate_continuous.py` -- WANController.__init__(), measure_rtt(), run_cycle(), config loading patterns
- `src/wanctl/storage/schema.py` -- Table creation pattern (CREATE TABLE IF NOT EXISTS)
- `tests/conftest.py` -- mock_autorate_config fixture pattern for new attributes

### Secondary (MEDIUM confidence)
- `.planning/phases/93-reflector-quality-scoring/93-CONTEXT.md` -- All locked decisions and integration points

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - 100% stdlib, patterns directly copied from existing modules
- Architecture: HIGH - Every integration point has been read and understood; measure_rtt modification path is clear
- Pitfalls: HIGH - The ping_hosts_concurrent host identity loss is verified by reading the source; MagicMock trap is documented in project memory
- Config loading: HIGH - Five prior config loaders (_load_irtt_config, _load_signal_processing_config, _load_alerting_config) provide exact templates

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain, no external dependencies)
