# Phase 113 Plan 03: Queue Depth and Memory Pressure Baseline

**Date:** 2026-03-26
**VM:** cake-shaper (10.10.110.223)
**Capture method:** `tc -s qdisc show` via SSH, idle and under multi-flow download load

---

## NETENG-05: Queue Depth and Memory Pressure Baseline

### Methodology

1. Captured CAKE qdisc statistics at idle (GREEN state, no active bulk downloads)
2. Generated Spectrum download load using 4 concurrent HTTP downloads (speedtest.tele2.net)
3. Captured statistics during load (5 seconds after starting downloads)
4. Also captured `tc -j -s qdisc show` for machine-readable JSON baseline
5. Read `spectrum_state.json` for current controller state and bandwidth settings

**System state at capture time:**
- Download: GREEN (89 consecutive green cycles), rate = 940 Mbit (full link)
- Upload: GREEN (89 consecutive green cycles), rate = 38 Mbit (full link)
- Baseline RTT: 22.67ms, Load RTT: 26.14ms (delta ~3.5ms, well within GREEN)
- Last applied: DL 879.8 Mbit, UL 36.72 Mbit

### Interface Map

| Interface | WAN | Direction | CAKE Bandwidth | Handle |
|-----------|-----|-----------|----------------|--------|
| ens16 | Spectrum | Upload | 38 Mbit | 8007: |
| ens17 | Spectrum | Download | 940 Mbit | 800a: |
| ens27 | ATT | Upload | 18 Mbit | 8005: |
| ens28 | ATT | Download | 95 Mbit | 8004: |

### Spectrum Upload (ens16) -- Idle vs Load

| Metric | Idle | Under Load | Delta | Notes |
|--------|------|------------|-------|-------|
| Sent bytes | 16,303,866,289 | 16,310,679,701 | +6.8 MB | Normal upload ACKs for download traffic |
| Sent packets | 33,550,326 | 33,584,753 | +34,427 | |
| Dropped | 7,105,716 | 7,105,722 | +6 | Minimal new drops |
| Overlimits | 62,337,910 | 62,345,606 | +7,696 | Rate limiting active |
| Requeues | 2,331 | 2,333 | +2 | Negligible |
| **Backlog (bytes)** | **0b** | **0b** | 0 | No queuing |
| **Backlog (packets)** | **0p** | **0p** | 0 | No queuing |
| **memory_used** | **6,793,072 (6.48 MB)** | **6,793,072 (6.48 MB)** | 0 | Stable |
| **memory_limit** | **33,554,432 (32 MB)** | **33,554,432 (32 MB)** | -- | Config value |
| **memory_used %** | **20.2%** | **20.2%** | 0 | Well within limits |
| Capacity estimate | 38 Mbit | 38 Mbit | 0 | Stable at configured rate |

**Per-tin breakdown (idle):**

| Tin | Packets | Bytes | Drops | ECN Marks | ACK Drops | Backlog |
|-----|---------|-------|-------|-----------|-----------|---------|
| Bulk | 16,117,606 | 11.1 GB | 10,278 | 167,436 | 3,032,145 | 0b |
| Best Effort | 13,679,929 | 2.55 GB | 1,190 | 37 | 1,119,611 | 0b |
| Video | 2,158,153 | 1.17 GB | 2,849 | 69,086 | 84,208 | 0b |
| Voice | 8,700,404 | 1.99 GB | 10,522 | 5 | 2,844,913 | 0b |

**Observations:** Bulk tin carries the most bytes (upload data destined for Bulk DSCP classification). Voice tin has high packet count and ACK drops (2.8M) -- these are TCP ACKs for download traffic being filtered by ack-filter (correct behavior). ECN marking is highest in Bulk (167K marks) -- CAKE actively ECN-marking rather than dropping.

### Spectrum Download (ens17) -- Idle vs Load

