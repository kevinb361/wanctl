# Phase 132: Cycle Budget Optimization - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Optimize the controller to run within its 50ms cycle budget under sustained RRUL load, and add a health endpoint regression indicator with configurable warning threshold. Phase 131 profiling identified RTT measurement (84.6% of budget, 42ms avg) as the overwhelming bottleneck. This phase implements the architectural fix: decouple measurement from the control loop.

</domain>

<decisions>
## Implementation Decisions

### RTT Measurement Architecture
- **D-01:** Decouple RTT measurement from the control loop entirely. A dedicated background thread runs ICMP pings continuously; the control loop reads the latest RTT from a thread-safe shared variable each cycle. This eliminates the 42ms blocking I/O from the hot path (Phase 131 Option D).
- **D-02:** The background measurement thread keeps the existing 3-host concurrent ping pattern (median-of-3). Since it's no longer blocking the control loop, the measurement time doesn't matter -- measurement quality stays high.
- **D-03:** RTT delivery uses a shared atomic variable pattern (thread-safe shared value via threading primitives). Fits existing `signal_utils.py` conventions. No queue-based handoff.
- **D-04:** Staleness timeout with fallback: if RTT data is older than ~500ms (10 cycles), log a warning and use last-known-good RTT. If stale beyond a hard limit (~5s), treat as measurement failure (same as all-pings-failed today).

### ThreadPool Lifecycle
- **D-05:** The background measurement thread uses a persistent ThreadPoolExecutor (max_workers=3), created once at startup and reused across all measurement cycles. Eliminates per-cycle thread creation/teardown overhead (16.4% of CPU in py-spy). Shutdown on daemon stop via existing signal_utils pattern.

### Regression Indicator (PERF-03)
- **D-06:** Health endpoint adds a configurable `warning_threshold_pct` (default 80%) to YAML under `continuous_monitoring`. Health response adds a `status` field to `cycle_budget`: `ok` / `warning` / `critical` based on rolling utilization vs threshold. Matches existing health endpoint patterns.
- **D-07:** AlertEngine fires a new `cycle_budget_warning` alert type when utilization exceeds threshold for N consecutive checks. Reuses existing Discord webhook + rate limiting infrastructure from v1.15. SIGUSR1 hot-reloadable.

### Target Budget
- **D-08:** Target: under 50ms avg cycle time, under 80% utilization (<40ms on 50ms cycle). With RTT measurement moved to background, the control loop should drop from ~51ms to well under 10ms avg (remaining subsystems total ~9ms avg under load).
- **D-09:** Interval fallback decision deferred to post-measurement. If optimization doesn't achieve <80% utilization, decision on whether to widen to 75ms or optimize secondary consumers will be made based on actual data, not pre-committed.

### Claude's Discretion
- Background thread sleep interval between measurement cycles
- Exact threading primitives for shared RTT value (Lock vs Event vs dataclass with timestamp)
- AlertEngine consecutive-check threshold for cycle_budget_warning
- Whether to also optimize secondary consumers (logging_metrics 3.3ms, router_communication 3.4ms) if headroom allows

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 131 Profiling Results
- `.planning/phases/131-cycle-budget-profiling/131-ANALYSIS.md` -- Complete profiling data: subsystem timings (idle + RRUL), py-spy flamegraph analysis, Option A-D recommendations
- `.planning/phases/131-cycle-budget-profiling/131-CONTEXT.md` -- Prior phase decisions and profiling methodology

### RTT Measurement Path (primary optimization target)
- `src/wanctl/rtt_measurement.py:135-180` -- `ping_host()`: icmplib ICMP with CAP_NET_RAW, blocking I/O
- `src/wanctl/rtt_measurement.py:237-273` -- `ping_hosts_with_results()`: ThreadPoolExecutor per-call pattern (the bottleneck)
- `src/wanctl/autorate_continuous.py:2193-2240` -- `measure_rtt()`: ReflectorScorer integration, graceful degradation logic

### Control Loop Hot Path
- `src/wanctl/autorate_continuous.py:3012` -- `run_cycle()` entry point
- `src/wanctl/autorate_continuous.py:2963-2990` -- `_record_profiling()` with sub-timer pattern

### Health & Alerting Infrastructure
- `src/wanctl/health_check.py:70-101` -- `_build_cycle_budget()` where regression indicator goes
- `src/wanctl/perf_profiler.py` -- PerfTimer, OperationProfiler (existing profiling infrastructure)
- `src/wanctl/alert_engine.py` -- AlertEngine with Discord webhook, rate limiting, alert type registry

### Threading & Signal Patterns
- `src/wanctl/signal_utils.py` -- Thread-safe shutdown events, signal handling conventions
- `src/wanctl/daemon_utils.py` -- Daemon lifecycle, watchdog integration

### Production Interval Context
- `docs/PRODUCTION_INTERVAL.md` -- 50ms interval decision rationale, rollback procedures

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PerfTimer` context manager: Verify cycle time improvement post-optimization
- `OperationProfiler`: Bounded deque with p95/p99 stats -- use for utilization rolling average
- `signal_utils.py` shutdown events: Pattern for clean background thread termination
- `AlertEngine.register_alert_type()`: Existing API for adding new alert types with rate limiting
- `ReflectorScorer`: Already handles host quality tracking -- background thread must still feed results to it

### Established Patterns
- 3-bucket profiling (rtt_measurement, state_management, router_communication): rtt_measurement bucket should drop to <1ms post-optimization
- SIGUSR1 hot-reload: warning_threshold_pct should be reloadable via existing generalized handler
- Health endpoint JSON structure: `cycle_budget.{cycle_time_ms, utilization_pct, overrun_count, subsystems}` -- add `status` and `warning_threshold_pct` fields

### Integration Points
- `WANController.__init__()`: Start background measurement thread
- `WANController.measure_rtt()`: Replace blocking ping with shared variable read
- `WANController.cleanup()` / signal handler: Stop background thread, shutdown persistent ThreadPoolExecutor
- `_build_cycle_budget()` in health_check.py: Add status field computation
- AlertEngine: Register `cycle_budget_warning` alert type

</code_context>

<specifics>
## Specific Ideas

- Phase 131 showed idle RTT measurement at 26.5ms (53% of budget) -- even idle cycles block on ICMP. Non-blocking architecture fixes both idle and loaded performance.
- py-spy flamegraph confirmed ThreadPoolExecutor scheduling at 16.4% CPU -- persistent pool eliminates this.
- The feedback loop (congestion delays ICMP replies, which delays the control loop that detects congestion) is the core architectural problem being solved.
- ReflectorScorer integration must be preserved -- background thread records per-host results for quality scoring, same as today.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 132-cycle-budget-optimization*
*Context gathered: 2026-04-03*
