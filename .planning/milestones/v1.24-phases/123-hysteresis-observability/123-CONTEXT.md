# Phase 123: Hysteresis Observability - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose hysteresis state in the health endpoint JSON and log suppressed transitions. Operators can monitor dwell counter activity and deadband behavior without log parsing, and see suppression events in logs when diagnosing flapping incidents.

</domain>

<decisions>
## Implementation Decisions

### Health Endpoint Structure
- **D-01:** Per-direction nested — add `hysteresis` sub-dict inside the existing `download{}` and `upload{}` sections of each WAN in the health JSON. Fields: `dwell_counter` (current), `dwell_cycles` (configured), `deadband_ms` (configured), `transitions_suppressed` (cumulative). This matches how download/upload already carry their own `state` and `current_rate_mbps`.

### Suppression Logging
- **D-02:** Log every suppressed cycle at DEBUG: `[HYSTERESIS] DL transition suppressed, dwell N/M`. Log at INFO when dwell expires and transition fires: `[HYSTERESIS] DL dwell expired, GREEN->YELLOW confirmed`. This matches the OBSV-02 requirement text and keeps logs quiet at default level while providing full visibility at DEBUG.

### Counter Scope
- **D-03:** Per-direction, since startup. Each QueueController (DL/UL) tracks its own `_transitions_suppressed` counter, incrementing each time `_yellow_dwell` is bumped (cycle absorbed). Resets to 0 on service restart. No persistence — restarts are rare and Prometheus handles long-term tracking.

### Claude's Discretion
- Whether to add a helper method for building the hysteresis health dict or inline it in `_get_health_status`
- Exact log message formatting details beyond the specified pattern

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Health Endpoint
- `src/wanctl/health_check.py` lines 138-464 — `_get_health_status()` method with existing per-WAN sections (signal_quality, irtt, fusion, tuning). New hysteresis dict goes inside the download/upload sub-dicts built at lines 171-178.

### QueueController (hysteresis state)
- `src/wanctl/autorate_continuous.py` lines 1359-1385 — QueueController.__init__ with `dwell_cycles`, `deadband_ms`, `_yellow_dwell` instance vars. New `_transitions_suppressed` counter goes here.
- `src/wanctl/autorate_continuous.py` lines 1416-1442 — adjust() method (3-state, upload) dwell logic. Suppression log and counter increment go at line ~1427.
- `src/wanctl/autorate_continuous.py` lines 1530-1567 — adjust_4state() method (4-state, download) dwell logic. Suppression log and counter increment go at line ~1550.

### Prior Phase Context
- `.planning/phases/121-core-hysteresis-logic/121-CONTEXT.md` — Decisions D-01 through D-05 on dwell/deadband behavior

### Requirements
- `.planning/REQUIREMENTS.md` — OBSV-01 (health endpoint) and OBSV-02 (log messages)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Health endpoint pattern: each per-WAN section checks feature availability, builds a dict, assigns to `wan_health["section_name"]`. Hysteresis follows the same pattern but nests inside `wan_health["download"]` and `wan_health["upload"]`.
- `[HYSTERESIS]` log prefix already used in `_reload_hysteresis_config()` (line ~2838). Suppression logs should use the same prefix.

### Established Patterns
- `_get_current_state()` helper reads QueueController streak counters — similar read of `_yellow_dwell` and `_transitions_suppressed` for health
- All health sections are guarded with `if self.controller:` — hysteresis data comes from `wan_controller.download` and `wan_controller.upload` QueueController instances
- Logging uses `logger.debug()` / `logger.info()` with structured prefix pattern

### Integration Points
- `QueueController.__init__()` — add `_transitions_suppressed = 0`
- `QueueController.adjust()` line ~1427 — add DEBUG log + counter increment when `_yellow_dwell` bumps
- `QueueController.adjust_4state()` line ~1550 — same
- Both methods where dwell expires (line ~1428, ~1551) — add INFO log for confirmed transition
- `HealthCheckHandler._get_health_status()` lines 171-178 — add `hysteresis` sub-dict to download/upload dicts

</code_context>

<specifics>
## Specific Ideas

- Health endpoint preview agreed upon:
  ```json
  "download": {
    "current_rate_mbps": 450.2,
    "state": "GREEN",
    "hysteresis": {
      "dwell_counter": 0,
      "dwell_cycles": 3,
      "deadband_ms": 3.0,
      "transitions_suppressed": 17
    }
  }
  ```
- Log message format agreed upon:
  ```
  DEBUG [HYSTERESIS] DL transition suppressed, dwell 2/3
  INFO  [HYSTERESIS] DL dwell expired, GREEN->YELLOW confirmed
  ```

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 123-hysteresis-observability*
*Context gathered: 2026-03-31*