| Metric | Idle | Under Load | Delta | Notes |
|--------|------|------------|-------|-------|
| Sent bytes | 174,808,528,259 | 174,894,532,323 | +86 MB | Download traffic during load |
| Sent packets | 141,132,326 | 141,218,603 | +86,277 | |
| Dropped | 2,580,668 | 2,580,668 | 0 | No new drops |
| Overlimits | 192,162,801 | 192,201,670 | +38,869 | Rate limiting active |
| Requeues | 63,313 | 63,447 | +134 | |
| **Backlog (bytes)** | **0b** | **0b** | 0 | No queuing buildup |
| **Backlog (packets)** | **0p** | **0p** | 0 | No queuing buildup |
| **memory_used** | **20,440,716 (19.49 MB)** | **20,440,716 (19.49 MB)** | 0 | Stable |
| **memory_limit** | **33,554,432 (32 MB)** | **33,554,432 (32 MB)** | -- | Config value |
| **memory_used %** | **60.9%** | **60.9%** | 0 | Moderate usage |
| Capacity estimate | 940 Mbit | 940 Mbit | 0 | At link speed |

**Per-tin breakdown (idle):**

| Tin | Packets | Bytes | Drops | ECN Marks | ACK Drops | Backlog |
|-----|---------|-------|-------|-----------|-----------|---------|
| Bulk | 32,527 | 48.6 MB | 0 | 295 | 0 | 0b |
| Best Effort | 129,145,280 | 177.8 GB | 2,580,667 | 2,128 | 0 | 0b |
| Video | 830 | 384 KB | 0 | 0 | 0 | 0b |
| Voice | 14,534,357 | 873.3 MB | 1 | 0 | 0 | 0b |

**Observations:** Best Effort carries 99.7% of all download traffic (177.8 GB) and all cumulative drops (2.58M). This is expected -- bulk downloads classified as CS0 (Best Effort) by MikroTik mangle rules. The zero backlog under load is because the CAKE bandwidth limit (940 Mbit) equals the Spectrum provisioned link speed, so CAKE is not rate-limiting below the link capacity. Memory usage at 60.9% is the highest of all qdiscs, reflecting the large bandwidth * RTT product for the download direction.

### ATT Upload (ens27) -- Idle vs Load

| Metric | Idle | Under Load | Delta | Notes |
|--------|------|------------|-------|-------|
| Sent bytes | 2,313,330,951 | 2,313,936,325 | +605 KB | Low background traffic |
| Sent packets | 11,047,530 | 11,052,811 | +5,281 | |
| Dropped | 138,555 | 138,555 | 0 | No new drops |
| Overlimits | 4,546,279 | 4,547,006 | +727 | |
| Requeues | 10 | 10 | 0 | |
| **Backlog (bytes)** | **0b** | **0b** | 0 | No queuing |
| **Backlog (packets)** | **0p** | **0p** | 0 | No queuing |
| **memory_used** | **533,736 (521 KB)** | **533,736 (521 KB)** | 0 | Minimal |
| **memory_limit** | **33,554,432 (32 MB)** | **33,554,432 (32 MB)** | -- | Config value |
| **memory_used %** | **1.6%** | **1.6%** | 0 | Very low |
| Capacity estimate | 18 Mbit | 18 Mbit | 0 | At configured rate |

**Per-tin breakdown (idle):**

| Tin | Packets | Bytes | Drops | ECN Marks | ACK Drops | Backlog |
|-----|---------|-------|-------|-----------|-----------|---------|
| Bulk | 336,412 | 45 MB | 563 | 0 | 74,598 | 0b |
| Best Effort | 6,611,645 | 1.56 GB | 294 | 27 | 2,782 | 0b |
| Video | 309,548 | 135.6 MB | 1,852 | 1 | 368 | 0b |
| Voice | 3,928,480 | 592.9 MB | 1,194 | 0 | 56,904 | 0b |

**Observations:** ATT upload memory usage is only 1.6% of limit -- 32 MB is significantly oversized for an 18 Mbit upload link. Bulk tin ACK drops (74.6K) from ack-filter are the dominant drop type, which is correct for TCP ACK compression. Video tin has the most true drops (1,852), possibly from IRTT or VPN packets that occasionally burst.

### ATT Download (ens28) -- Idle vs Load

