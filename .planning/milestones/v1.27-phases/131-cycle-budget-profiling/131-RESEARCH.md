# Phase 131: Cycle Budget Profiling - Research

**Researched:** 2026-04-02
**Domain:** Python performance profiling, sub-timer instrumentation, flamegraph analysis
**Confidence:** HIGH

## Summary

Phase 131 adds fine-grained sub-timers to the autorate hot path to identify which operations cause 138% cycle budget overruns under RRUL load (avg 69ms on 50ms cycle). The existing PerfTimer/OperationProfiler infrastructure is well-suited for extension -- the primary work is splitting the monolithic `autorate_state_management` timer into 5-7 sub-timers, extending the health endpoint to expose per-subsystem breakdown, and running py-spy flamegraph captures for deep drill-down.

The current profiling architecture has a significant measurement gap: `save_state()` and `record_autorate_cycle()` execute AFTER `_record_profiling()` but BEFORE the main loop calculates elapsed time. These un-profiled operations consume cycle budget but are invisible to the current instrumentation. Sub-timers must account for this gap.

**Primary recommendation:** Split state_management PerfTimer into sub-timers at natural boundaries (signal processing, EWMA/spike, congestion assessment, IRTT observation, alerts, metrics write), add a post-profiling timer for save_state, and extend `_build_cycle_budget()` to expose per-subsystem stats. Use py-spy for one-shot flamegraph confirmation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Split `autorate_state_management` PerfTimer into 5-7 sub-timers covering: signal processing, EWMA update, congestion assessment, hysteresis check, tuning rotation, alert engine. Reuses existing PerfTimer/OperationProfiler pattern.
- **D-02:** Sub-timers are always active (not gated behind --profile). PerfTimer logs at DEBUG, OperationProfiler uses bounded deques. Negligible overhead (<0.1ms per timer).
- **D-03:** Additionally capture one py-spy flamegraph for deep per-function analysis. Belt and suspenders: sub-timers for ongoing monitoring, py-spy for one-shot deep drill-down.
- **D-04:** Use `py-spy record --pid` to attach to running wanctl systemd process on cake-shaper VM. Record 30-60s during RRUL load, generate SVG flamegraph.
- **D-05:** Install py-spy on both dev machine and cake-shaper VM (via pipx).
- **D-06:** Use flent RRUL from dev machine against Dallas netperf server (same proven v1.26 methodology). 60s runs.
- **D-07:** 3 profiling runs: 1 idle baseline + 2 loaded runs. py-spy capture during one loaded run.
- **D-08:** Enhanced health endpoint with per-subsystem breakdown always visible (extend cycle_budget section). Feeds directly into PERF-03 regression indicator requirement.
- **D-09:** Analysis document in .planning/ with measurements, py-spy flamegraph reference, and clear recommendation (optimize specific subsystem(s) or adjust cycle interval). This document feeds Phase 132 planning.

### Claude's Discretion
- Exact sub-timer boundaries within run_cycle() (where to place PerfTimer start/stop)
- py-spy sampling rate and recording duration
- Analysis document format and structure

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-01 | Operator can identify which subsystems consume the most cycle time under RRUL load via profiling instrumentation | Sub-timer instrumentation in run_cycle(), health endpoint subsystem breakdown, py-spy flamegraph, analysis document with ranked subsystem timings |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| py-spy | 0.4.1 | Sampling profiler for Python, generates SVG flamegraphs | De facto standard for profiling running Python processes without code modification; zero overhead on target (external process) |
| PerfTimer (internal) | N/A | Context manager for timing code blocks | Already used throughout wanctl; perf_counter()-based, DEBUG-level logging |
| OperationProfiler (internal) | N/A | Bounded deque accumulator with percentile stats | Already used for cycle profiling; max_samples prevents memory growth |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| flent | 2.1.1 | Network test tool for generating RRUL load | Load generation during profiling runs |
| pipx | (system) | Install py-spy in isolated environment | Installing py-spy on dev and VM without polluting project venv |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| py-spy | cProfile | cProfile requires code instrumentation and restarts; py-spy attaches live |
| py-spy | scalene | Scalene is heavier, better for memory profiling; py-spy is simpler for CPU flamegraphs |
| Always-on sub-timers | --profile flag gating | User decided always-on (D-02); overhead is negligible (<0.1ms per timer) |

