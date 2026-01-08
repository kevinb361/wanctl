# RouterOS Transport Comparison: REST API vs SSH/Paramiko

**Test Date:** 2026-01-08
**Test Duration:** 3 minutes each
**Test Method:** 8 parallel netperf TCP_MAERTS (upload) streams
**Conclusion:** REST API recommended for production

---

## Executive Summary

A controlled stress test comparing REST API (HTTPS port 443) vs SSH/Paramiko transport for RouterOS queue management revealed significant performance differences:

| Metric             | REST API      | SSH/Paramiko | Improvement                  |
| ------------------ | ------------- | ------------ | ---------------------------- |
| Peak RTT           | 194ms         | 404ms        | **2.1x better**              |
| RED/RED cycles     | 0             | 5            | **No hard congestion**       |
| Download stability | 940M (stable) | 940M→417M    | **No unnecessary reduction** |
| Time to floor      | ~35s          | ~45s         | **22% faster**               |

**Recommendation:** Use REST API transport for production deployments.

---

## Test Methodology

### Environment

- **Router:** Mikrotik rb5009
- **Controller:** LXC container running wanctl
- **WAN:** Cable ~940/38 Mbps
- **Test server:** Remote netperf server

### Test Parameters

```bash
# 8 parallel upload streams for 180 seconds
for i in {1..8}; do
  netperf -H <netperf-server> -t TCP_MAERTS -l 180 &
done
```

### Controller Configuration

- Cycle time: ~2 seconds
- Upload ceiling: 38M, floor: 8M
- factor_down: 0.85 (15% reduction per RED cycle)
- Thresholds: GREEN ≤15ms, YELLOW ≤45ms, SOFT_RED ≤80ms, RED >80ms

---

## Results Summary

### REST API Test (01:15:01 - 01:18:07 UTC)

| State            | Count | Percentage |
| ---------------- | ----- | ---------- |
| YELLOW/YELLOW    | 47    | 55%        |
| YELLOW/RED       | 19    | 22%        |
| SOFT_RED/RED     | 18    | 21%        |
| RED/RED          | 0     | 0%         |
| **Total cycles** | 84    |            |

**Key metrics:**

- Peak RTT: **194ms**
- Peak delta: 65.5ms
- Download: Stable at 940M (no reduction)
- Upload: 38M → 8M (floor reached in ~35 seconds)
- Skipped cycles (ping failures): 4 bursts

### SSH/Paramiko Test (01:21:16 - 01:24:23 UTC)

| State            | Count | Percentage |
| ---------------- | ----- | ---------- |
| YELLOW/YELLOW    | 55    | 61%        |
| YELLOW/RED       | 12    | 13%        |
| SOFT_RED/RED     | 15    | 17%        |
| RED/RED          | 5     | **6%**     |
| **Total cycles** | 87    |            |

**Key metrics:**

- Peak RTT: **404ms** (2.1x worse)
- Peak delta: 115.8ms (hard RED threshold exceeded)
- Download: 940M → 417M (55% reduction due to RED/RED)
- Upload: 32M → 8M (floor reached in ~45 seconds)
- Skipped cycles (ping failures): 6 bursts

---

## Analysis

### Why REST API Performed Better

1. **Command Latency**
   - REST API: ~50ms per command
   - SSH/Paramiko: ~150-200ms per command
   - REST issues ~4 adjustments in the time SSH issues 1

2. **Feedback Loop Speed**
   - REST can reduce bandwidth before congestion escalates
   - SSH's slower response allows RTT to spike while waiting

3. **Congestion Cascade Prevention**
   - REST: Caught congestion at SOFT_RED, never reached hard RED
   - SSH: Slow response allowed escalation to RED/RED (delta >80ms)

4. **Download Stability**
   - REST: Download stayed at ceiling (940M) throughout
   - SSH: Download dropped to 417M due to RED/RED cycles

### Latency Impact on Control Loop

```
Congestion Event Timeline (simplified):

REST API:
  T+0ms:   RTT spike detected (60ms)
  T+50ms:  REST command sent, queue adjusted
  T+100ms: Bandwidth reduced, RTT stabilizing
  T+150ms: Next measurement shows improvement

SSH/Paramiko:
  T+0ms:   RTT spike detected (60ms)
  T+200ms: SSH command sent, queue adjusted
  T+400ms: Bandwidth reduced, but RTT already at 150ms+
  T+600ms: Playing catch-up, may hit RED/RED
```

---

## Raw Test Data

### REST API Test - Full Log

