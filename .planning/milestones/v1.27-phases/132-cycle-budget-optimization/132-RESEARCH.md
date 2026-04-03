# Phase 132: Cycle Budget Optimization - Research

**Researched:** 2026-04-03
**Domain:** Python threading, non-blocking I/O architecture, performance profiling
**Confidence:** HIGH

## Summary

Phase 131 profiling conclusively identified RTT measurement as the overwhelming bottleneck: 84.6% of cycle budget (42.3ms avg) under RRUL load, with ThreadPoolExecutor scheduling overhead at 16.4% of CPU. The architectural fix is to decouple RTT measurement from the control loop entirely, using a dedicated background thread with a shared atomic variable pattern -- identical to the existing `IRTTThread` pattern already proven in this codebase.

The control loop currently blocks on 3 concurrent ICMP pings via a per-call `ThreadPoolExecutor` that is created and destroyed every 50ms cycle. The background thread approach eliminates both the blocking I/O (42ms) and the thread pool churn (16.4% CPU). Post-optimization, the `rtt_measurement` subsystem should drop from 42ms to <1ms (a shared variable read). Combined with existing subsystem costs (~9ms total for everything else), total cycle time should drop to ~10ms, yielding ~20% utilization on a 50ms budget.

**Primary recommendation:** Follow `IRTTThread` pattern exactly -- frozen dataclass with GIL-protected pointer swap, daemon thread with `shutdown_event.wait()` cadence, persistent `ThreadPoolExecutor(max_workers=3)` inside the background thread. Add health endpoint `status` field and `cycle_budget_warning` alert type using existing `AlertEngine` infrastructure.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Decouple RTT measurement from the control loop entirely. A dedicated background thread runs ICMP pings continuously; the control loop reads the latest RTT from a thread-safe shared variable each cycle.
- **D-02:** The background measurement thread keeps the existing 3-host concurrent ping pattern (median-of-3). Measurement quality stays high since it's no longer blocking the control loop.
- **D-03:** RTT delivery uses a shared atomic variable pattern (thread-safe shared value via threading primitives). Fits existing signal_utils.py conventions. No queue-based handoff.
- **D-04:** Staleness timeout with fallback: if RTT data is older than ~500ms (10 cycles), log a warning and use last-known-good RTT. If stale beyond a hard limit (~5s), treat as measurement failure (same as all-pings-failed today).
- **D-05:** The background measurement thread uses a persistent ThreadPoolExecutor (max_workers=3), created once at startup and reused across all measurement cycles. Eliminates per-cycle thread creation/teardown overhead.
- **D-06:** Health endpoint adds a configurable `warning_threshold_pct` (default 80%) to YAML under `continuous_monitoring`. Health response adds a `status` field to `cycle_budget`: `ok` / `warning` / `critical`. Matches existing health endpoint patterns.
- **D-07:** AlertEngine fires a new `cycle_budget_warning` alert type when utilization exceeds threshold for N consecutive checks. Reuses existing Discord webhook + rate limiting infrastructure. SIGUSR1 hot-reloadable.
- **D-08:** Target: under 50ms avg cycle time, under 80% utilization (<40ms on 50ms cycle). Post-optimization, control loop should drop to well under 10ms avg.
- **D-09:** Interval fallback decision deferred to post-measurement. If optimization doesn't achieve <80% utilization, decision on adjustments will be made based on actual data.

### Claude's Discretion
- Background thread sleep interval between measurement cycles
- Exact threading primitives for shared RTT value (Lock vs Event vs dataclass with timestamp)
- AlertEngine consecutive-check threshold for cycle_budget_warning
- Whether to also optimize secondary consumers (logging_metrics 3.3ms, router_communication 3.4ms) if headroom allows

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-02 | Controller maintains cycle budget within target interval under sustained RRUL load | Background RTT thread architecture (D-01 through D-05) eliminates 42ms blocking I/O from hot path; persistent ThreadPoolExecutor removes 16.4% CPU overhead; target <10ms avg cycle time |
| PERF-03 | Health endpoint exposes cycle budget regression indicator that warns when utilization exceeds configurable threshold | `_build_cycle_budget()` extension with `status` field (D-06); `cycle_budget_warning` alert type via existing AlertEngine (D-07); SIGUSR1 hot-reload via existing `_reload_*_config()` pattern |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| icmplib | 3.0.4 | ICMP ping (CAP_NET_RAW) | Already in use, unchanged |
| threading | stdlib | Background thread, Event, daemon threads | Python stdlib, matches IRTTThread pattern |
| concurrent.futures | stdlib | ThreadPoolExecutor for parallel pings | Already in use, now persistent instead of per-call |
| dataclasses | stdlib | Frozen dataclass for atomic shared result | Matches IRTTResult pattern in irtt_thread.py |
| time | stdlib | perf_counter (timing), monotonic (staleness) | Already used throughout |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | existing | Unit tests for background thread, health endpoint | All test files |
| unittest.mock | stdlib | Mock ICMP pings, threading.Event | Test isolation |

