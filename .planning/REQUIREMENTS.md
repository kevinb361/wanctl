# Requirements: wanctl

**Defined:** 2026-03-11
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.13 Requirements

Requirements for Legacy Cleanup & Feature Graduation milestone. Each maps to roadmap phases.

### Legacy Cleanup

- [x] **LGCY-01**: Production configs on cake-spectrum and cake-att confirmed using only modern parameter names (no legacy fallbacks in use)
- [ ] **LGCY-02**: Dead state machine methods removed (`_update_state_machine_cake_aware`, `_update_state_machine_legacy`) from steering daemon
- [ ] **LGCY-03**: All legacy config parameter fallbacks removed — old parameter names produce clear deprecation errors instead of silent fallback
- [ ] **LGCY-04**: Legacy config validation code removed from `config_validation_utils.py`
- [ ] **LGCY-05**: Obsolete ISP-specific config files removed from `configs/` directory
- [ ] **LGCY-06**: Legacy-only test fixtures and test paths updated to reflect current-only code paths
- [ ] **LGCY-07**: RTT-only mode (`cake_aware: false`) disposition resolved — retired if unused or explicitly documented if kept

### Confidence Graduation

- [ ] **CONF-01**: Confidence-based steering config updated to `dry_run: false` for live routing decisions
- [ ] **CONF-02**: Health endpoint confirms confidence scores actively influencing steering decisions in production
- [ ] **CONF-03**: Rollback path documented and validated (revert to `dry_run: true` without daemon restart)

### WAN-Aware Enablement

- [ ] **WANE-01**: WAN-aware steering config updated to `wan_state.enabled: true` on cake-spectrum
- [ ] **WANE-02**: Health endpoint shows `wan_awareness.enabled=true` with live zone data and confidence contribution
- [ ] **WANE-03**: Graceful degradation confirmed under real conditions (stale zone → GREEN fallback, autorate unavailable → WAN weight skipped)

## Future Requirements

### Measurement Alternatives

- **IRTT-01**: Research IRTT as RTT measurement alternative (UDP-based, OWD, jitter)
- **IRTT-02**: Evaluate IRTT client overhead within 50ms cycle budget

### Testing

- **TEST-01**: Integration test infrastructure for router communication (mock router or VCR-style replay)

## Out of Scope

| Feature | Reason |
|---------|--------|
| IRTT integration | Research-only todo, deferred to future milestone |
| Router integration tests | Contract tests added in v1.12 reduced urgency |
| New feature development | Milestone focused on cleanup and activation |
| Breaking config changes | Legacy removal uses deprecation errors, not silent breakage |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LGCY-01 | Phase 67 | Complete |
| LGCY-02 | Phase 68 | Pending |
| LGCY-03 | Phase 69 | Pending |
| LGCY-04 | Phase 69 | Pending |
| LGCY-05 | Phase 68 | Pending |
| LGCY-06 | Phase 70 | Pending |
| LGCY-07 | Phase 69 | Pending |
| CONF-01 | Phase 71 | Pending |
| CONF-02 | Phase 71 | Pending |
| CONF-03 | Phase 71 | Pending |
| WANE-01 | Phase 72 | Pending |
| WANE-02 | Phase 72 | Pending |
| WANE-03 | Phase 72 | Pending |

**Coverage:**
- v1.13 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after roadmap creation*
