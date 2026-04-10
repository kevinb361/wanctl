# Phase 49: Telemetry & Monitoring - Research

**Researched:** 2026-03-06
**Domain:** Health endpoint telemetry, structured logging, OperationProfiler integration
**Confidence:** HIGH

## Summary

Phase 49 adds cycle budget telemetry to both health endpoints and structured logs. The core work is wiring existing `OperationProfiler` stats into the health JSON response and emitting per-subsystem timing at DEBUG level every cycle. All infrastructure already exists -- the profiler accumulates timing data every cycle (1200-sample deque), the JSONFormatter supports `extra={}` kwargs, and the health handlers have clear extension points. No new dependencies are needed.

The critical architectural concern is the `--profile` flag's `_profiler.clear()` call, which wipes all samples every 60s when enabled. This is incompatible with always-on health endpoint telemetry. The fix is straightforward: remove the `clear()` from `_record_profiling()` and let the deque's `maxlen=1200` naturally evict old samples. The `--profile` report remains useful (it reports on the current window) but no longer destroys the data that the health endpoint reads.

**Primary recommendation:** Wire `OperationProfiler.stats("*_cycle_total")` into health handlers, add `_overrun_count` to both daemons, emit structured DEBUG logs per cycle, and fix the `--profile` clear() conflict.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D1: Per-WAN placement in autorate health, top-level in steering health
- D2: Totals only (no subsystem breakdown in health JSON)
- D3: Cumulative overrun counter since startup
- D4: Overrun threshold = cycle_interval (50ms)
- D5: utilization_pct from windowed average
- D6: Per-subsystem timing every cycle at DEBUG level
- D7: Overruns at WARNING, rate-limited (1st/3rd/every 10th)
- D8: Always-on telemetry (zero per-cycle overhead)
- D9: Omit cycle_budget on cold start

### Claude's Discretion
None specified -- all decisions locked.

### Deferred Ideas (OUT OF SCOPE)
- Per-subsystem breakdown in health endpoint
- Profiling data persistence to SQLite
- `/profile` dedicated endpoint for live profiling
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROF-03 | Cycle budget utilization (% used, overrun count, slow cycle count) exposed via health endpoint | Health handlers have clear extension points; profiler.stats() provides avg/p95/p99; new _overrun_count counter on both daemons |
| TELM-01 | Per-subsystem timing data available in structured logs for production analysis | JSONFormatter already supports extra={}; PerfTimer already logs at DEBUG; add structured fields per cycle |
| TELM-02 | Cycle budget metrics queryable via existing health endpoint JSON response | Both health handlers (_get_health_status) iterate over daemon state; profiler accessible via controller/daemon reference |
</phase_requirements>

## Standard Stack

### Core (no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| OperationProfiler | existing | Cycle timing accumulation | Already records every cycle, 1200-sample deque, .stats() returns avg/p95/p99 |
| JSONFormatter | existing | Structured log emission | Already supports extra={} kwargs, filters internal LogRecord attrs |
| PerfTimer | existing | Per-subsystem timing | Already wraps each subsystem in both daemons |

### Supporting
No new libraries needed. All telemetry infrastructure is in place from Phase 47.

### Alternatives Considered
None -- CONTEXT.md specifies no new dependencies and leveraging existing infrastructure.

## Architecture Patterns

### Health Endpoint Extension Pattern

The health handlers use class-level references set by `start_*_server()`. The handler accesses daemon internals directly during request processing.

**Autorate pattern** (health_check.py):
```python
# In _get_health_status(), within the wan_info loop:
for wan_info in self.controller.wan_controllers:
    wan_controller = wan_info["controller"]
    # wan_controller._profiler is the OperationProfiler
    # wan_controller._overrun_count is the new counter
```

**Steering pattern** (steering/health.py):
```python
# In _get_health_status():
if self.daemon is not None:
    # self.daemon._profiler is the OperationProfiler
    # self.daemon._overrun_count is the new counter
```

### cycle_budget JSON Structure (from D1, D2)

```python
def _build_cycle_budget(profiler, overrun_count, cycle_interval_ms):
    """Build cycle_budget dict from profiler stats. Shared by both handlers."""
    stats = profiler.stats("autorate_cycle_total")  # or "steering_cycle_total"
    if not stats:
        return None  # D9: omit on cold start
    return {
        "cycle_time_ms": {
            "avg": round(stats["avg_ms"], 1),
            "p95": round(stats["p95_ms"], 1),
            "p99": round(stats["p99_ms"], 1),
        },
        "utilization_pct": round((stats["avg_ms"] / cycle_interval_ms) * 100, 1),
        "overrun_count": overrun_count,
    }
```