No new dependencies required. All work uses existing stdlib and project libraries.

## Architecture Patterns

### Recommended Project Structure (changes only)
```
src/wanctl/
  rtt_measurement.py     # Add BackgroundRTTThread class (follows IRTTThread pattern)
  health_check.py        # Extend _build_cycle_budget() with status field
  autorate_continuous.py  # WANController.measure_rtt() reads shared variable instead of blocking
  alert_engine.py        # No changes needed (register new type via config)
tests/
  test_rtt_measurement.py  # Add BackgroundRTTThread tests
  test_health_check.py     # Add cycle_budget status tests
```

### Pattern 1: Background RTT Thread (follows IRTTThread exactly)

**What:** A dedicated daemon thread that continuously measures RTT via ICMP and caches the result in a GIL-protected frozen dataclass pointer swap.

**When to use:** Any measurement that blocks on network I/O and should not block the control loop.

**Existing precedent:**
```python
# Source: src/wanctl/irtt_thread.py (lines 18-79)
class IRTTThread:
    def __init__(self, measurement, cadence_sec, shutdown_event, logger):
        self._cached_result: IRTTResult | None = None  # GIL-protected atomic swap
        ...

    def get_latest(self) -> IRTTResult | None:
        return self._cached_result  # Lock-free read

    def _run(self) -> None:
        while not self._shutdown_event.is_set():
            result = self._measurement.measure()
            if result is not None:
                self._cached_result = result  # Atomic pointer swap under GIL
            self._shutdown_event.wait(timeout=self._cadence_sec)
```

**New BackgroundRTTThread pattern:**
```python
@dataclasses.dataclass(frozen=True)
class RTTSnapshot:
    """Immutable RTT measurement result for GIL-protected atomic swap."""
    rtt_ms: float                          # Aggregated RTT (median-of-3)
    per_host_results: dict[str, float | None]  # For ReflectorScorer
    timestamp: float                       # time.monotonic() when measured
    measurement_ms: float                  # How long measurement took

class BackgroundRTTThread:
    def __init__(
        self,
        rtt_measurement: RTTMeasurement,
        reflector_scorer: ReflectorScorer,
        hosts_fn: Callable[[], list[str]],  # Deferred host resolution
        shutdown_event: threading.Event,
        logger: logging.Logger,
        pool: concurrent.futures.ThreadPoolExecutor,  # Persistent, shared
    ):
        self._cached: RTTSnapshot | None = None
        ...

    def get_latest(self) -> RTTSnapshot | None:
        return self._cached  # Lock-free read -- same as IRTTThread

    def _run(self) -> None:
        while not self._shutdown_event.is_set():
            hosts = self._hosts_fn()
            t0 = time.perf_counter()
            results = self._ping_with_persistent_pool(hosts)
            elapsed = (time.perf_counter() - t0) * 1000.0
            # ... aggregate RTT, build snapshot ...
            self._cached = RTTSnapshot(rtt_ms=rtt, per_host_results=results,
                                       timestamp=time.monotonic(),
                                       measurement_ms=elapsed)
            self._shutdown_event.wait(timeout=self._cadence_sec)
```

### Pattern 2: Persistent ThreadPoolExecutor

**What:** Create the ThreadPoolExecutor once at startup, reuse for every measurement cycle, shutdown on daemon stop.

**Why:** Benchmarked locally: persistent pool is 4x faster than per-call creation (24ms vs 98ms for 100 rounds of 3 tasks). The py-spy flamegraph showed 16.4% CPU in `concurrent.futures.thread._worker` due to per-cycle pool create/teardown.

