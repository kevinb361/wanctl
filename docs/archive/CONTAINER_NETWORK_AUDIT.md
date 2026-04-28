# Container Network Audit

> **Historical (pre-v1.21):** This audit was conducted when wanctl ran in LXC containers (cake-spectrum, cake-att) on Proxmox. The v1.21 VM migration eliminated the container networking layer entirely. These findings are preserved for reference but no longer apply to the current VM architecture.

**Generated:** 2026-03-17 00:35 UTC

## Executive Summary

**PASS** - All containers had mean RTT overhead < 0.5ms and jitter was NEGLIGIBLE relative to WAN idle jitter. Container networking added no meaningful measurement noise.

## Measurement Methodology

- **Method:** Host-to-container ICMP ping via subprocess
- **Path:** Host machine -> veth pair -> Linux bridge -> container
- **Measures:** Full round-trip through container networking stack (excludes WAN path)
- **Samples per container:** 5000

## Per-Container Results

### cake-spectrum

**Host:** 10.10.110.246

| Metric  | Value   |
| ------- | ------- |
| Mean    | 0.171ms |
| Median  | 0.167ms |
| P95     | 0.219ms |
| P99     | 0.288ms |
| Stddev  | 0.046ms |
| Min     | 0.101ms |
| Max     | 1.790ms |
| Samples | 5000    |

### cake-att

**Host:** 10.10.110.247

| Metric  | Value   |
| ------- | ------- |
| Mean    | 0.166ms |
| Median  | 0.163ms |
| P95     | 0.210ms |
| P99     | 0.277ms |
| Stddev  | 0.048ms |
| Min     | 0.098ms |
| Max     | 2.050ms |
| Samples | 5000    |

## Jitter Analysis

- **cake-spectrum:** NEGLIGIBLE (9.2% of WAN idle jitter) (container stddev=0.046ms vs WAN idle jitter=0.5ms)
- **cake-att:** NEGLIGIBLE (9.6% of WAN idle jitter) (container stddev=0.048ms vs WAN idle jitter=0.5ms)

## Network Topology

### cake-spectrum

**ip link show:**

```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: eth0@if67: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether bc:24:11:37:0d:30 brd ff:ff:ff:ff:ff:ff link-netnsid 0
```

**ip addr show:**

```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host noprefixroute
       valid_lft forever preferred_lft forever
2: eth0@if67: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether bc:24:11:37:0d:30 brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 10.10.110.246/24 brd 10.10.110.255 scope global dynamic eth0
       valid_lft 85909sec preferred_lft 85909sec
    inet6 fe80::be24:11ff:fe37:d30/64 scope link
       valid_lft forever preferred_lft forever
```

### cake-att

**ip link show:**

```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: eth0@if74: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether bc:24:11:97:c4:e3 brd ff:ff:ff:ff:ff:ff link-netnsid 0
```

**ip addr show:**

```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host noprefixroute
       valid_lft forever preferred_lft forever
2: eth0@if74: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether bc:24:11:97:c4:e3 brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 10.10.110.247/24 brd 10.10.110.255 scope global dynamic eth0
       valid_lft 65537sec preferred_lft 65537sec
    inet6 fe80::be24:11ff:fe97:c4e3/64 scope link
       valid_lft forever preferred_lft forever
```

## Recommendation

All containers show mean RTT overhead well below the 0.5ms threshold. Container jitter is negligible compared to WAN idle jitter. No changes to the measurement infrastructure are needed. The veth pair + bridge path adds no meaningful noise to RTT measurements.