### Overrun Detection Pattern (from D3, D4, D7)

Added to `_record_profiling()` in both daemons:

```python
def _record_profiling(self, ...):
    total_ms = (time.perf_counter() - cycle_start) * 1000.0
    # ... existing record() calls ...

    # Overrun detection (D4: threshold = cycle_interval)
    if total_ms > self.cycle_interval_ms:
        self._overrun_count += 1
        # Rate-limited WARNING (D7: 1st, 3rd, every 10th)
        if self._overrun_count == 1 or self._overrun_count == 3 or self._overrun_count % 10 == 0:
            self.logger.warning(
                f"Cycle overrun: {total_ms:.1f}ms > {self.cycle_interval_ms}ms "
                f"(total overruns: {self._overrun_count})"
            )
```

### Structured Logging Pattern (from D6)

```python
# In _record_profiling(), every cycle at DEBUG:
self.logger.debug(
    "Cycle timing",
    extra={
        "cycle_total_ms": round(total_ms, 1),
        "rtt_measurement_ms": round(rtt_ms, 1),
        "state_management_ms": round(state_ms, 1),
        "router_communication_ms": round(router_ms, 1),  # or cake_stats_ms for steering
        "overrun": total_ms > self.cycle_interval_ms,
    },
)
```

### Anti-Patterns to Avoid

- **Computing stats on the hot path:** Do NOT call `profiler.stats()` every cycle. It sorts 1200 samples. Only call on `/health` request (~0.1ms compute, on-demand).
- **Thread-unsafe profiler mutations:** The health handler runs on a different thread. Do NOT add locking -- CPython's GIL makes deque.append() and list(deque) atomic. Adding locks would add latency to the 50ms hot path.
- **Clearing profiler on report:** The `--profile` flag currently calls `_profiler.clear()` every 60s. This wipes health endpoint data. Fix: remove clear(), let maxlen eviction handle it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile stats | Custom percentile calculation | `OperationProfiler.stats()` | Already computes min/max/avg/p95/p99 with sorted-list indexing |
| Rate-limited logging | Custom counter/timer | Existing pattern from router error logging | Pattern already proven: `if count == 1 or count == 3 or count % 10 == 0` |
| Structured JSON logs | Custom JSON serialization | `JSONFormatter` with `extra={}` | Handles non-serializable values, excludes internal attrs, already in production |
| Rolling window stats | Custom circular buffer | `deque(maxlen=1200)` in OperationProfiler | Already bounded, auto-evicts old samples |

## Common Pitfalls

### Pitfall 1: --profile Flag Clears Health Endpoint Data
**What goes wrong:** `_record_profiling()` calls `self._profiler.clear()` every 1200 cycles when `--profile` is enabled. After clear, health endpoint returns empty `cycle_budget` until samples rebuild.
**Why it happens:** Phase 47 designed profiling as a diagnostic tool with periodic reset. Phase 49 makes it always-on infrastructure.
**How to avoid:** Remove `self._profiler.clear()` from `_record_profiling()` in both daemons. The deque's `maxlen=1200` already evicts old data. The periodic report (`self._profiler.report()`) still works -- it reads the current window.
**Warning signs:** Health endpoint `cycle_budget` disappearing periodically when `--profile` is active.

### Pitfall 2: cycle_interval_ms Must Be Portable
**What goes wrong:** Hardcoding `50.0` as overrun threshold instead of deriving from config.
**Why it happens:** Both daemons use module-level constants (`CYCLE_INTERVAL_SECONDS = 0.05`, `ASSESSMENT_INTERVAL_SECONDS = 0.05`).
**How to avoid:** Compute `self.cycle_interval_ms = CYCLE_INTERVAL_SECONDS * 1000.0` (autorate) or `ASSESSMENT_INTERVAL_SECONDS * 1000.0` (steering) during __init__. This respects the portable controller architecture.
**Warning signs:** Deployment with different interval fails overrun detection.

### Pitfall 3: Cold Start Health Response Must Not Include Nulls
**What goes wrong:** Including `cycle_budget: null` or `cycle_budget: {"cycle_time_ms": null}` in JSON response.
**Why it happens:** Profiler returns `{}` (empty dict) before any samples recorded.
**How to avoid:** Check `if not stats: return None`, then only add `cycle_budget` key if result is not None (D9 decision).
**Warning signs:** Monitoring tools parsing health JSON crash on null values.

### Pitfall 4: Structured Log Overhead
**What goes wrong:** Adding expensive operations to every cycle's DEBUG log.
**Why it happens:** Temptation to include stats computations in the log call.
**How to avoid:** Only log raw per-subsystem values (already computed by PerfTimer). Never call profiler.stats() in the log path. The extra={} dict construction is ~0.001ms.
**Warning signs:** Cycle time increase > 0.5ms after adding telemetry.

