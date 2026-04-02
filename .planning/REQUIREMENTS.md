# Requirements: wanctl

**Defined:** 2026-04-02
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.25 Requirements

Requirements for Reboot Resilience milestone. Each maps to roadmap phases.

### Boot Resilience

- [x] **BOOT-01**: All 4 bridge NICs have ethtool optimizations persisted and applied at boot before wanctl starts
- [x] **BOOT-02**: NIC tuning oneshot is idempotent, logs what was applied, and fails gracefully if a NIC is missing
- [ ] **BOOT-03**: wanctl services have explicit systemd dependency on NIC tuning completion
- [ ] **BOOT-04**: Full boot chain works end-to-end: bridges up -> NIC tuning -> wanctl (CAKE) -> recovery timer

### Validation

- [ ] **VALN-01**: Post-boot validation confirms NIC tuning applied, CAKE qdiscs active, and wanctl services healthy
- [ ] **VALN-02**: Validation is runnable on-demand as a CLI command (not only at boot)

## Future Requirements

None identified.

## Out of Scope

| Feature                          | Reason                                                            |
| -------------------------------- | ----------------------------------------------------------------- |
| CAKE qdisc setup in systemd unit | wanctl already handles CAKE via initialize_cake -- no duplication |
| Redundant IRTT server            | Separate concern, not boot-related                                |
| VM high-availability / failover  | Out of scope for this milestone -- infrastructure concern         |

## Traceability

| Requirement | Phase     | Status   |
| ----------- | --------- | -------- |
| BOOT-01     | Phase 125 | Complete |
| BOOT-02     | Phase 125 | Complete |
| BOOT-03     | Phase 125 | Pending  |
| BOOT-04     | Phase 125 | Pending  |
| VALN-01     | Phase 126 | Pending  |
| VALN-02     | Phase 126 | Pending  |

**Coverage:**

- v1.25 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---

_Requirements defined: 2026-04-02_
_Last updated: 2026-04-02 after roadmap creation_