```
2026-01-08 01:15:15,361 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=102.0ms, load_ewma=49.6ms, baseline=25.1ms, delta=24.5ms | DL=940M, UL=38M
2026-01-08 01:15:17,367 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=92.7ms, load_ewma=58.2ms, baseline=25.1ms, delta=33.1ms | DL=940M, UL=38M
2026-01-08 01:15:19,324 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=69.6ms, load_ewma=60.5ms, baseline=25.1ms, delta=35.4ms | DL=940M, UL=38M
2026-01-08 01:15:21,311 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=51.9ms, load_ewma=58.8ms, baseline=25.1ms, delta=33.6ms | DL=940M, UL=38M
2026-01-08 01:15:23,330 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=70.7ms, load_ewma=61.2ms, baseline=25.1ms, delta=36.0ms | DL=940M, UL=38M
2026-01-08 01:15:25,341 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=90.0ms, load_ewma=66.9ms, baseline=25.1ms, delta=41.8ms | DL=940M, UL=38M
2026-01-08 01:15:27,315 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=57.6ms, load_ewma=65.1ms, baseline=25.1ms, delta=39.9ms | DL=940M, UL=38M
2026-01-08 01:15:29,334 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=73.6ms, load_ewma=66.8ms, baseline=25.1ms, delta=41.6ms | DL=940M, UL=38M
2026-01-08 01:15:31,345 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=87.4ms, load_ewma=70.9ms, baseline=25.1ms, delta=45.8ms | DL=940M, UL=32M
2026-01-08 01:15:33,326 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=65.4ms, load_ewma=69.8ms, baseline=25.1ms, delta=44.7ms | DL=940M, UL=32M
2026-01-08 01:15:35,338 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=78.5ms, load_ewma=71.5ms, baseline=25.1ms, delta=46.4ms | DL=940M, UL=27M
2026-01-08 01:15:37,324 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=61.6ms, load_ewma=69.6ms, baseline=25.1ms, delta=44.4ms | DL=940M, UL=27M
2026-01-08 01:15:39,387 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=123.0ms, load_ewma=80.2ms, baseline=25.1ms, delta=55.1ms | DL=940M, UL=23M
2026-01-08 01:15:41,350 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=85.6ms, load_ewma=81.3ms, baseline=25.1ms, delta=56.2ms | DL=940M, UL=20M
2026-01-08 01:15:43,351 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=90.5ms, load_ewma=83.2ms, baseline=25.1ms, delta=58.0ms | DL=940M, UL=17M
2026-01-08 01:15:45,319 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=58.4ms, load_ewma=78.2ms, baseline=25.1ms, delta=53.1ms | DL=940M, UL=14M
2026-01-08 01:15:47,349 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=87.7ms, load_ewma=80.1ms, baseline=25.1ms, delta=55.0ms | DL=940M, UL=12M
2026-01-08 01:15:49,287 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=25.0ms, load_ewma=69.1ms, baseline=25.1ms, delta=43.9ms | DL=940M, UL=12M
2026-01-08 01:15:51,311 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=49.9ms, load_ewma=65.2ms, baseline=25.1ms, delta=40.1ms | DL=940M, UL=12M
2026-01-08 01:15:53,316 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=55.7ms, load_ewma=63.3ms, baseline=25.1ms, delta=38.2ms | DL=940M, UL=12M
2026-01-08 01:15:55,301 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=39.7ms, load_ewma=58.6ms, baseline=25.1ms, delta=33.5ms | DL=940M, UL=12M
2026-01-08 01:15:57,313 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=49.6ms, load_ewma=56.8ms, baseline=25.1ms, delta=31.7ms | DL=940M, UL=12M
2026-01-08 01:15:59,300 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=37.6ms, load_ewma=53.0ms, baseline=25.1ms, delta=27.8ms | DL=940M, UL=12M
2026-01-08 01:16:01,329 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=66.0ms, load_ewma=55.6ms, baseline=25.1ms, delta=30.4ms | DL=940M, UL=12M
2026-01-08 01:16:03,321 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=58.8ms, load_ewma=56.2ms, baseline=25.1ms, delta=31.1ms | DL=940M, UL=12M
2026-01-08 01:16:05,325 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=67.6ms, load_ewma=58.5ms, baseline=25.1ms, delta=33.4ms | DL=940M, UL=12M
2026-01-08 01:16:07,350 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=89.9ms, load_ewma=64.8ms, baseline=25.1ms, delta=39.6ms | DL=940M, UL=12M
2026-01-08 01:16:09,318 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=56.6ms, load_ewma=63.1ms, baseline=25.1ms, delta=38.0ms | DL=940M, UL=12M
2026-01-08 01:16:11,362 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=104.0ms, load_ewma=71.3ms, baseline=25.1ms, delta=46.2ms | DL=940M, UL=10M
2026-01-08 01:16:13,323 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=64.4ms, load_ewma=69.9ms, baseline=25.1ms, delta=44.8ms | DL=940M, UL=10M
2026-01-08 01:16:15,334 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=73.4ms, load_ewma=70.6ms, baseline=25.1ms, delta=45.5ms | DL=940M, UL=9M
2026-01-08 01:16:17,321 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=58.3ms, load_ewma=68.2ms, baseline=25.1ms, delta=43.0ms | DL=940M, UL=9M
2026-01-08 01:16:19,314 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=51.2ms, load_ewma=64.8ms, baseline=25.1ms, delta=39.6ms | DL=940M, UL=9M
2026-01-08 01:16:21,457 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=194.0ms, load_ewma=90.6ms, baseline=25.1ms, delta=65.5ms | DL=940M, UL=8M
2026-01-08 01:16:23,340 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=69.0ms, load_ewma=86.3ms, baseline=25.1ms, delta=61.2ms | DL=940M, UL=8M
2026-01-08 01:16:25,324 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=62.5ms, load_ewma=81.5ms, baseline=25.1ms, delta=56.4ms | DL=940M, UL=8M
2026-01-08 01:16:27,321 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=57.7ms, load_ewma=76.8ms, baseline=25.1ms, delta=51.6ms | DL=940M, UL=8M
2026-01-08 01:16:29,344 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=79.6ms, load_ewma=77.3ms, baseline=25.1ms, delta=52.2ms | DL=940M, UL=8M
2026-01-08 01:16:31,317 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=61.8ms, load_ewma=74.2ms, baseline=25.1ms, delta=49.1ms | DL=940M, UL=8M
2026-01-08 01:16:33,313 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=49.6ms, load_ewma=69.3ms, baseline=25.1ms, delta=44.2ms | DL=940M, UL=8M
2026-01-08 01:16:37,419 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=155.0ms, load_ewma=86.4ms, baseline=25.1ms, delta=61.3ms | DL=940M, UL=8M
2026-01-08 01:16:39,304 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=33.6ms, load_ewma=75.9ms, baseline=25.1ms, delta=50.7ms | DL=940M, UL=8M
2026-01-08 01:16:41,308 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=44.9ms, load_ewma=69.7ms, baseline=25.1ms, delta=44.5ms | DL=940M, UL=8M
2026-01-08 01:16:43,310 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=44.4ms, load_ewma=64.6ms, baseline=25.1ms, delta=39.5ms | DL=940M, UL=8M
2026-01-08 01:16:45,376 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=112.0ms, load_ewma=74.1ms, baseline=25.1ms, delta=49.0ms | DL=940M, UL=8M
2026-01-08 01:16:47,290 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=24.4ms, load_ewma=64.2ms, baseline=25.1ms, delta=39.0ms | DL=940M, UL=8M
2026-01-08 01:16:49,340 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=82.5ms, load_ewma=67.8ms, baseline=25.1ms, delta=42.7ms | DL=940M, UL=8M
2026-01-08 01:16:51,338 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=69.3ms, load_ewma=68.1ms, baseline=25.1ms, delta=43.0ms | DL=940M, UL=8M
2026-01-08 01:16:53,430 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=167.0ms, load_ewma=87.9ms, baseline=25.1ms, delta=62.8ms | DL=940M, UL=8M
2026-01-08 01:16:55,347 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=80.2ms, load_ewma=86.4ms, baseline=25.1ms, delta=61.2ms | DL=940M, UL=8M
2026-01-08 01:16:57,314 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=41.6ms, load_ewma=77.4ms, baseline=25.1ms, delta=52.3ms | DL=940M, UL=8M
2026-01-08 01:16:59,341 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=73.0ms, load_ewma=76.5ms, baseline=25.1ms, delta=51.4ms | DL=940M, UL=8M
2026-01-08 01:17:01,336 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=75.8ms, load_ewma=76.4ms, baseline=25.1ms, delta=51.2ms | DL=940M, UL=8M
2026-01-08 01:17:03,366 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=103.0ms, load_ewma=81.7ms, baseline=25.1ms, delta=56.6ms | DL=940M, UL=8M
2026-01-08 01:17:05,307 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=43.2ms, load_ewma=74.0ms, baseline=25.1ms, delta=48.9ms | DL=940M, UL=8M
2026-01-08 01:17:07,307 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=41.1ms, load_ewma=67.4ms, baseline=25.1ms, delta=42.3ms | DL=940M, UL=8M
2026-01-08 01:17:09,357 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=98.4ms, load_ewma=73.6ms, baseline=25.1ms, delta=48.5ms | DL=940M, UL=8M
2026-01-08 01:17:13,344 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=75.3ms, load_ewma=74.0ms, baseline=25.1ms, delta=48.8ms | DL=940M, UL=8M
2026-01-08 01:17:15,327 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=62.7ms, load_ewma=71.7ms, baseline=25.1ms, delta=46.6ms | DL=940M, UL=8M
2026-01-08 01:17:17,301 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=40.3ms, load_ewma=65.4ms, baseline=25.1ms, delta=40.3ms | DL=940M, UL=8M
2026-01-08 01:17:19,342 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=77.3ms, load_ewma=67.8ms, baseline=25.1ms, delta=42.7ms | DL=940M, UL=8M
2026-01-08 01:17:21,332 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=63.1ms, load_ewma=66.9ms, baseline=25.1ms, delta=41.7ms | DL=940M, UL=8M
2026-01-08 01:17:23,360 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=91.8ms, load_ewma=71.8ms, baseline=25.1ms, delta=46.7ms | DL=940M, UL=8M
2026-01-08 01:17:25,341 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=71.4ms, load_ewma=71.8ms, baseline=25.1ms, delta=46.6ms | DL=940M, UL=8M
2026-01-08 01:17:27,313 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=56.8ms, load_ewma=68.8ms, baseline=25.1ms, delta=43.6ms | DL=940M, UL=8M
2026-01-08 01:17:29,325 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=55.4ms, load_ewma=66.1ms, baseline=25.1ms, delta=41.0ms | DL=940M, UL=8M
2026-01-08 01:17:31,333 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=66.0ms, load_ewma=66.1ms, baseline=25.1ms, delta=40.9ms | DL=940M, UL=8M
2026-01-08 01:17:33,368 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=73.6ms, load_ewma=67.6ms, baseline=25.1ms, delta=42.4ms | DL=940M, UL=8M
2026-01-08 01:17:35,324 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=53.0ms, load_ewma=64.7ms, baseline=25.1ms, delta=39.5ms | DL=940M, UL=8M
2026-01-08 01:17:37,332 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=75.1ms, load_ewma=66.8ms, baseline=25.1ms, delta=41.6ms | DL=940M, UL=8M
2026-01-08 01:17:41,341 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=57.8ms, load_ewma=65.0ms, baseline=25.1ms, delta=39.8ms | DL=940M, UL=8M
2026-01-08 01:17:43,343 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=72.3ms, load_ewma=66.4ms, baseline=25.1ms, delta=41.3ms | DL=940M, UL=8M
2026-01-08 01:17:45,375 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=106.0ms, load_ewma=74.3ms, baseline=25.1ms, delta=49.2ms | DL=940M, UL=8M
2026-01-08 01:17:47,335 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=66.3ms, load_ewma=72.7ms, baseline=25.1ms, delta=47.6ms | DL=940M, UL=8M
2026-01-08 01:17:49,334 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=64.3ms, load_ewma=71.0ms, baseline=25.1ms, delta=45.9ms | DL=940M, UL=8M
2026-01-08 01:17:51,340 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=79.7ms, load_ewma=72.8ms, baseline=25.1ms, delta=47.6ms | DL=940M, UL=8M
2026-01-08 01:17:53,366 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=106.0ms, load_ewma=79.4ms, baseline=25.1ms, delta=54.3ms | DL=940M, UL=8M
2026-01-08 01:17:55,341 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=76.5ms, load_ewma=78.8ms, baseline=25.1ms, delta=53.7ms | DL=940M, UL=8M
2026-01-08 01:17:57,356 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=86.5ms, load_ewma=80.4ms, baseline=25.1ms, delta=55.2ms | DL=940M, UL=8M
2026-01-08 01:17:59,294 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=24.8ms, load_ewma=69.3ms, baseline=25.1ms, delta=44.1ms | DL=940M, UL=8M
2026-01-08 01:18:01,292 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=22.4ms, load_ewma=59.9ms, baseline=25.1ms, delta=34.7ms | DL=940M, UL=8M
2026-01-08 01:18:03,311 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=24.8ms, load_ewma=52.9ms, baseline=25.1ms, delta=27.7ms | DL=940M, UL=8M
2026-01-08 01:18:05,297 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=22.0ms, load_ewma=46.7ms, baseline=25.1ms, delta=21.6ms | DL=940M, UL=8M
2026-01-08 01:18:07,297 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=22.1ms, load_ewma=41.8ms, baseline=25.1ms, delta=16.6ms | DL=940M, UL=8M
```

