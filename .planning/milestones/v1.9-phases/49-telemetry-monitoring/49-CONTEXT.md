# Phase 49: Telemetry & Monitoring — Context

## Phase Goal

Expose cycle budget metrics via health endpoints and structured logs for ongoing production visibility.

## Requirements

- **PROF-03**: Cycle budget visibility in health endpoints
- **TELM-01**: Structured telemetry logging per cycle
- **TELM-02**: Steering daemon parity (same telemetry as autorate)

## Success Criteria

1. Health endpoint JSON includes `cycle_time_ms` (avg, P95, P99), `utilization_pct`, and `overrun_count`
2. Structured log entries include per-subsystem timing breakdowns at DEBUG level
3. Telemetry overhead <0.5ms per cycle
4. Steering daemon health endpoint (port 9102) includes same telemetry as autorate (port 9101)

## Decisions

### D1: Health telemetry placement — Per-WAN

Cycle budget telemetry lives inside each WAN object in the autorate health response. Each `WANController` has its own `OperationProfiler`, so per-WAN placement reflects the actual data ownership.

For steering (single daemon), `cycle_budget` goes at the top level.

```json
// Autorate (port 9101)
{
  "wans": [{
    "name": "spectrum",
    "cycle_budget": {
      "cycle_time_ms": { "avg": 37.6, "p95": 42.1, "p99": 48.3 },
      "utilization_pct": 75.2,
      "overrun_count": 47
    }
  }]
}

// Steering (port 9102)
{
  "cycle_budget": {
    "cycle_time_ms": { "avg": 29.0, "p95": 31.5, "p99": 34.2 },
    "utilization_pct": 58.0,
    "overrun_count": 2
  }
}
```

### D2: Health telemetry detail — Totals only

Health endpoint shows `cycle_time_ms`, `utilization_pct`, `overrun_count`. No per-subsystem breakdown in health JSON. Per-subsystem detail remains available via `--profile` INFO logs.

### D3: Overrun counter — Cumulative since startup

`overrun_count` is a monotonically increasing counter that resets only on daemon restart. Prometheus-style — consumers derive rate via `delta(count) / delta(time)`.

### D4: Overrun threshold — cycle_interval

An overrun is defined as `cycle_total_ms > self.cycle_interval_ms` (50ms by default). Portable across deployments with different intervals.

### D5: Utilization calculation — Windowed average

`utilization_pct = (avg_cycle_time / cycle_interval) * 100` where `avg_cycle_time` comes from the profiler's 1200-sample window (~60s at 50ms interval).

### D6: Structured log frequency — Every cycle at DEBUG

Per-subsystem timing logged every cycle at DEBUG level. Fields: `cycle_total_ms`, `rtt_measurement_ms`, `state_management_ms`, `router_communication_ms` (autorate) or `cake_stats_ms` (steering), plus `overrun: bool`.

### D7: Overrun log level — WARNING with rate limiting

Overrun events logged at WARNING level (visible in production). Rate-limited following the existing pattern: 1st, 3rd, then every 10th occurrence. Recovery event also logged as WARNING with total overrun count and duration.

### D8: Telemetry activation — Always-on

Health endpoint telemetry is always available. The `OperationProfiler` already records every cycle regardless of `--profile` flag. Health handler calls `profiler.stats()` on request — zero per-cycle overhead, ~0.1ms compute on `/health` request.

### D9: Cold start — Omit section

`cycle_budget` key is not included in health response until the profiler has recorded at least one cycle. Matches the steering health pattern (cold start omits `steering` section). No nulls or zeros.

## Code Context

### Integration Points

| Component | File | Key Location |
|-----------|------|-------------|
| Autorate health handler | `src/wanctl/health_check.py` | `_get_health_status()` — add cycle_budget to each WAN dict |
| Steering health handler | `src/wanctl/steering/health.py` | `_get_health_status()` — add cycle_budget at top level |
| Autorate profiler access | `src/wanctl/autorate_continuous.py` | `WANController._profiler` (OperationProfiler instance) |
| Steering profiler access | `src/wanctl/steering/daemon.py` | `SteeringDaemon._profiler` (OperationProfiler instance) |
| Profiler stats API | `src/wanctl/perf_profiler.py` | `OperationProfiler.stats(label)` returns `{count, min_ms, max_ms, avg_ms, p95_ms, p99_ms}` |
| JSON structured logging | `src/wanctl/logging_utils.py` | `JSONFormatter` — already supports `extra={}` kwargs |
| Existing rate-limit pattern | `src/wanctl/autorate_continuous.py` | Router error rate-limited logging (1st, 3rd, every 10th) |

### Profiler Labels (fixed from Phase 47)

**Autorate:** `autorate_rtt_measurement`, `autorate_state_management`, `autorate_router_communication`, `autorate_cycle_total`

**Steering:** `steering_cake_stats`, `steering_rtt_measurement`, `steering_state_management`, `steering_cycle_total`

### Overrun Counter Location

New instance variable on both `WANController` and `SteeringDaemon`: `self._overrun_count = 0`. Incremented in `_record_profiling()` when `total_ms > self.cycle_interval_ms`. Exposed to health handler alongside profiler reference.

### Health Handler Access Pattern

Health handlers need access to the profiler and overrun counter. Current pattern: autorate health handler receives WAN state via `_build_wan_status()` method. Steering health handler reads daemon state dict directly. Both will need profiler access added.

## Deferred Ideas

- Per-subsystem breakdown in health endpoint (could add later if monitoring needs grow)
- Profiling data persistence to SQLite (like metrics — would enable historical cycle budget queries)
- `/profile` dedicated endpoint for live profiling (separate from `/health`)

## Constraints

- Overhead must be <0.5ms per cycle (success criterion 3)
- No new dependencies — use existing OperationProfiler and JSONFormatter
- Backward compatible — existing health JSON consumers must not break (new keys only)
- Both daemons get identical telemetry structure (success criterion 4)
