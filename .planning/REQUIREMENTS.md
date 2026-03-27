# Requirements: wanctl v1.23 Self-Optimizing Controller

**Defined:** 2026-03-26
**Core Value:** Sub-second congestion detection with 50ms control loops — now self-optimizing across detection AND response

## v1.23 Requirements

Complete the tuner's vision, heal fusion automatically, make tc calls cheaper via direct netlink, and add proper observability.

### Netlink Backend

- [x] **NLNK-01**: LinuxCakeBackend can change CAKE bandwidth via pyroute2 netlink instead of subprocess `tc`
- [x] **NLNK-02**: NetlinkCakeBackend maintains a singleton IPRoute connection for daemon lifetime with reconnect on socket death
- [x] **NLNK-03**: NetlinkCakeBackend falls back to subprocess `tc` if netlink call fails
- [x] **NLNK-04**: NetlinkCakeBackend reads CAKE per-tin stats via netlink instead of subprocess `tc -j qdisc show`
- [x] **NLNK-05**: Factory registration allows config `transport: "linux-cake-netlink"` to select the netlink backend

### Fusion Healing

- [ ] **FUSE-01**: Controller auto-suspends fusion when protocol correlation drops below configurable threshold for sustained period
- [ ] **FUSE-02**: Controller auto-re-enables fusion when protocol correlation recovers (3-state: ACTIVE/SUSPENDED/RECOVERING)
- [ ] **FUSE-03**: Fusion state transitions trigger Discord alerts via AlertEngine
- [ ] **FUSE-04**: TuningEngine locks fusion_icmp_weight parameter when fusion healer suspends fusion
- [ ] **FUSE-05**: Health endpoint exposes fusion heal state (active/suspended/recovering) and correlation history

### Response Tuning

- [x] **RTUN-01**: Tuner learns optimal step_up_mbps from production recovery episode analysis
- [x] **RTUN-02**: Tuner learns optimal factor_down from congestion resolution speed
- [x] **RTUN-03**: Tuner learns optimal green_cycles_required from step-up re-trigger rate
- [x] **RTUN-04**: Oscillation lockout freezes all response parameters when transitions/minute exceeds threshold
- [x] **RTUN-05**: Response tuning is opt-in via exclude_params (disabled by default, matching existing tuning graduation pattern)

### Observability

- [ ] **OBSV-01**: Prometheus metrics exported via CustomCollector on separate port (9103) with zero hot-loop overhead
- [ ] **OBSV-02**: Grafana dashboard JSON committed to repo with provisioning YAML for operator import
- [ ] **OBSV-03**: Per-tin CAKE metrics exported with stable labels (wan, direction, tin)
- [ ] **OBSV-04**: prometheus_client is optional dependency — core operation works without it installed

### Retention

- [x] **RETN-01**: Retention thresholds configurable via `storage.retention` YAML section
- [x] **RETN-02**: Config validation enforces retention >= tuner lookback_hours data availability
- [x] **RETN-03**: Prometheus-compensated mode enables aggressive local retention (24-48h) when long-term TSDB is available

## Future Requirements

### v1.24 Candidates

- **IRTT-01**: Multiple IRTT servers for geographic diversity and redundancy
- **RESIL-01**: Graceful VM bypass if cake-shaper VM fails (bridge failover or MikroTik fallback route)
- **TEST-01**: Integration/contract tests for RouterOS communication (VCR-style replay)

## Out of Scope

| Feature | Reason |
|---------|--------|
| ML-based bandwidth prediction | Statistical tuning is already the adaptive learning system; ML adds complexity without measurable gain |
| Auto-tuning ceiling_mbps from speed tests | Policy decision, not measurement; saturating the link disrupts latency-sensitive traffic |
| Push-gateway / remote-write bridge | Pull model works on same VLAN; adds complexity without benefit |
| Cycle interval < 50ms | Validated as optimal for 20Hz signal processing chain; CAKE AQM interval is 100ms |
| Breaking changes to config format | Maintain backward compatibility |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| NLNK-01 | Phase 117 | Complete |
| NLNK-02 | Phase 117 | Complete |
| NLNK-03 | Phase 117 | Complete |
| NLNK-04 | Phase 117 | Complete |
| NLNK-05 | Phase 117 | Complete |
| FUSE-01 | Phase 119 | Pending |
| FUSE-02 | Phase 119 | Pending |
| FUSE-03 | Phase 119 | Pending |
| FUSE-04 | Phase 119 | Pending |
| FUSE-05 | Phase 119 | Pending |
| RTUN-01 | Phase 120 | Complete |
| RTUN-02 | Phase 120 | Complete |
| RTUN-03 | Phase 120 | Complete |
| RTUN-04 | Phase 120 | Complete |
| RTUN-05 | Phase 120 | Complete |
| OBSV-01 | Phase 121 | Pending |
| OBSV-02 | Phase 121 | Pending |
| OBSV-03 | Phase 121 | Pending |
| OBSV-04 | Phase 121 | Pending |
| RETN-01 | Phase 118 | Complete |
| RETN-02 | Phase 118 | Complete |
| RETN-03 | Phase 118 | Complete |

**Coverage:**
- v1.23 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after roadmap creation*