| Metric | Idle | Under Load | Delta | Notes |
|--------|------|------------|-------|-------|
| Sent bytes | 13,480,876,781 | 13,483,148,881 | +2.3 MB | Low background traffic |
| Sent packets | 15,440,214 | 15,446,040 | +5,826 | |
| Dropped | 83,800 | 83,800 | 0 | No new drops |
| Overlimits | 17,813,884 | 17,815,826 | +1,942 | |
| Requeues | 1,100 | 1,100 | 0 | |
| **Backlog (bytes)** | **0b** | **0b** | 0 | No queuing |
| **Backlog (packets)** | **0p** | **0p** | 0 | No queuing |
| **memory_used** | **1,476,272 (1.41 MB)** | **1,476,272 (1.41 MB)** | 0 | Low |
| **memory_limit** | **33,554,432 (32 MB)** | **33,554,432 (32 MB)** | -- | Config value |
| **memory_used %** | **4.4%** | **4.4%** | 0 | Very low |
| Capacity estimate | 95 Mbit | 95 Mbit | 0 | At configured rate |

**Per-tin breakdown (idle):**

| Tin | Packets | Bytes | Drops | ECN Marks | ACK Drops | Backlog |
|-----|---------|-------|-------|-----------|-----------|---------|
| Bulk | 0 | 0 | 0 | 0 | 0 | 0b |
| Best Effort | 15,436,514 | 13.6 GB | 83,800 | 19 | 0 | 0b |
| Video | 172 | 64 KB | 0 | 0 | 0 | 0b |
| Voice | 87,328 | 5.2 MB | 0 | 0 | 0 | 0b |

