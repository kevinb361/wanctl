# Phase 47: Cycle Profiling Infrastructure - Research

**Researched:** 2026-03-06
**Domain:** Python performance instrumentation, monotonic timing, production profiling at 50ms intervals
**Confidence:** HIGH

## Summary

Phase 47 instruments both the autorate and steering daemons with per-subsystem monotonic timing, then collects and analyzes production profiling data at the 50ms cycle interval. The project already has a `perf_profiler.py` module (PerfTimer, OperationProfiler) from v1.0 and 24 passing tests for it, but the instrumentation hooks were removed from the daemon code during v1.1-v1.8 refactoring. The analysis scripts (`scripts/profiling_collector.py`, `scripts/analyze_profiling.py`) also still exist.

The key context shift from v1.0 to v1.9: v1.0 profiling was at a 2s interval where cycles used only 2-4% of budget (no optimization needed). Since then, the interval was reduced to 50ms, and cycles now consume 60-80% of the budget (30-40ms average execution in a 50ms window). This means profiling overhead matters -- the <1ms overhead requirement is real and non-trivial.

**Primary recommendation:** Re-integrate PerfTimer hooks into both daemon `run_cycle()` methods with `time.perf_counter()` timing. Use the existing OperationProfiler (bounded deque, max_samples) for in-memory accumulation. Collect data by parsing structured log output with the existing `profiling_collector.py` script. No new dependencies needed -- this is pure Python stdlib work.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROF-01 | Operator can collect cycle-level profiling data at 50ms production interval for both autorate and steering daemons | Existing PerfTimer + OperationProfiler module provides timing infrastructure. Re-integrate hooks into both `run_cycle()` methods. Existing `profiling_collector.py` script parses log output for data collection. OperationProfiler's bounded deque prevents memory growth. |
| PROF-02 | Each cycle phase (RTT measurement, router communication, CAKE stats, state management) is individually timed with monotonic timestamps | `time.perf_counter()` already used in PerfTimer (monotonic, high-resolution). Subsystem boundaries clearly identified in both daemons -- see Architecture Patterns section for exact instrumentation points. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| time (stdlib) | Python 3.12 | `perf_counter()` for monotonic high-resolution timing | Sub-microsecond resolution, not affected by NTP adjustments, already used in PerfTimer |
| collections (stdlib) | Python 3.12 | `deque(maxlen=N)` for bounded sample storage | Automatic eviction of oldest samples, O(1) append, already in OperationProfiler |
| statistics (stdlib) | Python 3.12 | Percentile calculations for analysis | Already used elsewhere in codebase (median in RTT measurement) |
| logging (stdlib) | Python 3.12 | Structured log output of timing data | Existing pattern -- all timing goes through logger.debug() |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | Python 3.12 | Regex parsing of timing lines from logs | Used in `profiling_collector.py` for extracting "label: X.Xms" patterns |
| json (stdlib) | Python 3.12 | JSON output from analysis scripts | For machine-readable profiling data export |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PerfTimer (custom) | cProfile/profile | cProfile adds ~20% overhead per call, far exceeds 1ms budget. PerfTimer uses single `perf_counter()` pair = ~0.001ms overhead |
| Log-based collection | SQLite storage | SQLite writes add I/O overhead per cycle. Logs are already being written anyway -- zero additional I/O cost |
| OperationProfiler | Prometheus histograms | Already have Prometheus metrics module, but histogram overhead is higher than deque append. OperationProfiler is pure Python, ~0.01ms per record |

**Installation:** No new dependencies. Everything is Python 3.12 stdlib + existing `perf_profiler.py` module.

## Architecture Patterns

### Existing Infrastructure (Reuse)

```
src/wanctl/
  perf_profiler.py          # EXISTS: PerfTimer, OperationProfiler, measure_operation
scripts/
  profiling_collector.py    # EXISTS: Log parser for extracting timing data
  analyze_profiling.py      # EXISTS: Report generator with percentile breakdowns
docs/
  PROFILING.md              # EXISTS: Collection and analysis procedures
```

### Autorate Daemon Subsystem Boundaries