**Installation:**
```bash
# Dev machine
pipx install py-spy

# cake-shaper VM
ssh kevin@10.10.110.223 'pipx install py-spy'
```

## Architecture Patterns

### Current Profiling Architecture (run_cycle)
```
run_cycle() [cycle_start = perf_counter()]
  |
  +-- PerfTimer("autorate_rtt_measurement")     # Subsystem 1: ICMP/RTT
  |     measure_rtt(), handle_icmp_failure()
  |
  +-- PerfTimer("autorate_state_management")    # Subsystem 2: MONOLITHIC (312 lines)
  |     signal_processor.process()
  |     _compute_fused_rtt()
  |     EWMA load/baseline update
  |     spike detection
  |     download.adjust_4state()
  |     upload.adjust()
  |     _check_congestion_alerts()
  |     _check_baseline_drift()
  |     _check_flapping_alerts()
  |     IRTT observation + fusion healer
  |     asymmetry analyzer
  |     IRTT loss alerts
  |     reflector scorer probe
  |     logger.info() decision log
  |     metrics_writer.write_metrics_batch()    # <-- SQLite I/O inside timer
  |     metrics_writer.write_metric() (state transitions)
  |
  +-- PerfTimer("autorate_router_communication") # Subsystem 3: Router API
  |     apply_rate_changes_if_needed()
  |
  +-- _record_profiling()                       # Records to OperationProfiler
  |     (total_ms = perf_counter() - cycle_start)
  |
  +-- save_state()                              # ** NOT PROFILED **
  +-- record_autorate_cycle()                   # ** NOT PROFILED **
  |
  return True
```

### Target Sub-Timer Architecture
```
run_cycle() [cycle_start = perf_counter()]
  |
  +-- PerfTimer("rtt_measurement")              # Subsystem 1 (unchanged)
  |
  +-- PerfTimer("state_management") [OUTER TIMER KEPT for backward compat]
  |   |
  |   +-- PerfTimer("signal_processing")        # Sub-timer 1: process(), fused_rtt
  |   +-- PerfTimer("ewma_update")              # Sub-timer 2: EWMA + spike detection
  |   +-- PerfTimer("congestion_assessment")    # Sub-timer 3: adjust_4state + adjust
  |   +-- PerfTimer("alert_checks")             # Sub-timer 4: congestion/drift/flap alerts
  |   +-- PerfTimer("irtt_observation")         # Sub-timer 5: IRTT + fusion + asymmetry + loss
  |   +-- PerfTimer("metrics_write")            # Sub-timer 6: SQLite batch write
  |
  +-- PerfTimer("router_communication")         # Subsystem 3 (unchanged)
  |
  +-- PerfTimer("post_cycle")                   # NEW: save_state + record_autorate_cycle
  |
  +-- _record_profiling()                       # Extended with all sub-timer keys
```

### Recommended Sub-Timer Boundaries

Based on code analysis of run_cycle() lines 3030-3342:

| Sub-Timer Label | Start Line | End Line | Operations Covered |
|-----------------|-----------|----------|-------------------|
| `signal_processing` | 3033 | 3045 | signal_processor.process(), _compute_fused_rtt(), load_rtt EWMA, _update_baseline_if_idle() |
| `ewma_spike` | 3047 | 3064 | delta_accel spike detection, previous_load_rtt update |
| `congestion_assess` | 3067 | 3090 | download.adjust_4state(), upload.adjust(), _check_congestion/baseline/flapping alerts |
| `irtt_observation` | 3092 | 3187 | IRTT read, protocol correlation, fusion healer, asymmetry analyzer, loss alerts, reflector probe |
| `logging_metrics` | 3189 | 3342 | logger.info(), metrics_writer.write_metrics_batch(), write_metric() |
| `post_cycle` | 3396 | 3418 | save_state(), record_autorate_cycle() -- currently un-profiled gap |

