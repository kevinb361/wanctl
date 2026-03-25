# Requirements: wanctl v1.21 CAKE Offload

**Defined:** 2026-03-24
**Core Value:** Sub-second congestion detection with 50ms control loops -- now with full Linux CAKE capabilities

## v1.21 Requirements

Requirements for CAKE offload to Debian 12 VM on Proxmox. Each maps to roadmap phases.

### Backend

- [x] **BACK-01**: LinuxCakeBackend implements RouterBackend with `set_bandwidth()` via `tc qdisc change`
- [x] **BACK-02**: LinuxCakeBackend parses queue stats via `tc -j -s qdisc show` with JSON output
- [x] **BACK-03**: LinuxCakeBackend validates CAKE params after `tc qdisc replace` -- reads back via `tc -j qdisc show` and verifies diffserv mode, overhead, bandwidth match expectations
- [x] **BACK-04**: Per-tin statistics parsed from CAKE (Voice/Video/BE/Bulk -- drops, delays, flows per tin)

### CAKE Optimization

- [x] **CAKE-01**: `split-gso` enabled to split TSO/GSO segments before queuing
- [x] **CAKE-02**: ECN marking enabled for explicit congestion notification (download CAKE)
- [x] **CAKE-03**: `ack-filter` enabled for ACK compression on upload
- [x] **CAKE-05**: Precise `overhead`/`mpu` configured per-link (`docsis` for Spectrum, `bridged-ptm` for ATT)
- [x] **CAKE-06**: `memlimit` configured for bounded memory usage (32MB for ~1Gbps links)
- [x] **CAKE-07**: Per-tin statistics visible in health endpoint and wanctl-history
- [x] **CAKE-08**: `ingress` keyword on download CAKE for tighter drop accounting
- [x] **CAKE-09**: `ecn` on download CAKE for softer congestion signaling than drops
- [x] **CAKE-10**: `rtt` parameter configured per-link (candidate for adaptive tuning, default 100ms may be conservative)

### Configuration

- [x] **CONF-01**: `transport: "linux-cake"` config option with bridge interface names in YAML
- [x] **CONF-02**: Factory function selects LinuxCakeBackend based on transport config
- [x] **CONF-03**: Steering daemon uses dual-backend -- linux-cake for CAKE stats, REST for mangle rules
- [x] **CONF-04**: `wanctl-check-config` validates linux-cake transport settings and interface existence

### Infrastructure

- [x] **INFR-01**: IOMMU group verification confirms all 4 target NICs are in separate groups
- [ ] **INFR-02**: Proxmox VM created with VFIO passthrough for 4 NICs (2x i210, 2x i350)
- [ ] **INFR-03**: Transparent L2 bridges (br-spectrum, br-att) with STP disabled, forward_delay=0
- [ ] **INFR-04**: CAKE qdisc initialized on bridge member port egress via `tc qdisc replace`
- [ ] **INFR-05**: systemd-networkd persistent bridge and interface configuration (CAKE setup owned by wanctl, NOT systemd)
- [ ] **INFR-06**: VLAN 110 management interface on virtio NIC for SSH/health/ICMP/IRTT

### Cutover

- [ ] **CUTR-01**: MikroTik queue tree entries disabled (kept for rollback, not deleted)
- [ ] **CUTR-02**: Physical cabling completed -- modems through VM NICs to router
- [ ] **CUTR-03**: Staged migration -- ATT first (lower risk), then Spectrum
- [ ] **CUTR-04**: Rollback procedure documented and drill-tested before production cutover
- [ ] **CUTR-05**: RRUL benchmark before/after comparison validates throughput improvement

## Future Requirements

### Deferred

- **CAKE-11**: `diffserv8` mode for finer-grained traffic classification (requires mangle rule expansion)
- **CAKE-12**: Per-tin bandwidth allocation tuning (custom tin ratios)
- **PERF-01**: pyroute2 netlink backend for sub-millisecond tc calls (if subprocess proves too slow)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Generic multi-vendor router support | Linux CAKE backend is specific to transparent bridge offload |
| Automated VM provisioning (Terraform/Ansible) | Single VM, manual Proxmox setup is sufficient |
| 10GbE passthrough for Spectrum | i210 1GbE adequate -- Spectrum delivers ~820 Mbps currently |
| Multiple reflector IRTT servers | Separate concern from CAKE offload, tracked as existing todo |
| Automatic failover to MikroTik CAKE | Manual bypass cables + MikroTik queue re-enable is acceptable |
| IFB device for ingress shaping | Bridge member port egress provides bidirectional shaping -- IFB is unnecessary overhead (confirmed by LibreQoS, MagicBox) |
| `nat` CAKE keyword | Transparent bridge has no NAT/conntrack -- `nat` adds overhead for zero benefit |
| `wash` CAKE keyword | DSCP marks from RB5009 mangle rules must survive the bridge for diffserv4 classification |
| `autorate-ingress` CAKE keyword | wanctl IS the autorate system -- built-in CAKE autorate would conflict |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BACK-01 | Phase 105 | Complete |
| BACK-02 | Phase 105 | Complete |
| BACK-03 | Phase 105 | Complete |
| BACK-04 | Phase 105 | Complete |
| CAKE-01 | Phase 106 | Complete |
| CAKE-02 | Phase 106 | Complete |
| CAKE-03 | Phase 106 | Complete |
| CAKE-05 | Phase 106 | Complete |
| CAKE-06 | Phase 106 | Complete |
| CAKE-07 | Phase 108 | Complete |
| CAKE-08 | Phase 106 | Complete |
| CAKE-09 | Phase 106 | Complete |
| CAKE-10 | Phase 106 | Complete |
| CONF-01 | Phase 107 | Complete |
| CONF-02 | Phase 107 | Complete |
| CONF-03 | Phase 108 | Complete |
| CONF-04 | Phase 107 | Complete |
| INFR-01 | Phase 104 | Complete |
| INFR-02 | Phase 109 | Pending |
| INFR-03 | Phase 109 | Pending |
| INFR-04 | Phase 109 | Pending |
| INFR-05 | Phase 109 | Pending |
| INFR-06 | Phase 109 | Pending |
| CUTR-01 | Phase 110 | Pending |
| CUTR-02 | Phase 110 | Pending |
| CUTR-03 | Phase 110 | Pending |
| CUTR-04 | Phase 110 | Pending |
| CUTR-05 | Phase 110 | Pending |

**Coverage:**
- v1.21 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after open-source ecosystem research and roadmap revision*
