# Requirements: wanctl v1.19 Signal Fusion

**Defined:** 2026-03-17
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.19 Requirements

Requirements for signal fusion milestone. Each maps to roadmap phases.

### Signal Fusion

- [ ] **FUSE-01**: IRTT and icmplib RTT signals are combined via configurable weighted average for congestion control input
- [ ] **FUSE-02**: Fusion ships disabled by default with SIGUSR1 toggle for zero-downtime enable/disable
- [ ] **FUSE-03**: Fusion weights are YAML-configurable with warn+default validation
- [ ] **FUSE-04**: When IRTT is unavailable or stale, fusion falls back to icmplib-only with zero behavioral change
- [ ] **FUSE-05**: Fusion state (enabled, weights, active signal sources) is visible in health endpoint

### Asymmetric Congestion

- [ ] **ASYM-01**: Upstream vs downstream congestion is detected from IRTT send_delay vs receive_delay within same measurement burst
- [ ] **ASYM-02**: Asymmetric congestion direction is available as a named attribute for downstream consumers
- [ ] **ASYM-03**: Asymmetric congestion is persisted in SQLite for trend analysis

### Reflector Quality

- [x] **REFL-01**: Each ping_host reflector has a rolling quality score based on success rate, jitter, and timeout frequency
- [x] **REFL-02**: Low-scoring reflectors are deprioritized (skipped) when score falls below configurable threshold
- [x] **REFL-03**: Deprioritized reflectors are periodically re-checked for recovery
- [ ] **REFL-04**: Reflector quality scores are visible in health endpoint

### IRTT Loss Alerts

- [ ] **ALRT-01**: Sustained upstream packet loss triggers alert via existing AlertEngine with configurable threshold
- [ ] **ALRT-02**: Sustained downstream packet loss triggers alert via existing AlertEngine with configurable threshold
- [ ] **ALRT-03**: IRTT loss alerts use per-event cooldown consistent with existing alert types

## Future Requirements

Deferred to v1.20+. Tracked but not in current roadmap.

### NTP-Synchronized OWD

- **OWD-01**: NTP validation script verifies clock sync between containers and IRTT server
- **OWD-02**: True one-way delay measurement using NTP-synchronized timestamps for authoritative asymmetry detection

### Advanced Fusion

- **AFUS-01**: Adaptive fusion weights that self-tune based on signal quality history
- **AFUS-02**: Per-reflector IRTT path matching for meaningful cross-protocol correlation

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Replace icmplib with IRTT in hot loop | 5-10ms subprocess overhead incompatible with 50ms cycle budget |
| NTP-synchronized OWD as authoritative | Clock sync fragile in LXC containers -- defer to v1.20 after chrony verification |
| Cross-protocol path correction | ATT path asymmetry is geographic (Dallas vs CDN), not correctable in code |
| ML-based fusion weight optimization | Unpredictable behavior, untestable edge cases |
| Continuous IRTT background stream | Wastes bandwidth -- short burst measurements every 5-10s |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FUSE-01 | Phase 96 | Pending |
| FUSE-02 | Phase 97 | Pending |
| FUSE-03 | Phase 96 | Pending |
| FUSE-04 | Phase 96 | Pending |
| FUSE-05 | Phase 97 | Pending |
| ASYM-01 | Phase 94 | Pending |
| ASYM-02 | Phase 94 | Pending |
| ASYM-03 | Phase 94 | Pending |
| REFL-01 | Phase 93 | Complete |
| REFL-02 | Phase 93 | Complete |
| REFL-03 | Phase 93 | Complete |
| REFL-04 | Phase 93 | Pending |
| ALRT-01 | Phase 95 | Pending |
| ALRT-02 | Phase 95 | Pending |
| ALRT-03 | Phase 95 | Pending |

**Coverage:**
- v1.19 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-03-17*
*Last updated: 2026-03-17 after roadmap creation*
