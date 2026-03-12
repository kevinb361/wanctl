# Phase 79: Connectivity & Anomaly Alerts - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator is notified of WAN health issues and anomalous RTT behavior. Four new alert types: WAN-offline (ICMP targets unreachable), WAN-recovery (targets come back), baseline RTT drift (EWMA diverges from reference), and congestion flapping (rapid zone oscillations). Requirements: ALRT-04, ALRT-05, ALRT-06, ALRT-07.

</domain>

<decisions>
## Implementation Decisions

### Connectivity monitoring
- 30-second sustained threshold before wan_offline fires (shorter than congestion's 60s -- outages are more urgent)
- "Unreachable" means ALL ICMP ping targets failing (not just one -- avoids false alarms from single-target maintenance)
- Rich recovery alerts: include outage duration, number of recovered targets, current RTT
- WAN-offline severity: always critical (the 30s threshold already filters transient issues)
- Recovery gate: wan_recovered only fires if wan_offline actually fired first (consistent with Phase 78 pattern)

### Baseline drift thresholds
- Percentage-based drift detection (e.g., >X% from reference) -- adapts to different WAN baselines (37ms Spectrum vs 29ms ATT)
- Fire once then cooldown (consistent with all other alert types) -- natural re-fire if still drifted when cooldown expires
- Baseline drift alert details: current baseline, reference baseline, drift percentage (no trend tracking)

### Congestion flapping detection
- Independent DL/UL flapping tracking: `flapping_dl`, `flapping_ul` as separate alert types (consistent with Phase 78 DL/UL independence)
- One-shot with cooldown: no explicit "flapping stopped" recovery alert (flapping is transient -- either stops or re-fires after cooldown)

### Claude's Discretion
- Whether to separate wan_offline into ICMP vs router types, or use a single type with details dict specifying what's unreachable
- Drift reference point: initial baseline vs rolling window average
- Drift percentage threshold default (e.g., 30%, 50%, etc.)
- Whether baseline drift has a recovery alert (baseline_drift_recovered) or is informational-only
- Flapping detection algorithm: transition count in time window (FlapDetector pattern proven) vs pattern matching
- Flapping severity (warning vs info -- it indicates instability but controller handles it)
- Flapping detection thresholds (N transitions in M seconds)
- WAN-offline alert detail richness (duration + last RTT vs also target-specific failure info)
- Flapping alert detail level (transition count + window vs also including rate/RTT info)

</decisions>

<specifics>
## Specific Ideas

- Follow the Phase 78 `_check_congestion_alerts()` pattern: lightweight timer check each cycle, fire via existing `self.alert_engine`
- Reuse `FlapDetector` pattern from `steering_confidence.py` (time-windowed transition counting) for congestion zone flapping
- Baseline drift detection should be cheap -- compare `self.baseline_rtt` against reference each cycle, no extra state machine
- WAN-offline detection hooks into existing RTT measurement failure path (when all ICMP pings fail)
- All new alert types go through existing AlertEngine with (type, wan) cooldown keys
- `default_sustained_sec` per-rule override applies to wan_offline (30s default) and any duration-based thresholds

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AlertEngine` in `alert_engine.py`: fire(type, severity, wan_name, details) with cooldown, persistence, delivery callback -- fully wired from Phase 76-78
- `FlapDetector` in `steering_confidence.py`: Time-windowed transition counting with `check_flapping()` -- pattern for congestion flapping
- `self.baseline_rtt` in autorate daemon: Slow EWMA updated in `_update_baseline_if_idle()`, with `baseline_rtt_initial`, `baseline_rtt_min`, `baseline_rtt_max` config
- `_check_congestion_alerts()` in autorate_continuous.py: Phase 78 pattern for per-cycle alert checking with monotonic timers
- `router_connectivity.py`: Already classifies failure types (network_unreachable, connection_refused, etc.)

### Established Patterns
- **Per-cycle timer check**: `_check_congestion_alerts()` runs each cycle, compares `time.monotonic()` against threshold -- model for all Phase 79 checks
- **DL/UL independence**: Separate timers, separate alert types, separate cooldowns (Phase 78)
- **Recovery gate**: `_dl_sustained_fired` / `_ul_sustained_fired` flags prevent spurious recovery alerts (Phase 78)
- **Config pattern**: `alerting.rules` map with per-rule enabled/cooldown_sec/severity + global defaults
- **Zone tracking**: `self._dl_zone` and `self._ul_zone` updated each `run_cycle()` cycle

### Integration Points
- Autorate `run_cycle()`: After `_check_congestion_alerts()` -- add `_check_connectivity_alerts()`, `_check_baseline_drift()`, `_check_flapping_alerts()`
- Autorate RTT measurement: When all ICMP targets fail -- timestamp for connectivity tracking
- Autorate `_update_baseline_if_idle()`: After baseline update -- compare against reference for drift detection
- Config: `alerting.rules` map needs new rule entries for wan_offline, wan_recovered, baseline_drift, flapping_dl, flapping_ul (and possibly baseline_drift_recovered)
- Config: per-rule `sustained_sec` override for wan_offline (30s default vs congestion's 60s)

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 79-connectivity-anomaly-alerts*
*Context gathered: 2026-03-12*