### Pitfall 5: Health Handler Thread Safety
**What goes wrong:** Adding locks to the profiler for thread safety between health handler and cycle loop.
**Why it happens:** Concern about concurrent read/write on shared data.
**How to avoid:** CPython's GIL makes `deque.append()` and `list(deque)` effectively atomic. The `stats()` method copies the deque with `list()` first, then operates on the copy. No locking needed.
**Warning signs:** Adding threading.Lock adds measurable latency to 50ms cycle.

## Code Examples

### Health Endpoint Integration (autorate)

```python
# In health_check.py, _get_health_status(), inside wan_info loop:
wan_health: dict[str, Any] = {
    "name": config.wan_name,
    "baseline_rtt_ms": round(wan_controller.baseline_rtt, 2),
    # ... existing fields ...
}

# Add cycle_budget (D1: per-WAN, D9: omit on cold start)
cycle_budget = _build_cycle_budget(
    wan_controller._profiler,
    wan_controller._overrun_count,
    CYCLE_INTERVAL_SECONDS * 1000.0,
    "autorate_cycle_total",
)
if cycle_budget is not None:
    wan_health["cycle_budget"] = cycle_budget

health["wans"].append(wan_health)
```

### Health Endpoint Integration (steering)

```python
# In steering/health.py, _get_health_status(), after existing state fields:
# Add cycle_budget (D1: top-level, D9: omit on cold start)
cycle_budget = _build_cycle_budget(
    self.daemon._profiler,
    self.daemon._overrun_count,
    ASSESSMENT_INTERVAL_SECONDS * 1000.0,
    "steering_cycle_total",
)
if cycle_budget is not None:
    health["cycle_budget"] = cycle_budget
```

### Shared Build Function

```python
def _build_cycle_budget(
    profiler: OperationProfiler,
    overrun_count: int,
    cycle_interval_ms: float,
    total_label: str,
) -> dict[str, Any] | None:
    """Build cycle_budget dict for health response.

    Returns None if profiler has no data (cold start, D9).
    """
    stats = profiler.stats(total_label)
    if not stats:
        return None
    return {
        "cycle_time_ms": {
            "avg": round(stats["avg_ms"], 1),
            "p95": round(stats["p95_ms"], 1),
            "p99": round(stats["p99_ms"], 1),
        },
        "utilization_pct": round((stats["avg_ms"] / cycle_interval_ms) * 100, 1),
        "overrun_count": overrun_count,
    }
```

### Structured Debug Logging (autorate)

```python
# In WANController._record_profiling():
def _record_profiling(self, rtt_ms, state_ms, router_ms, cycle_start):
    total_ms = (time.perf_counter() - cycle_start) * 1000.0
    self._profiler.record("autorate_rtt_measurement", rtt_ms)
    self._profiler.record("autorate_state_management", state_ms)
    self._profiler.record("autorate_router_communication", router_ms)
    self._profiler.record("autorate_cycle_total", total_ms)

    # Overrun detection (D3: cumulative, D4: threshold = cycle_interval)
    is_overrun = total_ms > self._cycle_interval_ms
    if is_overrun:
        self._overrun_count += 1
        # Rate-limited WARNING (D7: 1st, 3rd, every 10th)
        count = self._overrun_count
        if count == 1 or count == 3 or count % 10 == 0:
            self.logger.warning(
                f"{self.wan_name}: Cycle overrun: {total_ms:.1f}ms > "
                f"{self._cycle_interval_ms:.0f}ms (total: {count})"
            )

    # Structured per-subsystem timing (D6: every cycle at DEBUG)
    self.logger.debug(
        "Cycle timing",
        extra={
            "cycle_total_ms": round(total_ms, 1),
            "rtt_measurement_ms": round(rtt_ms, 1),
            "state_management_ms": round(state_ms, 1),
            "router_communication_ms": round(router_ms, 1),
            "overrun": is_overrun,
        },
    )

    # Periodic report (--profile flag only, NO clear())
    self._profile_cycle_count += 1
    if self._profiling_enabled and self._profile_cycle_count >= PROFILE_REPORT_INTERVAL:
        self._profiler.report(self.logger)
        self._profile_cycle_count = 0
```

### Structured Debug Logging (steering)

