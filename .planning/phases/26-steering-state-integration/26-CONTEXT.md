# Phase 26: Steering State & Integration - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the existing health endpoint (from Phase 25) into the steering daemon and expose live steering-specific state in the health response. Requirements: STEER-01 through STEER-05, INTG-01 through INTG-03.

</domain>

<decisions>
## Implementation Decisions

### Steering Data Exposure

**User decisions:**
- WAN congestion states: Include BOTH string names AND numeric codes (e.g., "GREEN" + 0)
- Timers: YES, expose internal timers (time since last decision, time in current state)
- Mode: YES, expose dry_run/active mode
- Error counts: YES, expose error counts (failed router calls, measurement timeouts)
- Config thresholds: YES, expose steering decision thresholds from config
- PID: YES, include daemon's PID

**Claude's Discretion:**
- Confidence values (which to expose: primary, secondary, combined, or all)
- Decision info granularity (current state only vs state+reason vs history)
- RTT measurements (whether to include baseline RTT from autorate)
- WAN reachability (whether to expose per-WAN reachability status)
- Autorate reference (whether to include autorate health URL)
- Cycle count (whether to expose steering cycle count)

### Response Structure

**User decisions:**
- Timestamps: ISO 8601 strings (e.g., "2026-01-24T10:30:00Z")
- Field naming: Match autorate health endpoint convention

**Claude's Discretion:**
- Overall structure (flat vs nested)
- Config-disabled status value
- Service/component identification field
- Schema versioning
- Summary mode (?summary=true parameter)
- Null field handling (omit vs include as null)

### Lifecycle Wiring

**Claude's Discretion (all lifecycle decisions):**
- Startup failure behavior (fail daemon vs log and continue vs retry)
- Startup sequence position (before config, after config, after main loop)
- Mid-run crash handling (restart, log and continue, fail daemon)
- Logging verbosity (full lifecycle vs errors only)
- Graceful shutdown timeout
- Watchdog/heartbeat for unresponsive health thread
- Port configurability (hardcoded 9102 vs YAML config)
- Bind address (127.0.0.1 vs 0.0.0.0 vs configurable)

### State Freshness

**Claude's Discretion (all freshness decisions):**
- Concurrency handling (read current vs snapshot vs lock)
- Data age field (last_updated or data_age_ms)
- Cold start behavior (partial, starting status, or 503)
- Response caching (none vs brief cache)

</decisions>

<specifics>
## Specific Ideas

- Match autorate health endpoint patterns for consistency (port 9101 uses similar structure)
- Phase 25 created steering_health.py module with basic health server infrastructure
- Existing health_check.py in autorate provides the pattern to follow

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 26-steering-state-integration*
*Context gathered: 2026-01-24*
