# Requirements: wanctl v1.21 CAKE Offload

**Defined:** 2026-03-24
**Core Value:** Sub-second congestion detection with 50ms control loops — now with full Linux CAKE capabilities

## v1.21 Requirements

Requirements for CAKE offload to Debian 12 VM on Proxmox. Each maps to roadmap phases.

### Backend

- [ ] **BACK-01**: LinuxCakeBackend implements RouterBackend with `set_bandwidth()` via `tc qdisc change`
- [ ] **BACK-02**: LinuxCakeBackend parses queue stats via `tc -j -s qdisc show` with JSON output
- [ ] **BACK-03**: LinuxCakeBackend validates CAKE qdisc presence and tc availability via `test_connection()`
- [ ] **BACK-04**: Per-tin statistics parsed from CAKE (Voice/Video/BE/Bulk — drops, delays, flows per tin)
- [ ] **BACK-05**: IFB device creation and lifecycle management for download (ingress) shaping

### CAKE Optimization

- [ ] **CAKE-01**: `split-gso` enabled to split TSO/GSO segments before queuing
- [ ] **CAKE-02**: ECN marking enabled for explicit congestion notification
- [ ] **CAKE-03**: `ack-filter` enabled for ACK compression on upload
- [ ] **CAKE-04**: `nat` flow hashing enabled for per-host fairness through NAT
- [ ] **CAKE-05**: Precise `overhead`/`mpu` configured per-link (Spectrum DOCSIS, ATT bridged-ptm)
- [ ] **CAKE-06**: `memlimit` configured for bounded memory usage
- [ ] **CAKE-07**: Per-tin statistics visible in health endpoint and wanctl-history

### Configuration

- [ ] **CONF-01**: `transport: "linux-cake"` config option with bridge interface names in YAML
- [ ] **CONF-02**: Factory function selects LinuxCakeBackend based on transport config
- [ ] **CONF-03**: Steering daemon uses dual-backend — linux-cake for CAKE stats, REST for mangle rules
- [ ] **CONF-04**: `wanctl-check-config` validates linux-cake transport settings and interface existence

### Infrastructure

- [ ] **INFR-01**: IOMMU group verification confirms all 4 target NICs are in separate groups
- [ ] **INFR-02**: Proxmox VM created with VFIO passthrough for 4 NICs (2x i210, 2x i350)
- [ ] **INFR-03**: Transparent L2 bridges (br-spectrum, br-att) with STP disabled, forward_delay=0
- [ ] **INFR-04**: CAKE qdisc initialized on bridge member port egress (or IFB for ingress)
- [ ] **INFR-05**: systemd-networkd persistent bridge and interface configuration
- [ ] **INFR-06**: VLAN 110 management interface on virtio NIC for SSH/health/ICMP/IRTT

### Cutover

- [ ] **CUTR-01**: MikroTik queue tree entries disabled (kept for rollback, not deleted)
- [ ] **CUTR-02**: Physical cabling completed — modems through VM NICs to router
- [ ] **CUTR-03**: Staged migration — ATT first (lower risk), then Spectrum
- [ ] **CUTR-04**: Rollback procedure documented and drill-tested before production cutover
- [ ] **CUTR-05**: RRUL benchmark before/after comparison validates throughput improvement

## Future Requirements

### Deferred

- **CAKE-08**: `diffserv8` mode for finer-grained traffic classification (requires mangle rule expansion)
- **CAKE-09**: Per-tin bandwidth allocation tuning (custom tin ratios)
- **PERF-01**: pyroute2 netlink backend for sub-millisecond tc calls (if subprocess proves too slow)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Generic multi-vendor router support | Linux CAKE backend is specific to transparent bridge offload |
| Automated VM provisioning (Terraform/Ansible) | Single VM, manual Proxmox setup is sufficient |
| 10GbE passthrough for Spectrum | i210 1GbE adequate — Spectrum delivers ~820 Mbps currently |
| Multiple reflector IRTT servers | Separate concern from CAKE offload, tracked as existing todo |
| Automatic failover to MikroTik CAKE | Manual bypass cables + MikroTik queue re-enable is acceptable |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BACK-01 | — | Pending |
| BACK-02 | — | Pending |
| BACK-03 | — | Pending |
| BACK-04 | — | Pending |
| BACK-05 | — | Pending |
| CAKE-01 | — | Pending |
| CAKE-02 | — | Pending |
| CAKE-03 | — | Pending |
| CAKE-04 | — | Pending |
| CAKE-05 | — | Pending |
| CAKE-06 | — | Pending |
| CAKE-07 | — | Pending |
| CONF-01 | — | Pending |
| CONF-02 | — | Pending |
| CONF-03 | — | Pending |
| CONF-04 | — | Pending |
| INFR-01 | — | Pending |
| INFR-02 | — | Pending |
| INFR-03 | — | Pending |
| INFR-04 | — | Pending |
| INFR-05 | — | Pending |
| INFR-06 | — | Pending |
| CUTR-01 | — | Pending |
| CUTR-02 | — | Pending |
| CUTR-03 | — | Pending |
| CUTR-04 | — | Pending |
| CUTR-05 | — | Pending |

**Coverage:**
- v1.21 requirements: 27 total
- Mapped to phases: 0
- Unmapped: 27 ⚠️

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after initial definition*
