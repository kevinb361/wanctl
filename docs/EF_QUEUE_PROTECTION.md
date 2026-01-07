# EF Queue Protection

This document explains how wanctl protects Expedited Forwarding (EF) priority traffic.

## Overview

wanctl adjusts CAKE queue bandwidth limits based on real-time congestion. However, **EF queues are explicitly excluded from adjustment** to ensure priority traffic is never impacted.

## Design Philosophy

Priority traffic (VoIP, gaming, interactive SSH) requires:
1. **Consistent bandwidth** - no adaptive throttling
2. **Low latency** - guaranteed by CAKE's tin system
3. **Protection from congestion** - isolated from bulk traffic

wanctl achieves this by:
- Only adjusting **bulk traffic queues** (best-effort)
- Never touching **EF/priority queues**
- Letting CAKE's internal tin scheduling handle priority within queues

## Queue Hierarchy

### Adjusted by wanctl (Bulk Traffic)

These queues have dynamic limits based on RTT measurements:

```
WAN-Download-1    (floor_mbps → ceiling_mbps)
WAN-Upload-1      (floor_mbps → ceiling_mbps)
WAN-Download-2    (floor_mbps → ceiling_mbps)
WAN-Upload-2      (floor_mbps → ceiling_mbps)
```

### Protected (EF/Priority Traffic)

These queues have **fixed limits** and are never adjusted:

```
EF-Upload-1       (5 Mbps fixed)
EF-Upload-2       (5 Mbps fixed)
```

## Configuration

EF queues are protected by **not including them** in your wanctl config:

```yaml
# wan1.yaml - Only list queues you want wanctl to manage
queues:
  download: "WAN-Download-1"    # wanctl adjusts this
  upload: "WAN-Upload-1"        # wanctl adjusts this
  # EF-Upload-1 is NOT listed = NOT adjusted
```

## RouterOS Queue Structure

A typical RouterOS setup with EF protection:

```
/queue tree
add name="WAN-Download-1" parent=wan1-download queue=cake-download max-limit=940M
add name="WAN-Upload-1" parent=wan1-upload queue=cake-upload max-limit=38M
add name="EF-Upload-1" parent=wan1-upload queue=cake-ef-upload max-limit=5M priority=1

# EF queue gets:
# - Fixed 5M bandwidth (never throttled)
# - Priority 1 (highest)
# - Separate queue tree (isolated from bulk)
```

## Traffic Classification

Traffic reaches EF queues via mangle rules:

```
/ip firewall mangle
add chain=postrouting dscp=ef action=mark-packet new-packet-mark=ef-traffic
add chain=postrouting dscp=af31 action=mark-packet new-packet-mark=ef-traffic
```

Common EF traffic:
- **DSCP EF (46)**: VoIP RTP streams
- **DSCP AF31 (26)**: Gaming, interactive applications
- **DSCP CS6 (48)**: Network control (OSPF, BGP)

## Why Not Adjust EF Queues?

**Q: Why not proportionally reduce EF bandwidth during congestion?**

A: EF traffic is typically:
1. **Low volume** - VoIP is ~100 Kbps per call, gaming ~50-200 Kbps
2. **Not the cause of congestion** - bulk downloads cause bufferbloat
3. **Latency-critical** - any throttling causes user-visible degradation

Reducing EF bandwidth during congestion would:
- Cause VoIP audio degradation when you need it most
- Increase gaming latency during peak usage
- Provide negligible bandwidth recovery (~5 Mbps vs 900 Mbps bulk)

**The correct approach:** Throttle bulk traffic to reduce queue depth, protecting EF latency.

## Monitoring EF Queues (Optional)

While wanctl doesn't adjust EF queues, you may want to monitor them:

### RouterOS Queue Stats

```bash
/queue tree print stats where name~"EF"
```

### Prometheus/Grafana

If exporting metrics, include EF queue utilization to detect:
- Sustained high utilization (may need larger EF allocation)
- Zero utilization (EF rules not matching traffic)
- Drops (EF queue too small)

### Log EF Stats

Add to your monitoring scripts:

```bash
ssh admin@router '/queue tree print stats where name~"EF"' | grep -E 'bytes|packets|drops'
```

## EF Queue Sizing

Recommended EF queue sizes based on use case:

| Use Case | Recommended Size | Notes |
|----------|-----------------|-------|
| Single VoIP line | 1-2 Mbps | G.711 = 87 Kbps, G.729 = 32 Kbps |
| Home office | 3-5 Mbps | VoIP + video conferencing |
| Power user | 5-10 Mbps | Gaming + VoIP + interactive SSH |
| Multi-user | 10-15 Mbps | Multiple concurrent priority users |

**Rule of thumb:** EF queue should be 10-15% of upload capacity or enough for your priority applications, whichever is smaller.

## Interaction with Steering

When wanctl's steering daemon routes traffic to an alternate WAN:
- Only **new** EF connections are steered
- Existing EF flows continue on their original path
- EF queue limits remain fixed on both WANs

This ensures mid-call VoIP or gaming sessions are never disrupted.

## Troubleshooting

### EF Traffic Not Prioritized

1. Check mangle rules are matching:
   ```
   /ip firewall mangle print stats where comment~"EF"
   ```

2. Verify DSCP marking from source application

3. Confirm queue tree parent assignment

### EF Queue Dropping Packets

1. Increase EF queue size
2. Verify traffic classification isn't too broad
3. Check for misbehaving applications marking bulk traffic as EF

### Priority Traffic Still Laggy

1. Verify EF queue is separate from bulk queues
2. Check CAKE shaper is active (not bypassed)
3. Ensure upstream ISP isn't remarking DSCP

## Summary

- **wanctl only adjusts queues listed in config**
- **EF queues are protected by omission**
- **Priority traffic gets fixed bandwidth and highest priority**
- **Bulk traffic throttling protects EF latency during congestion**

This design ensures latency-sensitive applications work reliably even during heavy network load.
