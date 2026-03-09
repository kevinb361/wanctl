# Requirements: wanctl v1.11 WAN-Aware Steering

**Defined:** 2026-03-09
**Core Value:** Sub-second congestion detection with WAN-aware failover — steering considers ISP-level congestion alongside local CAKE queue health.

## v1.11 Requirements

### Signal Infrastructure

- [ ] **INFRA-01**: Autorate persists download congestion state (GREEN/YELLOW/SOFT_RED/RED) to state file
- [ ] **INFRA-02**: Steering reads WAN congestion state from autorate state file without double file reads
- [ ] **INFRA-03**: Stale WAN state (>5s) is treated as unknown and contributes zero to confidence
- [ ] **INFRA-04**: Missing congestion key in state file is handled gracefully (backward compatible)

### Signal Fusion

- [ ] **FUSE-01**: WAN state maps to additive confidence weights (RED=30, SOFT_RED=15, YELLOW=5, GREEN=0)
- [ ] **FUSE-02**: WAN RED alone cannot trigger steering (WAN score < steer_threshold without CAKE corroboration)
- [ ] **FUSE-03**: Sustained WAN RED amplifies existing CAKE signals to accelerate failover
- [ ] **FUSE-04**: Recovery requires WAN state GREEN (in addition to existing CAKE GREEN requirement)

### Observability & Config

- [ ] **OBS-01**: Health endpoint exposes WAN state (zone, age, staleness, weight contribution)
- [ ] **OBS-02**: WAN state weights and staleness threshold configurable in steering YAML
- [ ] **OBS-03**: Structured log line includes WAN state when it contributes to confidence score
- [ ] **OBS-04**: SOFT_RED contributes as intermediate weight between YELLOW and RED

## Future Requirements

### Tuning & Hardening

- **TUNE-01**: Asymmetric sustain timers for WAN vs CAKE degradation/recovery
- **TUNE-02**: Startup grace period (ignore WAN signal for first N seconds after steering starts)
- **TUNE-03**: RTT delta exported in autorate state for supplementary steering scoring

## Out of Scope

| Feature | Reason |
|---------|--------|
| WAN state overrides CAKE state | Violates "CAKE is primary" architecture; WAN can only amplify |
| Real-time IPC (sockets, shared memory) | JSON state file proven at 50ms cycle; simple, debuggable |
| Steering reads raw RTT instead of zone | Duplicates autorate's state machine logic; zone is the conclusion |
| Per-direction signals (separate dl/ul) | Upload congestion doesn't degrade inbound latency-sensitive traffic |
| Dynamic weight adjustment / ML | Hard to test, can diverge; fixed weights tunable via YAML |
| Steering existing connections mid-stream | Breaks TCP sequences; only new connections steer |
| Double EWMA on WAN zone state | Zone is already EWMA+hysteresis filtered; double-smoothing delays detection |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | — | Pending |
| INFRA-02 | — | Pending |
| INFRA-03 | — | Pending |
| INFRA-04 | — | Pending |
| FUSE-01 | — | Pending |
| FUSE-02 | — | Pending |
| FUSE-03 | — | Pending |
| FUSE-04 | — | Pending |
| OBS-01 | — | Pending |
| OBS-02 | — | Pending |
| OBS-03 | — | Pending |
| OBS-04 | — | Pending |

**Coverage:**
- v1.11 requirements: 12 total
- Mapped to phases: 0
- Unmapped: 12 (pending roadmap creation)

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after initial definition*
