# Phase 36: Steering Daemon Tests - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Write unit tests to achieve 90%+ coverage for steering daemon (`src/wanctl/steering/daemon.py`). Current coverage: 44.2%. Target: 90%+. Covers RouterOSController, SteeringDaemon state machine, run_daemon_loop, main() entry point, and confidence controller integration.

</domain>

<decisions>
## Implementation Decisions

### RouterOS Controller Mocking
- Mock at client level: patch `get_router_client_with_failover` to return a fake client
- Test rule status parsing for all output formats: enabled (no X flag), disabled (X flag), rule not found, malformed output
- Claude's discretion: command string verification specificity, retry logic test depth

### State Machine Edge Cases
- Test all counter transitions in GOOD state:
  - RED assessment increments degrade_count
  - YELLOW assessment resets degrade_count (early warning, no action)
  - GREEN assessment resets degrade_count
  - Threshold breach triggers GOOD→DEGRADED transition
- Test DEGRADED state recovery path with similar counter logic
- Claude's discretion: legacy state name handling (`SPECTRUM_GOOD`, `WAN1_GOOD`), CAKE-aware vs legacy mode test organization, metrics recording verification

### Main Entry Point Coverage
- Health server lifecycle: test start and graceful shutdown in finally block
- Verify server starts, daemon runs, server shuts down on exit
- Claude's discretion: config loading error paths, lock conflict handling, signal handling depth (early shutdown vs loop exit)

### Confidence Controller Integration
- Test both dry-run and live modes explicitly:
  - dry_run=True: logs confidence decision but falls through to hysteresis logic
  - dry_run=False (live): applies confidence decision directly via _apply_confidence_decision
- Claude's discretion: ConfidenceSignals construction tests, ENABLE/DISABLE decision path coverage, mock vs real ConfidenceController

### Claude's Discretion
- Test organization (parametrize vs separate classes for CAKE/legacy modes)
- Command string specificity in router tests
- Depth of retry verification (trust retry_utils tests vs integration)
- Signal handling test granularity

</decisions>

<specifics>
## Specific Ideas

- Use existing fixture patterns from test_steering_daemon.py (66 tests already exist)
- RouterOS output parsing should handle actual MikroTik CLI output format with rule numbers and flags
- Confidence dry_run mode is the current production default (safe deployment) - tests should reflect this

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 36-steering-daemon-tests*
*Context gathered: 2026-01-25*
