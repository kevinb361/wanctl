# Phase 90: IRTT Daemon Integration - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

IRTT measurements run continuously in a background daemon thread and are consumed by the autorate daemon each cycle without blocking. Delivers an IRTTThread class (background measurement loop with interruptible sleep), lock-free cache sharing via frozen dataclass, loss direction availability via cached result, and ICMP vs UDP protocol correlation with deprioritization detection. All in observation mode -- metrics and logs only, no congestion control changes.

</domain>

<decisions>
## Implementation Decisions

### Thread Lifecycle & Ownership
- Thread owned by ContinuousAutoRate (top-level daemon), started in main() alongside metrics/health servers
- One IRTT thread serves both WANs (measures single path per server)
- New module: `src/wanctl/irtt_thread.py` (separate from irtt_measurement.py -- clean separation of measurement logic vs threading)
- IRTTThread class: constructor takes IRTTMeasurement, cadence_sec, shutdown_event, logger
- start() / stop() methods. stop() signals shutdown event + join(5s timeout)
- Interruptible sleep via `shutdown_event.wait(timeout=cadence_sec)` -- thread wakes instantly on SIGTERM
- Thread runs as daemon thread (daemon=True)
- Started after daemon init, stopped in main() finally block (before connection cleanup)
- Cadence configurable via existing `irtt:` YAML section: `cadence_sec` key, default 10

### Cache Sharing Model
- Lock-free: frozen IRTTResult assignment is atomic under CPython GIL
- `self._cached_result: IRTTResult | None = None` on IRTTThread
- `get_latest() -> IRTTResult | None` returns the cached result directly
- Main loop reads each 50ms cycle -- zero blocking, zero lock contention
- Worst case: reads stale result (up to 10s old) -- acceptable for supplemental data
- Staleness computed by caller: `age_sec = time.monotonic() - result.timestamp` (timestamp already in IRTTResult)
- Result stored on IRTTThread, WANController accesses via reference to the thread

### run_cycle() Integration
- Read cached IRTT result each cycle after RTT measurement
- Log at DEBUG: RTT, IPDV, loss_up%, loss_down%
- Do NOT feed into congestion control -- observation mode only
- Result available for Phase 92 metrics persistence

### Loss Direction Tracking (IRTT-06)
- Existing IRTTResult fields `send_loss` (upstream %) and `receive_loss` (downstream %) are sufficient
- No additional interpretation logic needed -- raw percentages in cached result satisfy IRTT-06
- Interpretation (thresholds, enums) deferred to v1.19+ fusion
- Phase 92 will persist these values for trend analysis

### ICMP vs UDP Correlation (IRTT-07)
- Simple ratio per measurement: `ratio = icmp_rtt / irtt_rtt`
- Computed in WANController.run_cycle() where both load_rtt (ICMP) and cached irtt_result (UDP) are available
- Stored as `self._irtt_correlation: float | None` on WANController for Phase 92 health endpoint
- Deprioritization thresholds: ratio > 1.5 = ICMP deprioritized, ratio < 0.67 = UDP deprioritized
- First detection logged at INFO (with raw values and interpretation), subsequent at DEBUG, recovery at INFO
- Same first-detection/repeat-at-DEBUG log pattern as IRTT failure logging (Phase 89)
- Guards: only compute when both irtt_result.rtt_mean_ms > 0 and load_rtt > 0

### Claude's Discretion
- IRTTThread internal method naming and organization
- Exception handling inside the background thread loop
- Test fixture design for threading tests (mock threading.Event, mock IRTTMeasurement)
- DEBUG log format for per-cycle IRTT reporting
- Whether correlation check runs every cycle or only when IRTT result is new

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### IRTT measurement (Phase 89)
- `src/wanctl/irtt_measurement.py` -- IRTTMeasurement class, measure() -> IRTTResult | None, is_available()
- `src/wanctl/irtt_measurement.py` -- IRTTResult frozen dataclass (11 fields including timestamp, send_loss, receive_loss)

### Threading patterns
- `src/wanctl/webhook_delivery.py` -- Background daemon thread pattern (fire-and-forget, daemon=True)
- `src/wanctl/metrics.py` -- Persistent background thread pattern (MetricsServer)
- `src/wanctl/signal_utils.py` -- get_shutdown_event(), is_shutdown_requested(), threading.Event coordination

### Daemon lifecycle
- `src/wanctl/autorate_continuous.py` lines 2787-2893 -- main() startup, main loop, finally block (shutdown sequence)
- `src/wanctl/autorate_continuous.py` WANController.__init__() -- where per-WAN state is initialized
- `src/wanctl/autorate_continuous.py` WANController.run_cycle() -- where cached result is read each 50ms cycle

### Config
- `src/wanctl/autorate_continuous.py` _load_irtt_config() -- existing IRTT config loader (add cadence_sec)
- `docs/CONFIG_SCHEMA.md` -- IRTT section documentation (add cadence_sec)

### Requirements
- `.planning/REQUIREMENTS.md` -- IRTT-02, IRTT-03, IRTT-06, IRTT-07

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `signal_utils.get_shutdown_event()` -- returns threading.Event for interruptible sleep in background thread
- `webhook_delivery.py` threading pattern -- daemon=True, exception catching in thread loop, start/stop lifecycle
- `metrics.py` MetricsServer -- persistent background thread with join(timeout=5) shutdown
- IRTTMeasurement.measure() -- already handles all failure modes, returns None on any error

### Established Patterns
- Frozen dataclass for thread-safe cache sharing (SignalResult, IRTTResult)
- shutdown_event.wait(timeout=N) for interruptible sleep
- daemon=True threads that don't prevent process exit
- First-failure-WARNING/repeat-at-DEBUG log pattern (IRTTMeasurement)
- Per-cycle DEBUG logging with structured format (signal processing pattern)

### Integration Points
- ContinuousAutoRate main(): start IRTTThread after health server, stop in finally block
- _load_irtt_config(): add cadence_sec field (default 10)
- WANController.__init__(): receive IRTTThread reference
- WANController.run_cycle(): read cached result, compute correlation, log

</code_context>

<specifics>
## Specific Ideas

- Lock-free caching deliberately chosen over threading.Lock: frozen dataclass assignment is atomic under CPython GIL, and the 50ms hot path should have zero lock contention for supplemental data that changes every 10s
- Protocol correlation ratio is a simple, interpretable metric: 1.0 = equal, >1.5 = ICMP throttled, <0.67 = UDP throttled. Easy to explain to operators.
- Thread lifecycle matches existing server patterns: start in main() init sequence, stop in finally block with timeout, daemon=True as safety net
- IRTTThread is a thin coordinator: all measurement complexity lives in IRTTMeasurement (Phase 89). Thread just calls measure() on a schedule and caches the result.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 90-irtt-daemon-integration*
*Context gathered: 2026-03-16*