```python
# In SteeringDaemon._record_profiling():
def _record_profiling(self, cake_ms, rtt_ms, state_ms, cycle_start):
    total_ms = (time.perf_counter() - cycle_start) * 1000.0
    self._profiler.record("steering_cake_stats", cake_ms)
    self._profiler.record("steering_rtt_measurement", rtt_ms)
    self._profiler.record("steering_state_management", state_ms)
    self._profiler.record("steering_cycle_total", total_ms)

    # Overrun detection
    is_overrun = total_ms > self._cycle_interval_ms
    if is_overrun:
        self._overrun_count += 1
        count = self._overrun_count
        if count == 1 or count == 3 or count % 10 == 0:
            self.logger.warning(
                f"Steering cycle overrun: {total_ms:.1f}ms > "
                f"{self._cycle_interval_ms:.0f}ms (total: {count})"
            )

    # Structured timing (D6)
    self.logger.debug(
        "Cycle timing",
        extra={
            "cycle_total_ms": round(total_ms, 1),
            "rtt_measurement_ms": round(rtt_ms, 1),
            "cake_stats_ms": round(cake_ms, 1),
            "state_management_ms": round(state_ms, 1),
            "overrun": is_overrun,
        },
    )

    # Periodic report (--profile flag only, NO clear())
    self._profile_cycle_count += 1
    if self._profiling_enabled and self._profile_cycle_count >= PROFILE_REPORT_INTERVAL:
        self._profiler.report(self.logger)
        self._profile_cycle_count = 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `--profile` as only observability | Health endpoint + structured logs (always-on) | Phase 49 | Production visibility without CLI flag |
| `_profiler.clear()` every 60s | Deque maxlen eviction (no clear) | Phase 49 | Health endpoint always has data |
| Profiling data ephemeral | Profiling data feeds health response | Phase 49 | Monitoring tools can scrape cycle budget |

## Open Questions

None. All design decisions are locked in CONTEXT.md. Implementation is straightforward wiring of existing components.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 with pytest-cov |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_health_check.py tests/test_steering_health.py tests/test_perf_profiler.py -v -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROF-03 | Health endpoint includes cycle_budget with avg/p95/p99/utilization/overruns | integration | `.venv/bin/pytest tests/test_health_check.py -v -x -k cycle_budget` | New tests needed |
| PROF-03 | cycle_budget omitted on cold start (D9) | unit | `.venv/bin/pytest tests/test_health_check.py -v -x -k cold_start` | New tests needed |
| PROF-03 | Overrun counter increments correctly | unit | `.venv/bin/pytest tests/test_perf_profiler.py -v -x -k overrun` | New tests needed |
| TELM-01 | Structured DEBUG logs include per-subsystem timing | unit | `.venv/bin/pytest tests/test_autorate_profiling.py -v -x -k structured_log` | New file needed |
| TELM-01 | Overrun WARNING logged with rate limiting | unit | `.venv/bin/pytest tests/test_autorate_profiling.py -v -x -k overrun_warning` | New file needed |
| TELM-02 | Steering health includes cycle_budget (parity) | integration | `.venv/bin/pytest tests/test_steering_health.py -v -x -k cycle_budget` | New tests needed |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_health_check.py tests/test_steering_health.py tests/test_perf_profiler.py -v -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Tests for cycle_budget in autorate health response (in `tests/test_health_check.py`)
- [ ] Tests for cycle_budget in steering health response (in `tests/test_steering_health.py`)
- [ ] Tests for cold start omission of cycle_budget (both files)
- [ ] Tests for overrun detection and rate-limited WARNING logging (new or existing test files)
- [ ] Tests for structured DEBUG log fields (verify extra={} dict contents)
- [ ] Tests for _build_cycle_budget shared function (unit tests)
- [ ] No framework install needed -- pytest already configured

## Sources

### Primary (HIGH confidence)
- `src/wanctl/health_check.py` - Autorate health handler, _get_health_status() structure
- `src/wanctl/steering/health.py` - Steering health handler, _get_health_status() structure
- `src/wanctl/perf_profiler.py` - OperationProfiler.stats() API, deque-based storage
- `src/wanctl/logging_utils.py` - JSONFormatter with extra={} support
- `src/wanctl/autorate_continuous.py` lines 1340-1357 - _record_profiling() method
- `src/wanctl/steering/daemon.py` lines 1231-1248 - _record_profiling() method
- `src/wanctl/autorate_continuous.py` line 1515 - Rate-limited logging pattern (1st, 3rd, every 10th)
- `tests/test_health_check.py` - Existing health test patterns (mock controller, server lifecycle)
- `tests/test_steering_health.py` - Existing steering health test patterns

### Secondary (MEDIUM confidence)
- None needed -- all integration points are in the codebase

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all components already exist in codebase, no new dependencies
- Architecture: HIGH - health handlers have clear extension points, profiler API is well-defined
- Pitfalls: HIGH - identified through direct code reading (--profile clear() conflict, thread safety, cold start)

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable internal codebase, no external dependency changes)