**Observations:** Bulk tin has zero traffic -- ATT download does not serve bulk-classified traffic (it's the fallback WAN, only used for overflow). Best Effort carries 99.4% of all download traffic. Memory usage at 4.4% is very low. Like Spectrum, zero backlog because shaper bandwidth (95 Mbit) matches ATT link capacity.

### Memory Pressure Analysis

| Interface | WAN Direction | memory_used | memory_limit | Usage % | Assessment |
|-----------|--------------|-------------|--------------|---------|------------|
| ens16 | Spectrum UL | 6,793,072 (6.48 MB) | 33,554,432 (32 MB) | 20.2% | Appropriate |
| ens17 | Spectrum DL | 20,440,716 (19.49 MB) | 33,554,432 (32 MB) | **60.9%** | Moderate, monitor |
| ens27 | ATT UL | 533,736 (521 KB) | 33,554,432 (32 MB) | **1.6%** | Oversized |
| ens28 | ATT DL | 1,476,272 (1.41 MB) | 33,554,432 (32 MB) | **4.4%** | Oversized |

**Analysis:**

1. **Spectrum Download (60.9%):** Highest memory consumer. At 940 Mbit * 100ms RTT, the bandwidth-delay product (BDP) is ~11.75 MB. CAKE allocates memory for its flow tracking structures, per-tin state, and packet buffering. 60.9% usage indicates the memlimit is well-sized for this high-bandwidth direction -- enough headroom for burst absorption without being wasteful. Under heavy congestion with rate reduction (e.g., 200 Mbit during RED state), memory pressure would decrease proportionally.

2. **Spectrum Upload (20.2%):** Reasonable utilization. At 38 Mbit * 100ms, the BDP is ~475 KB. The higher memory usage (6.48 MB vs 475 KB BDP) reflects CAKE's per-flow tracking overhead for diffserv4 with triple-isolate (tracking per-flow state across 4 tins).

3. **ATT Upload (1.6%):** Significantly oversized. At 18 Mbit * 100ms, BDP is only ~225 KB. The 32 MB memlimit provides 142x the BDP. However, reducing memlimit is low-priority because the actual memory used (521 KB) is minimal -- the kernel allocates on demand, not up to the limit.

4. **ATT Download (4.4%):** Similarly oversized. At 95 Mbit * 100ms, BDP is ~1.19 MB. Actual usage (1.41 MB) tracks BDP closely, confirming CAKE allocates proportionally. The 32 MB limit provides 22x headroom.

**Recommendation on 32 MB memlimit:** The 32 MB memlimit is **appropriate for Spectrum download** (60.9% usage, headroom needed for burst absorption). For the other three qdiscs, 32 MB is generous but harmless -- CAKE allocates memory on demand, so the unused portion isn't wasted physical RAM. A uniform 32 MB across all qdiscs simplifies configuration and provides safety margin if bandwidth is temporarily increased (e.g., during ISP speed upgrades). **No change recommended** -- the current configuration prioritizes simplicity and safety over memory optimization. Total CAKE memory footprint across all 4 qdiscs is 29.3 MB out of 128 MB allocated (4 * 32 MB), well within the VM's available memory.

### Queue Depth Baseline (Backlog Analysis)

**Key finding: Backlog is zero across all qdiscs at both idle and under load.**

This is the expected steady-state for a correctly-tuned CAKE deployment:

1. **At idle:** No traffic queued, CAKE is passthrough. Zero backlog is trivially expected.

2. **Under load (download test):** The CAKE bandwidth limit equals the ISP provisioned link speed (940 Mbit for Spectrum). Since the shaper rate matches the link capacity, incoming traffic is forwarded at line rate without queuing. CAKE only creates backlog when traffic arrival rate exceeds the shaper rate.

3. **When backlog would appear:** During congestion (when wanctl detects RTT increase and reduces the CAKE bandwidth limit), the shaper rate drops below the link capacity. At that point, CAKE would queue excess traffic, creating non-zero backlog. This is intentional -- CAKE replaces ISP buffer bloat with controlled, shallow queuing.

4. **Historical drops confirm load existed:** The cumulative drop counts (7.1M on Spectrum upload, 2.6M on Spectrum download, 138K on ATT upload, 83K on ATT download) prove that CAKE has been actively managing traffic since the system started. The zero-backlog snapshot simply means the system was in GREEN state at capture time.

**Peak delay values confirm prior congestion management:**

| Interface | Tin | Peak Delay | Avg Delay | Notes |
|-----------|-----|------------|-----------|-------|
| ens16 (Spec UL) | Bulk | 1.34 ms | 258 us | Moderate peak, ack-filter active |
| ens16 (Spec UL) | Voice | 675 us | 25 us | Excellent voice latency |
| ens17 (Spec DL) | Bulk | 5.81 ms | 2.42 ms | Highest peak -- expected for bulk |
| ens17 (Spec DL) | Best Effort | 12 us | 3 us | Near-zero latency at 940 Mbit |
| ens27 (ATT UL) | Bulk | 43.5 ms | 8.79 ms | Highest overall -- ATT upload bottleneck |
| ens27 (ATT UL) | Voice | 315 us | 14 us | Good voice latency |
| ens28 (ATT DL) | Best Effort | 39 us | 4 us | Low latency, light usage |

**ATT upload Bulk tin at 43.5ms peak delay** is the highest delay across all qdiscs. This reflects the tight bandwidth constraint (18 Mbit) and the nature of bulk traffic. The 16.1ms target for the ATT upload Bulk tin (higher than the 5ms default for other tins) is automatically set by CAKE to accommodate the lower bandwidth -- CAKE scales targets based on bandwidth to avoid unnecessary drops on slower links.

### Drop Rate Analysis

| Interface | WAN Direction | Total Drops | Total Packets | Drop Rate % | Notes |
|-----------|--------------|-------------|---------------|-------------|-------|
| ens16 | Spectrum UL | 7,105,716 | 33,550,326 | 21.2% | High, but mostly ack-filter (7.08M) |
| ens17 | Spectrum DL | 2,580,668 | 141,132,326 | 1.83% | Best Effort only |
| ens27 | ATT UL | 138,555 | 11,047,530 | 1.25% | Split across tins |
| ens28 | ATT DL | 83,800 | 15,440,214 | 0.54% | Best Effort only |

**Note on Spectrum upload 21.2% "drop rate":** This is misleadingly high because it includes ack-filter drops (7,080,882 ACK drops across all tins). ACK-filter drops are intentional TCP ACK thinning -- redundant ACKs are removed to free upload bandwidth for real data. Excluding ack-filter drops, the actual loss rate is (7,105,716 - 7,080,882) / 33,550,326 = 0.074%, which is excellent.

### ECN Marking Summary

| Interface | WAN Direction | ECN Marks | Drops (non-ACK) | ECN:Drop Ratio | Notes |
|-----------|--------------|-----------|-----------------|----------------|-------|
| ens16 | Spectrum UL | 236,564 | 24,834 | 9.5:1 | Heavy ECN preference |
| ens17 | Spectrum DL | 2,423 | 2,580,668 | 0.001:1 | Drops dominate (ingress) |
| ens27 | ATT UL | 28 | 3,903 | 0.007:1 | Low ECN marking |
| ens28 | ATT DL | 19 | 83,800 | 0.0002:1 | Negligible ECN |

**Spectrum upload has an excellent 9.5:1 ECN-to-drop ratio** -- CAKE strongly prefers ECN marking over dropping on the upload path. This is the desired behavior for responsive TCP flows that support ECN. The download direction shows the opposite (drops >> ECN marks) because ingress CAKE operates differently -- it shapes after the packet has already been received by the NIC, so ECN marking is less effective (the sender is upstream of the shaper). The download-direction ECN marks (2,423 total) come from the Bulk tin (295) and Best Effort tin (2,128), confirming ECN is enabled on download as expected.

### Raw tc Statistics (JSON format at idle)

<details>
<summary>Full tc -j -s qdisc show output (click to expand)</summary>

```json
[{"kind":"noqueue","handle":"0:","dev":"lo","root":true,"refcnt":2,"options":{},"bytes":0,"packets":0,"drops":0,"overlimits":0,"requeues":0,"backlog":0,"qlen":0},{"kind":"fq_codel","handle":"0:","dev":"ens18","root":true,"refcnt":2,"options":{"limit":10240,"flows":1024,"quantum":1514,"target":4999,"interval":99999,"memory_limit":33554432,"ecn":true,"drop_batch":64},"bytes":1055075336,"packets":10765526,"drops":0,"overlimits":0,"requeues":1,"backlog":0,"qlen":0,"maxpacket":1700,"drop_overlimit":0,"new_flow_count":51484,"ecn_mark":0,"new_flows_len":0,"old_flows_len":0},{"kind":"cake","handle":"8007:","dev":"ens16","root":true,"refcnt":9,"options":{"bandwidth":4750000,"diffserv":"diffserv4","flowmode":"triple-isolate","nat":false,"wash":false,"ingress":false,"ack-filter":"enabled","split_gso":true,"rtt":100000,"raw":false,"atm":"noatm","overhead":18,"mpu":64,"memlimit":33554432,"fwmark":"0"},"bytes":16304449916,"packets":33551067,"drops":7105716,"overlimits":62338506,"requeues":2331,"backlog":0,"qlen":0,"memory_used":6793072,"memory_limit":33554432,"capacity_estimate":4750000,"min_network_size":46,"max_network_size":1500,"min_adj_size":64,"max_adj_size":1518,"avg_hdr_offset":14,"tins":[{"threshold_rate":296875,"sent_bytes":11122264970,"backlog_bytes":0,"target_us":7649,"interval_us":102649,"peak_delay_us":1171,"avg_delay_us":266,"base_delay_us":1,"sent_packets":16117791,"way_indirect_hits":31349,"way_misses":8646,"way_collisions":0,"drops":10278,"ecn_mark":167436,"ack_drops":3032145,"sparse_flows":1,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":68338,"flow_quantum":300},{"threshold_rate":4750000,"sent_bytes":2552604216,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":82,"avg_delay_us":5,"base_delay_us":1,"sent_packets":13680227,"way_indirect_hits":1743387,"way_misses":45589,"way_collisions":0,"drops":1190,"ecn_mark":37,"ack_drops":1119611,"sparse_flows":3,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":21810,"flow_quantum":1159},{"threshold_rate":2375000,"sent_bytes":1175237849,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":952,"avg_delay_us":233,"base_delay_us":1,"sent_packets":2158410,"way_indirect_hits":39581,"way_misses":73835,"way_collisions":0,"drops":2849,"ecn_mark":69086,"ack_drops":84208,"sparse_flows":1,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":24224,"flow_quantum":579},{"threshold_rate":1187500,"sent_bytes":1989441533,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":672,"avg_delay_us":25,"base_delay_us":1,"sent_packets":8700405,"way_indirect_hits":1080,"way_misses":84781,"way_collisions":0,"drops":10522,"ecn_mark":5,"ack_drops":2844913,"sparse_flows":4,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":11789,"flow_quantum":300}]},{"kind":"cake","handle":"800a:","dev":"ens17","root":true,"refcnt":9,"options":{"bandwidth":117500000,"diffserv":"diffserv4","flowmode":"triple-isolate","nat":false,"wash":false,"ingress":true,"ack-filter":"disabled","split_gso":true,"rtt":100000,"raw":false,"atm":"noatm","overhead":18,"mpu":64,"memlimit":33554432,"fwmark":"0"},"bytes":174808633527,"packets":141133732,"drops":2580668,"overlimits":192162803,"requeues":63313,"backlog":0,"qlen":0,"memory_used":20440716,"memory_limit":33554432,"capacity_estimate":117500000,"min_network_size":46,"max_network_size":1500,"min_adj_size":64,"max_adj_size":1518,"avg_hdr_offset":14,"tins":[{"threshold_rate":7343750,"sent_bytes":48559699,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":5812,"avg_delay_us":2420,"base_delay_us":1,"sent_packets":32527,"way_indirect_hits":0,"way_misses":255,"way_collisions":0,"drops":0,"ecn_mark":295,"ack_drops":0,"sparse_flows":6,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":15140,"flow_quantum":1514},{"threshold_rate":117500000,"sent_bytes":177793072325,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":6,"avg_delay_us":2,"base_delay_us":0,"sent_packets":129145862,"way_indirect_hits":646230,"way_misses":302785,"way_collisions":0,"drops":2580667,"ecn_mark":2128,"ack_drops":0,"sparse_flows":3,"bulk_flows":1,"unresponsive_flows":0,"max_pkt_len":68130,"flow_quantum":1514},{"threshold_rate":58750000,"sent_bytes":384467,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":19,"avg_delay_us":4,"base_delay_us":1,"sent_packets":830,"way_indirect_hits":0,"way_misses":565,"way_collisions":0,"drops":0,"ecn_mark":0,"ack_drops":0,"sparse_flows":6,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":2106,"flow_quantum":1514},{"threshold_rate":29375000,"sent_bytes":873360268,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":5,"avg_delay_us":2,"base_delay_us":1,"sent_packets":14535181,"way_indirect_hits":0,"way_misses":143,"way_collisions":0,"drops":1,"ecn_mark":0,"ack_drops":0,"sparse_flows":1,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":1342,"flow_quantum":1514}]},{"kind":"cake","handle":"8005:","dev":"ens27","root":true,"refcnt":9,"options":{"bandwidth":2250000,"diffserv":"diffserv4","flowmode":"triple-isolate","nat":false,"wash":false,"ingress":false,"ack-filter":"enabled","split_gso":true,"rtt":100000,"raw":false,"atm":"ptm","overhead":22,"memlimit":33554432,"fwmark":"0"},"bytes":2313362006,"packets":11047827,"drops":138555,"overlimits":4546306,"requeues":10,"backlog":0,"qlen":0,"memory_used":533736,"memory_limit":33554432,"capacity_estimate":2250000,"min_network_size":46,"max_network_size":1436,"min_adj_size":70,"max_adj_size":1481,"avg_hdr_offset":14,"tins":[{"threshold_rate":140625,"sent_bytes":44989164,"backlog_bytes":0,"target_us":16149,"interval_us":111149,"peak_delay_us":43482,"avg_delay_us":8788,"base_delay_us":4,"sent_packets":336412,"way_indirect_hits":0,"way_misses":75,"way_collisions":0,"drops":563,"ecn_mark":0,"ack_drops":74598,"sparse_flows":1,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":4542,"flow_quantum":300},{"threshold_rate":2250000,"sent_bytes":1555847668,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":31,"avg_delay_us":4,"base_delay_us":1,"sent_packets":6611931,"way_indirect_hits":2583,"way_misses":2871,"way_collisions":0,"drops":294,"ecn_mark":27,"ack_drops":2782,"sparse_flows":3,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":7220,"flow_quantum":549},{"threshold_rate":1125000,"sent_bytes":135550311,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":135,"avg_delay_us":10,"base_delay_us":2,"sent_packets":309549,"way_indirect_hits":2082,"way_misses":2658,"way_collisions":0,"drops":1852,"ecn_mark":1,"ack_drops":368,"sparse_flows":1,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":10318,"flow_quantum":300},{"threshold_rate":562500,"sent_bytes":592943752,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":303,"avg_delay_us":13,"base_delay_us":1,"sent_packets":3928490,"way_indirect_hits":0,"way_misses":379,"way_collisions":0,"drops":1194,"ecn_mark":0,"ack_drops":56904,"sparse_flows":1,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":7570,"flow_quantum":300}]},{"kind":"cake","handle":"8004:","dev":"ens28","root":true,"refcnt":9,"options":{"bandwidth":11875000,"diffserv":"diffserv4","flowmode":"triple-isolate","nat":false,"wash":false,"ingress":true,"ack-filter":"disabled","split_gso":true,"rtt":100000,"raw":false,"atm":"ptm","overhead":22,"memlimit":33554432,"fwmark":"0"},"bytes":13480909605,"packets":15440508,"drops":83800,"overlimits":17813890,"requeues":1100,"backlog":0,"qlen":0,"memory_used":1476272,"memory_limit":33554432,"capacity_estimate":11875000,"min_network_size":46,"max_network_size":1500,"min_adj_size":70,"max_adj_size":1546,"avg_hdr_offset":14,"tins":[{"threshold_rate":742187,"sent_bytes":0,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":0,"avg_delay_us":0,"base_delay_us":0,"sent_packets":0,"way_indirect_hits":0,"way_misses":0,"way_collisions":0,"drops":0,"ecn_mark":0,"ack_drops":0,"sparse_flows":0,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":0,"flow_quantum":300},{"threshold_rate":11875000,"sent_bytes":13602311560,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":34,"avg_delay_us":3,"base_delay_us":1,"sent_packets":15436808,"way_indirect_hits":2274705,"way_misses":18572,"way_collisions":0,"drops":83800,"ecn_mark":19,"ack_drops":0,"sparse_flows":3,"bulk_flows":1,"unresponsive_flows":0,"max_pkt_len":68130,"flow_quantum":1514},{"threshold_rate":5937500,"sent_bytes":63984,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":27,"avg_delay_us":2,"base_delay_us":1,"sent_packets":172,"way_indirect_hits":0,"way_misses":1,"way_collisions":0,"drops":0,"ecn_mark":0,"ack_drops":0,"sparse_flows":1,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":372,"flow_quantum":1449},{"threshold_rate":2968750,"sent_bytes":5242066,"backlog_bytes":0,"target_us":5000,"interval_us":100000,"peak_delay_us":5,"avg_delay_us":1,"base_delay_us":0,"sent_packets":87328,"way_indirect_hits":0,"way_misses":6,"way_collisions":0,"drops":0,"ecn_mark":0,"ack_drops":0,"sparse_flows":1,"bulk_flows":0,"unresponsive_flows":0,"max_pkt_len":126,"flow_quantum":724}]},{"kind":"noqueue","handle":"0:","dev":"br-att","root":true,"refcnt":2,"options":{},"bytes":0,"packets":0,"drops":0,"overlimits":0,"requeues":0,"backlog":0,"qlen":0},{"kind":"noqueue","handle":"0:","dev":"br-spectrum","root":true,"refcnt":2,"options":{},"bytes":0,"packets":0,"drops":0,"overlimits":0,"requeues":0,"backlog":0,"qlen":0}]
```

</details>

### Summary of Findings

1. **Queue depth (backlog) is zero at both idle and under load.** This is correct behavior when CAKE bandwidth matches ISP link speed and the controller is in GREEN state. Non-zero backlog occurs only during active congestion management (rate reduction).

2. **Memory pressure is moderate on Spectrum download (60.9%) and low everywhere else.** The 32 MB memlimit is well-sized for the Spectrum download direction (940 Mbit * 100ms RTT) and oversized for ATT directions. No change recommended.

3. **Traffic distribution matches DSCP design.** Best Effort tin carries the vast majority of traffic across all qdiscs. Bulk tin shows ack-filter activity on upload paths. Voice and Video tins carry proportionally less traffic with excellent latency characteristics.

4. **ECN marking is highly effective on Spectrum upload** (9.5:1 ECN-to-drop ratio). Download direction relies more on drops due to ingress shaping characteristics.

5. **ATT upload Bulk tin shows the highest peak delay (43.5 ms)** due to the constrained 18 Mbit bandwidth. This is expected and managed by CAKE's automatic target scaling.

6. **32 MB memlimit is appropriate.** No change recommended. The uniform value simplifies configuration. ATT qdiscs use <5% but the unused allocation is not wasted (kernel allocates on demand). Spectrum download at 60.9% has adequate headroom for burst absorption.

### NETENG-05 Verdict

**PASS** -- Queue depth and memory pressure baseline documented from production CAKE statistics. Operating range established: zero backlog in GREEN state, memory usage from 1.6% to 60.9% across qdiscs, 32 MB memlimit confirmed appropriate for all directions.
