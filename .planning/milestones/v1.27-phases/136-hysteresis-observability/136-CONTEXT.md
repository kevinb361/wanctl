# Phase 136: Hysteresis Observability - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Add windowed suppression rate monitoring to the health endpoint, periodic INFO logging during congestion, and Discord alerting when suppression rate exceeds a configurable threshold. Enables the operator to distinguish healthy jitter filtering from excessive suppression (potential false negatives). Builds on v1.24's cumulative hysteresis counters.

</domain>

<decisions>
## Implementation Decisions

### Windowed Rate Tracking (HYST-01)
- **D-01:** Fixed 60s window with counter reset at window boundary. Count suppressions in each 60s window. Reports "N suppressions in the last 60s". Simple, deterministic, matches HYST-01's "per-minute" requirement.
- **D-02:** Per-direction tracking (DL and UL independently). Each QueueController maintains its own window counter.

### Alert Threshold (HYST-03)
- **D-03:** YAML-configurable threshold under `continuous_monitoring.thresholds`, default 20 suppressions/min. At 20Hz cycle rate, 20/min = ~1.7% of cycles suppressed. SIGUSR1 hot-reloadable.
- **D-04:** Fire on single window exceeding threshold. AlertEngine's built-in cooldown prevents spam. No sustained-exceedance requirement.
- **D-05:** New `hysteresis_suppression` alert type in AlertEngine. Uses existing Discord webhook and rate limiting infrastructure.

### Periodic Logging (HYST-02)
- **D-06:** Log at each 60s window boundary, but ONLY when the controller was in YELLOW or worse during that window. Silent during GREEN-only windows. Keeps logs clean — suppression data visible only when congestion is active.

### Health Endpoint Structure
- **D-07:** Extend existing `hysteresis` section in health JSON. Add windowed fields alongside cumulative data: `suppressions_per_min`, `window_start_epoch`, `alert_threshold_per_min`. Keeps all hysteresis data co-located.

### Claude's Discretion
- Whether to track "was in congestion during this window" via a simple boolean flag or cycle count
- Exact log message format for the periodic INFO log
- Whether window_start_epoch uses time.time() or monotonic clock
- AlertEngine cooldown duration for hysteresis_suppression alerts

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Hysteresis Infrastructure (v1.24)
- `src/wanctl/autorate_continuous.py:1367-1445` — QueueController with dwell_cycles, deadband_ms, _yellow_dwell, _transitions_suppressed
- `src/wanctl/autorate_continuous.py:1435-1441` — Dwell timer logic: GREEN->YELLOW suppression with logging

### Health Endpoint (where windowed data goes)
- `src/wanctl/health_check.py:216-229` — Existing hysteresis section: dwell_counter, dwell_cycles, deadband_ms, transitions_suppressed per direction

### AlertEngine (for HYST-03)
- `src/wanctl/alert_engine.py` — AlertEngine with fire(), cooldown, SQLite persistence, Discord webhook
- Phase 132 added `cycle_budget_warning` alert type — same pattern for `hysteresis_suppression`

### SIGUSR1 Reload
- `src/wanctl/autorate_continuous.py` — Generalized SIGUSR1 handler, `_reload_*_config()` pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_transitions_suppressed`: Cumulative counter already tracks total suppressions per direction. Windowed counter adds rate dimension.
- AlertEngine `fire()`: Existing API for new alert types with severity, cooldown, Discord webhook
- `_reload_cycle_budget_config()`: Phase 132 pattern for SIGUSR1-reloadable threshold
- Health endpoint hysteresis section: Already structured per-direction, just needs new fields

### Established Patterns
- QueueController maintains hysteresis state per-direction (DL 4-state, UL 3-state)
- Health endpoint builds dicts in `_build_health_response()` → `hysteresis` sub-dict per direction
- AlertEngine alert types: `cycle_budget_warning` (Phase 132), various v1.15 types
- SIGUSR1 reload chain: `_reload_*_config()` methods called from generalized handler

### Integration Points
- `QueueController.adjust()` / `adjust_4state()`: Where suppressions are counted (increment window counter alongside `_transitions_suppressed`)
- `_build_health_response()` in health_check.py: Add windowed fields to hysteresis section
- `_record_profiling()`: Could be the window boundary check point (called every cycle)
- AlertEngine: Register `hysteresis_suppression` alert type

</code_context>

<specifics>
## Specific Ideas

- The current `_transitions_suppressed` counter is cumulative since startup — useless for real-time monitoring without context of uptime
- 20 suppressions/min at 20Hz = 1 suppression every 60 cycles = 1.7% suppression rate
- During RRUL load, suppression rate may spike to 5-10/min (healthy filtering) or 50+/min (potential false negatives)
- The window boundary check can piggyback on the existing PROFILE_REPORT_INTERVAL cadence (1200 cycles = ~60s at 50ms)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 136-hysteresis-observability*
*Context gathered: 2026-04-03*
