# Phase 23: Edge Case Tests - Context

**Gathered:** 2026-01-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Test boundary conditions for rate limiting and dual-fallback failure scenarios. Two specific requirements:
- TEST-04: Rate limiter handles rapid restarts without burst exceeding configured limit
- TEST-05: Dual fallback failure (ICMP + TCP both down) returns safe defaults, not stale data

</domain>

<decisions>
## Implementation Decisions

### Rate Limiter Test Design
- Claude determines appropriate "rapid restart" test parameters based on rate limiter configuration
- Claude determines test-specific vs production config values for deterministic testing
- Claude investigates existing rate limiter behavior (reject vs queue) and tests accordingly
- Claude determines if recovery testing (normal operation after burst) adds value

### Dual Fallback Test Scenarios
- Claude determines failure simulation strategy (mocking vs timeout injection)
- Claude investigates existing behavior to document what "safe defaults" means in codebase
- Claude determines staleness definition from existing implementation
- Claude determines appropriate test scope (measurement layer only vs full controller response)

### Test Harness Approach
- Claude follows existing test patterns in codebase for test level (unit vs integration)
- Claude follows existing conventions for test file organization
- Claude balances thoroughness with test execution speed
- Claude uses judgment on parameterization based on scenario coverage needs

### Claude's Discretion
- All test design parameters (restart rates, limits, timeouts)
- Failure simulation approach
- Definition of "safe defaults" and "stale data" (from codebase investigation)
- Test scope and organization
- Parameterization strategy

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User trusts Claude to investigate existing implementations and design appropriate tests.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-edge-case-tests*
*Context gathered: 2026-01-21*
