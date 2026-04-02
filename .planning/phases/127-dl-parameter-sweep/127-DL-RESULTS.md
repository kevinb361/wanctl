# Phase 127: DL Parameter Sweep Results

**Date:** 2026-04-02, 17:00-17:36 CDT
**Transport:** linux-cake (direct tc qdisc manipulation on cake-shaper VM)
**Methodology:** flent rrul_be -H 104.200.21.31 -l 60 (Dallas netperf server)
**Conditions:** Afternoon cable plant load, Spectrum DOCSIS
**Host:** cake-shaper VM 206 (10.10.110.223)

## Baseline (No Load)

| Metric            | Value      |
| ----------------- | ---------- |
| ICMP median       | 30.15ms    |
| ICMP p99          | 45.49ms    |
| DL throughput sum | 334 Mbps   |
| UL throughput sum | 12.76 Mbps |

## Test 1: factor_down_yellow (0.92 vs 0.97)

**YAML path:** `continuous_monitoring.download.factor_down_yellow`
**Starting value:** 0.92 (current production)

| Metric        | 0.92 (8% decay) | 0.97 (3% decay) |
| ------------- | --------------- | --------------- |
| ICMP median   | 54.40ms         | 59.10ms         |
| ICMP p99      | 161ms           | 132ms           |
| DL throughput | 421 Mbps        | 329 Mbps        |

**Winner: 0.92** -- Wins on throughput (+28%) and median latency (-8%). The 0.97 candidate has better p99 but substantially worse throughput. On linux-cake transport, 0.92 remains optimal -- same as REST.

**Changed from production:** No

---

## Test 2: green_required (5 vs 3)

**YAML path:** `continuous_monitoring.download.green_required`
**Starting value:** 5 (current production)
**Cumulative:** factor_down_yellow=0.92

| Metric        | 5 (conservative) | 3 (fast recovery) |
| ------------- | ---------------- | ----------------- |
| ICMP median   | 82.30ms          | 66.50ms           |
| ICMP p99      | 828ms            | 640ms             |
| DL throughput | 524 Mbps         | 427 Mbps          |

**Winner: 3** -- Wins on latency: median -19%, p99 -23%. The 5-cycle wait is too long on linux-cake -- faster feedback loop means the controller can recover safely with only 3 GREEN cycles. This reverses the REST finding where 5 won.

**Changed from production:** YES (5 -> 3)

---

## Test 3: step_up_mbps (15 vs 10)

**YAML path:** `continuous_monitoring.download.step_up_mbps`
**Starting value:** 15 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3

| Metric        | 15 (fast ramp) | 10 (moderate ramp) |
| ------------- | -------------- | ------------------ |
| ICMP median   | 57.80ms        | 61.10ms            |
| ICMP p99      | 285ms          | 141ms              |
| DL throughput | 309 Mbps       | 383 Mbps           |

**Winner: 10** -- Wins on p99 (-51%) and throughput (+24%). With green_required=3, the faster 15 Mbps step overshoots, triggering more congestion events. Moderate 10 Mbps step works better with the faster recovery cycle. Reverses the REST finding where 15 won.

**Changed from production:** YES (15 -> 10)

---

## Test 4: factor_down RED (0.90 vs 0.85)

**YAML path:** `continuous_monitoring.download.factor_down`
**Starting value:** 0.90 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10

| Metric        | 0.90 (10% decay) | 0.85 (15% decay) |
| ------------- | ---------------- | ---------------- |
| ICMP median   | 70.50ms          | 62.85ms          |
| ICMP p99      | 598ms            | 349ms            |
| DL throughput | 398 Mbps         | 405 Mbps         |

**Winner: 0.85** -- Wins on latency: median -11%, p99 -42%. More aggressive RED decay works better on linux-cake because the faster feedback loop delivers rate changes more quickly, so the deeper cut resolves congestion faster. Reverses the REST finding where 0.90 won.

**Changed from production:** YES (0.90 -> 0.85)

---

## Test 5: dwell_cycles (5 vs 3)