**Implementation:**
```python
# Created once in main() or WANController.__init__
self._rtt_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=3,
    thread_name_prefix="wanctl-rtt-ping",
)

# Used inside BackgroundRTTThread._run() for each measurement cycle
def _ping_with_persistent_pool(self, hosts):
    future_to_host = {
        self._pool.submit(self._rtt_measurement.ping_host, host, 1): host
        for host in hosts
    }
    results = {}
    for future in concurrent.futures.as_completed(future_to_host, timeout=3.0):
        host = future_to_host[future]
        try:
            results[host] = future.result()
        except Exception:
            results[host] = None
    return results

# Shutdown in finally block (after IRTT thread stop, before connection cleanup)
self._rtt_pool.shutdown(wait=True, cancel_futures=True)
```

### Pattern 3: Staleness Detection (D-04)

**What:** The control loop checks RTT age before using it. Two thresholds: warning (~500ms/10 cycles) and hard failure (~5s/100 cycles).

**Implementation:**
```python
def measure_rtt(self) -> float | None:
    snapshot = self._rtt_thread.get_latest()
    if snapshot is None:
        self.logger.warning(f"{self.wan_name}: No RTT data available")
        return None

    age = time.monotonic() - snapshot.timestamp
    if age > 5.0:  # Hard limit -- treat as measurement failure
        self.logger.warning(f"{self.wan_name}: RTT data stale ({age:.1f}s), treating as failure")
        return None
    if age > 0.5:  # Soft warning -- data is still usable
        self.logger.debug(f"{self.wan_name}: RTT data aging ({age:.1f}s)")

    # Record per-host results to ReflectorScorer (same as today)
    for host, rtt_val in snapshot.per_host_results.items():
        self._reflector_scorer.record_result(host, rtt_val is not None)
    self._persist_reflector_events()

    return snapshot.rtt_ms
```

### Pattern 4: Health Endpoint Status Field (D-06)

**What:** Extend `_build_cycle_budget()` to include a `status` field computed from rolling utilization vs configurable threshold.

**Implementation:**
```python
def _build_cycle_budget(profiler, overrun_count, cycle_interval_ms, total_label,
                        *, warning_threshold_pct=80.0):
    # ... existing code ...
    utilization = (stats["avg_ms"] / cycle_interval_ms) * 100

    if utilization >= 100.0:
        status = "critical"
    elif utilization >= warning_threshold_pct:
        status = "warning"
    else:
        status = "ok"

    result["status"] = status
    result["warning_threshold_pct"] = warning_threshold_pct
    return result
```

### Pattern 5: AlertEngine cycle_budget_warning (D-07)

**What:** Register `cycle_budget_warning` as a new alert type. Fire when utilization exceeds threshold for N consecutive health checks.

**Implementation approach:** Add a counter on WANController that tracks consecutive cycles where utilization exceeds the warning threshold. When the counter reaches a configurable limit (recommend 60 = 3 seconds at 50ms), fire the alert. Reset counter when utilization drops below threshold.

```python
# In WANController._record_profiling() or a new _check_cycle_budget_alert():
utilization = (total_ms / self._cycle_interval_ms) * 100
if utilization >= self._warning_threshold_pct:
    self._budget_warning_streak += 1
    if self._budget_warning_streak >= self._budget_warning_consecutive:
        self.alert_engine.fire(
            alert_type="cycle_budget_warning",
            severity="warning",
            wan_name=self.wan_name,
            details={
                "utilization_pct": round(utilization, 1),
                "threshold_pct": self._warning_threshold_pct,
                "cycle_time_ms": round(total_ms, 1),
                "interval_ms": self._cycle_interval_ms,
            },
        )
else:
    self._budget_warning_streak = 0
```

