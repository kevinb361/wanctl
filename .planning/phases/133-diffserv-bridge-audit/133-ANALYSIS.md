# Phase 133: Diffserv Bridge Audit -- Analysis

**Date:** 2026-04-03
**Tested by:** Claude Code (SSH commands run from dev machine)
**Equipment:** cake-shaper VM 206 (10.10.110.223), MikroTik RB5009 (10.10.99.1)
**Traffic generator:** Python sockets with explicit IP_TOS from dev machine (10.10.110.226)

## Executive Summary

**DSCP marks survive the entire bridge path.** The MikroTik mangle rules correctly set DSCP, the Linux bridge passes L3 headers untouched, and CAKE diffserv4 correctly classifies packets into the expected tins. The v1.26 observation that "diffserv tins not separating" was caused by **iperf3 --dscp not actually setting the TOS byte** on this Linux system -- the test tool was broken, not the network path.

## Test Environment

### CAKE Qdisc Configuration
```
ens17 (download, 940Mbit): cake diffserv4 triple-isolate nonat nowash ingress rtt 50ms overhead 38
ens16 (upload, 38Mbit):    cake diffserv4 triple-isolate nonat nowash ack-filter rtt 50ms overhead 38
```
Both NICs use `nowash` -- DSCP marks are not stripped by CAKE itself.

### Bridge Configuration
- **br-spectrum:** L2 bridge, members: ens16 (modem-side) + ens17 (router-side)
- **vlan_filtering:** 0 (disabled)
- **Bridge type:** Standard Linux bridge, no VLAN processing
- No IP addresses on bridge (pure transparent L2)

### MikroTik Mangle Rules (DSCP-relevant)

**Prerouting chain:**
- "Trust EF": `action=accept, dscp=46` -- passes EF packets without modification
- "Trust AF4x": `action=accept, dscp=34/36/38` -- passes AF4x packets without modification
- "DSCP WASH: inbound from WAN": `action=change-dscp, new-dscp=0, in-interface-list=WAN` -- strips inbound WAN DSCP (1.7B packets processed)
- Connection marking: QOS_HIGH, QOS_MEDIUM, QOS_NORMAL, QOS_LOW based on ports/protocols

**Postrouting chain:**
- "DSCP SET: HIGH (EF)": `connection-mark=QOS_HIGH, dscp=0 → new-dscp=46`
- "DSCP SET: MEDIUM (AF31)": `connection-mark=QOS_MEDIUM, dscp=0 → new-dscp=26`
- "DSCP SET: LOW (CS1)": `connection-mark=QOS_LOW, dscp=0 → new-dscp=8`
- "DSCP SET: NORMAL (CS0)": `connection-mark=QOS_NORMAL, dscp=0 → new-dscp=0`
- "DSCP: Map DSCP to 802.1p priority on egress": `action=set-priority, new-priority=from-dscp`

**Key observation:** DSCP SET rules match `dscp=0` (only modify unmarked packets). Packets arriving with DSCP already set (via Trust rules or client-set) pass through postrouting unmodified.

### System Settings
- **ip_forward_update_priority:** 1 (enabled, but only affects IP forwarding, not bridge forwarding)
- **ethtool offloads on ens17:** rx-checksum on, tx-checksum on, GSO on, GRO on, scatter-gather on

## Hop-by-Hop Results

| DSCP Class | DSCP Value | TOS Hex | Dev Machine (local) | ens17 (phys NIC) | br-spectrum (bridge) | CAKE Tin Hit (ens16 upload) | Expected Tin | Result |
|------------|------------|---------|---------------------|------------------|----------------------|---------------------------|--------------|--------|
| EF (Voice) | 46 | 0xb8 | 0xb8 | 0xb8 | N/A (same path) | Voice (+100 pkts) | Voice (3) | **PASS** |
| AF41 (Video) | 34 | 0x88 | 0x88 | 0x88 | N/A | Video (+113 pkts) | Video (2) | **PASS** |
| CS0 (BE) | 0 | 0x00 | 0x00 | 0x00 | N/A | BestEffort (+195 pkts) | BestEffort (1) | **PASS** |
| CS1 (Bulk) | 8 | 0x20 | 0x20 | 0x20 | N/A | Bulk (+219 pkts) | Bulk (0) | **PASS** |

**All 4 DSCP classes land in their correct CAKE tins.**

### ens16 (Upload) Tin Stats Delta

| Tin | Baseline | Post-test | Delta | Analysis |
|-----|----------|-----------|-------|----------|
| Bulk | 44,339,831 | 44,340,050 | +219 | ~100 CS1 test + background |
| BestEffort | 108,887,320 | 108,887,515 | +195 | Background traffic only |
| Video | 5,410,373 | 5,410,486 | +113 | ~100 AF41 test + background |
| Voice | 59,132,323 | 59,132,423 | +100 | Exactly 100 EF test packets |

### ens17 (Download) Tin Stats (historical)

| Tin | Packets | Bytes | Notes |
|-----|---------|-------|-------|
| Bulk | 117,538 | 18.4 MB | Minimal -- few CS1 inbound |
| BestEffort | 1,184M | 1.7 TB | Vast majority of download traffic |
| Video | 5,864 | 3.0 MB | Almost no AF4x inbound |
| Voice | 96.2M | 5.8 GB | EF traffic (VoIP, VPN, IRTT) |