The `WanController.run_cycle()` method (line 1326) has these clear phases:

```
run_cycle():
  1. RTT Measurement       -> self.measure_rtt()                    [lines 1330]
  2. ICMP Failure Handling  -> self.handle_icmp_failure()            [lines 1333-1340]
  3. EWMA Update            -> self.update_ewma(measured_rtt)        [line 1350]
  4. Rate Adjustment Logic  -> self.download.adjust_4state(...)      [lines 1367-1378]
                              self.upload.adjust(...)
  5. Metrics Recording      -> self._metrics_writer.write_metrics..  [lines 1390-1429]
  6. Router Communication   -> self.apply_rate_changes_if_needed()   [lines 1434-1470]
  7. State Persistence      -> self.save_state()                     [lines 1472-1478]
  8. Prometheus Metrics     -> record_autorate_cycle()               [lines 1481-1492]
```

**Recommended timing groups (4 subsystems matching PROF-02):**

| Timer Label | What It Covers | Expected Range |
|-------------|---------------|----------------|
| `autorate_rtt_measurement` | `measure_rtt()` -- subprocess ping, concurrent pings for median-of-3 | 20-40ms (dominant) |
| `autorate_router_communication` | `apply_rate_changes_if_needed()` -- REST/SSH to MikroTik (0.2% of cycles) | 0ms (skipped) or 15-25ms (when rates change) |
| `autorate_state_management` | EWMA update + rate adjustment + state save + metrics recording | <1ms |
| `autorate_cycle_total` | Entire `run_cycle()` from entry to exit | 30-45ms |

Note: CAKE stats are not collected by the autorate daemon (only RTT measurement). CAKE stats are a steering daemon concern.

### Steering Daemon Subsystem Boundaries

The `SteeringDaemon.run_cycle()` method (line 1215) has these phases:

```
run_cycle():
  1. Baseline RTT Update    -> self.update_baseline_rtt()             [lines 1222-1227]
  2. CAKE Stats Collection  -> self.collect_cake_stats()              [line 1230]
  3. RTT Measurement        -> self._measure_current_rtt_with_retry() [lines 1233-1239]
  4. Delta Calculation      -> self.calculate_delta()                  [line 1242]
  5. EWMA Smoothing         -> self.update_ewma_smoothing()           [lines 1253-1258]
  6. State Machine Update   -> self.update_state_machine()             [line 1288]
  7. State Persistence      -> self.state_mgr.save()                  [line 1304]
  8. Metrics Recording      -> record_steering_state() + SQLite write  [lines 1306-1347]
```

**Recommended timing groups (4 subsystems matching PROF-02):**

| Timer Label | What It Covers | Expected Range |
|-------------|---------------|----------------|
| `steering_rtt_measurement` | `_measure_current_rtt_with_retry()` -- subprocess ping with up to 3 retries | 20-40ms (dominant) |
| `steering_cake_stats` | `collect_cake_stats()` -- REST/SSH to MikroTik for queue stats | 15-25ms (every cycle if CAKE-aware) |
| `steering_state_management` | Baseline update + delta + EWMA + state machine + save + metrics | <1ms |
| `steering_cycle_total` | Entire `run_cycle()` from entry to exit | 30-50ms |

Note: Router communication for steering is embedded in `collect_cake_stats()` (reads queue stats) and `execute_steering_transition()` (only on state changes). The CAKE stats read IS the router communication for steering.

### Instrumentation Pattern

Use PerfTimer as a context manager wrapping each subsystem:

```python
# In WanController.run_cycle() (autorate_continuous.py)
from wanctl.perf_profiler import PerfTimer

def run_cycle(self) -> bool:
    cycle_start = time.monotonic()

    with PerfTimer("autorate_rtt_measurement", self.logger) as rtt_timer:
        measured_rtt = self.measure_rtt()

    # ... ICMP failure handling (included in rtt_timer if inside block,
    #     or separate -- decision for planner)

    with PerfTimer("autorate_state_management", self.logger) as state_timer:
        self.update_ewma(measured_rtt)
        dl_zone, dl_rate, dl_transition_reason = self.download.adjust_4state(...)
        ul_zone, ul_rate, ul_transition_reason = self.upload.adjust(...)
        # metrics recording...

    with PerfTimer("autorate_router_communication", self.logger) as router_timer:
        self.apply_rate_changes_if_needed(dl_rate, ul_rate)

    # state save is part of state_management or separate -- planner decides

    # Record to profiler for accumulation
    self._profiler.record("autorate_rtt_measurement", rtt_timer.elapsed_ms)
    self._profiler.record("autorate_router_communication", router_timer.elapsed_ms)
    self._profiler.record("autorate_state_management", state_timer.elapsed_ms)
    total_ms = (time.monotonic() - cycle_start) * 1000.0
    self._profiler.record("autorate_cycle_total", total_ms)
```

### Periodic Report Pattern

Log accumulated stats periodically (e.g., every 1200 cycles = 60 seconds at 50ms):

```python
PROFILE_REPORT_INTERVAL = 1200  # cycles between reports

if self._cycle_count % PROFILE_REPORT_INTERVAL == 0:
    self._profiler.report(self.logger)
    self._profiler.clear()
```

This provides regular profiling summaries in logs without unbounded memory growth.

### Anti-Patterns to Avoid

- **Timing inside the sleep:** Do not include `time.sleep(remainder)` in cycle_total. The existing code already calculates `elapsed = time.monotonic() - cycle_start` before sleeping.
- **Timing at DEBUG level only:** Profiling output should go to DEBUG level (as PerfTimer already does). This means profiling is only visible when `--debug` flag is set, keeping production logs clean.
- **Adding I/O in the timing path:** Do not write profiling data to SQLite or files per-cycle. Use in-memory OperationProfiler + periodic log reports.
- **Modifying protected logic:** Timing wraps around code blocks but MUST NOT change any logic flow, especially the architectural spine (EWMA, baseline update, flash wear protection).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| High-resolution timing | Custom time tracking | `PerfTimer` from `perf_profiler.py` | Already exists, tested (24 tests), uses `perf_counter()` |
| Bounded sample storage | Custom ring buffer | `OperationProfiler` with `deque(maxlen=N)` | Already exists, handles eviction automatically |
| Percentile calculation | Manual sorted-list indexing | `OperationProfiler.stats()` method | Already implements P50/P95/P99 calculation |
| Log parsing for data collection | Custom parser | `scripts/profiling_collector.py` | Already parses "label: X.Xms" pattern from logs |
| Analysis report generation | Custom report builder | `scripts/analyze_profiling.py` | Already generates markdown with percentile breakdowns |

**Key insight:** ~80% of the infrastructure for this phase already exists from v1.0. The main work is re-integrating hooks into daemon code that changed significantly since v1.0, and updating the analysis scripts for the new subsystem labels and 50ms timing context.

## Common Pitfalls

### Pitfall 1: Observer Effect (Profiling Changes What It Measures)
**What goes wrong:** Profiling overhead exceeds 1ms budget, distorting measurements and reducing effective cycle budget.
**Why it happens:** Adding I/O (file writes, network calls) or complex computation per-cycle for profiling.
**How to avoid:** PerfTimer uses only 2 `perf_counter()` calls (~0.001ms) + 1 `logger.debug()` call (buffered, ~0.01ms). OperationProfiler.record() is a single deque.append (~0.001ms). Total overhead: <0.1ms per subsystem, <0.5ms for 4 subsystems.
**Warning signs:** Cycle times increase by >1ms after instrumentation. Measure before/after.

### Pitfall 2: Unbounded Memory Growth
**What goes wrong:** Profiler accumulates samples forever, consuming memory in long-running daemon.
**Why it happens:** Not using bounded storage or not clearing periodically.
**How to avoid:** OperationProfiler already uses `deque(maxlen=N)`. Use max_samples=1200 (1 minute of data at 50ms). Clear after each periodic report.