Note: EWMA + spike detection is very lightweight (few arithmetic ops). The user's D-01 mentions "EWMA update, congestion assessment, hysteresis check, tuning rotation, alert engine" but tuning rotation runs on an hourly cadence in the outer daemon loop (line 4593), NOT inside run_cycle(). The sub-timer boundaries should reflect what actually runs per-cycle.

### Health Endpoint Extension

Current `cycle_budget` structure:
```json
{
  "cycle_budget": {
    "cycle_time_ms": {"avg": 69.0, "p95": 120.0, "p99": 369.0},
    "utilization_pct": 138.0,
    "overrun_count": 51000
  }
}
```

Target structure (D-08):
```json
{
  "cycle_budget": {
    "cycle_time_ms": {"avg": 69.0, "p95": 120.0, "p99": 369.0},
    "utilization_pct": 138.0,
    "overrun_count": 51000,
    "subsystems": {
      "rtt_measurement": {"avg": 5.2, "p95": 8.1, "p99": 12.0},
      "signal_processing": {"avg": 1.1, "p95": 1.5, "p99": 2.0},
      "ewma_spike": {"avg": 0.1, "p95": 0.2, "p99": 0.3},
      "congestion_assess": {"avg": 0.5, "p95": 0.8, "p99": 1.2},
      "irtt_observation": {"avg": 0.3, "p95": 0.5, "p99": 0.8},
      "logging_metrics": {"avg": 45.0, "p95": 80.0, "p99": 300.0},
      "router_communication": {"avg": 3.0, "p95": 5.0, "p99": 8.0},
      "post_cycle": {"avg": 2.0, "p95": 4.0, "p99": 6.0}
    }
  }
}
```

