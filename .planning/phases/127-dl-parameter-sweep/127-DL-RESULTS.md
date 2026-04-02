# Phase 127: DL Parameter Sweep Results

**Date:** 2026-04-02, 17:00-17:36 CDT
**Transport:** linux-cake (direct tc qdisc manipulation on cake-shaper VM)
**Methodology:** flent rrul_be -H 104.200.21.31 -l 60 (Dallas netperf server)
**Conditions:** Afternoon cable plant load, Spectrum DOCSIS
**Host:** cake-shaper VM 206 (10.10.110.223)

## Baseline (No Load)

| Metric | Value |
|--------|-------|
| ICMP median | 30.15ms |
| ICMP p99 | 45.49ms |
| DL throughput sum | 334 Mbps |
| UL throughput sum | 12.76 Mbps |

## Test 1: factor_down_yellow (0.92 vs 0.97)

**YAML path:** `continuous_monitoring.download.factor_down_yellow`
**Starting value:** 0.92 (current production)

| Metric | 0.92 (8% decay) | 0.97 (3% decay) |
|--------|-----------------|-----------------|
| ICMP median | 54.40ms | 59.10ms |
| ICMP p99 | 161ms | 132ms |
| DL throughput | 421 Mbps | 329 Mbps |

**Winner: 0.92** -- Wins on throughput (+28%) and median latency (-8%). The 0.97 candidate has better p99 but substantially worse throughput. On linux-cake transport, 0.92 remains optimal -- same as REST.

**Changed from production:** No

---

## Test 2: green_required (5 vs 3)

**YAML path:** `continuous_monitoring.download.green_required`
**Starting value:** 5 (current production)
**Cumulative:** factor_down_yellow=0.92

| Metric | 5 (conservative) | 3 (fast recovery) |
|--------|------------------|-------------------|
| ICMP median | 82.30ms | 66.50ms |
| ICMP p99 | 828ms | 640ms |
| DL throughput | 524 Mbps | 427 Mbps |

**Winner: 3** -- Wins on latency: median -19%, p99 -23%. The 5-cycle wait is too long on linux-cake -- faster feedback loop means the controller can recover safely with only 3 GREEN cycles. This reverses the REST finding where 5 won.

**Changed from production:** YES (5 -> 3)

---

## Test 3: step_up_mbps (15 vs 10)

**YAML path:** `continuous_monitoring.download.step_up_mbps`
**Starting value:** 15 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3

| Metric | 15 (fast ramp) | 10 (moderate ramp) |
|--------|----------------|---------------------|
| ICMP median | 57.80ms | 61.10ms |
| ICMP p99 | 285ms | 141ms |
| DL throughput | 309 Mbps | 383 Mbps |

**Winner: 10** -- Wins on p99 (-51%) and throughput (+24%). With green_required=3, the faster 15 Mbps step overshoots, triggering more congestion events. Moderate 10 Mbps step works better with the faster recovery cycle. Reverses the REST finding where 15 won.

**Changed from production:** YES (15 -> 10)

---

## Test 4: factor_down RED (0.90 vs 0.85)

**YAML path:** `continuous_monitoring.download.factor_down`
**Starting value:** 0.90 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10

| Metric | 0.90 (10% decay) | 0.85 (15% decay) |
|--------|-------------------|-------------------|
| ICMP median | 70.50ms | 62.85ms |
| ICMP p99 | 598ms | 349ms |
| DL throughput | 398 Mbps | 405 Mbps |

**Winner: 0.85** -- Wins on latency: median -11%, p99 -42%. More aggressive RED decay works better on linux-cake because the faster feedback loop delivers rate changes more quickly, so the deeper cut resolves congestion faster. Reverses the REST finding where 0.90 won.

**Changed from production:** YES (0.90 -> 0.85)

---

## Test 5: dwell_cycles (5 vs 3)

**YAML path:** `continuous_monitoring.thresholds.dwell_cycles`
**Starting value:** 5 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85

| Metric | 5 (longer dwell) | 3 (shorter dwell) |
|--------|-------------------|--------------------|
| ICMP median | 55.35ms | 61.85ms |
| ICMP p99 | 140ms | 597ms |
| DL throughput | 361 Mbps | 443 Mbps |

**Winner: 5** -- Wins on p99 (-77%) and median (-11%). Dwell=5 still essential for filtering DOCSIS jitter even on linux-cake. Same as REST finding.

**Changed from production:** No

---

## Test 6: deadband_ms (3.0 vs 5.0)

**YAML path:** `continuous_monitoring.thresholds.deadband_ms`
**Starting value:** 3.0 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85, dwell_cycles=5

| Metric | 3.0 (narrow) | 5.0 (wider) |
|--------|--------------|-------------|
| ICMP median | 55.80ms | 57.00ms |
| ICMP p99 | 184ms | 786ms |
| DL throughput | 354 Mbps | 326 Mbps |

**Winner: 3.0** -- Wins on p99 (-77%) and throughput (+9%). Wider deadband still traps in YELLOW. Same as REST finding.

**Changed from production:** No

---

## Test 7: target_bloat_ms (9 vs 12 vs 15) -- 3-way

**YAML path:** `continuous_monitoring.thresholds.target_bloat_ms`
**Starting value:** 9 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85, dwell_cycles=5, deadband_ms=3.0