### Pitfall 3: Instrumenting Error Paths Differently
**What goes wrong:** Timing data only reflects successful cycles, missing slow error-path cycles that may be the real problem.
**Why it happens:** PerfTimer wraps around code that returns early on error.
**How to avoid:** Place cycle_total timer at the very top of run_cycle(), before any early returns. Individual subsystem timers should wrap the attempt, not the success path.

### Pitfall 4: Mixing Up Autorate vs Steering Subsystems
**What goes wrong:** Autorate doesn't read CAKE stats (steering does). Steering doesn't do rate adjustment (autorate does). Using wrong labels creates confusion.
**Why it happens:** Assuming both daemons have identical subsystem structures.
**How to avoid:** Use prefixed labels (`autorate_*` vs `steering_*`). Document which daemon has which subsystems. See Architecture Patterns section for the exact mapping.

### Pitfall 5: Stale Analysis Scripts
**What goes wrong:** Existing `profiling_collector.py` and `analyze_profiling.py` from v1.0 expect old subsystem labels and 2s timing context.
**Why it happens:** Scripts were written for v1.0 profiling with different label names.
**How to avoid:** Update scripts to handle new label names. The regex pattern `(\w+): (\d+\.\d+)ms` should still work, but report generation may need updating for 50ms budget context.

### Pitfall 6: PerfTimer in Exception-Raising Code
**What goes wrong:** Timer's `__exit__` runs before exception propagates, but elapsed_ms may reflect partial execution.
**Why it happens:** Context manager exit fires on exception.
**How to avoid:** This is actually fine for profiling -- we WANT to know how long the failed attempt took. PerfTimer already handles this correctly (test_timer_handles_exception passes). Just be aware that error cycles may show shorter timings.

## Code Examples

### Existing PerfTimer Usage (from perf_profiler.py)

```python
# Source: src/wanctl/perf_profiler.py lines 25-64
class PerfTimer:
    def __init__(self, label: str, logger: logging.Logger | None = None):
        self.label = label
        self.logger = logger
        self.start_time = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> "PerfTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        end_time = time.perf_counter()
        self.elapsed_ms = (end_time - self.start_time) * 1000.0
        if self.logger:
            self.logger.debug(f"{self.label}: {self.elapsed_ms:.1f}ms")
```

### Existing OperationProfiler Record + Stats (from perf_profiler.py)

```python
# Source: src/wanctl/perf_profiler.py lines 66-153
profiler = OperationProfiler(max_samples=1200)
profiler.record("autorate_rtt_measurement", timer.elapsed_ms)
stats = profiler.stats("autorate_rtt_measurement")
# Returns: {count, min_ms, max_ms, avg_ms, p95_ms, p99_ms, samples}
```

### Existing Cycle Timing Pattern (autorate daemon loop)

```python
# Source: src/wanctl/autorate_continuous.py lines 1909-2006
while not is_shutdown_requested():
    cycle_start = time.monotonic()
    cycle_success = controller.run_cycle(use_lock=False)
    elapsed = time.monotonic() - cycle_start
    # ... watchdog, health, maintenance ...
    sleep_time = max(0, CYCLE_INTERVAL_SECONDS - elapsed)
    if sleep_time > 0 and not is_shutdown_requested():
        time.sleep(sleep_time)
```

## State of the Art

| Old Approach (v1.0) | Current Approach (v1.9) | When Changed | Impact |
|---------------------|------------------------|--------------|--------|
| 2s cycle interval, 2-4% budget utilization | 50ms cycle interval, 60-80% budget utilization | v1.0 Phase 5 (2026-01-13) | Profiling overhead now matters -- <1ms requirement is real |
| PerfTimer hooks in both daemons | Hooks removed during refactoring | v1.1-v1.8 (2026-01-14 to 2026-03-06) | Need to re-integrate, but daemon code has changed significantly |
| Steering uses 2s timer intervals | Steering uses 0.05s (50ms) intervals | v1.0 Phase 2 | Assessment interval matches autorate |
| autorate_rtt, autorate_router, autorate_ewma labels | Need new labels matching current subsystem structure | v1.1+ | Analysis scripts need label updates |

