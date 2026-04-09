# Requirements: wanctl v1.30

**Defined:** 2026-04-08
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.30 Requirements

Requirements for Burst Detection milestone. Each maps to roadmap phases.

### Detection

- [ ] **DET-01**: Controller detects multi-flow burst ramps via RTT second derivative (acceleration) within 200ms of onset
- [ ] **DET-02**: Burst detection does not false-trigger on normal single-flow congestion (video call + browsing)

### Response

- [ ] **RSP-01**: When burst ramp detected, controller jumps directly to SOFT_RED or RED floor (skipping gradual descent)
- [ ] **RSP-02**: Fast-path response does not cause rate oscillation (aggressive drop → recovery → aggressive drop loop)

### Validation

- [ ] **VAL-01**: p99 latency under tcp_12down drops below 500ms (from current 800-3200ms)
- [ ] **VAL-02**: No regression on RRUL and rrul_be tests (median and p99 stay within 10% of current)
- [ ] **VAL-03**: No false triggers during 24h normal usage soak test

## Future Requirements

- Variance-gated fusion healer correlation (idle-link Pearson r noise fix) — deferred to measurement quality milestone
- CAKE tin separation improvements (diffserv marking, per-flow fairness) — deferred pending burst detection results

## Out of Scope

- CAKE AQM parameter changes — burst detection is controller-side, not AQM-side
- ATT WAN tuning sweep — separate todo, different WAN characteristics
- Fusion healer changes — separate signal processing concern

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| DET-01 | Phase 151 | Not started |
| DET-02 | Phase 151 | Not started |
| RSP-01 | Phase 152 | Not started |
| RSP-02 | Phase 152 | Not started |
| VAL-01 | Phase 153 | Not started |
| VAL-02 | Phase 153 | Not started |
| VAL-03 | Phase 153 | Not started |