**YAML path:** `continuous_monitoring.thresholds.dwell_cycles`
**Starting value:** 5 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85

| Metric        | 5 (longer dwell) | 3 (shorter dwell) |
| ------------- | ---------------- | ----------------- |
| ICMP median   | 55.35ms          | 61.85ms           |
| ICMP p99      | 140ms            | 597ms             |
| DL throughput | 361 Mbps         | 443 Mbps          |

**Winner: 5** -- Wins on p99 (-77%) and median (-11%). Dwell=5 still essential for filtering DOCSIS jitter even on linux-cake. Same as REST finding.

**Changed from production:** No

---

## Test 6: deadband_ms (3.0 vs 5.0)

**YAML path:** `continuous_monitoring.thresholds.deadband_ms`
**Starting value:** 3.0 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85, dwell_cycles=5

| Metric        | 3.0 (narrow) | 5.0 (wider) |
| ------------- | ------------ | ----------- |
| ICMP median   | 55.80ms      | 57.00ms     |
| ICMP p99      | 184ms        | 786ms       |
| DL throughput | 354 Mbps     | 326 Mbps    |

**Winner: 3.0** -- Wins on p99 (-77%) and throughput (+9%). Wider deadband still traps in YELLOW. Same as REST finding.

**Changed from production:** No

---

## Test 7: target_bloat_ms (9 vs 12 vs 15) -- 3-way

**YAML path:** `continuous_monitoring.thresholds.target_bloat_ms`
**Starting value:** 9 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85, dwell_cycles=5, deadband_ms=3.0

| Metric        | 9ms (tight) | 12ms (medium) | 15ms (loose) |
| ------------- | ----------- | ------------- | ------------ |
| ICMP median   | 59.85ms     | 59.90ms       | 57.10ms      |
| ICMP p99      | 141ms       | 248ms         | 137ms        |
| DL throughput | --          | --            | 401 Mbps     |

**Winner: 15** -- Best median and p99. With linux-cake's faster feedback, the tight 9ms threshold triggers too many unnecessary transitions. The looser 15ms threshold lets CAKE's AQM handle small queue buildups while the controller only intervenes for real congestion. Major reversal from REST where 9ms won.

**Changed from production:** YES (9 -> 15)

**Coupling note:** target_bloat_ms=15 is safe at any dwell_cycles value. The dwell/target coupling concern (dwell=3 requires target>=12) is satisfied.

---

## Test 8: warn_bloat_ms (30 vs 45 vs 60) -- 3-way

**YAML path:** `continuous_monitoring.thresholds.warn_bloat_ms`
**Starting value:** 45 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85, dwell_cycles=5, deadband_ms=3.0, target_bloat_ms=15

| Metric        | 30ms (tight) | 45ms (medium) | 60ms (loose) |
| ------------- | ------------ | ------------- | ------------ |
| ICMP median   | 65.40ms      | 67.20ms       | 60.00ms      |
| ICMP p99      | 679ms        | 1091ms        | 157ms        |
| DL throughput | --           | --            | 415 Mbps     |

**Winner: 60** -- Dramatically better p99 (-86% vs 45ms). With target_bloat raised to 15ms, the previous 45ms warn threshold was only 30ms of headroom. At 60ms, there's 45ms between GREEN->YELLOW and YELLOW->SOFT_RED, giving CAKE's AQM proper room to work. This is the biggest single-parameter improvement in the sweep.

**Changed from production:** YES (45 -> 60)

---

## Test 9: hard_red_bloat_ms (60 vs 80 vs 100) -- 3-way

**YAML path:** `continuous_monitoring.thresholds.hard_red_bloat_ms`
**Starting value:** 60 (current production)
**Cumulative:** factor_down_yellow=0.92, green_required=3, step_up_mbps=10, factor_down=0.85, dwell_cycles=5, deadband_ms=3.0, target_bloat_ms=15, warn_bloat_ms=60

