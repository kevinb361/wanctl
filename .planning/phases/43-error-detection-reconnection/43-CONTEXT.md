# Phase 43: Error Detection & Reconnection - Context

**Gathered:** 2026-01-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Controller detects mid-cycle router failures (ERRR-01) and handles connection drops gracefully with reconnection (ERRR-02). Covers detection, response during outage, reconnection, and state handling. Does NOT cover fail-safe rate limit behavior (Phase 44) or graceful shutdown (Phase 45).

</domain>

<decisions>
## Implementation Decisions

### Detection Strategy
- Distinguish between failure types (timeout vs connection refused vs DNS failure) — different types may warrant different responses
- Claude's discretion: threshold for declaring "unreachable" (single vs consecutive failures)
- Claude's discretion: timeout values (use existing or adjust based on 50ms cycle constraints)
- Claude's discretion: integration with existing FailoverRouterClient (REST→SSH)

### Error Response
- Claude's discretion: logging verbosity during outage (every failure vs transitions vs rate-limited)
- Claude's discretion: control loop behavior during outage (continue cycling vs pause)
- Claude's discretion: health endpoint status during outage (503 vs degraded 200 vs unchanged)
- Claude's discretion: metrics recording during outage

### Reconnection Behavior
- Claude's discretion: retry strategy (immediate vs backoff vs fixed interval)
- Claude's discretion: maximum retry limit (give up vs retry forever)
- Claude's discretion: resume behavior (immediate vs gradual vs verify first)
- Claude's discretion: logging successful reconnection

### State Handling
- Claude's discretion: RTT baseline handling after reconnection
- Claude's discretion: congestion state (GREEN/YELLOW/RED) reset behavior
- Claude's discretion: rate limit verification after reconnection
- Claude's discretion: duration-aware handling (short vs long outage)

### Claude's Discretion
The user has delegated essentially all implementation details to Claude. Key guidance:
- Distinguish failure types (timeout, connection refused, DNS) — this is the one explicit decision
- Everything else should follow codebase patterns, production daemon best practices, and safety considerations
- Prioritize: stability > safety > clarity > elegance (from CLAUDE.md)
- Reference existing FailoverRouterClient, health endpoint, and metrics patterns

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches that fit the existing codebase patterns.

User trusts Claude to make implementation decisions based on:
- Existing codebase patterns (FailoverRouterClient, health endpoints, metrics recording)
- Production daemon best practices
- 50ms cycle constraints
- Safety-first design (fail-safe behavior in Phase 44)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 43-error-detection-reconnection*
*Context gathered: 2026-01-29*
