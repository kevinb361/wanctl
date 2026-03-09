# Phase 44: Fail-Safe Behavior - Context

**Gathered:** 2026-01-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Ensure rate limits are never removed during error conditions and watchdog handles transient failures gracefully. This phase builds on Phase 43's detection/tracking to define *behavior* during and after outages. Does NOT cover initial detection (Phase 43) or graceful shutdown (Phase 45).

</domain>

<decisions>
## Implementation Decisions

### Rate Limit Persistence
- Queue pending rate changes during outage — apply when router returns
- Claude's discretion: Whether to send "remove queue" commands (lean toward fail-closed)
- Claude's discretion: Rate aging/expiration policy
- Claude's discretion: Floor-stuck concern (balance safety vs performance)

### Watchdog Thresholds
- Claude's discretion: Whether router failures count toward watchdog failure threshold
- Claude's discretion: Different treatment for different failure types (timeout vs auth)
- Claude's discretion: Maximum consecutive timeouts before restart (current default is 3)
- Claude's discretion: Whether to continue watchdog notification during router outage

### Recovery Behavior
- Claude's discretion: Verify router limits match internal state on reconnection
- Claude's discretion: Immediate vs gradual resume (EWMA is preserved from Phase 43)
- Claude's discretion: Long outage (5+ min) vs short outage handling
- Claude's discretion: Queued rate changes on reconnection (apply vs recalculate)

### Logging During Outage
- Claude's discretion: Outage duration in reconnection log message
- Claude's discretion: Metrics recording during outage (null/flags vs skip)
- Claude's discretion: Health endpoint sufficiency (Phase 43 already degrades on unreachable)
- Claude's discretion: Additional alerting beyond health endpoint (keep simple)

### Claude's Discretion
The user has delegated nearly all implementation details to Claude. Key guidance:
- Prioritize fail-safe over fail-fast (rate limits should persist, not be removed)
- Watchdog should distinguish between daemon problems and router problems
- Recovery should be safe — EWMA is preserved (Phase 43 invariant), use that
- Keep logging operationally useful but not spammy
- Reference existing codebase patterns (retry_utils, FailoverRouterClient)

</decisions>

<specifics>
## Specific Ideas

- Rate changes calculated during outage should be queued and applied on reconnection
- Fail-closed philosophy: when in doubt, keep existing rate limits in place
- EWMA/baseline preservation (Phase 43) means recovery can trust internal state

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 44-fail-safe-behavior*
*Context gathered: 2026-01-29*
