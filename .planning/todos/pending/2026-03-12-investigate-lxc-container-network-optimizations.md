---
created: "2026-03-12T16:47:54.997Z"
title: Investigate LXC container network optimizations
area: infrastructure
files: []
---

## Problem

wanctl runs on two LXC containers (cake-spectrum, cake-att) in production. These containers haven't been audited for performance optimizations — especially network-related tuning. Since RTT measurement accuracy is critical to the 50ms control loop (ping response time directly affects congestion detection quality), any network stack overhead in the LXC layer could add latency noise or jitter that degrades measurement fidelity.

Areas to investigate:
- LXC network driver/mode (veth vs macvlan vs passthrough)
- Kernel network stack tuning (sysctl params: net.core.rmem_max, net.ipv4.tcp_low_latency, etc.)
- CPU pinning / cgroup resource allocation for network-intensive workloads
- NAPI/interrupt coalescing settings that may add latency
- Bridge vs routed networking overhead
- Container-specific ICMP handling and any added latency vs bare metal

## Solution

TBD — needs research into Proxmox LXC network configuration options and benchmarking against bare-metal ping times to quantify any LXC overhead.
