# Phase 35: Core Controller Tests - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Test coverage for `autorate_continuous.py` (main control loop) from 33% to 90%+. Includes entry points, signal handlers, state transitions, and error recovery. No new controller features — tests only.

</domain>

<decisions>
## Implementation Decisions

### Test Isolation Strategy
- Mock at router client level — inject fake RouterOS client, tests full control logic without network I/O
- Router client mock boundary is primary; no HTTP/SSH mocking in control loop tests

### State Transition Coverage
- Test ALL valid state transitions (every edge in state graph)
- Download states: GREEN → YELLOW → SOFT_RED → RED and recovery paths
- Upload states: GREEN → YELLOW → RED and recovery paths
- Verify baseline RTT freeze: baseline must NOT update when delta > 3ms (critical invariant)

### Error Scenario Depth
- Test ALL error categories: router failures, measurement failures, config errors
- Test REST-to-SSH failover explicitly at control loop level
- Test BOTH graceful degradation (transient errors) AND correct exit (fatal errors)
- Test ICMP blackout scenario with TCP RTT fallback (real production issue from v1.1.0)

### Signal Handler Testing
- Mock signal handlers — patch signal.signal() and call handlers directly (safe, deterministic)
- No real signals to test process (os.kill unsafe in test runner)

### Claude's Discretion
- RTT mocking approach (inject mock vs mock socket layer)
- Config source (programmatic objects vs YAML fixtures) based on what's being tested
- Time control strategy (freeze time vs short real intervals) per test needs
- Assertion level (exact rate values vs direction only) per test
- GREEN cycle counter testing if coverage-relevant
- SIGTERM cleanup verification depth based on actual cleanup actions
- SIGHUP testing if implemented and coverage-relevant
- Signal handler reset approach (fixtures vs manual)

</decisions>

<specifics>
## Specific Ideas

- Baseline freeze is a "safety invariant" per CLAUDE.md architectural spine — tests must verify this explicitly
- TCP fallback for ICMP blackout was a real production incident (Spectrum ISP blocking) — integration-level test confirms the fix works end-to-end
- REST-to-SSH failover already tested in Phase 32, but control loop test verifies the controller continues operating after failover activates

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 35-core-controller-tests*
*Context gathered: 2026-01-25*
