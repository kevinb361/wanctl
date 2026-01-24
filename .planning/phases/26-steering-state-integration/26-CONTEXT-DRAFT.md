# Phase 26: Steering State & Integration - Context (DRAFT)

**Gathered:** 2026-01-24
**Status:** INCOMPLETE - Discussion paused

<domain>
## Phase Boundary

Wire the existing health endpoint (from Phase 25) into the steering daemon and expose live steering-specific state in the health response. Requirements: STEER-01 through STEER-05, INTG-01 through INTG-03.

</domain>

<decisions>
## Implementation Decisions

### Steering Data Exposure

**User decisions:**
- WAN congestion states: Include BOTH string names AND numeric codes
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
- Timestamps: ISO 8601 strings (not Unix epoch)
- Field naming: Match autorate health endpoint convention

**Claude's Discretion:**
- Overall structure (flat vs nested)
- Config-disabled status value
- Service/component identification field
- Schema versioning
- Summary mode (?summary=true parameter)
- Null field handling (omit vs include as null)

### Lifecycle Wiring

**NOT YET DISCUSSED** - Discussion paused before completing this section

Claude's Discretion on all lifecycle decisions:
- Startup failure behavior (fail daemon vs log and continue vs retry)
- Startup sequence position
- Mid-run crash handling
- Logging verbosity

### State Freshness

**NOT YET DISCUSSED** - Discussion paused before starting this section

</decisions>

<specifics>
## Specific Ideas

Discussion incomplete - resume to capture any specific references or examples.

</specifics>

<deferred>
## Deferred Ideas

None captured yet.

</deferred>

---

## Resume Instructions

This discussion was paused partway through. When resuming:
1. Complete "Lifecycle wiring" area (only checked "more questions" once, user gave all to Claude discretion)
2. Discuss "State freshness" area (not yet started)
3. Create final CONTEXT.md

---

*Phase: 26-steering-state-integration*
*Context draft: 2026-01-24*
