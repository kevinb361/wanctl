---
phase: 110-production-cutover
plan: 02
subsystem: infra
tags: [cutover, att, cabling, cake, vfio, bridge]

requires:
  - phase: 110-01
    provides: "VM configs and baseline benchmarks"
provides:
  - "ATT traffic flowing through cake-shaper VM bridge"
  - "CAKE active on ens28 (download) + ens27 (upload)"
  - "MikroTik ATT queue trees disabled"
  - "Old cake-att container services stopped"
affects: [110-03, 110-04]

key-files:
  created: [src/wanctl/backends/linux_cake_adapter.py, tests/test_linux_cake_adapter.py]
  modified: [src/wanctl/backends/linux_cake.py, src/wanctl/backends/__init__.py, src/wanctl/autorate_continuous.py, src/wanctl/rtt_measurement.py]

key-decisions:
  - "LinuxCakeAdapter wraps two backends (download + upload on separate NICs) with RouterOS-compatible set_limits() API"
  - "Download CAKE on router-side NIC egress (ens28), upload CAKE on modem-side NIC egress (ens27)"
  - "ecn keyword removed from CAKE init (iproute2-6.15.0 incompatible, CAKE default anyway)"
  - "bridged-ptm expanded to ptm overhead 22 (compound keyword not valid tc token)"
  - "CAP_NET_ADMIN added to systemd service (tc qdisc replace requires it)"
  - "python3-systemd installed (watchdog sd_notify was no-op without it)"
  - "ping_source_ip config field + second IP (10.10.110.227) for per-WAN ICMP routing"

requirements-completed: [CUTR-01, CUTR-02, CUTR-03]

duration: ~90min
completed: 2026-03-25
---

# Plan 110-02: ATT Cutover Summary

**ATT migrated to Linux CAKE on cake-shaper: +8.5% download, +97% upload, -3.8% latency vs MikroTik baseline**

## Accomplishments
- Physical cabling: ATT modem → ens27 → br-att → ens28 → MikroTik ether2
- LinuxCakeAdapter created to bridge LinuxCakeBackend to daemon's set_limits() API
- 5 bugs fixed during integration: adapter wiring, overhead expansion, ecn removal, CAP_NET_ADMIN, python3-systemd
- MikroTik ATT queue trees disabled (3 entries)
- Old cake-att container fully shut down

## Issues Encountered
- daemon hardcoded RouterOS — created LinuxCakeAdapter (adapter pattern)
- bridged-ptm not a valid tc keyword — expanded to ptm + overhead 22
- ecn not supported by iproute2-6.15.0 — removed (CAKE default)
- Operation not permitted on tc — added CAP_NET_ADMIN to systemd service
- Watchdog timeout — installed python3-systemd for sd_notify

---
*Completed: 2026-03-25*
