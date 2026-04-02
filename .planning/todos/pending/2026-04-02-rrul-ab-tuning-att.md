---
title: RRUL A/B tuning sweep for ATT WAN
area: tuning
priority: medium
created: 2026-04-02
---

# RRUL A/B Tuning Sweep — ATT WAN

Run the same 10-parameter RRUL A/B testing methodology used on Spectrum (2026-04-02, 23 soaks) against the ATT DSL link.

## Parameters to test

All parameters in `/etc/wanctl/att.yaml`:

1. `factor_down_yellow` — current value TBD (check att.yaml)
2. `green_required` DL — current value TBD
3. `green_required` UL — test independently from DL
4. `step_up_mbps` DL — current value TBD
5. `dwell_cycles` — may need adding to YAML (uses code default)
6. `factor_down` (RED) — current value TBD
7. `deadband_ms` — may need adding to YAML (uses code default)
8. `target_bloat_ms` — current value TBD
9. `warn_bloat_ms` — current value TBD
10. `hard_red_bloat_ms` — current value TBD

## Methodology

- Back-to-back 5-minute RRUL soaks via flent to Dallas server (104.200.21.31)
- One variable at a time, A/B or three-way comparison
- Measure: ICMP median/p99/max, DL/UL throughput, state distribution
- RRUL must route through ATT WAN (use FORCE_OUT_ATT mangle rule on router)

## Key differences from Spectrum

- ATT is DSL (not DOCSIS) — near-zero idle jitter, point-to-point circuit
- 95 Mbps DL / 18 Mbps UL (much lower bandwidth than Spectrum 940/38)
- Different congestion characteristics — DSL doesn't have CMTS scheduling noise
- dwell_cycles and target_bloat_ms may have different optimal values (DSL may work fine with defaults)

## Deliverables

- Update `docs/CABLE_TUNING.md` with DSL-specific notes (or create `docs/DSL_TUNING.md`)
- Update `configs/examples/att-vm.yaml.example` with validated values
- Update `configs/examples/dsl.yaml.example` with validated values
- Memory entries for each parameter finding
- CHANGELOG entry

## Prerequisites

- Confirm FORCE_OUT_ATT mangle rule is active on MikroTik router
- Confirm ATT service is healthy and at ceiling before testing
- Schedule during low-usage period (RRUL will saturate the 95Mbps link)
