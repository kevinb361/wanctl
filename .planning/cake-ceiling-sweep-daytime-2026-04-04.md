# CAKE Ceiling Sweep — Daytime Analysis (2026-04-04)

**Time:** 12:43 - 15:18 (peak afternoon DOCSIS load)
**Methodology:** flent rrul -H 104.200.21.31 -l 60, 10 runs per config
**CAKE params:** rtt=25ms, overhead=docsis (18), mpu=64 (sweep winners from last night)
**Caveat:** Sequential testing during peak hours — later configs may show time-of-day bias

## UL Ceiling Sweep (DL locked at 940 Mbit)

| Config | Ceiling | % of ISP | Median Lat | p25 Lat | p75 Lat | Median p99 | Median DL | Median UL |
|--------|---------|----------|------------|---------|---------|------------|-----------|-----------|
| ul28 | 28 Mbit | 70% | 36.5 ms | 35.8 ms | 42.5 ms | 84.5 ms | 462 Mbps | 11.0 Mbps |
| ul30 ** | 30 Mbit | 75% | 34.5 ms | 31.9 ms | 39.4 ms | 78.2 ms | 367 Mbps | 9.7 Mbps |
| ul32 | 32 Mbit | 80% | 43.2 ms | 40.4 ms | 44.9 ms | 102.0 ms | 413 Mbps | 8.6 Mbps |
| ul34 | 34 Mbit | 85% | 37.4 ms | 28.5 ms | 41.9 ms | 84.7 ms | 482 Mbps | 12.0 Mbps |
| ul36 | 36 Mbit | 90% | 37.0 ms | 29.6 ms | 39.4 ms | 77.3 ms | 476 Mbps | 11.7 Mbps |

## DL Ceiling Sweep (UL locked at 32 Mbit)

| Config | Ceiling | % of ISP | Median Lat | p25 Lat | p75 Lat | Median p99 | Median DL | Median UL |
|--------|---------|----------|------------|---------|---------|------------|-----------|-----------|
| dl500 | 500 Mbit | 50% | 33.1 ms | 27.8 ms | 40.2 ms | 74.3 ms | 494 Mbps | 14.1 Mbps |
| dl600 | 600 Mbit | 60% | 39.1 ms | 35.6 ms | 40.5 ms | 89.9 ms | 456 Mbps | 9.9 Mbps |
| dl700 | 700 Mbit | 70% | 41.5 ms | 40.7 ms | 43.2 ms | 101.6 ms | 346 Mbps | 7.6 Mbps |
| dl800 | 800 Mbit | 80% | 38.8 ms | 37.2 ms | 40.4 ms | 93.6 ms | 562 Mbps | 13.5 Mbps |
| dl850 | 850 Mbit | 85% | 41.6 ms | 33.9 ms | 43.5 ms | 91.8 ms | 462 Mbps | 11.3 Mbps |
| dl900 | 900 Mbit | 90% | 35.3 ms | 31.1 ms | 42.0 ms | 90.2 ms | 390 Mbps | 11.7 Mbps |
| dl940 | 940 Mbit | 94% | 41.2 ms | 33.5 ms | 43.1 ms | 92.0 ms | 424 Mbps | 10.7 Mbps |

## Observations (Daytime Only — Pending 3 AM Confirmation)

### UL Ceiling
- **ul30 (75%)** lowest median latency (34.5ms) but worst throughput — possible time-of-day advantage (ran early)
- **ul32 (80%, current)** highest median latency (43.2ms) — ran during peak lunch congestion
- **ul34-36 (85-90%)** better latency than ul32 with better throughput — need 3 AM data to confirm
- Spread is wide (27-48ms range within configs) — DOCSIS noise dominates

### DL Ceiling
- **dl500 (50%)** lowest median latency (33.1ms) and lowest p99 (74.3ms) — possible ISP tier boundary
- **dl800 (80%)** best raw throughput (562 Mbps) with moderate latency (38.8ms)
- **dl940 (94%, current)** middle of pack on latency (41.2ms), moderate throughput
- No clear monotonic trend — time-of-day bias likely distorting results

## Pending

- 3 AM sweep (same 12 configs) scheduled for 2026-04-05 03:00
- Compare daytime vs nighttime to separate ceiling effects from DOCSIS plant variance
- Deploy winner after nighttime confirmation