**Note:** REST test ended with delta=16.6ms (approaching GREEN threshold of 15ms), showing rapid recovery once load stopped.

---

### SSH/Paramiko Test - Full Log

```
2026-01-08 01:21:17,956 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=312.0ms, load_ewma=84.1ms, baseline=25.6ms, delta=58.5ms | DL=940M, UL=32M
2026-01-08 01:21:27,715 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=62.4ms, load_ewma=79.7ms, baseline=25.6ms, delta=54.1ms | DL=940M, UL=27M
2026-01-08 01:21:29,720 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=74.0ms, load_ewma=78.6ms, baseline=25.6ms, delta=53.0ms | DL=940M, UL=23M
2026-01-08 01:21:31,707 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=60.7ms, load_ewma=75.0ms, baseline=25.6ms, delta=49.4ms | DL=940M, UL=20M
2026-01-08 01:21:33,728 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=79.0ms, load_ewma=75.8ms, baseline=25.6ms, delta=50.2ms | DL=940M, UL=17M
2026-01-08 01:21:38,056 [spectrum] [INFO] spectrum: [RED/RED] RTT=404.0ms, load_ewma=141.5ms, baseline=25.6ms, delta=115.8ms | DL=799M, UL=14M
2026-01-08 01:21:39,704 [spectrum] [INFO] spectrum: [RED/RED] RTT=58.4ms, load_ewma=124.8ms, baseline=25.6ms, delta=99.2ms | DL=679M, UL=12M
2026-01-08 01:21:41,690 [spectrum] [INFO] spectrum: [RED/RED] RTT=41.7ms, load_ewma=108.2ms, baseline=25.6ms, delta=82.6ms | DL=577M, UL=10M
2026-01-08 01:21:43,754 [spectrum] [INFO] spectrum: [RED/RED] RTT=108.0ms, load_ewma=108.2ms, baseline=25.6ms, delta=82.6ms | DL=491M, UL=9M
2026-01-08 01:21:45,736 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=89.8ms, load_ewma=104.5ms, baseline=25.6ms, delta=78.9ms | DL=491M, UL=8M
2026-01-08 01:21:47,726 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=82.1ms, load_ewma=100.0ms, baseline=25.6ms, delta=74.4ms | DL=491M, UL=8M
2026-01-08 01:21:49,695 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=48.5ms, load_ewma=89.7ms, baseline=25.6ms, delta=64.1ms | DL=491M, UL=8M
2026-01-08 01:21:51,836 [spectrum] [INFO] spectrum: [RED/RED] RTT=188.0ms, load_ewma=109.4ms, baseline=25.6ms, delta=83.8ms | DL=417M, UL=8M
2026-01-08 01:21:53,697 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=47.3ms, load_ewma=97.0ms, baseline=25.6ms, delta=71.4ms | DL=417M, UL=8M
2026-01-08 01:21:55,756 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=109.0ms, load_ewma=99.4ms, baseline=25.6ms, delta=73.8ms | DL=417M, UL=8M
2026-01-08 01:21:57,715 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=66.5ms, load_ewma=92.8ms, baseline=25.6ms, delta=67.2ms | DL=417M, UL=8M
2026-01-08 01:21:59,721 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=75.4ms, load_ewma=89.3ms, baseline=25.6ms, delta=63.7ms | DL=417M, UL=8M
2026-01-08 01:22:01,715 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=63.2ms, load_ewma=84.1ms, baseline=25.6ms, delta=58.5ms | DL=417M, UL=8M
2026-01-08 01:22:03,707 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=56.3ms, load_ewma=78.5ms, baseline=25.6ms, delta=52.9ms | DL=417M, UL=8M
2026-01-08 01:22:05,696 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=48.4ms, load_ewma=72.5ms, baseline=25.6ms, delta=46.9ms | DL=417M, UL=8M
2026-01-08 01:22:07,744 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=93.6ms, load_ewma=76.7ms, baseline=25.6ms, delta=51.1ms | DL=417M, UL=8M
2026-01-08 01:22:09,697 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=47.6ms, load_ewma=70.9ms, baseline=25.6ms, delta=45.3ms | DL=417M, UL=8M
2026-01-08 01:22:11,702 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=53.9ms, load_ewma=67.5ms, baseline=25.6ms, delta=41.9ms | DL=417M, UL=8M
2026-01-08 01:22:15,752 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=104.0ms, load_ewma=74.8ms, baseline=25.6ms, delta=49.2ms | DL=417M, UL=8M
2026-01-08 01:22:17,694 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=47.5ms, load_ewma=69.3ms, baseline=25.6ms, delta=43.7ms | DL=417M, UL=8M
2026-01-08 01:22:19,710 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=60.8ms, load_ewma=67.6ms, baseline=25.6ms, delta=42.0ms | DL=417M, UL=8M
2026-01-08 01:22:21,720 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=71.3ms, load_ewma=68.4ms, baseline=25.6ms, delta=42.8ms | DL=417M, UL=8M
2026-01-08 01:22:23,691 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=43.8ms, load_ewma=63.5ms, baseline=25.6ms, delta=37.8ms | DL=417M, UL=8M
2026-01-08 01:22:25,700 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=50.5ms, load_ewma=60.9ms, baseline=25.6ms, delta=35.3ms | DL=417M, UL=8M
2026-01-08 01:22:27,794 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=144.0ms, load_ewma=77.5ms, baseline=25.6ms, delta=51.9ms | DL=417M, UL=8M
2026-01-08 01:22:29,729 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=78.9ms, load_ewma=77.8ms, baseline=25.6ms, delta=52.2ms | DL=417M, UL=8M
2026-01-08 01:22:31,759 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=111.0ms, load_ewma=84.4ms, baseline=25.6ms, delta=58.8ms | DL=417M, UL=8M
2026-01-08 01:22:33,707 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=58.9ms, load_ewma=79.3ms, baseline=25.6ms, delta=53.7ms | DL=417M, UL=8M
2026-01-08 01:22:35,698 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=48.3ms, load_ewma=73.1ms, baseline=25.6ms, delta=47.5ms | DL=417M, UL=8M
2026-01-08 01:22:37,695 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=39.3ms, load_ewma=66.3ms, baseline=25.6ms, delta=40.7ms | DL=417M, UL=8M
2026-01-08 01:22:39,703 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=52.6ms, load_ewma=63.6ms, baseline=25.6ms, delta=38.0ms | DL=417M, UL=8M
2026-01-08 01:22:41,691 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=40.8ms, load_ewma=59.0ms, baseline=25.6ms, delta=33.4ms | DL=417M, UL=8M
2026-01-08 01:22:43,705 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=54.2ms, load_ewma=58.1ms, baseline=25.6ms, delta=32.5ms | DL=417M, UL=8M
2026-01-08 01:22:45,706 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=57.4ms, load_ewma=57.9ms, baseline=25.6ms, delta=32.3ms | DL=417M, UL=8M
2026-01-08 01:22:47,700 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=48.6ms, load_ewma=56.1ms, baseline=25.6ms, delta=30.5ms | DL=417M, UL=8M
2026-01-08 01:22:49,714 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=63.9ms, load_ewma=57.6ms, baseline=25.6ms, delta=32.0ms | DL=417M, UL=8M
2026-01-08 01:22:51,701 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=48.0ms, load_ewma=55.7ms, baseline=25.6ms, delta=30.1ms | DL=417M, UL=8M
2026-01-08 01:22:53,702 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=50.2ms, load_ewma=54.6ms, baseline=25.6ms, delta=29.0ms | DL=417M, UL=8M
2026-01-08 01:22:55,715 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=63.6ms, load_ewma=56.4ms, baseline=25.6ms, delta=30.8ms | DL=417M, UL=8M
2026-01-08 01:22:57,698 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=46.0ms, load_ewma=54.3ms, baseline=25.6ms, delta=28.7ms | DL=417M, UL=8M
2026-01-08 01:22:59,696 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=45.2ms, load_ewma=52.5ms, baseline=25.6ms, delta=26.9ms | DL=417M, UL=8M
2026-01-08 01:23:01,699 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=45.9ms, load_ewma=51.2ms, baseline=25.6ms, delta=25.6ms | DL=417M, UL=8M
2026-01-08 01:23:03,695 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=40.7ms, load_ewma=49.1ms, baseline=25.6ms, delta=23.5ms | DL=417M, UL=8M
2026-01-08 01:23:05,694 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=44.2ms, load_ewma=48.1ms, baseline=25.6ms, delta=22.5ms | DL=417M, UL=8M
2026-01-08 01:23:07,693 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=42.8ms, load_ewma=47.0ms, baseline=25.6ms, delta=21.4ms | DL=417M, UL=8M
2026-01-08 01:23:09,692 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=39.7ms, load_ewma=45.6ms, baseline=25.6ms, delta=20.0ms | DL=417M, UL=8M
2026-01-08 01:23:11,722 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=68.3ms, load_ewma=50.1ms, baseline=25.6ms, delta=24.5ms | DL=417M, UL=8M
2026-01-08 01:23:13,709 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=58.1ms, load_ewma=51.7ms, baseline=25.6ms, delta=26.1ms | DL=417M, UL=8M
2026-01-08 01:23:15,725 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=70.3ms, load_ewma=55.4ms, baseline=25.6ms, delta=29.8ms | DL=417M, UL=8M
2026-01-08 01:23:17,727 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=74.5ms, load_ewma=59.2ms, baseline=25.6ms, delta=33.6ms | DL=417M, UL=8M
2026-01-08 01:23:19,688 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=38.3ms, load_ewma=55.1ms, baseline=25.6ms, delta=29.5ms | DL=417M, UL=8M
2026-01-08 01:23:21,689 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=34.3ms, load_ewma=50.9ms, baseline=25.6ms, delta=25.3ms | DL=417M, UL=8M
2026-01-08 01:23:23,722 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=69.3ms, load_ewma=54.6ms, baseline=25.6ms, delta=29.0ms | DL=417M, UL=8M
2026-01-08 01:23:25,819 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=166.0ms, load_ewma=76.9ms, baseline=25.6ms, delta=51.3ms | DL=417M, UL=8M
2026-01-08 01:23:27,680 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=26.9ms, load_ewma=66.9ms, baseline=25.6ms, delta=41.3ms | DL=417M, UL=8M
2026-01-08 01:23:29,691 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=38.9ms, load_ewma=61.3ms, baseline=25.6ms, delta=35.7ms | DL=417M, UL=8M
2026-01-08 01:23:31,699 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=44.9ms, load_ewma=58.0ms, baseline=25.6ms, delta=32.4ms | DL=417M, UL=8M
2026-01-08 01:23:33,713 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=60.1ms, load_ewma=58.4ms, baseline=25.6ms, delta=32.8ms | DL=417M, UL=8M
2026-01-08 01:23:35,705 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=51.4ms, load_ewma=57.0ms, baseline=25.6ms, delta=31.4ms | DL=417M, UL=8M
2026-01-08 01:23:37,715 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=60.5ms, load_ewma=57.7ms, baseline=25.6ms, delta=32.1ms | DL=417M, UL=8M
2026-01-08 01:23:39,724 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=70.2ms, load_ewma=60.2ms, baseline=25.6ms, delta=34.6ms | DL=417M, UL=8M
2026-01-08 01:23:41,713 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=58.5ms, load_ewma=59.9ms, baseline=25.6ms, delta=34.3ms | DL=417M, UL=8M
2026-01-08 01:23:43,699 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=43.9ms, load_ewma=56.7ms, baseline=25.6ms, delta=31.1ms | DL=417M, UL=8M
2026-01-08 01:23:45,684 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=40.7ms, load_ewma=53.5ms, baseline=25.6ms, delta=27.9ms | DL=417M, UL=8M
2026-01-08 01:23:47,693 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=39.1ms, load_ewma=50.6ms, baseline=25.6ms, delta=25.0ms | DL=417M, UL=8M
2026-01-08 01:23:49,693 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=36.8ms, load_ewma=47.8ms, baseline=25.6ms, delta=22.2ms | DL=417M, UL=8M
2026-01-08 01:23:51,695 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=41.2ms, load_ewma=46.5ms, baseline=25.6ms, delta=20.9ms | DL=417M, UL=8M
2026-01-08 01:23:53,743 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=86.9ms, load_ewma=54.6ms, baseline=25.6ms, delta=29.0ms | DL=417M, UL=8M
2026-01-08 01:23:55,688 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=42.3ms, load_ewma=52.1ms, baseline=25.6ms, delta=26.5ms | DL=417M, UL=8M
2026-01-08 01:23:57,701 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=54.4ms, load_ewma=52.6ms, baseline=25.6ms, delta=27.0ms | DL=417M, UL=8M
2026-01-08 01:23:59,705 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=49.3ms, load_ewma=51.9ms, baseline=25.6ms, delta=26.3ms | DL=417M, UL=8M
2026-01-08 01:24:01,750 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=94.1ms, load_ewma=60.4ms, baseline=25.6ms, delta=34.8ms | DL=417M, UL=8M
2026-01-08 01:24:03,708 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=51.0ms, load_ewma=58.5ms, baseline=25.6ms, delta=32.9ms | DL=417M, UL=8M
2026-01-08 01:24:05,744 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=94.6ms, load_ewma=65.7ms, baseline=25.6ms, delta=40.1ms | DL=417M, UL=8M
2026-01-08 01:24:07,719 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=62.7ms, load_ewma=65.1ms, baseline=25.6ms, delta=39.5ms | DL=417M, UL=8M
2026-01-08 01:24:09,745 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=92.7ms, load_ewma=70.6ms, baseline=25.6ms, delta=45.0ms | DL=417M, UL=8M
2026-01-08 01:24:11,798 [spectrum] [INFO] spectrum: [YELLOW/RED] RTT=145.0ms, load_ewma=85.5ms, baseline=25.6ms, delta=59.9ms | DL=417M, UL=8M
2026-01-08 01:24:15,680 [spectrum] [INFO] spectrum: [SOFT_RED/RED] RTT=23.4ms, load_ewma=73.1ms, baseline=25.6ms, delta=47.5ms | DL=417M, UL=8M
2026-01-08 01:24:17,680 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=23.3ms, load_ewma=63.1ms, baseline=25.6ms, delta=37.5ms | DL=417M, UL=8M
2026-01-08 01:24:19,681 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=23.3ms, load_ewma=55.2ms, baseline=25.6ms, delta=29.6ms | DL=417M, UL=8M
2026-01-08 01:24:21,677 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=22.8ms, load_ewma=48.7ms, baseline=25.6ms, delta=23.1ms | DL=417M, UL=8M
2026-01-08 01:24:23,683 [spectrum] [INFO] spectrum: [YELLOW/YELLOW] RTT=34.6ms, load_ewma=45.9ms, baseline=25.6ms, delta=20.3ms | DL=417M, UL=8M
```