### Anti-Patterns to Avoid
- **Nesting PerfTimers without recording sub-timers separately:** The outer `state_management` timer should stay for backward compat, but sub-timers must be individually recorded to OperationProfiler with distinct labels.
- **Using time.time() instead of time.perf_counter():** PerfTimer already uses perf_counter() which is monotonic and high-resolution. Do not mix clock sources.
- **Recording sub-timer labels without a prefix:** Use `autorate_` prefix consistently (e.g., `autorate_signal_processing`) to match the existing pattern in `record_cycle_profiling()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| High-resolution timing | Custom time.time() wrappers | PerfTimer (perf_counter-based) | Already handles context manager, logging, exception safety |
| Stats accumulation | Custom arrays/dicts | OperationProfiler (bounded deques) | Already handles p95/p99, max_samples eviction, report generation |
| Process-level flamegraphs | Custom cProfile + pstats | py-spy record --pid | Attaches to running process, no restart, zero code changes, SVG output |
| Cycle total calculation | Manual summing of sub-timers | Keep outer PerfTimer + record_cycle_profiling() | Avoids accumulated floating-point error from summing 6 sub-timers |

**Key insight:** The existing PerfTimer/OperationProfiler/record_cycle_profiling infrastructure already handles the hard parts (bounded memory, percentile stats, overrun detection, structured logging). Sub-timers are just more instances of the same pattern.

## Common Pitfalls

### Pitfall 1: Profiling Gap Between _record_profiling and End of run_cycle
**What goes wrong:** The current `_record_profiling()` call at line 3390 calculates `total_ms = perf_counter() - cycle_start`, but `save_state()` and `record_autorate_cycle()` execute AFTER this call (lines 3396-3418). These operations are invisible to profiling but consume real cycle budget.
**Why it happens:** The profiling infrastructure was designed around the 3-bucket model and save_state was treated as negligible.
**How to avoid:** Add a `post_cycle` sub-timer wrapping save_state() and record_autorate_cycle(). OR move _record_profiling() to the very end of run_cycle(). The former is cleaner since it preserves the existing profiling call site.
**Warning signs:** Profiled total consistently lower than main loop's elapsed time.

### Pitfall 2: Sub-Timer Overhead Exceeding Budget
**What goes wrong:** Adding 6 PerfTimer instances adds 6 perf_counter() calls per cycle (~0.3us each on Linux = ~1.8us total). Under extreme load this is negligible, but nested timers that accidentally include other timers inflate numbers.
**Why it happens:** Careless nesting where outer timer includes inner timer setup/teardown time.
**How to avoid:** Sub-timers should NOT be nested inside each other -- they should be sequential. The outer `state_management` timer encompasses all sub-timers; sub-timers are siblings, not parent-child.
**Warning signs:** Sum of sub-timers exceeds outer timer.

### Pitfall 3: py-spy Requires Root on Linux for PID Attachment
**What goes wrong:** `py-spy record --pid <PID>` fails with permission denied when run as non-root user.
**Why it happens:** Linux ptrace security restrictions prevent non-root processes from attaching to other processes' memory.
**How to avoid:** Use `sudo py-spy record --pid <PID>` on the cake-shaper VM. Alternatively, set `kernel.yama.ptrace_scope=0` temporarily (revert after profiling).
**Warning signs:** "Permission denied" or "Operation not permitted" errors from py-spy.

### Pitfall 4: MagicMock Guard in _build_cycle_budget
**What goes wrong:** Tests using MagicMock for profiler stats return truthy MagicMock objects that pass dict checks but fail key lookups.
**Why it happens:** The existing `isinstance(stats, dict)` guard in `_build_cycle_budget()` (line 90 of health_check.py) protects against this. New subsystem stats code must replicate this pattern.
**How to avoid:** Always check `isinstance(stats, dict) and "avg_ms" in stats` before accessing stats values. This is the established pattern in the codebase.
**Warning signs:** Tests passing but health endpoint returning garbage or crashing on mock controllers.

### Pitfall 5: Metrics Write Is Likely the Dominant Bottleneck
**What goes wrong:** The SQLite `write_metrics_batch()` call inside the state_management timer writes 8-16 metrics per cycle with JSON serialization and a full transaction (BEGIN/executemany/COMMIT). Under RRUL load, this runs at 14-20Hz with 8-16 rows per call. This is very likely the dominant cost.
**Why it happens:** SQLite write path includes fsync on COMMIT, lock acquisition, and JSON serialization -- all heavyweight for a 50ms budget.
**How to avoid:** This phase is about measurement, not optimization. But be prepared for the finding that metrics_write dominates. Phase 132 will address it.
**Warning signs:** The `logging_metrics` sub-timer showing 40-60ms avg would explain most of the 69ms total.

### Pitfall 6: flent Must Run From Dev Machine
**What goes wrong:** Running flent from the cake-shaper VM would measure VM-internal paths, not the actual WAN path through CAKE.
**Why it happens:** Forgetting the proven methodology from v1.26 testing.
**How to avoid:** Always run flent from the dev machine (per memory `feedback_flent_from_dev_only`). Target is Dallas netperf server (104.200.21.31).
**Warning signs:** Unusually low latency or no CAKE queue activity during "load" test.

## Code Examples

Verified patterns from existing codebase:

### Adding a Sub-Timer (PerfTimer pattern)
```python
# Source: src/wanctl/autorate_continuous.py:2998 (existing pattern)
with PerfTimer("autorate_signal_processing", self.logger) as signal_timer:
    signal_result = self.signal_processor.process(
        raw_rtt=measured_rtt,
        load_rtt=self.load_rtt,
        baseline_rtt=self.baseline_rtt,
    )
    self._last_signal_result = signal_result
    fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
    self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * fused_rtt
    self._update_baseline_if_idle(signal_result.filtered_rtt)
