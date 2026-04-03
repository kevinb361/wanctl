# Phase 133: Diffserv Bridge Audit - Research

**Researched:** 2026-04-03
**Domain:** Linux bridge DSCP handling, CAKE diffserv4 classification, network packet tracing
**Confidence:** HIGH

## Summary

This phase traces DSCP marks hop-by-hop through the MikroTik-to-CAKE bridge path to find exactly where they are lost or preserved. The v1.26 test findings show "diffserv tins not separating" -- all traffic lands in the Best Effort tin despite diffserv4 config.

Key research finding: **CAKE reads DSCP directly from the IP header** via `ipv4_get_dsfield()` in the kernel's `cake_handle_diffserv()` function -- it does NOT rely on `skb->priority`. This means a Linux bridge (which operates at L2 and passes L3 headers unchanged) should NOT strip DSCP marks. The issue is likely upstream of the bridge (MikroTik not marking packets) or a configuration issue (CAKE not initialized with diffserv4, or the test traffic itself lacking DSCP marks). The audit will determine the exact failure point.

**Primary recommendation:** Execute the 3-point tcpdump + tc stats methodology from CONTEXT.md D-01/D-02 to isolate the exact hop where DSCP marks disappear, then document fix strategy for Phase 134.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Hop-by-hop tcpdump + tc stats. Capture packets with tcpdump at each of 3 points checking IP TOS/DSCP byte. Cross-reference with `tc -s -j qdisc show` per-tin counters as final confirmation. This pinpoints exactly which hop strips marks.
- **D-02:** Three capture points: 1) MikroTik packet sniffer or torch on egress interface, 2) tcpdump on the physical NIC receiving from MikroTik (before bridge), 3) tcpdump on the bridge interface (after bridging, before CAKE). Plus tc -s tin stats as confirmation.
- **D-03:** Use iperf3 with `--dscp` flag from dev machine to generate marked flows. iperf3 server on Dallas (same infrastructure as flent testing). Tests the real end-to-end path.
- **D-04:** Test all 4 CAKE diffserv4 tin classes: EF (Voice tin), CS5 or AF41 (Video tin), CS0/default (Best Effort tin), CS1 (Bulk tin). Confirms whether each tin receives its marked traffic.
- **D-05:** Hop-by-hop results table in Markdown. Each row = hop (MikroTik egress, bridge NIC, CAKE ingress), columns = DSCP class tested, result (preserved/stripped). Plus a "Fix Strategy" section identifying what to change. Lives in `.planning/` as an analysis document that feeds Phase 134.
- **D-06:** Phase 133 documents WHERE marks are lost and WHAT the fix options are (bridge config, ethtool offload flags, tc filter, nftables DSCP restore, etc.). No implementation of fixes -- Phase 134 handles that. Clean separation: audit (133) vs fix (134).

### Claude's Discretion
- Exact tcpdump filter expressions for capturing DSCP bytes
- MikroTik sniffer/torch configuration commands
- iperf3 session duration and parallelism
- Whether to test both download and upload DSCP paths or just download
- Analysis document structure and detail level

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QOS-01 | Operator can verify whether DSCP marks survive the L2 bridge path from MikroTik mangle to CAKE tins | Full audit methodology with tcpdump at 3 capture points + tc per-tin stats; DSCP-to-TOS conversion table; iperf3 --dscp usage; MikroTik torch DSCP monitoring |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Change conservatively** -- this is a production network system
- **Explain before changing, prefer analysis over implementation** -- this phase IS analysis only
- **Priority: stability > safety > clarity > elegance** -- no changes to production config in this phase
- **Never refactor core logic without approval** -- no code changes in this phase

## Architecture: Network Topology Under Audit

### Physical Path (Spectrum WAN -- the primary audit target)

```
Dev Machine (LAN)
    |
MikroTik RB5009 (10.10.99.1)
    | eth1 (mangle rules apply DSCP here)
    |
cake-shaper VM 206 (PCIe passthrough NICs):
    ens17 (router-side, Intel i210, CAKE qdisc attached here)
    |  [Linux bridge: br-spectrum]
    ens16 (modem-side, Intel i210)
    |
Spectrum Modem -> ISP -> Internet -> Dallas (iperf3 server)
```