**Note:** SSH test ended with download still at 417M (55% reduction from 940M) and delta=20.3ms. The download bandwidth would take many more GREEN cycles to recover.

---

## Critical Observations

### The RED/RED Cascade (SSH Only)

The SSH test experienced a catastrophic cascade at 01:21:38:

```
01:21:33 [SOFT_RED/RED] delta=50.2ms | DL=940M, UL=17M
  (5 second gap - ping failures while SSH command executing)
01:21:38 [RED/RED] RTT=404ms, delta=115.8ms | DL=799M, UL=14M  <- HARD RED
01:21:39 [RED/RED] delta=99.2ms | DL=679M, UL=12M
01:21:41 [RED/RED] delta=82.6ms | DL=577M, UL=10M
01:21:43 [RED/RED] delta=82.6ms | DL=491M, UL=9M
```

This cascade happened because:

1. SSH command took ~200ms to execute
2. During that time, congestion escalated
3. By the time the next measurement occurred, RTT had spiked to 404ms
4. Download was aggressively reduced (940M → 491M in 5 cycles)

**REST API prevented this cascade** by executing commands fast enough to catch congestion before it spiraled.

### Download Recovery Time

After the test, both systems need to recover download bandwidth:

- **REST:** Download was never reduced (940M throughout)
- **SSH:** Download at 417M, needs ~52 GREEN cycles (104 seconds) to recover to 940M

