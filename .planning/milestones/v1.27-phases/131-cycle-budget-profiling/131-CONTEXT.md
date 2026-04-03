# Phase 131: Cycle Budget Profiling - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Profile the autorate hot path under RRUL load to identify which subsystems cause 138% cycle budget overruns (avg 69ms on 50ms cycle, ~14Hz instead of 20Hz). Deliver per-subsystem timing breakdown and a clear recommendation for Phase 132 (optimize code or adjust interval).

</domain>

<decisions>
## Implementation Decisions

### Profiling Granularity
- **D-01:** Split `autorate_state_management` PerfTimer into 5-7 sub-timers covering: signal processing, EWMA update, congestion assessment, hysteresis check, tuning rotation, alert engine. Reuses existing PerfTimer/OperationProfiler pattern.
- **D-02:** Sub-timers are always active (not gated behind --profile). PerfTimer logs at DEBUG, OperationProfiler uses bounded deques. Negligible overhead (<0.1ms per timer).
- **D-03:** Additionally capture one py-spy flamegraph for deep per-function analysis. Belt and suspenders: sub-timers for ongoing monitoring, py-spy for one-shot deep drill-down.

### Profiling Methodology
- **D-04:** Use `py-spy record --pid` to attach to running wanctl systemd process on cake-shaper VM. Record 30-60s during RRUL load, generate SVG flamegraph.
- **D-05:** Install py-spy on both dev machine and cake-shaper VM (via pipx).

### Load Generation & Test Plan
- **D-06:** Use flent RRUL from dev machine against Dallas netperf server (same proven v1.26 methodology). 60s runs.
- **D-07:** 3 profiling runs: 1 idle baseline + 2 loaded runs. py-spy capture during one loaded run.

### Output & Recommendation
- **D-08:** Enhanced health endpoint with per-subsystem breakdown always visible (extend cycle_budget section). Feeds directly into PERF-03 regression indicator requirement.
- **D-09:** Analysis document in .planning/ with measurements, py-spy flamegraph reference, and clear recommendation (optimize specific subsystem(s) or adjust cycle interval). This document feeds Phase 132 planning.

### Claude's Discretion
- Exact sub-timer boundaries within run_cycle() (where to place PerfTimer start/stop)
- py-spy sampling rate and recording duration
- Analysis document format and structure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Profiling Infrastructure
- `src/wanctl/perf_profiler.py` -- PerfTimer, OperationProfiler, record_cycle_profiling() shared helper
- `src/wanctl/health_check.py:70-101` -- _build_cycle_budget() that generates health endpoint cycle telemetry

### Hot Path (where sub-timers go)
- `src/wanctl/autorate_continuous.py:2963-2990` -- _record_profiling() method showing current 3-bucket pattern
- `src/wanctl/autorate_continuous.py:2992` -- run_cycle() entry point containing the full control loop

### Production Interval Context
- `docs/PRODUCTION_INTERVAL.md` -- 50ms interval decision, original profiling analysis, rollback procedures

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PerfTimer` context manager: Zero-config timing with DEBUG logging, used throughout codebase
- `OperationProfiler`: Bounded deque accumulator with min/max/avg/p95/p99 stats and periodic reports
- `record_cycle_profiling()`: Shared helper already handles overrun detection, structured logging, and periodic reporting
- `_build_cycle_budget()`: Builds health endpoint JSON from profiler stats -- extend for per-subsystem data

### Established Patterns
- 3-bucket profiling: rtt_measurement, state_management, router_communication -- add sub-buckets within state_management
- `PROFILE_REPORT_INTERVAL = 1200` (~60s at 50ms): Periodic report cadence
- Overrun count: rate-limited WARNING at 1st, 3rd, every 10th
- Health endpoint exposes `cycle_budget.cycle_time_ms.{avg,p95,p99}` + `utilization_pct` + `overrun_count`

### Integration Points
- `_record_profiling()` in autorate_continuous.py receives timing dict -- extend dict with sub-timer keys
- `_build_cycle_budget()` in health_check.py returns dict -- add `subsystems` sub-dict
- `record_cycle_profiling()` in perf_profiler.py is the shared sink -- accepts arbitrary timing dict already

</code_context>

<specifics>
## Specific Ideas

- v1.26 health endpoint showed 138% utilization (avg 69ms on 50ms cycle), p99 369ms, 51k overruns during RRUL
- py-spy SVG flamegraph should be saved and referenced in the analysis document
- Profiling should cover both the Spectrum WAN controller (primary, does steering) and potentially ATT for comparison

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 131-cycle-budget-profiling*
*Context gathered: 2026-04-02*