| Metric        | 60ms (tight) | 80ms (medium) | 100ms (loose) |
| ------------- | ------------ | ------------- | ------------- |
| ICMP median   | 61.20ms      | 63.80ms       | 62.70ms       |
| ICMP p99      | 244ms        | 575ms         | 150ms         |
| DL throughput | --           | --            | 371 Mbps      |

**Winner: 100** -- Best p99 (-39% vs 60ms). With warn_bloat raised to 60ms, the previous 60ms hard_red was zero headroom (SOFT_RED->RED fires immediately on any delta above warn). At 100ms, there's 40ms of SOFT_RED operating range, allowing the floor clamp to work before escalating to RED.

**Changed from production:** YES (60 -> 100)

---

## Summary

### Final Validated Configuration (linux-cake transport)

```yaml
continuous_monitoring:
  download:
    factor_down_yellow: 0.92 # Confirmed (same as REST)
    green_required: 3 # Changed from 5 (was REST winner)
    step_up_mbps: 10 # Changed from 15 (was REST winner)
    factor_down: 0.85 # Changed from 0.90 (was REST winner)

  thresholds:
    dwell_cycles: 5 # Confirmed (same as REST)
    deadband_ms: 3.0 # Confirmed (same as REST)
    target_bloat_ms: 15 # Changed from 9 (was REST winner)
    warn_bloat_ms: 60 # Changed from 45 (was REST winner)
    hard_red_bloat_ms: 100 # Changed from 60 (was REST winner)
```

### Changes from REST-validated values

| Parameter          | REST Winner | linux-cake Winner | Direction           |
| ------------------ | ----------- | ----------------- | ------------------- |
| factor_down_yellow | 0.92        | 0.92              | Same                |
| green_required     | 5           | 3                 | Faster recovery     |
| step_up_mbps       | 15          | 10                | Smaller steps       |
| factor_down        | 0.90        | 0.85              | More aggressive RED |
| dwell_cycles       | 5           | 5                 | Same                |
| deadband_ms        | 3.0         | 3.0               | Same                |
| target_bloat_ms    | 9           | 15                | Looser threshold    |
| warn_bloat_ms      | 45          | 60                | Looser threshold    |
| hard_red_bloat_ms  | 60          | 100               | Looser threshold    |

**6 of 9 parameters changed.** 3 confirmed (hysteresis/YELLOW decay).

### Key Insight

linux-cake's faster feedback loop (direct tc qdisc vs REST API roundtrip) shifts optimal values in two directions:

1. **Response parameters shift toward less aggressive:** green_required=3, step_up=10, factor_down=0.85. Faster feedback means the controller acts on fresher data, so it can afford smaller steps and faster cycles without losing responsiveness.

2. **Thresholds shift toward wider spacing:** target=15, warn=60, hard_red=100. The faster feedback means CAKE's AQM has more time to work before the controller intervenes. Tighter thresholds that were necessary on REST (to compensate for API latency) now cause unnecessary intervention.

The 3 confirmed parameters (factor_down_yellow, dwell_cycles, deadband_ms) are DOCSIS-intrinsic -- they filter cable plant jitter regardless of transport speed.

---

## UL Parameter Sweep

**Date:** 2026-04-02, 17:53-18:01 CDT
**Transport:** linux-cake (direct tc qdisc manipulation on cake-shaper VM)
**Methodology:** flent rrul_be -H 104.200.21.31 -l 60 (Dallas netperf server)
**Conditions:** Afternoon/evening cable plant load, Spectrum DOCSIS
**Host:** cake-shaper VM 206 (10.10.110.223)
**Starting UL config:** factor_down=0.85, step_up_mbps=1, green_required=3
**DL config:** All Phase 127 winners in place (green_required=3, step_up=10, factor_down=0.85, target_bloat=15, warn_bloat=60, hard_red=100)

### UL Test 1: factor_down (0.85 vs 0.90)

**YAML path:** `continuous_monitoring.upload.factor_down`
**Starting value:** 0.85 (current production)

