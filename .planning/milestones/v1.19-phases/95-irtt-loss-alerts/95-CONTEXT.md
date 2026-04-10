# Phase 95: IRTT Loss Alerts - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Discord notifications when sustained upstream or downstream packet loss is detected via IRTT. Uses existing AlertEngine for cooldown suppression and webhook delivery. Uses existing IRTTResult.send_loss and receive_loss fields. This phase does NOT change IRTT measurement, congestion control, or state transitions -- it adds alerting on top of existing loss data.

</domain>

<decisions>
## Implementation Decisions

### Loss thresholds
- Default loss threshold **5%** -- sustained loss above 5% triggers alert
- **Same threshold** for both upstream and downstream (not independent)
- Threshold is **YAML-configurable** per alert rule in `alerting.rules` section
- Follows existing per-rule override pattern (sustained_sec, cooldown_sec overrides)

### Sustained duration
- Uses **wall-clock seconds** (existing sustained_sec pattern from v1.15 congestion alerts)
- Default **60 seconds** -- approximately 6 consecutive lossy IRTT bursts at 10s cadence
- Configurable via sustained_sec per-rule override in alerting.rules
- Timer resets when loss drops below threshold

### Alert types and content
- **Separate alert types**: `irtt_loss_upstream` and `irtt_loss_downstream`
- Independent cooldown suppression via (type, WAN) key
- **Recovery alert**: `irtt_loss_recovered` when loss clears after sustained alert was sent
- Recovery includes outage duration, matches wan_recovered/steering_recovered pattern
- **Discord embed content**: loss %, direction, duration, WAN name
- Example: "IRTT upstream packet loss: 15.0% on spectrum (sustained 62s)"
- Severity: "warning" for loss alerts, "recovery" for recovery alerts

### Claude's Discretion
- Internal timer tracking implementation (monotonic timestamps like existing sustained timers)
- Whether to use one recovery type or direction-specific recovery types
- How to handle IRTT unavailable/stale during sustained loss tracking (likely reset timers)
- DiscordFormatter color choices for loss alerts

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### AlertEngine infrastructure
- `src/wanctl/alert_engine.py` -- AlertEngine class with fire(), per-event cooldown, SQLite persistence; this is the core alerting API to use
- `src/wanctl/webhook_delivery.py` -- WebhookDelivery with Discord formatting; handles retry and rate-limiting

### Existing alert patterns (model for implementation)
- `src/wanctl/autorate_continuous.py` -- Congestion sustained timer pattern (_check_congestion_alerts), connectivity alerts (_check_connectivity), baseline drift -- follow these patterns for IRTT loss timing
- `src/wanctl/steering/daemon.py` -- Steering alert patterns in SteeringDaemon

### IRTT loss data source
- `src/wanctl/irtt_measurement.py` lines 33-34 -- IRTTResult.send_loss and receive_loss fields (upstream/downstream loss percentages)
- `src/wanctl/irtt_thread.py` -- IRTTThread.get_latest() returns cached IRTTResult with loss data

### Configuration
- `src/wanctl/autorate_continuous.py` -- Alerting config loading pattern, alerting.rules section, per-rule overrides

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AlertEngine.fire(alert_type, severity, wan_name, details)`: Proven API for firing alerts with cooldown suppression
- `DiscordFormatter`: Color-coded severity embeds with field injection
- `IRTTResult.send_loss` / `receive_loss`: Already parsed from IRTT JSON as 0-100% floats
- `IRTTThread.get_latest()`: Lock-free cache read of latest IRTT measurement
- Sustained timer pattern: `_congestion_start_dl`, `_congestion_start_ul` with monotonic timestamps

### Established Patterns
- **Per-event cooldown**: (alert_type, wan_name) as cooldown key -- independent suppression
- **Sustained timing**: monotonic timestamp set on first detection, compared against sustained_sec on each cycle
- **Fire-then-deliver**: AlertEngine.fire() returns bool, webhook delivery happens async in background thread
- **isinstance(ae, AlertEngine) guard**: MagicMock safety check before firing alerts
- **Per-rule overrides**: alerting.rules YAML allows per-type sustained_sec, cooldown_sec, enabled overrides

### Integration Points
- `WANController.run_cycle()`: Where IRTT loss checking would be added (after existing IRTT result read)
- `WANController.__init__()`: Where sustained timer state variables would be initialized
- AlertEngine already wired into WANController from v1.15

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches following existing alert patterns

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 95-irtt-loss-alerts*
*Context gathered: 2026-03-17*
