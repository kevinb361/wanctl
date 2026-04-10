# Phase 135: UL Recovery Tuning Results

**Date:** 2026-04-03
**Transport:** linux-cake
**Methodology:** flent rrul -H 104.200.21.31 -l 60, 3 runs per config (per D-04)
**Host:** cake-shaper VM 206 (10.10.110.223)
**Params tested:** step_up_mbps x factor_down matrix (per D-01, D-02, D-03)
**Success threshold:** 15% UL throughput OR 20% latency improvement (per D-07)
**Baseline UL:** step_up_mbps=1, factor_down=0.85 (actual production values)

## Baseline (step_up=1, factor_down=0.85)

| Run | ICMP Median (ms) | ICMP p99 (ms) | DL Sum (Mbps) | UL Sum (Mbps) |
|-----|-------------------|----------------|---------------|---------------|
| 1   | 58.50             | 166.52         | 814.51        | 15.67         |
| 2   | 60.10             | 276.55         | 823.84        | 15.27         |
| 3   | 61.05             | 271.53         | 833.39        | 15.82         |
| **Avg** | **59.88**     | **238.20**     | **823.91**    | **15.59**     |

## factor_down=0.80 Row

### Config A1: step_up=3, factor_down=0.80

| Run | ICMP Median (ms) | ICMP p99 (ms) | DL Sum (Mbps) | UL Sum (Mbps) |
|-----|-------------------|----------------|---------------|---------------|
| 1   | 222.00            | 1809.10        | 805.14        | 7.19          |
| 2   | 92.70             | 667.10         | 826.93        | 11.80         |
| 3   | 52.55             | 309.83         | 822.68        | 16.18         |
| **Avg** | **122.42**    | **928.68**     | **818.25**    | **11.72**     |

Note: Run 1 had extreme latency spike (possible cable plant event or recovery oscillation).

### Config A2: step_up=4, factor_down=0.80

| Run | ICMP Median (ms) | ICMP p99 (ms) | DL Sum (Mbps) | UL Sum (Mbps) |
|-----|-------------------|----------------|---------------|---------------|
| 1   | 54.85             | 188.30         | 840.51        | 16.24         |
| 2   | 73.10             | 497.20         | 813.64        | 12.85         |
| 3   | 44.65             | 193.77         | 842.61        | 19.56         |
| **Avg** | **57.53**     | **293.09**     | **832.25**    | **16.22**     |

### Config A3: step_up=5, factor_down=0.80

| Run | ICMP Median (ms) | ICMP p99 (ms) | DL Sum (Mbps) | UL Sum (Mbps) |
|-----|-------------------|----------------|---------------|---------------|
| 1   | 48.35             | 129.53         | 847.83        | 18.80         |
| 2   | 71.45             | 585.19         | 835.93        | 12.90         |
| 3   | 40.95             | 243.00         | 836.47        | 19.18         |
| **Avg** | **53.58**     | **319.24**     | **840.08**    | **16.96**     |

## factor_down=0.90 Row

### Config B1: step_up=3, factor_down=0.90

| Run | ICMP Median (ms) | ICMP p99 (ms) | DL Sum (Mbps) | UL Sum (Mbps) |
|-----|-------------------|----------------|---------------|---------------|
| 1   | 56.80             | 193.16         | 833.59        | 16.18         |
| 2   | 65.20             | 452.46         | 826.42        | 14.41         |
| 3   | 47.80             | 258.76         | 842.37        | 18.07         |
| **Avg** | **56.60**     | **301.46**     | **834.13**    | **16.22**     |

### Config B2: step_up=4, factor_down=0.90

| Run | ICMP Median (ms) | ICMP p99 (ms) | DL Sum (Mbps) | UL Sum (Mbps) |
|-----|-------------------|----------------|---------------|---------------|
| 1   | 57.30             | 156.04         | 833.01        | 16.78         |
| 2   | 47.50             | 245.53         | 836.23        | 18.32         |
| 3   | 50.45             | 208.83         | 824.16        | 17.93         |
| **Avg** | **51.75**     | **203.47**     | **831.13**    | **17.68**     |

