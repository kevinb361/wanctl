# WireGuard Baseline Capture

**Captured:** 2026-04-05T03:53:00Z (Task 1 of 140-01-PLAN)
**Router:** RB5009 10.10.99.1 (RouterOS 7.20.7)
**Uptime:** 2w5d10h15m54s (19.43 days)

## WireGuard Interface (wireguard1, .id=*5A)

| Counter     | Value       | Per Day   |
| ----------- | ----------- | --------- |
| tx-error    | 850,160     | 43,760    |
| tx-drop     | 3,238       | 167       |
| tx-packet   | 7,811,389   | 402,085   |
| tx-byte     | 5,515,087,596 (5.14 GB) | 265 MB |
| rx-error    | 0           | 0         |
| rx-drop     | 0           | 0         |
| rx-packet   | 6,826,619   | 351,368   |
| rx-byte     | 1,234,114,084 (1.15 GB) | 59 MB |

**Error rate:** 10.9% of TX packets
**TX:RX byte ratio:** 4.5x (asymmetric -- VNC screen updates to phone)
**MTU:** 1420 (actual-mtu=1420)
**Running:** true
**Last link-up:** 2026-03-16 12:38:00
**Link-downs:** 0

## WireGuard Peer (phone, .id=*3)

| Field                    | Value            |
| ------------------------ | ---------------- |
| name                     | peer3            |
| comment                  | phone            |
| allowed-address          | 10.255.255.2/32  |
| current-endpoint-address | 10.10.110.210    |
| current-endpoint-port    | 60306            |
| last-handshake           | 2d2h38m19s ago   |
| tx (peer counter)        | 1,220,181,160    |
| rx (peer counter)        | 1,234,114,084    |
| endpoint-address         | (not set)        |

**Observation:** Peer last connected from 10.10.110.210 (home WiFi LAN), NOT a WAN/cellular address. Last handshake was 2+ days ago -- phone is currently disconnected.

## MSS Clamp Rule (*29F)

| Field              | Value                                    |
| ------------------ | ---------------------------------------- |
| chain              | postrouting                              |
| action             | change-mss                               |
| new-mss            | clamp-to-pmtu                            |
| out-interface-list | WAN                                      |
| protocol           | tcp                                      |
| tcp-flags          | syn                                      |
| packets matched    | 1,403,839                                |
| passthrough        | true                                     |
| comment            | ROUTING: Clamp MSS to PMTU on WAN egress |

**Critical finding:** This rule does NOT apply to inner WG tunnel traffic. The rule matches TCP SYN on postrouting with out-interface=WAN. By the time traffic reaches postrouting, WG has already encapsulated inner packets into UDP. The MSS clamp sees the outer UDP packet, not inner TCP. Inner TCP through the WG tunnel is therefore NOT MSS-clamped.

## WAN Interface MTUs

| Interface           | MTU  | Actual MTU | Running |
| ------------------- | ---- | ---------- | ------- |
| ether1-WAN-Spectrum | 1500 | 1500       | true    |
| ether2-WAN-ATT      | 1500 | 1500       | true    |

## WG Dual-WAN Routing Rules

**Rule *338 (input chain):** Mark WG connections arriving on ether2-WAN-ATT as `wg_via_att`
- 78 packets / 12,668 bytes matched
- Matches: udp dst-port=51820, in-interface=ether2-WAN-ATT, connection-state=new

**Rule *339 (output chain):** Route WG responses with `wg_via_att` mark via ATT
- 6,765,414 packets / 5,220,888,920 bytes (5.22 GB) matched
- 86.6% of WG TX packets (6.76M / 7.81M) routed via ATT

## MTU Budget Analysis

```
Inner MTU:  1420 bytes (WG interface setting)
WG header:    32 bytes
UDP header:    8 bytes
IP header:    20 bytes
--------------------------
Outer packet: 1480 bytes maximum
WAN MTU:      1500 bytes
Margin:         20 bytes
```

20 bytes margin is tight but should be sufficient for standard Ethernet with no VLAN tags.

## Post-Reset Error Accumulation (KEY FINDING)

Counters reset at ~03:54:10Z. Monitoring showed:

| Time     | tx-error | tx-packet | Notes                          |
| -------- | -------- | --------- | ------------------------------ |
| +0s      | 0        | 0         | Reset confirmed                |
| +30s     | 9        | 0         | Errors with ZERO tx-packets!   |
| +38s     | 9        | 0         | Brief pause                    |
| +48s     | 18       | 0         | More errors, still no tx-pkts  |

**TX errors accumulate with tx-packet=0.** This means the router is attempting to transmit through the WG interface but failing before the packet is counted as "sent." The peer is offline (2d2h since handshake), so there may be:
1. Queued/buffered packets the router keeps retrying
2. Keepalive or handshake initiation attempts failing
3. ARP/NDP resolution failures for the WG peer address

The error rate at idle (~18 errors in ~48 seconds = ~32,400/day) is close to the lifetime average (43,760/day), suggesting errors occur continuously regardless of active tunnel use.

## Key Questions for Task 2

1. Do tx-errors stop if the peer connects? (i.e., are errors only from failed sends to offline peer?)
2. Does the MSS clamp gap cause additional errors under load with TCP traffic?
3. Is the error rate different on ATT vs Spectrum WAN path?
4. Would reducing WG MTU from 1420 to a lower value help?

---

*Counter reset timestamp: 2026-04-05T03:54:10Z*
*All data collected via REST API per D-01*