```

### Recording Sub-Timers to OperationProfiler
```python
# Source: src/wanctl/perf_profiler.py:269 (existing pattern in record_cycle_profiling)
# The timings dict already accepts arbitrary keys:
timings = {
    "autorate_rtt_measurement": rtt_ms,
    "autorate_state_management": state_ms,
    "autorate_router_communication": router_ms,
    # NEW sub-timers:
    "autorate_signal_processing": signal_timer.elapsed_ms,
    "autorate_ewma_spike": ewma_timer.elapsed_ms,
    "autorate_congestion_assess": congestion_timer.elapsed_ms,
    "autorate_irtt_observation": irtt_timer.elapsed_ms,
    "autorate_logging_metrics": metrics_timer.elapsed_ms,
    "autorate_post_cycle": post_timer.elapsed_ms,
}
```

### Extending _build_cycle_budget for Subsystems
```python
# Source: src/wanctl/health_check.py:70 (extending existing function)
def _build_cycle_budget(profiler, overrun_count, cycle_interval_ms, total_label):
    stats = profiler.stats(total_label)
    if not isinstance(stats, dict) or "avg_ms" not in stats:
        return None

    result = {
        "cycle_time_ms": {
            "avg": round(stats["avg_ms"], 1),
            "p95": round(stats["p95_ms"], 1),
            "p99": round(stats["p99_ms"], 1),
        },
        "utilization_pct": round((stats["avg_ms"] / cycle_interval_ms) * 100, 1),
        "overrun_count": overrun_count,
    }

    # Per-subsystem breakdown
    subsystem_labels = [
        "autorate_rtt_measurement",
        "autorate_signal_processing",
        "autorate_ewma_spike",
        "autorate_congestion_assess",
        "autorate_irtt_observation",
        "autorate_logging_metrics",
        "autorate_router_communication",
        "autorate_post_cycle",
    ]
    subsystems = {}
    for label in subsystem_labels:
        sub_stats = profiler.stats(label)
        if isinstance(sub_stats, dict) and "avg_ms" in sub_stats:
            short_name = label.replace("autorate_", "")
            subsystems[short_name] = {
                "avg": round(sub_stats["avg_ms"], 1),
                "p95": round(sub_stats["p95_ms"], 1),
                "p99": round(sub_stats["p99_ms"], 1),
            }
    if subsystems:
        result["subsystems"] = subsystems

    return result
```

### py-spy Flamegraph Capture
```bash
# On cake-shaper VM (10.10.110.223):
# 1. Find wanctl PID
PID=$(pgrep -f 'wanctl.*spectrum' | head -1)

# 2. Record 30s flamegraph at 100Hz sampling (default)
sudo py-spy record -o /tmp/wanctl-rrul-profile.svg --pid $PID --duration 30

# 3. Or with higher sampling rate for short captures
sudo py-spy record -o /tmp/wanctl-rrul-profile.svg --pid $PID --duration 30 --rate 200

# 4. Copy flamegraph to dev machine
scp kevin@10.10.110.223:/tmp/wanctl-rrul-profile.svg .
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 3-bucket profiling (rtt/state/router) | 3-bucket + sub-timers within state_management | Phase 131 (this phase) | Identifies specific bottleneck within the 312-line state_management block |
| Manual timing with time.time() | PerfTimer with perf_counter() | Phase 49 (v1.9) | 10-100x higher precision, not affected by system clock adjustments |
| No flamegraph capability | py-spy SVG flamegraphs | Phase 131 (this phase) | Per-function drill-down without code modification |

**Key context from v1.26 testing:**
- 138% utilization = avg 69ms on 50ms cycle
- 51,000 overruns during RRUL load
- p99 of 369ms indicates severe occasional spikes
- This was measured on linux-cake transport (not REST API)

## Open Questions

1. **What portion of the 69ms average is SQLite metrics writing?**
   - What we know: write_metrics_batch() writes 8-16 rows per cycle with JSON serialization and transaction commit inside the state_management timer
   - What's unclear: actual wall-clock cost of SQLite I/O under 20Hz write load
   - Recommendation: Sub-timers will answer this definitively. Hypothesis: metrics_write is 40-60ms (majority of budget)

2. **Does save_state() contribute significantly to overruns?**
   - What we know: save_state() uses atomic_write_json() (temp file + fsync + rename) and runs every cycle. Currently un-profiled.
   - What's unclear: cost under load, especially when force=True every FORCE_SAVE_INTERVAL_CYCLES
   - Recommendation: post_cycle sub-timer will capture this