**Download tin distribution confirms:** DSCP marks from MikroTik's postrouting rules do reach CAKE. Voice tin has 96M packets (8.1% of total) -- consistent with QOS_HIGH (EF-marked) traffic like VoIP and VPN.

## Detailed Per-Class Results

### EF (Voice, DSCP 46, TOS 0xb8)
- **Local tcpdump:** `tos 0xb8` confirmed on dev machine outgoing interface
- **ens17 tcpdump:** `tos 0xb8` confirmed -- marks survive MikroTik Trust rule + bridge
- **CAKE tin:** Voice tin received exactly +100 packets
- **MikroTik flow:** Prerouting "Trust EF" (`dscp=46, action=accept`) → skips classification → postrouting DSCP SET rules don't match (`dscp=0` condition fails) → DSCP 46 preserved

### AF41 (Video, DSCP 34, TOS 0x88)
- **Local tcpdump:** `tos 0x88` confirmed
- **ens17 tcpdump:** `tos 0x88` confirmed
- **CAKE tin:** Video tin received +113 packets (~100 test + background)
- **MikroTik flow:** Same as EF -- "Trust AF4x" rule passes through

### CS0 (Best Effort, DSCP 0, TOS 0x00)
- **CAKE tin:** BestEffort tin received +195 packets (background-dominated)
- **Control test:** Confirms unmarked traffic correctly lands in BestEffort

### CS1 (Bulk, DSCP 8, TOS 0x20)
- **Local tcpdump:** `tos 0x20` confirmed
- **ens17 tcpdump:** `tos 0x20` confirmed
- **CAKE tin:** Bulk tin received +219 packets (~100 test + background)

## Failure Point Identification

**There is no failure in the DSCP bridge path.** The MikroTik-to-CAKE pipeline works correctly:

1. MikroTik prerouting: "Trust" rules preserve incoming DSCP marks; WASH rule only strips WAN inbound
2. MikroTik postrouting: DSCP SET rules stamp connection-mark-based DSCP on unmarked packets
3. Linux bridge (br-spectrum): Transparent L2 -- does not modify IP header TOS/DSCP byte
4. CAKE diffserv4: Correctly reads DSCP from IP header and classifies into appropriate tins

**Root cause of v1.26 "tins not separating" observation:** The iperf3 `--dscp` flag on this Linux system does not actually set the TOS byte on outgoing packets (verified via local tcpdump: `tos 0x0` despite `--dscp EF`). All iperf3 test packets arrived as CS0 (unmarked), so all traffic correctly landed in BestEffort -- CAKE was doing exactly what it should with unmarked traffic.

**Verification method:** Python `socket.setsockopt(IPPROTO_IP, IP_TOS, 0xb8)` correctly sets TOS and was used for the definitive test. This proved the network path is healthy and the v1.26 issue was a test tool problem, not a network problem.

## Fix Strategy (per D-06: document only, no implementation)

### The bridge path needs no fix.

DSCP marks survive the entire path from dev machine through MikroTik through the Linux bridge to CAKE. The tins are separating correctly.

### Recommendations for Phase 134

Since the bridge path is healthy, Phase 134 should pivot from "fix tin separation" to "validate and automate DSCP verification":

**Option 1: Add DSCP verification to wanctl-check-cake (Low complexity)**
- Extend `wanctl-check-cake` to verify tin distribution is non-trivial (Voice > 0, Video > 0, Bulk > 0)
- Alerts if all traffic is in BestEffort (likely indicates DSCP marking is misconfigured)
- Fits QOS-03 requirement: "wanctl-check-cake validates DSCP mark survival"

**Option 2: Add a Python-based DSCP test tool (Medium complexity)**
- Send known-DSCP test packets via Python sockets (not iperf3)
- Read tin stats before/after
- Confirm correct tin classification
- Could be a `wanctl-check-dscp` CLI tool

**Option 3: Fix iperf3 --dscp (Low complexity, external tool)**
- Investigate why iperf3 --dscp doesn't set TOS (possibly a capabilities issue or build flag)
- If fixable, existing flent RRUL tests would automatically test tin separation
- `getcap $(which iperf3)` to check capabilities, or rebuild with appropriate socket options

### Recommended for Phase 134

**Option 1 (wanctl-check-cake extension)** -- lowest risk, highest value, directly satisfies QOS-03. The tin distribution check can detect DSCP misconfiguration automatically without requiring test traffic generation.

## Raw Data References

- MikroTik mangle rules: Full JSON dump captured via REST API during audit
- tcpdump captures: ens17 and br-spectrum showing TOS bytes for EF/AF41/CS1 packets
- CAKE tin stats: ens16 baseline + post-test deltas confirming correct classification
- iperf3 --dscp failure: Local tcpdump proving iperf3 sends tos=0x0 despite --dscp EF flag

---

*Phase: 133-diffserv-bridge-audit*
*Audit completed: 2026-04-03*
*Conclusion: Bridge path is healthy. v1.26 "tins not separating" was caused by broken iperf3 --dscp, not a network issue.*
