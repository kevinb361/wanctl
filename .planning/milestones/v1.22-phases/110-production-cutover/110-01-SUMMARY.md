---
phase: 110-production-cutover
plan: 01
subsystem: infra
tags: [config, yaml, linux-cake, benchmark, rrul, flent]

requires:
  - phase: 109-vm-infrastructure-bridges
    provides: "VM 206 with VFIO NICs, bridges, wanctl deployed"
provides:
  - "configs/spectrum-vm.yaml with transport: linux-cake and cake_params"
  - "configs/att-vm.yaml with transport: linux-cake and cake_params"
  - "Baseline RRUL benchmarks (MikroTik CAKE) for before/after comparison"
  - "Secrets deployed to cake-shaper /etc/wanctl/secrets"
affects: [110-02, 110-03, 110-04]

tech-stack:
  added: []
  patterns: [linux-cake-transport-config, gitignored-deployment-configs]

key-files:
  created: [configs/spectrum-vm.yaml, configs/att-vm.yaml, configs/examples/spectrum-vm.yaml.example, configs/examples/att-vm.yaml.example]
  modified: []

key-decisions:
  - "Deployment configs gitignored per project convention -- example templates tracked in configs/examples/"
  - "ecn keyword omitted from cake_params (not supported by iproute2-6.15.0, ECN default in CAKE)"
  - "Both RRUL baselines likely routed through Spectrum default gateway -- ATT numbers may not reflect true ATT performance"

patterns-established:
  - "linux-cake config pattern: clone REST config, change transport, add cake_params section"

requirements-completed: [CUTR-05]

duration: ~10min
completed: 2026-03-25
---

# Plan 110-01: Config YAML + Baseline Benchmarks Summary

**linux-cake configs created for both WANs, baseline RRUL benchmarks captured: Spectrum 696 Mbps avg download (MikroTik ceiling to beat)**

## Performance

- **Duration:** ~10 min (including 2x 60s benchmarks)
- **Started:** 2026-03-25
- **Completed:** 2026-03-25
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- configs/spectrum-vm.yaml: transport linux-cake, ens17 interface, docsis overhead 18, memlimit 32mb
- configs/att-vm.yaml: transport linux-cake, ens28 interface, bridged-ptm overhead 0, memlimit 32mb
- All production thresholds, IRTT, fusion, signal processing settings preserved from existing configs
- Secrets deployed to cake-shaper from cake-spectrum container
- Baseline RRUL benchmarks:
  - Spectrum: 696.0 Mbps download avg, 9.6 Mbps upload avg, 35.2 ms latency under load
  - ATT: 627.3 Mbps download avg, 7.4 Mbps upload avg, 40.4 ms latency under load

## Task Commits

1. **Task 1: Create VM config YAML files** - `17fb279` (feat)
2. **Task 2: Deploy secrets + run baselines** - executed inline (secrets via SSH, benchmarks via flent)

## Files Created/Modified
- `configs/spectrum-vm.yaml` - linux-cake transport config for Spectrum (gitignored)
- `configs/att-vm.yaml` - linux-cake transport config for ATT (gitignored)
- `configs/examples/spectrum-vm.yaml.example` - git-tracked template
- `configs/examples/att-vm.yaml.example` - git-tracked template

## Decisions Made
- Deployment configs gitignored (project convention) with example templates in git

## Deviations from Plan
None — plan executed as written.

## Issues Encountered
- Both flent RRUL tests route through default gateway (Spectrum) — ATT baseline may not reflect true ATT performance

## Next Phase Readiness
- Configs ready for deployment to cake-shaper (Plan 110-02)
- Baseline benchmarks captured for before/after comparison (Plan 110-04)
- Secrets deployed to cake-shaper

---
*Phase: 110-production-cutover*
*Completed: 2026-03-25*