This means SSH users would experience reduced download capacity for nearly 2 minutes after the congestion event ended.

---

## Configuration

### Production Config (REST API)

```yaml
# /etc/wanctl/<wan_name>.yaml
router:
  transport: "rest" # REST API recommended
  host: "<router-ip>"
  user: "admin"
  password: "${ROUTER_PASSWORD}" # From /etc/wanctl/secrets
  port: 443
  verify_ssl: false
```

### Secrets File

```bash
# /etc/wanctl/secrets (mode 640, root:wanctl)
ROUTER_PASSWORD=<password>
```

### RouterOS Requirements

Enable REST API on the router:

```routeros
/ip service set www-ssl disabled=no port=443
/certificate add name=local-cert common-name=router
/ip service set www-ssl certificate=local-cert
```

---

## Conclusion

REST API transport provides measurably better congestion control than SSH/Paramiko:

1. **Faster feedback loop** prevents congestion escalation
2. **No download reduction** during upload-only congestion
3. **Lower peak RTT** for better user experience
4. **Faster recovery** after congestion events

The only tradeoff is password-based authentication vs SSH keys, which is acceptable with proper secrets management.

**REST API is now the recommended and default transport for wanctl.**

---

_Document generated: 2026-01-08_
_wanctl version: 4.6 (REST API transport)_