### CAKE Attachment Point

CAKE attaches to **router-side bridge member ports only** (egress toward MikroTik):
- Spectrum download: `ens17` with `ingress` flag (shapes incoming traffic from internet)
- Spectrum upload: `ens17` (same NIC -- both download and upload CAKE on single interface per config)

### Bridge Configuration

- `br-spectrum`: ens16 (modem-side) + ens17 (router-side), STP=0, forward_delay=0, no IP
- `br-att`: ens27 + ens28, STP=0, forward_delay=0, no IP
- Configured via systemd-networkd (.netdev + .network files)
- CAKE initialized by wanctl daemon via `tc qdisc replace`, NOT by systemd-networkd

## CAKE Diffserv4 Classification: How It Works

### Kernel-Level DSCP Extraction (HIGH confidence)

CAKE's `cake_handle_diffserv()` function in `sch_cake.c` reads DSCP **directly from the IP header**:

```c
// IPv4: reads TOS byte from IP header, right-shifts to get 6-bit DSCP
dscp = ipv4_get_dsfield((struct iphdr *)buf) >> 2;

// IPv6: reads traffic class field
dscp = ipv6_get_dsfield((struct ipv6hdr *)buf) >> 2;
```

**Classification priority order** in `cake_select_tin()`:
1. Firewall marks (if `mark && mark <= qd->tin_cnt`)
2. skb->priority (if major number matches qdisc handle)
3. DSCP from IP header (the default/fallback)

Since CAKE reads the actual IP header byte, **a Linux bridge should NOT interfere with DSCP classification**. Bridges operate at L2 and do not modify L3 headers. The IP TOS byte passes through a bridge unchanged.

