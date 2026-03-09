# Requirements: wanctl v1.11

**Defined:** 2026-03-09
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.11 Requirements

Requirements for WAN-Aware Steering. Each maps to roadmap phases.

### State Export

- [ ] **STATE-01**: Autorate persists `congestion.dl_state` (GREEN/YELLOW/SOFT_RED/RED) to state file each cycle
- [ ] **STATE-02**: State file extension is backward-compatible (pre-upgrade steering ignores unknown keys)
- [ ] **STATE-03**: Zone field excluded from dirty-tracking comparison to prevent write amplification

### Signal Fusion

- [ ] **FUSE-01**: Steering reads WAN zone from autorate state file (same read as baseline RTT, zero additional I/O)
- [ ] **FUSE-02**: WAN zone mapped to confidence weights (WAN_RED, WAN_SOFT_RED) in `compute_confidence()`
- [ ] **FUSE-03**: WAN state alone cannot trigger steering (WAN_RED < steer_threshold enforced by weight values)
- [ ] **FUSE-04**: Sustained WAN RED amplifies CAKE-based signals toward steer threshold
- [ ] **FUSE-05**: Recovery eligibility requires WAN state GREEN (or unavailable) in addition to existing CAKE checks

### Safety

- [ ] **SAFE-01**: Stale WAN state (>5s) defaults to GREEN (fail-safe)
- [ ] **SAFE-02**: Graceful degradation when autorate unavailable (None = skip WAN weight)
- [ ] **SAFE-03**: Startup grace period ignores WAN signal for first 30s after daemon start
- [ ] **SAFE-04**: Feature ships disabled by default (`wan_state.enabled: false`)

### Configuration

- [ ] **CONF-01**: YAML `wan_state:` section with `enabled`, weight values, staleness threshold, grace period
- [ ] **CONF-02**: Config validated via existing schema validation framework

### Observability

- [ ] **OBSV-01**: Health endpoint exposes WAN awareness state (zone, staleness, sustained cycles, confidence contribution)
- [ ] **OBSV-02**: SQLite metrics record WAN awareness signal each cycle
- [ ] **OBSV-03**: Log output includes WAN state when it contributes to steering decisions

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Extended WAN Awareness

- **FUTURE-01**: Upload zone awareness (separate ul_state consumption by steering)
- **FUTURE-02**: RTT delta export in autorate state file for supplementary scoring
- **FUTURE-03**: Asymmetric WAN-specific sustain timers (separate from CAKE sustain timers)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| WAN state overrides CAKE state | Violates "CAKE is primary" architecture; WAN RTT can spike from unrelated causes |
| Bidirectional state sharing | Creates circular dependency; autorate must remain link-agnostic per PORTABLE_CONTROLLER_ARCHITECTURE.md |
| Real-time IPC (shared memory, Unix sockets) | Over-engineering; file polling on tmpfs is <1ms, steering polls at 500ms |
| Automatic parameter tuning / ML | PROJECT.md explicitly excludes ML-based prediction; self-tuning weights are unpredictable |
| Kill existing connections on failover | Breaks TCP sessions; pfSense documented bugs with "kill states" approach |
| Per-direction WAN awareness | Upload congestion rarely affects latency-sensitive traffic; download zone is authoritative |
| WAN state EWMA smoothing | Double-smoothing; autorate zone is already EWMA-filtered with streak counters |
| Separate WAN state polling interval | Timer complexity; steering already reads state file every cycle for baseline RTT |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| STATE-01 | Phase 58 | Pending |
| STATE-02 | Phase 58 | Pending |
| STATE-03 | Phase 58 | Pending |
| FUSE-01 | Phase 59 | Pending |
| FUSE-02 | Phase 59 | Pending |
| FUSE-03 | Phase 59 | Pending |
| FUSE-04 | Phase 59 | Pending |
| FUSE-05 | Phase 59 | Pending |
| SAFE-01 | Phase 59 | Pending |
| SAFE-02 | Phase 59 | Pending |
| SAFE-03 | Phase 60 | Pending |
| SAFE-04 | Phase 60 | Pending |
| CONF-01 | Phase 60 | Pending |
| CONF-02 | Phase 60 | Pending |
| OBSV-01 | Phase 61 | Pending |
| OBSV-02 | Phase 61 | Pending |
| OBSV-03 | Phase 61 | Pending |

**Coverage:**
- v1.11 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after roadmap creation*
