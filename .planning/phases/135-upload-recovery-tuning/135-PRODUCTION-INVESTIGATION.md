# Post-Milestone Production Investigation: CAKE Parameter Optimization

**Date:** 2026-04-03
**Context:** After v1.27 deployment + production RRUL validation, expert network analysis revealed significant latency issues under bidirectional load. Investigation tested UL ceiling, CAKE rtt, overhead, and wanctl UL management.

## Baseline (pre-investigation)

- **Config:** ceiling=38 Mbps, rtt=50ms (drifted from validated 40ms), overhead=38
- **RRUL:** 173ms median, 2303ms p99, UL 8.0 Mbps sum
- **Grade:** D (unacceptable for bufferbloat control)

## Investigation Results

### 1. UL Ceiling Sweep (biggest win)

| Ceiling | RRUL Median | RRUL p99 | UL Sum | DL Sum | Verdict |
|---------|-------------|----------|--------|--------|---------|
| 38 Mbps (original) | 173ms | 2303ms | 8.0 | 807 | Bad — ISP buffer fills |
| 35 Mbps | 89ms | 490ms | 11.9 | 823 | Better |
| **32 Mbps** | **47-95ms** | **127-818ms** | **10-14** | **813-825** | **Winner — 60% improvement** |
| 30 Mbps | 70ms | 1246ms | 12.7 | 812 | Too low — oscillation |

**Root cause:** At ceiling=38 on a 40 Mbps ISP plan, only 5% headroom exists. The ISP's CMTS buffer fills before CAKE can react. At ceiling=32 (80% of plan), the ISP buffer never saturates. The remaining 8 Mbps of ISP capacity serves as a safety margin.

**Deployed:** ceiling=32 Mbps

### 2. wanctl UL Rate Management (is it helping?)

| Config | RRUL Median | UL Sum | Verdict |
|--------|-------------|--------|---------|
| wanctl active (floor=8, ceil=32) | 47ms | 13 Mbps | Good |
| wanctl disabled (floor=ceil=32) | 126ms | 9 Mbps | Bad |

**Conclusion:** wanctl IS helping. Dynamic rate management adds value on top of CAKE's AQM. CAKE alone at a fixed rate can't prevent ISP buffer bloat during sustained upload bursts.

### 3. CAKE rtt Parameter

| rtt | RRUL Avg Median (3 runs) | DL Throughput | Notes |
|-----|--------------------------|---------------|-------|
| 25ms (MikroTik tuned) | 63.8ms | 765-795 Mbps | Slightly less DL throughput |
| 40ms (v1.26 validated) | 69.6ms | 809-829 Mbps | Better DL throughput balance |
| 50ms (drifted production) | 68-95ms | 813-825 Mbps | Similar to 40ms |
| 100ms (CAKE default) | 86ms | 849 Mbps | More DL, worse latency |

**MikroTik reference:** The heavily-tuned MikroTik CAKE config uses rtt=25ms for both Spectrum directions. However, MikroTik operates at L3 (routing) while the VM bridge operates at L2. The optimal rtt may differ due to qdisc attachment point.

**Conclusion:** rtt differences are within cable plant noise floor at 3 runs. Need 10+ runs at a quiet time (late night) to resolve 25ms vs 40ms definitively.

**Kept:** rtt=40ms (v1.26 validated value, pending deeper testing)

### 4. CAKE Overhead

| Overhead | RRUL Avg Median | Notes |
|----------|-----------------|-------|
| 38 bytes (current) | 64-70ms | Standard Ethernet+DOCSIS from router perspective |
| 18 bytes + mpu=64 (MikroTik) | 77ms | DOCSIS-only overhead |

**MikroTik reference config:**
- `overhead: 18`, `docsis` scheme, `mpu: 64`
- `ack-filter: filter` on BOTH DL and UL
- `wash: true` on UL, `wash: false` on DL
- `nat: true` (router does NAT; bridge doesn't)

**Bridge vs Router overhead analysis:**
- Router (L3): CAKE sees IP packets. Must add Ethernet (14) + DOCSIS (18) = ~32-38 bytes
- Bridge (L2): CAKE sees Ethernet frames. Only add DOCSIS (18) + CRC (4) = ~22 bytes
- Current 38 bytes is likely too high for bridge topology. Correct value: ~22 bytes or `overhead 18` with `docsis` keyword

**Conclusion:** Overhead difference didn't produce measurable improvement in noisy RRUL testing. Needs controlled late-night testing.

### 5. ack-filter on Download

| Config | RRUL Avg Median | Notes |
|--------|-----------------|-------|
| no-ack-filter (current) | 64ms | Standard |
| ack-filter | 83ms | Slightly worse |

**Conclusion:** ack-filter on download doesn't help on a 940 Mbps link. Makes sense — ACK compression matters on constrained links, not gigabit.

## Parameters to Investigate Further (Late Night Testing)

These require 10+ runs at a quiet cable plant time (2-5 AM) to see through DOCSIS variance:

1. **rtt: 25ms vs 40ms** — MikroTik was tuned at 25ms via extensive testing. Need controlled comparison.
2. **overhead: 18 vs 22 vs 38** — Bridge topology should use lower overhead. Need to calculate correct value for L2 qdisc.
3. **mpu: 64 vs default** — Minimum packet unit, MikroTik had it, we don't.
4. **DL ceiling: 940 vs 900 vs 850** — Same headroom logic as UL. ISP plan is 1000, we use 940. Could 900 improve DL latency under 12-stream load?
5. **Combined optimal:** After finding individual winners, test the combination.

## Current Production Config (post-investigation)

```yaml
# Upload
ceiling_mbps: 32         # CHANGED from 38 (validated 2026-04-03)
floor_mbps: 8
step_up_mbps: 5          # Phase 135 validated
factor_down: 0.90        # Phase 135 validated

# CAKE params (both interfaces)
rtt: 40ms                # v1.26 validated (25ms under investigation)
overhead: 38             # Under investigation (may be too high for bridge)
```

## Cable Plant Variance Note

DOCSIS upload is a shared medium. Run-to-run variance of 20-40ms is typical. Any A/B comparison with fewer than 5 runs is unreliable. Late-night testing (2-5 AM) when the DOCSIS node is least loaded will produce the cleanest data. Weeknight preferred over weekend (fewer streaming subscribers).

---

*Investigation completed: 2026-04-03*
*Investigator: Claude Code (expert network analysis mode)*
