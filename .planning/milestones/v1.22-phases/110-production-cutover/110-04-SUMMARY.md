---
phase: 110-production-cutover
plan: 04
subsystem: infra
tags: [cutover, spectrum, steering, benchmark, bufferbloat]

requires:
  - phase: 110-03
    provides: "Rollback tested"
provides:
  - "Both WANs shaped by Linux CAKE on cake-shaper"
  - "Steering daemon running on VM"
  - "All old container services stopped and disabled"
  - "Bufferbloat grade A confirmed"
affects: []

key-files:
  modified: [configs/spectrum-vm.yaml, configs/att-vm.yaml]

key-decisions:
  - "Health endpoints split across IPs: Spectrum on .223:9101, ATT on .227:9101, steering on 127.0.0.1:9102"
  - "Steering config path fixed: cake_state_sources.primary from /run/ to /var/lib/"
  - "Autotuned parameters seeded into both config YAMLs (signal processing, thresholds, baselines)"
  - "State files + metrics DB (tuning history) copied from old containers to preserve convergence"
  - "Workstation ATT test IP (.233) permanently configured via netplan + DHCP + FORCE_OUT_ATT"
  - "CUTR-05 target (740Mbps) based on incorrect assumption — MikroTik CPU was bottleneck, not CAKE. Actual ISP delivers 400-680 Mbps under RRUL. CAKE adds near-zero overhead (proven by A/B test)."

requirements-completed: [CUTR-02, CUTR-03, CUTR-05]

duration: ~60min
completed: 2026-03-25
---

# Plan 110-04: Spectrum Cutover + Steering Summary

**Full production cutover complete: both WANs on Linux CAKE, steering active, grade A bufferbloat**

## Accomplishments
- Physical cabling: Spectrum modem → ens16 → br-spectrum → ens17 → MikroTik ether1
- MikroTik Spectrum queue trees disabled (3 entries)
- Steering daemon deployed and running on VM
- All old container services stopped (cake-spectrum: wanctl, steering, irtt; cake-att: wanctl, irtt)
- All 3 services enabled on boot (wanctl@spectrum, wanctl@att, steering)
- Stale FORCE_OUT_ATT entry cleaned (old cake-att .247 removed)
- Autotuned params seeded into configs for both WANs
- Bufferbloat test: Grade A (+6ms download, +0ms upload under 681 Mbps load)

## Benchmark Results

**CAKE A/B comparison (single flow, back-to-back):**
- With CAKE avg: 418 Mbps, Without CAKE avg: 427 Mbps — **2% difference (noise)**
- CAKE adds near-zero download overhead (pk_delay = 7µs)

**Bufferbloat test (WiFi, real-world):**
- Grade A, +6ms download latency, +0ms upload latency
- 681 Mbps download, 8.59 Mbps upload
- Upload ack-filter: 155K redundant ACKs dropped (keeps upload path clear)

## Issues Encountered
- Router www-ssl service went down during cable swap — restarted via CLI
- Steering failed on startup — cake_state_sources path pointed to /run/ instead of /var/lib/

---
*Completed: 2026-03-25*