### Anti-Patterns to Avoid
- **Creating ThreadPoolExecutor per cycle:** The current pattern. 16.4% CPU overhead from thread create/teardown every 50ms. Always use persistent pool.
- **Using threading.Lock for the shared RTT value:** Unnecessary. Python GIL already protects single-attribute assignment of immutable objects. The frozen dataclass pointer swap is atomic. A Lock would add latency and contention risk. IRTTThread has proven this pattern over months of production use.
- **Queue-based handoff between threads:** Adds complexity (queue full/empty handling, backpressure). The control loop needs only the latest value, not a history. Shared variable with staleness check is simpler and faster.
- **Changing the measurement cadence to match the cycle interval:** The background thread should measure as fast as ICMP allows (30-50ms per round), not artificially slow to 50ms. Faster measurement means fresher data.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe shared value | Custom Lock/RLock wrapper | Frozen dataclass + GIL pointer swap | IRTTThread proves this works; Lock adds unnecessary latency |
| Background daemon thread | Custom thread management | Follow IRTTThread pattern (shutdown_event.wait) | Battle-tested in production since v1.18 |
| Alert rate limiting | Custom cooldown tracking | AlertEngine with per-rule cooldown_sec | Already handles Discord webhook + SQLite persistence |
| Config hot-reload | Custom file watcher | SIGUSR1 + existing _reload_*_config() pattern | Proven, generalized, all reload goes through same path |
| Cycle overrun detection | Custom threshold logic | Extend existing _record_profiling() | Already has overrun counter, rate-limited warnings |

**Key insight:** This phase's primary innovation is architectural (decouple measurement from control). All implementation primitives already exist in the codebase -- `IRTTThread` for the background thread pattern, `AlertEngine` for alerting, `_build_cycle_budget()` for health reporting, SIGUSR1 for config reload. The work is connecting existing patterns, not inventing new ones.

## Common Pitfalls

### Pitfall 1: ReflectorScorer Starvation
**What goes wrong:** Background thread records per-host results to ReflectorScorer, but if the control loop also calls `record_result()` or `drain_events()` concurrently, the scorer's internal state could become inconsistent.
**Why it happens:** ReflectorScorer was designed for single-threaded access in the control loop.
**How to avoid:** Keep ReflectorScorer interaction in the control loop only. The background thread populates `per_host_results` in the snapshot; the control loop reads the snapshot and calls `record_result()` synchronously (same as today, just with data from the snapshot instead of from blocking pings).
**Warning signs:** Reflector deprioritization events happening too frequently or not at all.

### Pitfall 2: Stale RTT During Startup
**What goes wrong:** Control loop starts before background thread has completed its first measurement. `get_latest()` returns None, causing the first several cycles to return None from `measure_rtt()`.
**Why it happens:** Thread scheduling -- the background thread may not get CPU time before the first control cycle.
**How to avoid:** Either (a) do one synchronous measurement at startup before entering the main loop, or (b) accept that the first few cycles may get None and let existing ICMP failure handling manage it (the controller already handles `measure_rtt() -> None` gracefully via `handle_icmp_failure()`).
**Warning signs:** Logs showing "All pings failed" on first 1-3 cycles after startup.

### Pitfall 3: ThreadPoolExecutor Leak on Crash
**What goes wrong:** If the daemon crashes without reaching the `finally` block, the persistent ThreadPoolExecutor threads remain as zombies.
**Why it happens:** Persistent pool is not automatically cleaned up like a context-manager pool.
**How to avoid:** (a) Create pool threads as daemon threads (ThreadPoolExecutor default since Python 3.9). (b) Register pool.shutdown in `atexit` alongside existing `emergency_lock_cleanup`. (c) Add pool shutdown to the `finally` cleanup chain between IRTT stop and connection cleanup.
**Warning signs:** Orphaned threads visible in `ps aux | grep wanctl-rtt-ping`.

### Pitfall 4: Background Thread Cadence vs Measurement Time
**What goes wrong:** If ICMP pings take 50ms under load, and the cadence sleep is also 50ms, actual measurement cadence is 100ms (measurement time + sleep time).
**Why it happens:** `shutdown_event.wait(timeout=cadence)` waits AFTER measurement completes, not from measurement START.
**How to avoid:** Calculate remaining sleep time: `sleep_time = max(0, cadence - measurement_time)`. This ensures measurements happen at the target cadence regardless of measurement duration.
**Warning signs:** RTT data staleness warnings despite the thread running normally.