| Metric | 9ms (tight) | 12ms (medium) | 15ms (loose) |
|--------|-------------|---------------|--------------|
| ICMP median | 59.85ms | 59.90ms | 57.10ms |
| ICMP p99 | 141ms | 248ms | 137ms |
| DL throughput | -- | -- | 401 Mbps |

**Winner: 15** -- Best median and p99. With linux-cake's faster feedback, the tight 9ms threshold triggers too many unnecessary transitions. The looser 15ms threshold lets CAKE's AQM handle small queue buildups while the controller only intervenes for real congestion. Major reversal from REST where 9ms won.

**Changed from production:** YES (9 -> 15)

**Coupling note:** target_bloat_ms=15 is safe at any dwell_cycles value. The dwell/target coupling concern (dwell=3 requires target>=12) is satisfied.

---

## Test 8: warn_bloat_ms (30 vs 45 vs 60) -- 3-way

**YAML path:** `continuous_monitoring.thresholds.warn_bloat_ms`
**Starting value:** 45 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85, dwell_cycles=5, deadband_ms=3.0, target_bloat_ms=15

| Metric | 30ms (tight) | 45ms (medium) | 60ms (loose) |
|--------|-------------|---------------|--------------|
| ICMP median | 65.40ms | 67.20ms | 60.00ms |
| ICMP p99 | 679ms | 1091ms | 157ms |
| DL throughput | -- | -- | 415 Mbps |

**Winner: 60** -- Dramatically better p99 (-86% vs 45ms). With target_bloat raised to 15ms, the previous 45ms warn threshold was only 30ms of headroom. At 60ms, there's 45ms between GREEN->YELLOW and YELLOW->SOFT_RED, giving CAKE's AQM proper room to work. This is the biggest single-parameter improvement in the sweep.

**Changed from production:** YES (45 -> 60)

---

## Test 9: hard_red_bloat_ms (60 vs 80 vs 100) -- 3-way

**YAML path:** `continuous_monitoring.thresholds.hard_red_bloat_ms`
**Starting value:** 60 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85, dwell_cycles=5, deadband_ms=3.0, target_bloat_ms=15, warn_bloat_ms=60

| Metric | 60ms (tight) | 80ms (medium) | 100ms (loose) |
|--------|-------------|---------------|---------------|
| ICMP median | 61.20ms | 63.80ms | 62.70ms |
| ICMP p99 | 244ms | 575ms | 150ms |
| DL throughput | -- | -- | 371 Mbps |

**Winner: 100** -- Best p99 (-39% vs 60ms). With warn_bloat raised to 60ms, the previous 60ms hard_red was zero headroom (SOFT_RED->RED fires immediately on any delta above warn). At 100ms, there's 40ms of SOFT_RED operating range, allowing the floor clamp to work before escalating to RED.

**Changed from production:** YES (60 -> 100)

---

## Summary

### Final Validated Configuration (linux-cake transport)

```yaml
continuous_monitoring:
  download:
    factor_down_yellow: 0.92  # Confirmed (same as REST)
    green_required: 3         # Changed from 5 (was REST winner)
    step_up_mbps: 10          # Changed from 15 (was REST winner)
    factor_down: 0.85         # Changed from 0.90 (was REST winner)

  thresholds:
    dwell_cycles: 5           # Confirmed (same as REST)
    deadband_ms: 3.0          # Confirmed (same as REST)
    target_bloat_ms: 15       # Changed from 9 (was REST winner)
    warn_bloat_ms: 60         # Changed from 45 (was REST winner)
    hard_red_bloat_ms: 100    # Changed from 60 (was REST winner)
```

### Changes from REST-validated values

| Parameter | REST Winner | linux-cake Winner | Direction |
|-----------|-------------|-------------------|-----------|
| factor_down_yellow | 0.92 | 0.92 | Same |
| green_required | 5 | 3 | Faster recovery |
| step_up_mbps | 15 | 10 | Smaller steps |
| factor_down | 0.90 | 0.85 | More aggressive RED |
| dwell_cycles | 5 | 5 | Same |
| deadband_ms | 3.0 | 3.0 | Same |
| target_bloat_ms | 9 | 15 | Looser threshold |
| warn_bloat_ms | 45 | 60 | Looser threshold |
| hard_red_bloat_ms | 60 | 100 | Looser threshold |

**6 of 9 parameters changed.** 3 confirmed (hysteresis/YELLOW decay).

### Key Insight

linux-cake's faster feedback loop (direct tc qdisc vs REST API roundtrip) shifts optimal values in two directions:

1. **Response parameters shift toward less aggressive:** green_required=3, step_up=10, factor_down=0.85. Faster feedback means the controller acts on fresher data, so it can afford smaller steps and faster cycles without losing responsiveness.

2. **Thresholds shift toward wider spacing:** target=15, warn=60, hard_red=100. The faster feedback means CAKE's AQM has more time to work before the controller intervenes. Tighter thresholds that were necessary on REST (to compensate for API latency) now cause unnecessary intervention.

The 3 confirmed parameters (factor_down_yellow, dwell_cycles, deadband_ms) are DOCSIS-intrinsic -- they filter cable plant jitter regardless of transport speed.

---
*Phase 127 DL Parameter Sweep -- Completed 2026-04-02*
