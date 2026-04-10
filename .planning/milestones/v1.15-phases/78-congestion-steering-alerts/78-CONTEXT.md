# Phase 78: Congestion & Steering Alerts - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator is notified when sustained congestion occurs or when steering reroutes/recovers traffic. Detection logic in both autorate and steering daemons calls `alert_engine.fire()`. Requirements: ALRT-01 (sustained congestion), ALRT-02 (steering activated), ALRT-03 (steering recovered).

</domain>

<decisions>
## Implementation Decisions

### Congestion thresholds
- 60-second wall-clock timer using `time.monotonic()` (not cycle count)
- Same 60s threshold for both RED and SOFT_RED zones
- RED and SOFT_RED share a single "congested" timer -- RED→SOFT_RED does not reset the timer, only GREEN/YELLOW clears it
- Global `default_sustained_sec` config key with per-rule override (like `default_cooldown_sec` pattern)
- Config key naming at Claude's discretion (e.g., `sustained_sec` or `duration_threshold_sec`)

### Alert granularity
- Download and upload congestion tracked and alerted independently (separate timers)
- Separate alert types per direction: `congestion_sustained_dl`, `congestion_sustained_ul`
- Separate recovery types: `congestion_recovered_dl`, `congestion_recovered_ul`
- Steering types: `steering_activated`, `steering_recovered`
- **6 total alert types**, each with independent cooldown in the (type, wan) model
- All 6 types fully independent in config (each can be enabled/disabled, cooldown overridden)

### Congestion recovery alerts
- Recovery alert fires when congestion clears (zone returns to non-congested state)
- `congestion_recovered` is a separate alert type with its own cooldown (not shared with sustained)
- Alert details include zone name (RED vs SOFT_RED) that was active
- Include current rate limits at recovery time and congestion duration

### Congestion alert details
- Include current zone name (RED or SOFT_RED)
- Include current rate limits (DL rate, UL rate in Mbps)
- Include RTT and delta values
- Include duration of sustained congestion

### Steering alert context
- Rich context on activation: primary WAN congestion signals (RTT delta, CAKE drops, queue depth), confidence score, from/to state
- Fire immediately on steering transition -- no additional delay (existing hysteresis in state machine is sufficient)
- Recovery alert includes how long steering was active (duration)

### Severity mapping
- Congestion severity is zone-dependent: RED zone = critical, SOFT_RED zone = warning
- `steering_activated` default severity: warning
- `steering_recovered` default severity: Claude's discretion (recovery/green or info/blue)
- `congestion_recovered_dl` and `congestion_recovered_ul` default severity: Claude's discretion (consistent with steering recovery)

### Claude's Discretion
- Config key name for sustained duration threshold
- Whether recovery alert fires only if the congestion alert actually fired first (recovery gate)
- Whether YELLOW counts as "recovered" or only GREEN
- Re-fire behavior (fire once then cooldown, or periodic re-fire while congested)
- Whether all 6 rules are enabled by default or some opt-in
- Recovery alert detail richness (current rates + duration vs also tracking peak metrics)
- Which WAN names to include in steering alerts (both WANs or degraded only)
- Congestion episode start time tracking approach (inline timestamp vs SQLite lookup)
- Exact severity for recovery alert types (recovery/green recommended for consistency)

</decisions>

<specifics>
## Specific Ideas

- Follow the existing `execute_steering_transition()` pattern -- it already logs from_state, to_state, and congestion signals. Alert fire() call should go right after a successful transition
- Congestion detection should be lightweight -- just a timestamp comparison each cycle, not a new class or complex state machine
- Reuse the existing `self._dl_zone` and `self._ul_zone` attributes that `run_cycle()` already computes
- Recovery duration matches Phase 77 embed design ("was RED for 5m, now GREEN")

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AlertEngine` in `alert_engine.py`: `fire(alert_type, severity, wan_name, details)` with cooldown and delivery callback already wired
- `self.alert_engine` already instantiated in both daemons (autorate line 1118, steering line 1005)
- `WebhookDelivery` with `DiscordFormatter` already handles embed creation from alert details
- `RateLimiter` in `rate_utils.py` as pattern reference for timing logic
- `time.monotonic()` used throughout codebase for timing (cooldowns, grace periods)

### Established Patterns
- **State zone tracking**: `self._dl_zone` and `self._ul_zone` updated each `run_cycle()` call in autorate_continuous.py
- **Steering transitions**: `_handle_good_state()` returns `(degrade_count, state_changed)`, `_handle_degraded_state()` returns `(recover_count, state_changed)`
- **execute_steering_transition()**: Handles router enable/disable, logs transition, records metrics -- the hook point for steering alerts
- **Hysteresis already built-in**: `degrade_threshold` samples before GOOD→DEGRADED, `recover_threshold` before DEGRADED→GOOD
- **last_transition_time**: Steering daemon already tracks transition timestamps for duration calculation

### Integration Points
- Autorate `run_cycle()` at ~line 1596-1610: After `dl_zone` and `ul_zone` are computed -- insert sustained congestion timer check
- Steering `_handle_good_state()` at ~line 1342: After `execute_steering_transition()` succeeds for GOOD→DEGRADED -- fire steering_activated
- Steering `_handle_degraded_state()` at ~line 1384: After `execute_steering_transition()` succeeds for DEGRADED→GOOD -- fire steering_recovered
- Config: `alerting.rules` map needs 6 new rule entries with sustained_sec support
- Config: `alerting.default_sustained_sec` new global default

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 78-congestion-steering-alerts*
*Context gathered: 2026-03-12*