### Pitfall 5: Alert Storm on Optimization Failure
**What goes wrong:** If optimization doesn't achieve <80% utilization, `cycle_budget_warning` fires every N cycles forever.
**Why it happens:** Cooldown window expires, alert fires again. Repeat.
**How to avoid:** Use AlertEngine's built-in per-rule cooldown_sec (set to 600s or higher for this alert type). The first alert tells the operator; subsequent alerts are suppressed. Also, the "critical" status in the health endpoint provides continuous visibility without alert fatigue.
**Warning signs:** Discord webhook rate limiting kicking in, or operator disabling alerting entirely.

## Code Examples

### Existing IRTTThread (the pattern to follow)
```python
# Source: src/wanctl/irtt_thread.py (complete file, 79 lines)
# Key points:
# - frozen dataclass for lock-free reads (IRTTResult)
# - daemon=True thread
# - shutdown_event.wait(timeout=cadence) for sleep
# - .start() / .stop() lifecycle
# - .get_latest() returns cached result or None
```

### Existing _build_cycle_budget (where status field goes)
```python
# Source: src/wanctl/health_check.py:70-127
# Key points:
# - isinstance(stats, dict) guard for MagicMock safety
# - Per-subsystem breakdown with short_name = label.replace("autorate_", "")
# - Returns None when profiler has no data (cold start)
# Add: status field, warning_threshold_pct field
```

### Existing SIGUSR1 Reload Chain (where threshold reload goes)
```python
# Source: src/wanctl/autorate_continuous.py:4729-4754
# Key points:
# - Pattern: reload requested -> reload all config sections -> reset_reload_state()
# - Each _reload_*_config() re-reads fresh YAML via safe_load
# - New: _reload_cycle_budget_config() reads warning_threshold_pct from YAML
```

### Existing Cleanup Chain (where pool shutdown goes)
```python
# Source: src/wanctl/autorate_continuous.py:4766-4825
# Priority: state > locks > connections > servers > metrics
# IRTT thread stopped at step 0.5
# New: RTT thread stop at step 0.6, pool shutdown at step 0.7
# Each step wrapped in try/except + check_cleanup_deadline()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-call ThreadPoolExecutor for pings | Persistent ThreadPoolExecutor in background thread | Phase 132 | Eliminates 42ms blocking + 16.4% CPU overhead |
| Blocking ICMP in control loop | Non-blocking read from shared variable | Phase 132 | rtt_measurement drops from 42ms to <1ms |
| No cycle budget health indicator | status: ok/warning/critical + alerting | Phase 132 | Operators can detect performance regressions |

**Deprecated/outdated after this phase:**
- `ping_hosts_with_results()` direct call from `WANController.measure_rtt()` -- replaced by background thread
- `ping_hosts_concurrent()` method -- no longer called from hot path (may still be used by calibrate.py)

## Open Questions

1. **Background thread cadence value**
   - What we know: ICMP round trip takes ~26ms idle, ~42ms under load. IRTTThread uses 10s cadence (very different scale).
   - What's unclear: Optimal cadence for background RTT thread. Too fast = unnecessary CPU. Too slow = stale data.
   - Recommendation: Start with 0ms additional sleep (measure-sleep-measure as fast as ICMP allows). Under load, natural measurement time of ~42ms provides ~24Hz effective measurement rate, plenty fresh for a 20Hz control loop. Under idle, ~26ms provides ~38Hz. If CPU impact is too high, add a small sleep (10-20ms).

2. **Whether measure_rtt() should do one synchronous measurement on first call**
   - What we know: First few cycles after startup will get None from background thread.
   - What's unclear: Whether existing handle_icmp_failure() gracefully handles 2-3 None results at startup without adverse effects.
   - Recommendation: Likely fine -- handle_icmp_failure() already handles ICMP outages. But verify by reading the first-cycle startup path. If it triggers circuit breaker or watchdog concern, add a synchronous first measurement.

3. **Consecutive-check threshold for cycle_budget_warning alert**
   - What we know: Alert should not fire on brief spikes (e.g., maintenance VACUUM).
   - What's unclear: How many consecutive cycles of >80% before alerting.
   - Recommendation: 60 cycles (3 seconds). Short enough to detect sustained overload, long enough to ignore maintenance spikes. Make configurable via `alerting.rules.cycle_budget_warning.consecutive_checks` with SIGUSR1 reload.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via .venv/bin/pytest) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_rtt_measurement.py tests/test_health_check.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-02 | BackgroundRTTThread measures and caches RTT | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k background` | Wave 0 |
