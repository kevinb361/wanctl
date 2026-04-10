# Phase 93: Reflector Quality Scoring - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Rolling quality scores for each configured `ping_host` reflector based on measured success rate. Low-scoring reflectors are automatically skipped during RTT measurement, with periodic recovery probes. Per-reflector scores are visible in the health endpoint and deprioritization/recovery events are persisted to SQLite. This phase does NOT change congestion control logic, EWMA, or state transitions -- it only filters which reflectors participate in `measure_rtt()`.

</domain>

<decisions>
## Implementation Decisions

### Scoring model
- Quality score is **success rate** (0.0-1.0) -- fraction of successful pings over a rolling window
- Only signal is success/failure of each ping attempt -- no per-reflector jitter or RTT deviation tracking
- Rolling window is **count-based** (e.g., last 50 measurement attempts per reflector) using a deque
- Score is raw ratio (success_count / window_size), not mapped to discrete grades
- Single **global threshold** configurable via YAML (e.g., `reflector_quality.min_score: 0.8`)
- No per-reflector threshold overrides

### Deprioritization behavior
- Deprioritized reflectors are **skipped entirely** -- removed from the active set for `measure_rtt()`
- If **all reflectors** are deprioritized, **force-use the best-scoring one** (never have zero targets)
- Forced-use logs a WARNING (matches ICMP blackout resilience pattern from v1.1)
- **Graceful degradation** for median-of-three mode: 3 healthy = median-of-3, 2 healthy = average-of-2, 1 healthy = single ping, 0 healthy = force best-scoring
- Deprioritization transitions logged at **WARNING** level
- Recovery transitions logged at **INFO** level

### Recovery mechanism
- **Periodic probe pings** to deprioritized reflectors on a configurable interval (default 30 seconds)
- Probe is a single ICMP ping via existing `RTTMeasurement.ping_host()`
- Recovery requires **sustained improvement**: N consecutive successful probes (configurable, default 3)
- Probe results update the reflector's score normally
- YAML config: `reflector_quality.probe_interval_sec` (default 30), `reflector_quality.recovery_count` (default 3)

### Health endpoint
- New **top-level `reflector_quality` section** in health response (peer to `signal_quality` and `irtt`)
- **Per-host detail**: each reflector gets an entry with score, status (active/deprioritized), and measurement count
- Example: `{"8.8.8.8": {"score": 0.94, "status": "active", "measurements": 50}}`
- Section is **always present** regardless of reflector count (matches signal_quality always-present pattern)
- Includes `available: true` and standard availability pattern from v1.18

### SQLite persistence
- **Event-based** writes: one row per deprioritization or recovery event (not per-cycle)
- Low write volume -- reflector transitions are infrequent
- Enables "which reflectors have been flaky?" operational queries
- Follows alerting SQLite persistence pattern from v1.15

### Claude's Discretion
- Exact deque size for rolling window (50 suggested, Claude can adjust based on measurement frequency analysis)
- Internal class/module structure for ReflectorScorer or similar
- How probe timer integrates with the 50ms cycle loop (monotonic clock check vs separate timer)
- Whether to add a `reflector_quality` YAML section or extend `continuous_monitoring`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### RTT measurement infrastructure
- `src/wanctl/rtt_measurement.py` -- RTTMeasurement class with ping_host() and ping_hosts_concurrent() methods; this is where reflector pings originate
- `src/wanctl/autorate_continuous.py` lines 1412-1441 -- measure_rtt() method that selects reflectors and aggregates RTT; primary integration point for reflector scoring

### Signal processing (parallel pattern)
- `src/wanctl/signal_processing.py` -- SignalProcessor with rolling window deque, outlier tracking, and frozen dataclass result pattern; model for per-reflector state tracking

### Health endpoint
- `src/wanctl/health_check.py` -- Autorate health endpoint; add reflector_quality section here following signal_quality pattern

### Configuration
- `src/wanctl/autorate_continuous.py` lines 280, 445 -- ping_hosts config loading from continuous_monitoring section
- `src/wanctl/config_base.py` -- BaseConfig and validate_ping_host(); config validation patterns

### Alerting persistence pattern
- `src/wanctl/alerting/engine.py` -- AlertEngine with SQLite event-based persistence; model for reflector transition persistence

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RTTMeasurement.ping_host()`: Already used for single reflector pings -- reuse for recovery probes
- `RTTMeasurement.ping_hosts_concurrent()`: Concurrent pinging with ThreadPoolExecutor -- current multi-reflector path
- `SignalProcessor` pattern: deque-based rolling windows, frozen dataclass results, per-WAN instantiation
- `AlertEngine` SQLite pattern: event-based persistence with fire_count and cooldown

### Established Patterns
- **Frozen dataclass for results**: SignalResult pattern -- use for per-reflector quality snapshots
- **Always-present health sections**: signal_quality uses available/reason even when warming up
- **Per-WAN state**: SignalProcessor is instantiated per-WAN -- reflector scorer should be too
- **Config with defaults**: `config.get("key", default)` pattern throughout signal_processing.py
- **WARNING for abnormal, INFO for recovery**: matches alerting log patterns

### Integration Points
- `WANController.__init__()`: Where ReflectorScorer would be instantiated (alongside SignalProcessor)
- `WANController.measure_rtt()`: Primary integration -- filter ping_hosts through active reflector set
- `WANController.run_cycle()`: Where probe timing would be checked (monotonic clock comparison)
- `_build_health_response()`: Where reflector_quality section gets added to health endpoint
- `MetricsWriter`: For SQLite event persistence (existing table creation pattern)

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 93-reflector-quality-scoring*
*Context gathered: 2026-03-17*