3. **Is the p99 of 369ms caused by periodic maintenance or I/O spikes?**
   - What we know: Hourly maintenance runs cleanup + downsample + VACUUM. SQLite WAL checkpointing can cause I/O stalls.
   - What's unclear: Whether the p99 correlates with maintenance windows or random I/O contention
   - Recommendation: py-spy flamegraph during a spike event would reveal this; periodic report timestamps can correlate

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| py-spy | D-03, D-04 flamegraph | Not installed | -- | Install via pipx (D-05) |
| flent | D-06 load generation | Available | 2.1.1 | -- |
| Python 3.12 | Runtime | Available | 3.12.3 | -- |
| pipx | D-05 py-spy install | Available | (system) | pip install --user |
| SSH to cake-shaper VM | D-04 py-spy attachment | Available (10.10.110.223) | -- | -- |
| Dallas netperf server | D-06 flent target | Available (104.200.21.31) | -- | -- |

**Missing dependencies with no fallback:**
- None

**Missing dependencies with fallback:**
- py-spy: not installed on dev or VM -- plan must include installation step (pipx install py-spy)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_perf_profiler.py tests/test_health_check.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-01a | Sub-timers recorded to OperationProfiler with correct labels | unit | `.venv/bin/pytest tests/test_perf_profiler.py -x -v` | Exists (extend) |
| PERF-01b | _build_cycle_budget returns subsystems dict with per-timer stats | unit | `.venv/bin/pytest tests/test_health_check.py::TestBuildCycleBudget -x -v` | Exists (extend) |
| PERF-01c | _record_profiling passes sub-timer keys through to profiler | unit | `.venv/bin/pytest tests/test_perf_profiler.py -x -v` | Exists (extend) |
| PERF-01d | Health endpoint JSON includes subsystems breakdown | unit | `.venv/bin/pytest tests/test_health_check.py -x -v` | Exists (extend) |
| PERF-01e | py-spy flamegraph generated under RRUL load | manual | `sudo py-spy record --pid <PID> -o /tmp/profile.svg --duration 30` | N/A (manual) |
| PERF-01f | Analysis document with top-3 consumers and recommendation | manual | Review document in .planning/ | N/A (manual) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_perf_profiler.py tests/test_health_check.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before /gsd:verify-work

### Wave 0 Gaps
- None -- existing test infrastructure (test_perf_profiler.py, test_health_check.py) covers profiling and health endpoint. Tests need extension for new sub-timer labels and subsystems dict, not new files.

## Project Constraints (from CLAUDE.md)

- **Conservative changes:** Production network control system. Explain before changing.
- **Never refactor core logic:** Sub-timers are instrumentation ONLY -- zero behavioral changes to control loop.
- **Priority:** stability > safety > clarity > elegance
- **No full test suite for config-only changes** (memory feedback) -- but this phase IS code changes, so tests required.
- **flent from dev machine only** -- never from cake-shaper VM.
- **Verify CAKE qdiscs active** before production profiling runs.
- **Run project-finalizer before commits** (MANDATORY per CLAUDE.md).
- **Dev commands:** `.venv/bin/pytest`, `.venv/bin/ruff check`, `.venv/bin/mypy` (not system python).

## Sources

### Primary (HIGH confidence)
- `src/wanctl/perf_profiler.py` -- Full read of PerfTimer, OperationProfiler, record_cycle_profiling
- `src/wanctl/autorate_continuous.py:2963-3420` -- Full read of _record_profiling, run_cycle, post-cycle operations
- `src/wanctl/health_check.py:70-101` -- Full read of _build_cycle_budget
- `src/wanctl/storage/writer.py:155-229` -- Full read of write_metric, write_metrics_batch
- `docs/CABLE_TUNING.md` -- Source of 138% utilization finding
- `docs/PRODUCTION_INTERVAL.md` -- Original 50ms interval decision and profiling baseline

### Secondary (MEDIUM confidence)
- [py-spy GitHub README](https://github.com/benfred/py-spy) -- Version 0.4.1, installation, usage, permissions
- py-spy web documentation -- confirmed sudo requirement on Linux for PID attachment

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools (PerfTimer, OperationProfiler, py-spy, flent) verified via direct code reading or official docs
- Architecture: HIGH -- sub-timer boundaries based on direct reading of run_cycle() source code (312 lines mapped)
- Pitfalls: HIGH -- profiling gap (save_state un-profiled), SQLite hypothesis, and permission requirements all derived from code analysis

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable domain, internal codebase)