| PERF-02 | measure_rtt() reads from shared variable instead of blocking | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k measure_rtt_nonblocking` | Wave 0 |
| PERF-02 | Staleness detection (soft warning at 500ms, hard fail at 5s) | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k staleness` | Wave 0 |
| PERF-02 | Persistent ThreadPoolExecutor reused across cycles | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k persistent_pool` | Wave 0 |
| PERF-02 | Thread lifecycle: start, stop, shutdown_event integration | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k lifecycle` | Wave 0 |
| PERF-03 | Health endpoint cycle_budget has status field (ok/warning/critical) | unit | `.venv/bin/pytest tests/test_health_check.py -x -k cycle_budget_status` | Wave 0 |
| PERF-03 | warning_threshold_pct configurable via YAML | unit | `.venv/bin/pytest tests/test_health_check.py -x -k warning_threshold` | Wave 0 |
| PERF-03 | cycle_budget_warning alert fires after N consecutive overruns | unit | `.venv/bin/pytest tests/test_alert_engine.py -x -k cycle_budget` | Wave 0 |
| PERF-03 | SIGUSR1 reloads warning_threshold_pct from YAML | unit | `.venv/bin/pytest tests/test_health_check.py -x -k reload_threshold` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_rtt_measurement.py tests/test_health_check.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_rtt_measurement.py` -- add BackgroundRTTThread test class (lifecycle, caching, staleness, persistent pool)
- [ ] `tests/test_health_check.py` -- add cycle_budget status field tests (ok/warning/critical thresholds)
- [ ] `tests/test_health_check.py` -- add SIGUSR1 threshold reload tests

*(Existing test infrastructure (pytest, fixtures, mock patterns) covers all other needs)*

## Project Constraints (from CLAUDE.md)

- **Change policy:** Explain before changing, prefer analysis over implementation. Never refactor core logic without approval.
- **Priority:** stability > safety > clarity > elegance
- **Portable Controller Architecture:** Controller is link-agnostic. All variability in config parameters (YAML).
- **Architectural Spine (READ-ONLY):** Control model, state logic, flash wear protection, steering spine -- do not modify.
- **Testing:** Use `.venv/bin/pytest tests/ -v`. Use `.venv/bin/ruff check src/ tests/` and `.venv/bin/mypy src/wanctl/` for linting/type checking.
- **Python style:** Absolute imports, modern type hints (Python 3.12), externalized config.
- **Signal handling:** Thread-safe `threading.Event` in `signal_utils.py` -- do not change.
- **project-finalizer:** MANDATORY before every commit.
- **Production system:** Conservative changes, 24/7 operation.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/irtt_thread.py` -- Existing background thread pattern (frozen dataclass + GIL atomic swap)
- `src/wanctl/rtt_measurement.py` -- Current RTT measurement implementation (ThreadPoolExecutor per-call)
- `src/wanctl/health_check.py` -- Current `_build_cycle_budget()` implementation
- `src/wanctl/alert_engine.py` -- AlertEngine API for new alert types
- `src/wanctl/signal_utils.py` -- Shutdown event and reload patterns
- `src/wanctl/autorate_continuous.py` -- Control loop, WANController, cleanup chain, SIGUSR1 handler
- `.planning/phases/131-cycle-budget-profiling/131-ANALYSIS.md` -- Phase 131 profiling data (RTT=84.6%, ThreadPool=16.4%)

### Secondary (HIGH confidence -- local benchmarks)
- ThreadPoolExecutor persistent vs per-call benchmark: 24ms vs 98ms (4x improvement, 100 rounds, local machine)
- GIL atomic pointer swap verification: 100K concurrent read/write iterations, 0 errors

### Tertiary (HIGH confidence -- Python documentation)
- Python GIL guarantees atomic reference assignment for single attribute writes on immutable objects
- `concurrent.futures.ThreadPoolExecutor` threads are daemonic by default since Python 3.9
- `threading.Event.wait(timeout)` is the standard interruptible sleep pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use, no new dependencies
- Architecture: HIGH - IRTTThread pattern proven in production for months, ThreadPoolExecutor benchmark confirms improvement
- Pitfalls: HIGH - Based on reading actual codebase, understanding threading model, production experience documented in MEMORY.md

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain -- Python threading and this codebase architecture won't change)