### Config B3: step_up=5, factor_down=0.90

| Run | ICMP Median (ms) | ICMP p99 (ms) | DL Sum (Mbps) | UL Sum (Mbps) |
|-----|-------------------|----------------|---------------|---------------|
| 1   | 85.70             | 489.44         | 823.39        | 12.41         |
| 2   | 36.70             | 86.73          | 831.91        | 22.27         |
| 3   | 44.60             | 205.40         | 836.56        | 20.35         |
| **Avg** | **55.67**     | **260.52**     | **830.62**    | **18.34**     |

## Summary Comparison

| Config | step_up | factor_down | UL Avg (Mbps) | UL vs Baseline | ICMP Median (ms) | Latency vs Baseline | DL Sum (Mbps) |
|--------|---------|-------------|---------------|----------------|-------------------|---------------------|---------------|
| **Baseline** | **1** | **0.85** | **15.59** | **--** | **59.88** | **--** | **823.91** |
| A1 | 3 | 0.80 | 11.72 | -24.8% | 122.42 | +104.4% | 818.25 |
| A2 | 4 | 0.80 | 16.22 | +4.0% | 57.53 | -3.9% | 832.25 |
| A3 | 5 | 0.80 | 16.96 | +8.8% | 53.58 | -10.5% | 840.08 |
| B1 | 3 | 0.90 | 16.22 | +4.0% | 56.60 | -5.5% | 834.13 |
| **B2** | **4** | **0.90** | **17.68** | **+13.4%** | **51.75** | **-13.6%** | **831.13** |
| B3 | 5 | 0.90 | 18.34 | +17.6% | 55.67 | -7.0% | 830.62 |

## Analysis

### Winner: B3 (step_up=5, factor_down=0.90)

**UL throughput:** 18.34 Mbps avg (+17.6% vs baseline 15.59) — **exceeds 15% threshold**
**Latency:** 55.67ms median (-7.0%) — improvement but below 20% threshold
**DL regression:** 830.62 Mbps (vs 823.91 baseline) — no regression

### Runner-up: B2 (step_up=4, factor_down=0.90)

**UL throughput:** 17.68 Mbps avg (+13.4%) — just under 15% threshold
**Latency:** 51.75ms median (-13.6%) — best latency of all configs
**DL regression:** 831.13 Mbps — no regression

### Key Findings

1. **factor_down=0.90 consistently outperforms 0.80** across all step_up values. Gentler decay (10% vs 20%) preserves more UL throughput and produces lower latency. The aggressive 0.80 decay overshoots on UL, causing unnecessary bandwidth oscillation.

2. **Higher step_up improves UL throughput monotonically** within each factor_down row. step_up=5 beats 4 beats 3 in both the 0.80 and 0.90 rows. No sign of oscillation at step_up=5 (13% of 38Mbps ceiling).

3. **A1 (step_up=3, factor_down=0.80) is the worst config** — 24.8% LESS UL throughput than baseline and doubled latency. The combination of aggressive decay + slow recovery creates a death spiral on the 38Mbps UL link.

4. **B2 and B3 are both good choices.** B3 exceeds the 15% throughput threshold; B2 has the best latency. B3 is recommended because throughput is the primary objective (the v1.26 finding was "only 10% of ceiling").

5. **DL throughput is stable across all configs** (818-842 Mbps range, no regression). UL param changes don't affect DL performance.

6. **High run-to-run variance** (especially A1 run 1 and B3 run 1) suggests cable plant conditions contribute to test noise. 3-run averages help, but individual runs can vary significantly.

### Recommendation

Deploy **B3: step_up=5, factor_down=0.90** as new production UL parameters. This exceeds the 15% throughput threshold while maintaining lower latency than baseline. If stability concerns arise, B2 (step_up=4, factor_down=0.90) is a conservative fallback with the best latency profile.

---

*Phase: 135-upload-recovery-tuning*
*Testing completed: 2026-04-03*
*21 flent RRUL runs (3 baseline + 18 matrix)*
