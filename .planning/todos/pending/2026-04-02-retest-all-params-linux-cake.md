---
title: Re-test ALL tuning parameters on linux-cake transport
area: tuning
priority: critical
created: 2026-04-02
---

# Re-Test All Parameters — Linux-CAKE Transport

ALL 30 previous RRUL A/B tests were run while Spectrum used REST transport.
Rate changes went to the MikroTik router, NOT the local CAKE qdiscs.
The entire tuning sweep must be re-done on the correct linux-cake transport.

## Parameters to re-test (same methodology)

DL parameters:
1. factor_down_yellow: 0.92 vs 0.97
2. green_required: 3 vs 5
3. step_up_mbps: 10 vs 15
4. factor_down (RED): 0.85 vs 0.90
5. dwell_cycles: 3 vs 5
6. deadband_ms: 3.0 vs 5.0
7. target_bloat_ms: 9 vs 12 vs 15
8. warn_bloat_ms: 30 vs 45 vs 60
9. hard_red_bloat_ms: 60 vs 80 vs 100

UL parameters:
10. factor_down: 0.85 vs 0.90
11. step_up_mbps: 1 vs 2
12. green_required: 3 vs 5

CAKE parameter:
13. rtt: 50ms vs 100ms (re-test since feedback loop is now correct)

## Pre-test checklist (MANDATORY)

- [ ] Verify `transport: "linux-cake"` in spectrum.yaml
- [ ] Verify `cake_params` section exists with correct interfaces
- [ ] Verify `tc -d qdisc show` shows CAKE on all 4 NICs
- [ ] Trigger a rate change and watch `tc -s qdisc show` — confirm CAKE bandwidth changes
- [ ] Confirm wanctl health endpoint shows correct version

## Current production values (starting point)

These were chosen from the invalidated REST-transport tests.
They may or may not be optimal on linux-cake transport.

```
DL: factor_down_yellow=0.92, green_required=5, step_up=15,
    factor_down=0.90, dwell_cycles=5, deadband_ms=3.0,
    target_bloat_ms=9, warn_bloat_ms=45, hard_red_bloat_ms=60
UL: factor_down=0.85, step_up=1, green_required=5
CAKE: rtt=50ms
```