Source: [Linux kernel sch_cake.c](https://github.com/torvalds/linux/blob/master/net/sched/sch_cake.c)

### Diffserv4 DSCP-to-Tin Mapping

| Tin Index | Tin Name    | Threshold | DSCP Codepoints | iperf3 --dscp Value |
|-----------|-------------|-----------|-----------------|---------------------|
| 3         | Voice       | 25%       | CS7, CS6, EF (46), VA, CS5 (40), CS4 | `EF` or `46` |
| 2         | Video       | 50%       | AF4x (34-38), AF3x (26-30), CS3, AF2x (18-22), CS2, TOS4, TOS1 | `AF41` or `34` |
| 1         | Best Effort | 100%      | CS0 (0), all unmarked traffic | `CS0` or `0` |
| 0         | Bulk        | 6.25%     | CS1 (8), LE | `CS1` or `8` |

Source: [tc-cake(8) man page](https://man7.org/linux/man-pages/man8/tc-cake.8.html)

### Wash Behavior

- **Upload:** `wash=yes` (excluded on linux-cake transparent bridge topology per `cake_params.py:60`)
- **Download:** `wash=no` (excluded on linux-cake transparent bridge topology)
- **Important:** On the linux-cake backend, `nat`, `wash`, and `autorate-ingress` are ALL excluded via `EXCLUDED_PARAMS` in `cake_params.py`. CAKE's built-in diffserv classification reads the IP header directly -- no wash is applied.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DSCP capture | Custom packet parser | tcpdump with `ip[1]` filter | tcpdump is the standard tool, handles all edge cases |
| Per-tin verification | Manual tc output parsing | `tc -s -j qdisc show` JSON output | Already parsed by linux_cake.py per-tin stats code |
| DSCP traffic generation | Custom socket programming | `iperf3 --dscp` | Supports symbolic names (EF, CS5, AF41, CS1) and numeric values |
| MikroTik DSCP check | SSH scripting | MikroTik torch via REST API or CLI | Built-in tool shows DSCP per-flow |

## Common Pitfalls

### Pitfall 1: Assuming Bridge Strips DSCP

**What goes wrong:** Blaming the Linux bridge for DSCP loss when the actual cause is upstream (no DSCP marks being set in the first place) or a CAKE configuration issue.
**Why it happens:** The bridge is "new" in the topology (v1.21 offload to VM). Previous REST transport had MikroTik handle everything.
**How to avoid:** Start audit from the source (MikroTik mangle rules). If no DSCP marks exist at MikroTik egress, the bridge is irrelevant.
**Warning signs:** All tins show 0 packets except Best Effort -- indicates no DSCP marking at all, not DSCP stripping.

### Pitfall 2: Confusing TOS Byte vs DSCP Value

**What goes wrong:** tcpdump shows TOS hex value, but DSCP is the upper 6 bits only. Off-by-factor-of-4 errors.
**Why it happens:** TOS byte = (DSCP << 2) | ECN. DSCP 46 (EF) = TOS 0xb8 = 184 decimal.
**How to avoid:** Use the conversion table below. Always verify with both tcpdump hex AND tc tin counters.
**Warning signs:** tcpdump shows non-zero TOS but tc stats show all traffic in one tin.

### Pitfall 3: Testing with Unmatched Traffic Direction

**What goes wrong:** Testing download DSCP by sending FROM dev machine, but download DSCP is set by the remote server, not by local iperf3 --dscp.
**Why it happens:** iperf3 --dscp sets DSCP on outgoing packets from the client. For download testing, the SERVER must mark return traffic.
**How to avoid:** For download audit: use iperf3 in reverse mode (`-R`) with `--dscp` flag so the server sends DSCP-marked traffic to the client. OR test upload direction where the client's --dscp marks are what we want to trace.
**Warning signs:** tcpdump on ens17 shows TOS 0x00 on download traffic even though iperf3 --dscp was set.

### Pitfall 4: CAKE Not Initialized with diffserv4

**What goes wrong:** CAKE qdisc exists but was initialized without `diffserv4` keyword -- defaults to `diffserv3` or `besteffort`.
**Why it happens:** Daemon restart, systemd-networkd race, or manual tc command without diffserv4.
**How to avoid:** Always verify current CAKE config: `tc qdisc show dev ens17` should show `diffserv4` in output.
**Warning signs:** `tc -s qdisc show` shows fewer than 4 tins (3 = diffserv3, 1 = besteffort).

### Pitfall 5: iperf3 Server Not Marking Return Traffic

**What goes wrong:** Running `iperf3 -c dallas -R --dscp EF` but Dallas iperf3 server does not honor `--dscp` for server-to-client traffic.
**Why it happens:** The `--dscp` flag on the iperf3 client sets DSCP on packets sent BY the client. In reverse mode (`-R`), the server sends data packets but may not apply the DSCP value.
**How to avoid:** Test upload path first (client sends, DSCP set by client). For download, verify server actually marks packets by capturing at MikroTik ingress before mangle.
**Warning signs:** Upload DSCP tests pass but download tests show no DSCP marks.

## Code Examples

### tcpdump Filter Expressions for DSCP Capture

```bash
# Capture ALL traffic showing TOS byte (verbose mode shows "tos 0x.." in output)
sudo tcpdump -i ens17 -v -n -c 50 host <dallas_ip>

# Filter for specific DSCP value: EF (DSCP 46, TOS 0xb8)
# Formula: TOS = DSCP << 2, so mask with 0xfc to ignore ECN bits
sudo tcpdump -i ens17 -n 'ip and (ip[1] & 0xfc) >> 2 == 46'

# Filter for CS1 (DSCP 8, TOS 0x20)
sudo tcpdump -i ens17 -n 'ip and (ip[1] & 0xfc) >> 2 == 8'

# Filter for ANY non-zero DSCP (any marked traffic)
sudo tcpdump -i ens17 -v -n 'ip and (ip[1] & 0xfc) != 0' -c 20

# Capture on bridge interface vs physical NIC comparison
sudo tcpdump -i ens17 -v -n -c 10 host <dallas_ip> &  # physical NIC
sudo tcpdump -i br-spectrum -v -n -c 10 host <dallas_ip> &  # bridge
```

**TOS/DSCP Conversion Reference:**

| DSCP Name | DSCP Dec | TOS Hex | TOS Dec | CAKE Tin |
|-----------|----------|---------|---------|----------|
| EF        | 46       | 0xb8    | 184     | Voice (3) |
| CS5       | 40       | 0xa0    | 160     | Voice (3) |
| AF41      | 34       | 0x88    | 136     | Video (2) |
| AF31      | 26       | 0x68    | 104     | Video (2) |
| CS0       | 0        | 0x00    | 0       | Best Effort (1) |
| CS1       | 8        | 0x20    | 32      | Bulk (0) |

### iperf3 DSCP Test Commands

```bash
# Test Voice tin (EF = DSCP 46)
iperf3 -c <dallas_ip> --dscp EF -t 10 -P 1

# Test Video tin (AF41 = DSCP 34)
iperf3 -c <dallas_ip> --dscp AF41 -t 10 -P 1

# Test Best Effort tin (CS0 = default, no marking needed)
iperf3 -c <dallas_ip> -t 10 -P 1

# Test Bulk tin (CS1 = DSCP 8)
iperf3 -c <dallas_ip> --dscp CS1 -t 10 -P 1

# Reverse mode for download testing (server sends to client)
iperf3 -c <dallas_ip> --dscp EF -R -t 10 -P 1
```

The `--dscp` flag accepts both symbolic names (EF, CS5, AF41, CS1) and numeric decimal values.

Source: [iperf3 documentation](https://software.es.net/iperf/invoking.html)

### tc Per-Tin Statistics Commands

```bash
# Human-readable per-tin stats
sudo tc -s qdisc show dev ens17

# JSON format (parseable, used by linux_cake.py)
sudo tc -s -j qdisc show dev ens17

# Quick verification: show just tin packet counts
# Look for non-zero sent_packets in tins other than Best Effort
sudo tc -s -j qdisc show dev ens17 | python3 -c "
import json, sys
data = json.load(sys.stdin)
for entry in data:
    if entry.get('kind') == 'cake':
        for i, tin in enumerate(entry.get('tins', [])):
            names = ['Bulk', 'BestEffort', 'Video', 'Voice']
            name = names[i] if i < len(names) else f'Tin{i}'
            print(f'{name}: {tin.get(\"sent_packets\", 0)} pkts, {tin.get(\"sent_bytes\", 0)} bytes')
"
```

Existing code: `linux_cake.py:197-260` already parses per-tin stats with fields: `sent_bytes`, `sent_packets`, `dropped_packets`, `ecn_marked_packets`, `peak_delay_us`, `avg_delay_us`.

### MikroTik Torch DSCP Monitoring

```bash
# Via SSH CLI -- monitor DSCP on egress interface toward cake-shaper
/tool torch interface=ether1 src-address=0.0.0.0/0 dst-address=0.0.0.0/0

# Via REST API (MikroTik RB5009 at 10.10.99.1)
# Torch is a streaming tool -- typically used via WinBox or CLI, not REST
# For DSCP verification, prefer MikroTik packet sniffer or mangle rule counters

# Check mangle rule counters (verify rules exist and have packet counts)
# REST API:
curl -k -u admin:$ROUTER_PASSWORD \
  "https://10.10.99.1/rest/ip/firewall/mangle?comment=dscp"

# CLI equivalent:
/ip firewall mangle print stats where comment~"dscp"
```

### Verify CAKE Initialization State

```bash
# Confirm CAKE is running with diffserv4
sudo tc qdisc show dev ens17
# Expected output includes: "cake ... diffserv4 ..."

# Confirm 4 tins exist
sudo tc -s qdisc show dev ens17 | grep -c "Tin"
# Expected: 4

# Check for unexpected qdisc (fq_codel = CAKE not initialized)
sudo tc qdisc show dev ens17 | head -1
# Should show "qdisc cake" not "qdisc fq_codel"
```

## Architecture Patterns

### Audit Methodology (3-Point Capture)

```
Capture Point 1: MikroTik egress (torch or mangle counters)
    |
    v
Capture Point 2: ens17 physical NIC (tcpdump before bridge processing)
    |
    v
Capture Point 3: CAKE tin statistics (tc -s -j qdisc show dev ens17)
```

For each of the 4 DSCP classes (EF, AF41, CS0, CS1):
1. Reset CAKE tin counters (reload qdisc or note baseline counters)
2. Generate ~10s of iperf3 traffic with specific --dscp value
3. Capture at all 3 points simultaneously
4. Record which tins received packets

### Expected Failure Modes

| Failure Mode | CP1 (MikroTik) | CP2 (ens17 tcpdump) | CP3 (CAKE tins) | Root Cause |
|--------------|-----------------|----------------------|------------------|------------|
| No DSCP marking | TOS=0x00 | TOS=0x00 | All in BestEffort | MikroTik mangle rules missing or not matching |
| Bridge strips DSCP | TOS=0xb8 | TOS=0x00 | All in BestEffort | Bridge or NIC offload issue (unlikely) |
| CAKE not classifying | TOS=0xb8 | TOS=0xb8 | All in BestEffort | CAKE not in diffserv4 mode or init issue |
| Working correctly | TOS=0xb8 | TOS=0xb8 | Voice tin has pkts | No fix needed |

### Analysis Document Pattern

Output document follows existing pattern from `.planning/` (e.g., 131-ANALYSIS.md):

```
.planning/phases/133-diffserv-bridge-audit/133-ANALYSIS.md
```

Structure:
- Test conditions (date, interfaces, CAKE config, iperf3 server)
- Per-DSCP-class results table (hop-by-hop)
- Failure point identification
- Fix strategy options with tradeoffs
- Recommended fix for Phase 134

## Potential Fix Strategies (for documentation, NOT implementation)

If DSCP marks are lost, these are the fix categories to document:

| Fix Category | When Applicable | Complexity | Example |
|--------------|-----------------|------------|---------|
| MikroTik mangle rules | No DSCP marks at source | Low | Add `/ip firewall mangle` rules for DSCP marking |
| Bridge nf_call_iptables | Bridge strips marks (unlikely) | Low | `sysctl net.bridge.bridge-nf-call-iptables=1` |
| ethtool NIC offloads | Hardware offload interfering | Low | `ethtool -K ens17 <offload> off` |
| tc filter + ctinfo | Need to restore DSCP from conntrack | Medium | `tc filter add ... action ctinfo dscp` |
| nftables DSCP restore | Need to re-mark after bridge | Medium | nftables rule in bridge family |
| IFB device redirect | Ingress classification impossible on NIC | High | `tc qdisc add ... ingress; tc filter ... mirred` |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| REST transport (MikroTik handles CAKE) | linux-cake transport (VM handles CAKE directly) | v1.21 (2026-03-25) | DSCP path changed: MikroTik queue trees had built-in diffserv; linux-cake on bridge member NIC is new territory |
| MikroTik CAKE with wash/nat/diffserv | linux-cake CAKE excludes wash/nat (transparent bridge) | v1.21 | `cake_params.py` EXCLUDED_PARAMS removes wash/nat -- not needed on transparent bridge |

## Open Questions

1. **Do MikroTik mangle rules currently set DSCP on traffic egressing toward cake-shaper?**
   - What we know: MikroTik has mangle capability, steering uses DSCP (EF/AF31), but we haven't verified mangle rules exist for general QoS DSCP marking
   - What's unclear: Whether any mangle rules target traffic going through ether1 toward the cake-shaper bridge
   - Recommendation: First audit step -- check MikroTik mangle rules via REST API or CLI. This may be the entire root cause.

2. **Does iperf3 --dscp work in reverse mode (-R)?**
   - What we know: `--dscp` sets DSCP on packets sent by the client. In reverse mode, the server sends data.
   - What's unclear: Whether the server applies the client-requested DSCP value to its return packets
   - Recommendation: Test upload path first (client sends, DSCP definitely applied). Then test download with capture at point 2 to verify server behavior.

3. **Are there existing MikroTik mangle rules for DSCP marking, or only for steering?**
   - What we know: Steering daemon uses DSCP marks (EF/AF31) for latency-sensitive detection
   - What's unclear: Whether these marks are set by MikroTik mangle rules or by the originating applications
   - Recommendation: Check `/ip firewall mangle print` on the router to see all current rules

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| tcpdump | Packet capture on VM | Likely (standard Linux) | -- | Install via apt |
| iperf3 | Traffic generation with DSCP | On dev machine | -- | Install if missing |
| iperf3 server | Dallas endpoint | Yes (existing flent infra) | -- | -- |
| tc (iproute2) | CAKE stats | Yes | 6.15.0 | -- |
| MikroTik REST API | Router mangle rule check | Yes | RouterOS 7.x | SSH CLI |
| SSH to cake-shaper | Remote tcpdump execution | Yes (10.10.110.223) | -- | -- |

**Missing dependencies with no fallback:** None expected. All tools are standard Linux utilities.

**Missing dependencies with fallback:**
- tcpdump may need to be installed on cake-shaper VM (`sudo apt install tcpdump`)
- iperf3 may need to be installed on cake-shaper VM for server mode if needed

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Manual network forensics (tcpdump, tc, iperf3) |
| Config file | N/A -- this is an audit phase, not a code phase |
| Quick run command | N/A |
| Full suite command | N/A |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QOS-01 | Operator can verify DSCP mark survival through bridge path | manual | SSH to VM, run tcpdump + tc commands, compare results | N/A -- operator procedure |

### Sampling Rate
- **Per task:** Manual verification via tcpdump + tc stats
- **Phase gate:** Completed 133-ANALYSIS.md document with hop-by-hop results table

### Wave 0 Gaps
None -- this is a manual audit phase producing a documentation artifact, not a code phase requiring test infrastructure.

## Sources

### Primary (HIGH confidence)
- [Linux kernel sch_cake.c](https://github.com/torvalds/linux/blob/master/net/sched/sch_cake.c) - CAKE DSCP extraction reads IP header directly via ipv4_get_dsfield()
- [tc-cake(8) man page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) - diffserv4 tin mapping, wash behavior, classification override
- [Linux kernel bridge docs](https://docs.kernel.org/networking/bridge.html) - Bridge is L2, protocol independent, does not modify L3 headers
- Project code: `src/wanctl/backends/linux_cake.py` - TIN_NAMES ordering, per-tin stats parsing
- Project code: `src/wanctl/cake_params.py` - EXCLUDED_PARAMS (wash/nat excluded on bridge), diffserv4 defaults
- Project docs: `docs/VM_INFRASTRUCTURE.md` - Bridge topology, NIC mapping, CAKE attachment points

### Secondary (MEDIUM confidence)
- [iperf3 documentation](https://software.es.net/iperf/invoking.html) - --dscp flag accepts symbolic names and numeric values
- [MikroTik Torch docs](https://help.mikrotik.com/docs/spaces/ROS/pages/8323150/Torch) - DSCP monitoring capability confirmed
- [OpenWrt CAKE + ctinfo gist](https://gist.github.com/heri16/06c94b40f0d30f11e3a82166eca718f3) - DSCP restoration via conntrack (potential fix strategy if needed)
- [CAKE classification override](https://github.com/heistp/qdisc-custom-classification) - tc filter priority/classid mechanism for custom tin assignment

### Tertiary (LOW confidence)
- [ip_forward_update_priority sysctl](https://www.kernel.org/doc/html/v5.12/networking/ip-sysctl.html) - Updates skb priority from TOS on forward; docs say it applies to IP forwarding not bridge forwarding, but worth verifying on the VM

## Metadata

**Confidence breakdown:**
- CAKE DSCP extraction mechanism: HIGH - verified from kernel source code
- Bridge L2 passthrough of L3 headers: HIGH - fundamental networking principle confirmed by kernel docs
- tcpdump/iperf3 usage: HIGH - standard tools with well-documented behavior
- Root cause hypothesis: MEDIUM - strong evidence points to "no DSCP marks at source" but audit must confirm
- Fix strategies: MEDIUM - documented from community patterns (OpenWrt, bufferbloat.net) but applicability depends on audit results

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain -- kernel CAKE behavior and bridge semantics change rarely)
