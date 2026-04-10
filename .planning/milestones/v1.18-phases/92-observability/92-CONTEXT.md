# Phase 92: Observability - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Signal quality and IRTT data are visible in health endpoints and persisted in SQLite for trend analysis. Delivers two new health endpoint sections (signal_quality and irtt per WAN), four signal quality SQLite metrics written per cycle, four IRTT SQLite metrics written per measurement, and STORED_METRICS schema updates. This is the final v1.18 phase — it ties together all the observational data from Phases 88-90 into queryable, monitorable form.

</domain>

<decisions>
## Implementation Decisions

### Health Endpoint — signal_quality Section (OBSV-01)
- Per-WAN section inside each WAN's health object (alongside cycle_budget)
- Fields: jitter_ms, variance_ms2, confidence, outlier_rate, total_outliers, warming_up
- Skip internal fields: is_outlier, consecutive_outliers, filtered_rtt, raw_rtt (per-cycle noise, not monitoring-relevant)
- During warm-up: include section with warming_up: true and initial values (0.0 jitter, 1.0 confidence)
- When signal_result is None (shouldn't happen — always active): omit section

### Health Endpoint — irtt Section (OBSV-02)
- Per-WAN section (same level as signal_quality) — even though one IRTT thread, protocol_correlation differs per WAN
- Fields: rtt_mean_ms, ipdv_ms, loss_up_pct, loss_down_pct, server (formatted as "host:port"), staleness_sec, protocol_correlation, available
- Always include section: available: false with reason when disabled; available: true with null values when awaiting first measurement; full data when working
- Staleness computed from result.timestamp via time.monotonic()
- protocol_correlation from WANController._irtt_correlation (may be None if stale or unavailable)
- reason field: "disabled" | "binary_not_found" | "awaiting_first_measurement" | omitted when working

### SQLite Metric Naming (OBSV-03, OBSV-04)
- Signal quality metrics (wanctl_signal_* prefix):
  - wanctl_signal_jitter_ms
  - wanctl_signal_variance_ms2
  - wanctl_signal_confidence
  - wanctl_signal_outlier_count
- IRTT metrics (wanctl_irtt_* prefix):
  - wanctl_irtt_rtt_ms
  - wanctl_irtt_ipdv_ms
  - wanctl_irtt_loss_up_pct
  - wanctl_irtt_loss_down_pct
- All added to STORED_METRICS dict in storage/schema.py
- No schema migration needed — metrics table is generic (metric_name TEXT, value REAL)

### Write Cadence
- Signal quality metrics: write EVERY cycle (50ms) — values change every cycle (jitter, variance update per sample)
  - 4 metrics × 20 cycles/sec = 80 rows/sec (consistent with existing rtt/rate metrics)
- IRTT metrics: write ONLY when a new measurement arrives — track last-written timestamp, compare with irtt_result.timestamp
  - 4 metrics × 0.1 measurements/sec = 0.4 rows/sec
  - Prevents 200x duplication (10s measurement / 50ms cycle)

### Staleness Handling
- IRTT health section always present with available flag and reason
- signal_quality always present (signal processing is always active) with warming_up flag during first 7 cycles
- IRTT staleness_sec shows how old the cached result is
- IRTT protocol_correlation is None when result is stale (>3x cadence) or unavailable

### Claude's Discretion
- Exact health endpoint dict construction (follow cycle_budget pattern)
- isinstance guards for MagicMock safety in health endpoint
- Test fixture design for health endpoint tests
- Whether to round metric values in SQLite (or store full precision)
- Exact placement of metrics batch extension in run_cycle()

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Health endpoint
- `src/wanctl/health_check.py` lines 166-189 -- Per-WAN health building, cycle_budget optional section pattern
- `src/wanctl/health_check.py` lines 194-209 -- AlertEngine isinstance guard pattern for MagicMock safety
- `src/wanctl/steering/health.py` -- Steering health endpoint (similar pattern, has wan_awareness section)

### Signal quality data
- `src/wanctl/signal_processing.py` lines 39-65 -- SignalResult frozen dataclass (10 fields)
- `src/wanctl/autorate_continuous.py` line 1896 -- Where signal_result is cached on WANController

### IRTT data
- `src/wanctl/irtt_measurement.py` lines 22-40 -- IRTTResult frozen dataclass (11 fields)
- `src/wanctl/irtt_thread.py` lines 46-48 -- get_latest() method
- `src/wanctl/autorate_continuous.py` line 1940 -- Where IRTT result is read in run_cycle()

### Metrics persistence
- `src/wanctl/storage/schema.py` lines 11-22 -- STORED_METRICS dict (add new entries)
- `src/wanctl/storage/writer.py` lines 193-228 -- write_metrics_batch() interface
- `src/wanctl/autorate_continuous.py` lines 1971-2008 -- Current metrics batch construction in run_cycle()

### Requirements
- `.planning/REQUIREMENTS.md` -- OBSV-01, OBSV-02, OBSV-03, OBSV-04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- cycle_budget optional section pattern in health_check.py: `if value is not None: wan_health["section"] = {...}`
- AlertEngine isinstance guard: protects against MagicMock in test environments
- metrics_batch tuple format: `(timestamp, wan_name, metric_name, value, labels_dict, granularity)`
- STORED_METRICS dict: just add new metric name -> description entries, no schema changes

### Established Patterns
- Per-WAN health sections (download, upload, router_connectivity, cycle_budget)
- Optional section inclusion via None checks
- Metrics batch extension with `metrics_batch.extend([...])`
- Rounding in health: `round(value, 2)` for display, full precision in SQLite

### Integration Points
- health_check.py `_get_health_status()`: add signal_quality and irtt sections per WAN
- autorate_continuous.py run_cycle() metrics batch: extend with signal quality metrics (every cycle) and IRTT metrics (on new measurement only)
- storage/schema.py STORED_METRICS: add 8 new metric entries

</code_context>

<specifics>
## Specific Ideas

- IRTT health section always present with available/reason is deliberately chosen over omission — operators checking health endpoint should immediately see whether IRTT is configured, not wonder if it's missing
- Signal quality warming_up flag lets operators know the Hampel filter is initializing without hiding the section entirely
- IRTT write-on-new-measurement prevents 200x SQLite row duplication — critical for storage efficiency at 20Hz cycle rate
- protocol_correlation in health endpoint gives operators a single number to assess ISP protocol fairness

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 92-observability*
*Context gathered: 2026-03-17*
