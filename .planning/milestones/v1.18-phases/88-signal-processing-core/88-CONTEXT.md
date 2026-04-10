# Phase 88: Signal Processing Core - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

RTT measurements are filtered, tracked, and annotated with quality metadata before reaching the control loop. Delivers a Hampel outlier filter, jitter tracker, confidence score, and variance EWMA -- all as a pre-EWMA signal processing stage in the autorate daemon. Operates in observation mode: signal processing DOES affect EWMA input (filtered RTT replaces outliers), but does NOT alter congestion state transitions, rate adjustments, or alerting logic.

</domain>

<decisions>
## Implementation Decisions

### Hampel Filter Behavior
- Outlier RTT samples are replaced with rolling window median before passing to EWMA
- Both raw and filtered RTT values are stored in SignalResult for metrics/logging
- YAML-configurable parameters under `signal_processing.hampel:` section (window_size: 7, sigma_threshold: 3.0 as defaults)
- Rolling outlier rate tracked: outlier_rate (percentage of recent window), total_outliers (lifetime count), consecutive_outliers
- Warm-up period: pass through raw RTT unfiltered until window has enough samples (7 cycles = 350ms), log at DEBUG

### Signal Processor Architecture
- Pre-EWMA filter position: raw RTT -> SignalProcessor.process() -> filtered_rtt -> existing update_ewma()
- SignalResult frozen dataclass (slots=True) returned from process(): filtered_rtt, raw_rtt, jitter_ms, variance_ms2, confidence, is_outlier, outlier_rate, warming_up
- Per-WAN SignalProcessor instance, instantiated in WANController.__init__() with its own independent state (Hampel window, jitter EWMA, variance EWMA)
- No state persistence across daemon restarts -- warm-up is 350ms, negligible
- New module: `src/wanctl/signal_processing.py` (standalone, imported by autorate_continuous.py)

### Jitter & Variance Tracking
- Configurable EWMA alpha via time_constant_sec (matching existing load_rtt pattern), not strict RFC 3550 fixed alpha
- Default time constants: jitter 2.0s (alpha=0.025), variance 5.0s (alpha=0.01)
- Jitter computed from RAW RTT samples (not filtered) -- reflects true network behavior including spikes
- Variance computed from RAW RTT samples -- squared deviation of raw_rtt from load_rtt EWMA mean
- Confidence score: variance-based 0-1 scale: `1.0 / (1.0 + variance / baseline^2)` -- high=stable, low=noisy

### Observation Mode Boundaries
- Filtered RTT DOES feed into EWMA (Hampel replacement is the value of signal processing)
- Signal processing DOES NOT alter congestion state transitions, rate adjustments, or alerting
- Confidence, jitter, variance are computed and logged but do not gate any control decisions
- Always active -- no enable/disable flag. Zero config change needed to activate on deploy. If signal_processing YAML section is omitted, all defaults used.
- SQLite persistence and health endpoint exposure deferred to Phase 92 (Observability)
- Per-cycle signal results logged at DEBUG; outlier events logged at INFO with raw/replaced values and outlier_rate

### Claude's Discretion
- Exact SignalResult field naming beyond the core fields discussed
- Internal data structure choices (deque sizing, EWMA initialization values)
- Test organization and fixture design
- DEBUG log message formatting details
- Alpha calculation implementation (reuse existing utility or inline)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Signal processing integration
- `src/wanctl/autorate_continuous.py` -- WANController class, update_ewma() method (~line 1247), run_cycle() RTT measurement subsystem (~line 1611), state management subsystem (~line 1643)
- `src/wanctl/rtt_measurement.py` -- RTTMeasurement class, ping_host() method, aggregation strategies

### Existing EWMA patterns
- `src/wanctl/autorate_continuous.py` lines 365-415 -- Alpha calculation from time_constant_sec at 50ms cycle interval
- `src/wanctl/baseline_rtt_manager.py` -- Baseline EWMA logic, frozen-during-load pattern

### Config patterns
- `src/wanctl/autorate_config.py` -- YAML config loading, section parsing, defaults
- `docs/CONFIG_SCHEMA.md` -- Configuration reference (add signal_processing section)

### Metrics integration (Phase 92)
- `src/wanctl/storage/schema.py` -- SQLite schema, metric_name conventions
- `src/wanctl/storage/writer.py` -- MetricsWriter singleton, write_metrics_batch() pattern
- `src/wanctl/health_check.py` -- Health endpoint response structure

### Project architecture
- `docs/PORTABLE_CONTROLLER_ARCHITECTURE.md` -- Link-agnostic design principles
- `.planning/REQUIREMENTS.md` -- SIGP-01 through SIGP-06 requirements

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Alpha-from-time-constant calculation (autorate_continuous.py:365-415): Reuse for jitter/variance EWMA alpha derivation
- Acceleration detection pattern (autorate_continuous.py:1649-1661): Shows where raw RTT spike detection currently lives -- signal processor replaces this role
- EWMA bounds validation (steering/congestion_assessment.py:125-156): NaN/Inf guard pattern applicable to signal processing math

### Established Patterns
- Two-track EWMA (fast load_rtt + slow baseline_rtt): Signal processor sits before the fast track, baseline logic untouched
- Frozen dataclasses with slots for data transfer (used in alerting, steering)
- Per-WAN instance pattern (WANController owns all per-WAN state)
- Config section with defaults (alerting, wan_state patterns): signal_processing follows same YAML section pattern
- Warn+disable for invalid config: Apply same pattern if signal_processing config is malformed

### Integration Points
- WANController.__init__(): Instantiate SignalProcessor with config and wan_name
- run_cycle() after RTT measurement, before update_ewma(): Call signal_processor.process(raw_rtt)
- update_ewma(): Receives result.filtered_rtt instead of raw measured_rtt
- Metrics batch (run_cycle ~line 1700): SignalResult available for Phase 92 metrics addition

</code_context>

<specifics>
## Specific Ideas

- Confidence formula `1.0 / (1.0 + variance / baseline^2)` chosen for interpretability: >0.8 = stable link, 0.5-0.8 = moderate noise, <0.5 = unreliable
- Jitter and variance both computed from RAW samples deliberately -- they reflect true network quality, not post-filter quality
- Hampel outlier INFO log includes raw value, replacement median, and rolling outlier_rate for operator visibility
- signal_processing YAML section is optional -- all defaults work without any config changes on existing deployments

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 88-signal-processing-core*
*Context gathered: 2026-03-16*