**Key difference from v1.0 profiling:** At 2s intervals, the profiling merely confirmed everything was fine (30-40ms in a 2000ms budget). At 50ms intervals, every millisecond matters. The v1.9 profiling needs to identify optimization targets within a tight budget where RTT measurement alone may consume 60-80% of available time.

## Open Questions

1. **OperationProfiler max_samples sizing**
   - What we know: Default is 100. For 50ms intervals, 100 samples = 5 seconds of data.
   - What's unclear: Whether 1200 (60s) or 72000 (1 hour) is better for production collection.
   - Recommendation: Use 1200 (60s) with periodic log reports every 60s. For the 1-hour collection requirement, parse the log output with profiling_collector.py which aggregates all periodic reports.

2. **Profiling data collection method for 1-hour production run**
   - What we know: Success criteria requires 1-hour production collection.
   - What's unclear: Whether to use `--debug` flag on production (which enables PerfTimer logging) or add a separate `--profile` flag.
   - Recommendation: Add a `--profile` flag that enables PerfTimer output at INFO level (not requiring --debug). This avoids flood of other debug output while collecting profiling data.

3. **ICMP failure handling timing in autorate**
   - What we know: Lines 1333-1340 handle ICMP failure with fallback connectivity checks.
   - What's unclear: Should this be part of `autorate_rtt_measurement` timer or separate?
   - Recommendation: Include it in `autorate_rtt_measurement` since it's part of the RTT measurement path (fallback is still measuring reachability).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-cov |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_perf_profiler.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROF-01 | Both daemons emit profiling data collectible at 50ms | unit | `.venv/bin/pytest tests/test_perf_profiler.py -x` | Exists (24 tests) |
| PROF-01 | Autorate run_cycle records per-subsystem timing | unit | `.venv/bin/pytest tests/test_autorate_continuous.py -k profil -x` | Wave 0 |
| PROF-01 | Steering run_cycle records per-subsystem timing | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k profil -x` (find actual test file) | Wave 0 |
| PROF-02 | Each phase individually timed with monotonic timestamps | unit | `.venv/bin/pytest tests/test_perf_profiler.py::TestPerfTimer -x` | Exists |
| PROF-02 | Timer labels match expected subsystem names | unit | `.venv/bin/pytest tests/test_autorate_continuous.py -k "profil and label" -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_perf_profiler.py tests/test_autorate_continuous.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before verify-work

### Wave 0 Gaps
- [ ] Tests verifying autorate `run_cycle` records profiling data -- covers PROF-01
- [ ] Tests verifying steering `run_cycle` records profiling data -- covers PROF-01
- [ ] Tests verifying correct subsystem timer labels -- covers PROF-02
- [ ] Tests verifying profiling overhead <1ms -- covers success criteria #4

*(Existing `test_perf_profiler.py` covers PerfTimer and OperationProfiler core functionality. Gap is integration testing that instrumented daemons actually use them.)*

## Sources

### Primary (HIGH confidence)
- `src/wanctl/perf_profiler.py` -- existing profiling module, 225 lines, fully tested
- `src/wanctl/autorate_continuous.py` -- autorate daemon with run_cycle at line 1326
- `src/wanctl/steering/daemon.py` -- steering daemon with run_cycle at line 1215
- `tests/test_perf_profiler.py` -- 24 existing tests for profiling module
- `.planning/milestones/v1.0-phases/01-measurement-infrastructure-profiling/PROFILING-ANALYSIS.md` -- v1.0 profiling results and methodology

### Secondary (MEDIUM confidence)
- Python 3.12 docs: `time.perf_counter()` resolution is system-dependent but typically sub-microsecond on Linux
- `scripts/profiling_collector.py` and `scripts/analyze_profiling.py` -- existing analysis tools (may need updates for new labels)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pure Python stdlib, no new dependencies, existing module reuse
- Architecture: HIGH -- daemon code read thoroughly, subsystem boundaries clearly identified with line numbers
- Pitfalls: HIGH -- v1.0 profiling experience documented, overhead constraints verified against PerfTimer implementation

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable -- no external dependencies to go stale)