| Metric        | 0.85 (15% decay) | 0.90 (10% decay) |
| ------------- | ---------------- | ---------------- |
| ICMP median   | 52.20ms          | 63.10ms          |
| ICMP p99      | 179ms            | 204ms            |
| UL throughput | 5.07 Mbps        | 3.63 Mbps        |

**Winner: 0.85** -- Wins on all metrics: median -17%, p99 -12%, UL throughput +40%. UL still needs more aggressive RED decay than DL's 0.85 would suggest -- on the constrained ~38 Mbps upstream, gentler decay leaves rates depressed longer. Same result as REST transport.

**Changed from production:** No

---

### UL Test 2: step_up_mbps (1 vs 2)

**YAML path:** `continuous_monitoring.upload.step_up_mbps`
**Starting value:** 1 (current production)
**Cumulative:** factor_down=0.85

| Metric        | 1 (gentle) | 2 (faster) |
| ------------- | ---------- | ---------- |
| ICMP median   | 65.90ms    | 58.25ms    |
| ICMP p99      | 391ms      | 163ms      |
| UL throughput | 5.48 Mbps  | 4.42 Mbps  |

**Winner: 2** -- Wins on latency: median -12%, p99 -58%. UL throughput slightly lower (-19%) but the massive p99 improvement makes this a clear win for bufferbloat control. With linux-cake's faster feedback loop, the larger 2 Mbps step (~5.3% of 38 Mbps ceiling) recovers from congestion faster without causing oscillation. Reverses the REST finding where step_up=1 won.

**Changed from production:** YES (1 -> 2)

---

### UL Test 3: green_required (3 vs 5)

**YAML path:** `continuous_monitoring.upload.green_required`
**Starting value:** 3 (current production)
**Cumulative:** factor_down=0.85, step_up_mbps=2

| Metric        | 3 (fast recovery) | 5 (conservative) |
| ------------- | ----------------- | ---------------- |
| ICMP median   | 48.20ms           | 60.10ms          |
| ICMP p99      | 184ms             | 266ms            |
| UL throughput | 11.53 Mbps        | 4.15 Mbps        |

**Winner: 3** -- Wins on all metrics: median -20%, p99 -31%, UL throughput +178%. With linux-cake's faster feedback and the larger step_up=2, green_required=3 gives UL enough cycles to confirm clearance without the excessive delay of 5 cycles. Same as DL finding -- linux-cake's faster feedback makes 3 cycles sufficient. Reverses the REST finding where green_required=5 won.

**Changed from production:** No

---

### UL Summary

#### Final Validated UL Configuration (linux-cake transport)

```yaml
continuous_monitoring:
  upload:
    factor_down: 0.85 # Confirmed (same as REST)
    step_up_mbps: 2 # Changed from 1 (was REST winner)
    green_required: 3 # Confirmed (matches DL finding on linux-cake)
```

#### Changes from REST-validated UL values

| Parameter      | REST Winner | linux-cake Winner | Direction       |
| -------------- | ----------- | ----------------- | --------------- |
| factor_down    | 0.85        | 0.85              | Same            |
| step_up_mbps   | 1           | 2                 | Larger step     |
| green_required | 5           | 3                 | Faster recovery |

**1 of 3 UL parameters changed.** 2 confirmed.

#### Key UL Insight

UL step_up benefits from a slightly larger step on linux-cake (2 vs 1), matching the DL pattern where step sizes shifted toward moderate values. On REST, step_up=1 was necessary because the slow API roundtrip made each step's effect stale by the time the next measurement arrived -- the controller would overshoot with larger steps. On linux-cake, the near-instant tc feedback means the controller sees each step's effect immediately, so step_up=2 recovers faster without oscillation.

The green_required=3 confirmation on UL reinforces the DL finding: linux-cake's faster feedback makes 3 GREEN cycles sufficient for both directions. On REST, 5 was needed because each cycle's data was slightly stale -- the controller needed more confirmations to build confidence.

---

_Phase 127 DL + Phase 128 UL Parameter Sweep -- Completed 2026-04-02_
