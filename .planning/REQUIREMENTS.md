# Requirements: wanctl

**Defined:** 2026-04-02
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.26 Requirements

Requirements for Tuning Validation milestone. Re-test all tuning parameters on linux-cake transport after REST→linux-cake backend switch.

### Pre-Test Validation

- [x] **GATE-01**: Spectrum transport confirmed as linux-cake with CAKE qdiscs active on all 4 bridge NICs (ens16, ens17, ens27, ens28)
- [x] **GATE-02**: MikroTik router has no active CAKE queues that could cause double-shaping
- [x] **GATE-03**: A wanctl rate change produces visible bandwidth change in `tc -s qdisc show`

### Tuning

- [x] **TUNE-01**: All 9 DL parameters tested sequentially (one variable at a time), each winner applied before next test, under consistent network conditions
- [x] **TUNE-02**: All 3 UL parameters tested sequentially, each winner applied before next test
- [ ] **TUNE-03**: CAKE rtt (50ms vs 100ms) tested after DL/UL sweep complete
- [ ] **TUNE-04**: Confirmation re-test of response group (factor_down_yellow, factor_down, step_up_mbps) with all other winners in place to check for interaction effects

### Results

- [x] **RSLT-01**: Each test documented with winner, metrics delta, and test conditions (time of day, cable plant load)
- [ ] **RSLT-02**: Production config (spectrum.yaml) updated with final validated parameter set

## Future Requirements

None identified.

## Out of Scope

| Feature                          | Reason                                                                         |
| -------------------------------- | ------------------------------------------------------------------------------ |
| ATT WAN tuning                   | Separate todo, different transport (REST), different link characteristics      |
| Boot validation CLI              | Deferred from v1.25, requires physical access                                  |
| Automated A/B test tooling       | Manual RRUL methodology is established and sufficient                          |
| Full factorial parameter testing | Sequential one-at-a-time sufficient; factorial would require hundreds of tests |

## Traceability

| Requirement | Phase     | Status   |
| ----------- | --------- | -------- |
| GATE-01     | Phase 126 | Complete |
| GATE-02     | Phase 126 | Complete |
| GATE-03     | Phase 126 | Complete |
| TUNE-01     | Phase 127 | Complete |
| TUNE-02     | Phase 128 | Complete |
| TUNE-03     | Phase 129 | Pending  |
| TUNE-04     | Phase 129 | Pending  |
| RSLT-01     | Phase 127 | Complete |
| RSLT-02     | Phase 130 | Pending  |

**Coverage:**

- v1.26 requirements: 9 total
- Mapped to phases: 9/9
- Unmapped: 0

---

_Requirements defined: 2026-04-02_
_Last updated: 2026-04-02 after Phase 127 completion_
