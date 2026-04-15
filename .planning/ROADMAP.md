# Roadmap: wanctl v1.38 Measurement Resilience Under Load

## Overview

Close the production gap where multi-flow download can collapse RTT measurement
quality badly enough to recreate multi-second `tcp_12down` tail latency while
autorate still reports healthy/GREEN operation. This milestone focuses on
reflector quorum, stale RTT masking, health surfacing, and bounded operator
verification without retuning the core congestion algorithm.

## Phases

### Phase 186: Measurement Degradation Contract

**Goal**: Define and expose an explicit measurement-health contract for reduced reflector quorum and stale RTT  
**Depends on**: Phase 185  
**Plans**: 3 plans

Plans:

- [x] 186-01: Audit the current measurement-collapse path and lock the v1.38 contract for degraded measurement states
- [ ] 186-02: Add machine-readable health surfacing for reflector quorum, staleness, and degraded measurement quality
- [ ] 186-03: Add focused contract tests for the new measurement-health surface

**Details:**
Phase 186 turns reduced reflector success and stale measurement from passive
debug context into an explicit contract. The main output is not a new control
policy yet; it is a reliable way for code, tests, and operators to distinguish
healthy current RTT from degraded or masked measurement quality.

### Phase 187: RTT Cache And Fallback Safety

**Goal**: Prevent zero-success RTT cycles from silently reusing stale cached RTT as healthy current input  
**Depends on**: Phase 186  
**Plans**: 3 plans

Plans:

- [x] 187-01: Change background RTT behavior so zero-success cycles follow explicit degraded semantics
- [ ] 187-02: Preserve bounded controller behavior and existing real-outage fallback handling while measurement quality is degraded
- [ ] 187-03: Add regression coverage around zero-success cycles, reduced quorum, and non-regression of existing fallback behavior

**Details:**
Phase 187 addresses the most concrete code-path gap from the live
investigation: stale cached RTT should not continue to look like a healthy
current sample when current reflector measurement has collapsed. The fix stays
bounded and conservative by preserving the existing total-connectivity fallback
path and avoiding threshold retuning.

### Phase 188: Operator Verification And Closeout

**Goal**: Prove the new measurement-resilience behavior against the real `tcp_12down` failure mode and align operator guidance  
**Depends on**: Phase 187  
**Plans**: 2 plans

Plans:

- [ ] 188-01: Add operator-facing verification guidance and bounded reproduction steps for measurement degradation
- [ ] 188-02: Verify the milestone against live or replayable evidence and close the requirement traceability

**Details:**
Phase 188 connects the code and health changes back to the real production
problem. It locks the operator workflow for identifying measurement collapse
under load and verifies that the milestone closes the stale-healthy gap without
spilling into unrelated congestion or steering behavior.
