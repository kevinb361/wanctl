# Bridge-Before-Router DSCP Classification Gap: Research

**Researched:** 2026-04-04
**Domain:** Linux bridge DSCP classification, CAKE qdisc tin selection override, tc filters, nftables bridge family, connection tracking on bridges
**Confidence:** HIGH (kernel source verified, man pages cross-referenced, existing Phase 133/134 research validated)

## Executive Summary

The "bridge-before-router" problem is fundamental to the cake-shaper topology: for download traffic, ISP delivers packets with DSCP 0 (washed), the bridge+CAKE processes them before MikroTik can classify, and all download traffic lands in CAKE's Best Effort tin. Phase 134 solved this via MikroTik prerouting `change-dscp` rules -- the router marks download packets BEFORE they traverse the bridge. This research investigates six alternative approaches for classifying download traffic ON the bridge itself, independent of MikroTik.

**Key finding:** Three viable approaches exist, ranked by practicality:

1. **nftables bridge `ip dscp set` (RECOMMENDED for on-bridge classification)** -- Directly modify the IP DSCP header in the bridge forward path using nftables bridge family rules. CAKE reads DSCP from the IP header, so modified DSCP is immediately effective. Port/protocol matching is supported via `ether type ip` guard. No kernel modules beyond stock nftables.

2. **nftables bridge `meta mark set` + CAKE `fwmark` option** -- Set `skb->mark` via nftables in bridge forward, then configure CAKE with `fwmark MASK` to read tin selection from the mark. More flexible (decouples classification from DSCP) but requires CAKE re-initialization with fwmark parameter.

3. **tc filter + `skbedit priority` before CAKE** -- Attach tc filters to the CAKE qdisc parent that set `skb->priority` to override CAKE's tin selection. Kernel-verified mechanism (CAKE checks priority major number against handle). Works but tc filter rules are harder to maintain than nftables rules.

**Primary recommendation:** The Phase 134 MikroTik prerouting approach is the CORRECT production solution. It leverages MikroTik's existing 61-rule classification engine, requires zero bridge-side changes, and keeps the bridge transparent. On-bridge classification should only be pursued if: (a) MikroTik rules cannot cover a specific classification need, or (b) endpoint DSCP needs to be overridden on the bridge. For a "pure bridge-side" solution, nftables bridge `ip dscp set` is the cleanest approach.

---

## Problem Analysis

### Topology and Packet Flow

```
DOWNLOAD PATH (the broken direction):
Internet -> ISP Modem -> ens16 (ingress) -> [Linux Bridge] -> ens17 (egress, CAKE here) -> MikroTik

Packet enters ens16 with DSCP 0 (ISP washed)
  -> Bridge forwards to ens17
  -> CAKE on ens17 egress reads DSCP 0 -> Best Effort tin
  -> MikroTik receives packet, COULD classify, but too late

UPLOAD PATH (working correctly):
MikroTik -> ens17 (ingress) -> [Linux Bridge] -> ens16 (egress, CAKE here) -> ISP Modem

MikroTik marks DSCP in postrouting
  -> Packet enters bridge at ens17 with correct DSCP
  -> Bridge forwards to ens16
  -> CAKE on ens16 egress reads DSCP -> correct tin
```

### Why This Matters

CAKE's diffserv4 mode provides 4 tins with different scheduling:
- **Voice** (25% bandwidth threshold): EF, CS5, CS4-CS7 -- lowest latency
- **Video** (50%): AF2x-AF4x, CS2, CS3 -- medium priority
- **Best Effort** (100%): CS0, unmarked -- default
- **Bulk** (6.25%): CS1, LE -- background

Without download classification, a VoIP call and a bulk download compete equally in the same Best Effort tin. CAKE's `triple-isolate` flow fairness helps somewhat (per-flow queuing), but tin-level priority scheduling is lost.

### What Already Works

1. **Endpoint-set DSCP** (VoIP phones marking EF) survives the bridge unchanged and lands in the correct CAKE tin
2. **Upload DSCP** from MikroTik postrouting works perfectly
3. **Phase 134 solution** (MikroTik prerouting change-dscp rules) fixes download by marking packets before they reach the bridge

---

## Approach 1: tc Filters + skbedit priority (Before CAKE)

### How It Works

CAKE supports external tin override via `skb->priority`. From kernel source (`sch_cake.c`):

```c
// cake_select_tin() priority override check:
if (TC_H_MAJ(skb->priority) == sch->handle &&
    TC_H_MIN(skb->priority) > 0 &&
    TC_H_MIN(skb->priority) <= qd->tin_cnt) {
    tin = qd->tin_order[TC_H_MIN(skb->priority) - 1];
}
```

The tin index is **1-based** when set via tc filter (the kernel subtracts 1 internally).

**Diffserv4 tin indices for `skbedit priority`:**
| Tin Index | Tin Name | skbedit priority value (handle 1:) |
|-----------|----------|-------------------------------------|
| 1 | Bulk | `1:1` |
| 2 | Best Effort | `1:2` |
| 3 | Video | `1:3` |
| 4 | Voice | `1:4` |

### Example Configuration

```bash
# CAKE must have an explicit handle
tc qdisc replace dev ens17 handle 1: root cake bandwidth 500000kbit \
  diffserv4 ingress split-gso docsis memlimit 32mb rtt 40ms

# Voice: match DSCP EF (46) -- but for download, DSCP is 0, so this
# only works for endpoint-set DSCP or if we first modify DSCP elsewhere
tc filter add dev ens17 parent 1: protocol ip prio 1 \
  u32 match ip tos 0xb8 0xfc \
  action skbedit priority 1:4

# Match by destination port (e.g., DNS = Voice)
tc filter add dev ens17 parent 1: protocol ip prio 2 \
  u32 match ip dport 53 0xffff \
  action skbedit priority 1:4

# Match by source port range (e.g., HTTPS video streaming = Video)
tc filter add dev ens17 parent 1: protocol ip prio 3 \
  u32 match ip sport 443 0xffff \
  action skbedit priority 1:3
```

### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| **Works on bridge member egress?** | YES -- tc filters attach to egress qdisc on any interface |
| **Fires before CAKE?** | YES -- tc filters are evaluated during enqueue, before CAKE's internal classification |
| **Performance impact** | LOW -- u32 filters are fast; flower filters slightly slower but more readable |
| **Maintains bridge transparency** | YES -- does not modify packet headers, only sets skb metadata |
| **Complexity** | MEDIUM -- tc filter syntax is error-prone; no persistent config without scripting |
| **Interaction with wanctl** | RISK -- wanctl uses `tc qdisc replace` at startup which would DESTROY attached filters. Must add filters AFTER wanctl initializes CAKE. Handle must be stable. |

### Pros
- Kernel-native mechanism, officially documented in tc-cake(8) man page
- Does not modify packet headers (pure metadata)
- Can match on L3/L4 fields (ports, protocols, IP ranges)
- Works on bridge member ports without any netfilter involvement

### Cons
- tc filter rules are fragile -- destroyed on `tc qdisc replace` (which wanctl does at startup)
- tc filter syntax is hard to maintain and debug compared to nftables
- No connection tracking support in basic u32/flower filters (stateless matching only)
- wanctl code would need modification to add filters after CAKE initialization
- No way to replicate MikroTik's connection-mark-based classification (conntrack not accessible from tc u32)

### Verdict: VIABLE but NOT RECOMMENDED

The startup race condition with wanctl's `tc qdisc replace` makes this fragile. Every CAKE re-initialization drops all filters. Would require wanctl code changes to re-apply filters after each `initialize_cake()` call.

---

## Approach 2: nftables Bridge Family -- `ip dscp set`

### How It Works

nftables bridge family can match and modify L3 headers on bridged packets using the forward hook. The bridge forward hook fires BEFORE the packet reaches the egress TC qdisc on the output bridge member port.

```
Bridge packet path:
  ens16 ingress -> bridge prerouting -> bridge forward -> bridge postrouting -> ens17 egress qdisc (CAKE)
```

By setting DSCP in the bridge forward chain, the modified IP header is what CAKE reads when it processes the packet on ens17 egress.

### Example Configuration

```bash
# Create bridge table and forward chain
nft add table bridge qos
nft add chain bridge qos forward '{ type filter hook forward priority 0; policy accept; }'

# Only classify download direction: packets entering from modem (ens16), exiting to router (ens17)
# Guard with "ether type ip" to only match IPv4

# Voice: SIP, RTP, DNS
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  udp dport 5060 ip dscp set ef
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  udp dport { 16384-32767 } ip dscp set ef
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  tcp dport 53 ip dscp set ef
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  udp dport 53 ip dscp set ef

# Video: HTTPS streaming (port 443) -- aggressive, but common
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  tcp sport 443 ip dscp set af41

# Bulk: known bulk ports
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  tcp sport { 6881-6889 } ip dscp set cs1
```

### Connection Tracking Enhancement

With `NF_CONNTRACK_BRIDGE` (kernel 5.3+), nftables bridge family supports conntrack:

```bash
# Trust established connections' initial classification
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  ct state established,related accept

# Only classify new connections
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  ct state new tcp dport 53 ip dscp set ef
```

This enables connection-mark-based classification similar to MikroTik:

```bash
# Mark new connections based on port
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  ct state new tcp dport 443 ct mark set 3

# Restore DSCP from connection mark on all packets of the flow
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  ct mark 4 ip dscp set ef
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  ct mark 3 ip dscp set af41
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  ct mark 1 ip dscp set cs1
```

### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| **Works on bridge forward?** | YES (HIGH confidence) -- bridge family supports forward hook with L3 matching |
| **`ip dscp set` in bridge family?** | LIKELY YES (MEDIUM confidence) -- nftables payload modification works across families; `ether type ip` guard required for L3 access; needs validation on cake-shaper |
| **Fires before CAKE egress?** | YES -- netfilter bridge hooks fire before egress TC qdisc processing |
| **Performance impact** | LOW -- nftables is fast, especially with connection tracking (only first packet classified) |
| **Maintains bridge transparency** | MOSTLY -- modifies DSCP header bytes on download packets (intentional, but changes wire-level content) |
| **Complexity** | LOW-MEDIUM -- nftables syntax is clean and well-documented |
| **Interaction with wanctl** | NONE -- completely independent of wanctl and tc. Survives CAKE re-initialization. |

### Pros
- Survives wanctl restarts (independent of tc qdisc lifecycle)
- Clean nftables syntax, easy to maintain and audit
- Connection tracking support (stateful classification)
- nftables rules persist via `/etc/nftables.conf` or systemd service
- Direction-specific (iif/oif matching limits to download only)
- CAKE reads modified DSCP directly -- no special CAKE configuration needed

### Cons
- Modifies actual IP header (DSCP bytes change on the wire) -- changes what MikroTik sees
- Requires `NF_CONNTRACK_BRIDGE` kernel module for stateful classification
- Cannot replicate MikroTik's full 61-rule classification engine on the bridge
- `ip dscp set` in bridge family needs empirical validation (MEDIUM confidence it works, but kernel support is there)
- Potential interaction with MikroTik's own DSCP Trust/WASH rules if bridge-set DSCP values conflict

### Verdict: BEST ON-BRIDGE APPROACH

If on-bridge classification is needed, this is the cleanest option. Independent of wanctl, clean syntax, survives restarts, and can do stateful classification with conntrack. The main risk is `ip dscp set` in bridge family needs testing on the actual kernel.

---

## Approach 3: nftables Bridge `meta mark set` + CAKE `fwmark`

### How It Works

CAKE has a built-in `fwmark` option (merged in kernel ~5.5, present in 6.17) that reads `skb->mark` to select tins:

```
tc qdisc replace dev ens17 handle 1: root cake bandwidth 500000kbit \
  diffserv4 ingress split-gso docsis memlimit 32mb rtt 40ms \
  fwmark 0x0f
```

With `fwmark 0x0f`, CAKE extracts the lower 4 bits of `skb->mark`, right-shifts by 0 (no trailing zeros in mask), and uses the result as a 1-based tin index.

nftables in bridge forward sets `skb->mark`:

```bash
nft add table bridge qos
nft add chain bridge qos forward '{ type filter hook forward priority 0; policy accept; }'

# Download direction only
# Tin 4 = Voice
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  udp dport 5060 meta mark set 4
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  udp dport 53 meta mark set 4

# Tin 3 = Video
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  tcp sport 443 meta mark set 3

# Tin 1 = Bulk
nft add rule bridge qos forward iif ens16 oif ens17 ether type ip \
  tcp sport { 6881-6889 } meta mark set 1

# Tin 2 = Best Effort is the default (no mark needed)
```

### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| **CAKE fwmark available?** | YES (HIGH confidence) -- in kernel since ~5.5, documented in tc-cake(8), verified in kernel source |
| **`meta mark set` in bridge family?** | YES (HIGH confidence) -- meta mark set is supported in all nftables families |
| **Fires before CAKE?** | YES -- same as Approach 2 |
| **Performance impact** | LOW -- only sets metadata, no packet header modification |
| **Maintains bridge transparency** | YES -- does not modify any packet headers, only kernel-internal metadata |
| **Complexity** | MEDIUM -- requires CAKE re-initialization with fwmark parameter; wanctl `cake_params.py` needs update |
| **Interaction with wanctl** | REQUIRES CODE CHANGE -- `initialize_cake()` must pass fwmark parameter; `cake_params.py` needs fwmark support |

### Pros
- Does NOT modify packet headers (true bridge transparency)
- Survives wanctl restarts (nftables rules persist independently)
- CAKE's fwmark is a first-class feature, not a workaround
- Conntrack mark can be used (`ct mark`) for stateful classification
- Mark can be stored in conntrack (`ct mark set meta mark`) for per-flow persistence

### Cons
- Requires wanctl code changes to support `fwmark` in `cake_params.py` and `initialize_cake()`
- CAKE fwmark overrides ALL DSCP-based classification, including endpoint-set EF from VoIP phones
- Must coordinate fwmark mask to not conflict with other mark users (steering, etc.)
- If mark is not set (0), CAKE falls back to DSCP -- but fwmark mask of 0x0f means any stray mark bits would cause misclassification
- More complex to debug (marks are invisible in tcpdump; must use `nft monitor trace`)

### Verdict: VIABLE but OVER-ENGINEERED for this use case

The fwmark approach has a critical drawback: it overrides DSCP-based classification for ALL packets, including those with legitimate endpoint-set DSCP (VoIP phones). The `ip dscp set` approach (Approach 2) is better because it augments DSCP rather than replacing the classification mechanism.

---

## Approach 4: IFB (Intermediate Functional Block) Device

### How It Works

IFB redirects ingress traffic through a virtual device where it appears as egress, allowing full tc qdisc/filter/action chains:

```bash
# Create IFB device
ip link add name ifb-dl type ifb
ip link set ifb-dl up

# Add ingress qdisc to ens16 (modem-side, where download enters bridge)
tc qdisc add dev ens16 handle ffff: ingress

# Redirect ingress to IFB with optional ctinfo DSCP restore
tc filter add dev ens16 parent ffff: protocol all prio 10 \
  u32 match u32 0 0 flowid 1:1 \
  action ctinfo dscp 0xfc000000 0x01000000 \
  action mirred egress redirect dev ifb-dl

# Attach CAKE to IFB
tc qdisc replace dev ifb-dl root cake bandwidth 500000kbit \
  diffserv4 split-gso docsis memlimit 32mb rtt 40ms
```

### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| **Works with bridge?** | PROBLEMATIC -- redirecting bridge member ingress through IFB may break bridge forwarding |
| **Performance** | ADDS LATENCY -- extra packet processing hop through IFB device |
| **Complexity** | HIGH -- requires careful coordination of ingress qdisc, IFB, mirred, and CAKE |
| **Bridge transparency** | BREAKS -- IFB redirect steals packets from normal bridge forwarding path |
| **Interaction with wanctl** | MAJOR REWORK -- current architecture attaches CAKE to bridge member NIC egress, not IFB |

### Verdict: NOT RECOMMENDED

IFB is designed for the router-on-a-stick topology (sqm-scripts pattern) where the router is the endpoint, not a transparent bridge. Redirecting bridge member ingress to IFB would break the bridge forwarding path or require double-processing. The current CAKE-on-bridge-member-egress architecture is correct for the topology and should not be changed.

---

## Approach 5: tc-ct (Connection Tracking in tc) + tc-ctinfo

### How It Works

`act_ctinfo` is a tc action that restores DSCP from conntrack marks. Combined with connection tracking, it can restore DSCP that was previously stored in connmark on egress:

1. **Egress (upload):** MikroTik marks DSCP -> nftables/iptables stores DSCP in connmark
2. **Ingress (download):** `act_ctinfo` reads connmark, restores DSCP to packet header
3. **CAKE reads restored DSCP** for tin selection

### Why It Doesn't Apply Here

The ctinfo pattern is designed for NAT gateways where:
- The gateway sees BOTH directions of traffic
- Egress DSCP can be stored in connmark
- Ingress DSCP is restored from connmark

In the cake-shaper bridge topology:
- The bridge sees both directions, BUT
- Download packets arrive with DSCP 0 (ISP washed) -- there is no "previously stored" DSCP to restore
- The "source of truth" for DSCP classification is MikroTik's connection marks, not conntrack on the bridge
- Connection tracking on the bridge would need to independently classify traffic, which is the same problem we're trying to solve

### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| **Kernel support** | YES -- act_ctinfo is in mainline kernel; available on kernel 6.17 |
| **Applicable to this topology?** | NO -- requires a prior DSCP marking that can be stored in connmark. ISP sends DSCP 0. |
| **Could it work with bridge-side conntrack?** | THEORETICALLY -- if we first classify on the bridge (via nftables), store mark in conntrack, then restore via ctinfo. But this is just a more complex version of Approach 2. |

### Verdict: NOT APPLICABLE

The ctinfo DSCP-restore pattern solves a different problem (ISP washes YOUR marks; restore from connmark). Our problem is that the ISP never had marks to wash -- we need to CREATE classification, not restore it.

---

## Approach 6: eBPF/XDP Classification

### How It Works

A BPF program attached via tc (BPF_PROG_TYPE_SCHED_CLS) can inspect packet headers and set `skb->priority` or `tc_classid` to direct packets to specific CAKE tins:

```c
// Simplified eBPF tc classifier
SEC("classifier")
int cake_classify(struct __sk_buff *skb) {
    void *data = (void *)(long)skb->data;
    void *data_end = (void *)(long)skb->data_end;
    struct ethhdr *eth = data;
    if ((void*)(eth + 1) > data_end) return TC_ACT_OK;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return TC_ACT_OK;

    struct iphdr *iph = (void*)(eth + 1);
    if ((void*)(iph + 1) > data_end) return TC_ACT_OK;

    // Check destination port for UDP
    if (iph->protocol == IPPROTO_UDP) {
        struct udphdr *udp = (void*)iph + (iph->ihl * 4);
        if ((void*)(udp + 1) > data_end) return TC_ACT_OK;
        __u16 dport = bpf_ntohs(udp->dest);
        if (dport == 53 || dport == 5060) {
            skb->priority = 0x00010004; // handle 1:, tin 4 (Voice)
            return TC_ACT_OK;
        }
    }
    return TC_ACT_OK;
}
```

### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| **Works on bridge member egress?** | YES -- tc BPF classifiers work on any interface with a qdisc |
| **Performance** | EXCELLENT -- eBPF is JIT-compiled, sub-microsecond per packet |
| **Complexity** | HIGH -- requires C/BPF toolchain, compilation, loading, debugging |
| **Maintainability** | LOW -- BPF programs need recompilation for rule changes; kernel version sensitivity |
| **Bridge transparency** | YES -- can set metadata without modifying headers |
| **Same tc lifecycle issue as Approach 1?** | YES -- destroyed on `tc qdisc replace` |

### Verdict: OVER-ENGINEERED

eBPF is the most powerful but least maintainable option. For a home network QoS system, the complexity of maintaining BPF programs, toolchains, and debugging infrastructure vastly outweighs the marginal performance benefit over nftables. LibreQoS uses eBPF because they classify 10,000+ subscribers; we have one bridge with four tins.

---

## Approach 7: Two-Pass Architecture (Topology Change)

### Concept

Route download traffic through MikroTik first for classification, then redirect back through the bridge for CAKE shaping:

```
ISP -> Modem -> MikroTik (classify, set DSCP) -> cake-shaper bridge (CAKE shapes) -> MikroTik (final delivery)
```

### Why This Is Bad

- Requires additional NICs and VLANs
- Doubles the traffic through MikroTik (CPU impact)
- Adds latency from extra routing hop
- The Phase 134 prerouting solution achieves the same result without topology changes

### Verdict: REJECTED -- Topology changes are never justified when software solutions exist.

---

## Comparative Analysis

| Approach | Feasibility | Complexity | Maintains Transparency | Survives wanctl Restart | Requires Code Changes | Conntrack Support |
|----------|-------------|------------|----------------------|-------------------------|----------------------|-------------------|
| **Phase 134 (MikroTik prerouting)** | HIGH | LOW | YES | YES | NO | YES (MikroTik connmark) |
| **1. tc filter + skbedit** | HIGH | MEDIUM | YES (metadata only) | NO (destroyed on replace) | YES (filter mgmt) | NO |
| **2. nftables bridge `ip dscp set`** | HIGH | LOW-MEDIUM | MOSTLY (modifies DSCP) | YES | NO | YES (NF_CONNTRACK_BRIDGE) |
| **3. nftables bridge + CAKE fwmark** | HIGH | MEDIUM | YES (metadata only) | YES | YES (cake_params) | YES |
| **4. IFB device** | LOW | HIGH | NO (breaks bridge) | N/A | YES (major rework) | Depends |
| **5. tc-ctinfo** | LOW | MEDIUM | YES | NO | YES | YES (but inapplicable) |
| **6. eBPF** | HIGH | VERY HIGH | YES | NO (destroyed on replace) | YES (BPF toolchain) | Custom |
| **7. Two-pass topology** | LOW | VERY HIGH | N/A (topology change) | N/A | YES (major rework) | N/A |

---

## Recommendation

### Production (Current)

**Use Phase 134's MikroTik prerouting approach.** It is already designed, documented, and leverages MikroTik's 61-rule classification engine. Zero bridge-side changes. Zero wanctl code changes. Maximum stability.

### If Bridge-Side Classification Is Ever Needed

**Use Approach 2: nftables bridge `ip dscp set`.** Reasons:
1. Independent of wanctl lifecycle (survives restarts)
2. Clean, readable syntax
3. Connection tracking available via `NF_CONNTRACK_BRIDGE`
4. CAKE reads modified DSCP directly -- no CAKE config changes needed
5. Direction-specific with `iif`/`oif` guards
6. Persists via `/etc/nftables.conf` or systemd unit

**Validation step before implementing:** Test on cake-shaper that `ip dscp set` works in bridge forward:
```bash
nft add table bridge test
nft add chain bridge test forward '{ type filter hook forward priority 0; policy accept; }'
nft add rule bridge test forward iif ens16 oif ens17 ether type ip udp dport 9999 ip dscp set ef
# Send UDP to port 9999, verify CAKE Voice tin counter increments
nft delete table bridge test
```

### Is This Worth Pursuing?

**For download classification: No -- Phase 134 solves it better.** MikroTik has the classification intelligence (61 mangle rules, connection marks, address lists). Replicating even a subset on the bridge is inferior.

**For overriding endpoint DSCP: Potentially.** If untrusted endpoints set inappropriate DSCP values (gaming consoles marking EF, etc.), bridge-side nftables could override before CAKE. But CAKE's `wash` keyword handles this for all traffic, and the current topology excludes `wash` because MikroTik's marks ARE trusted.

**For future deployment without MikroTik:** Yes. If the bridge ever operates without a downstream classifier (e.g., standalone CAKE appliance), bridge-side nftables classification becomes essential. The nftables approach documented here would be the foundation.

---

## CAKE Tin Override Mechanisms (Reference)

### Method 1: DSCP (Default)
CAKE reads `ipv4_get_dsfield()` from the IP header. This is the default classification mechanism when no override is active.

### Method 2: skb->priority (tc filter)
Set via `tc filter ... action skbedit priority HANDLE:TIN_INDEX`. Major number must match CAKE's handle. Tin index is 1-based. Checked BEFORE DSCP.

### Method 3: fwmark (CAKE option)
Set via `tc qdisc ... cake ... fwmark MASK`. CAKE reads `(skb->mark & mask) >> shift` as tin index. Checked BEFORE skb->priority AND DSCP. Requires CAKE re-initialization with `fwmark` parameter.

### Classification Priority Order (from kernel source)
```
1. fwmark (if CAKE_FLAG_FWMARK set and mark in range)
2. skb->priority (if major matches handle and minor in range)
3. DSCP from IP header (fallback)
```

Source: [sch_cake.c cake_select_tin()](https://github.com/torvalds/linux/blob/master/net/sched/sch_cake.c)

---

## Key Risks and Tradeoffs

### If Using nftables Bridge Classification

| Risk | Impact | Mitigation |
|------|--------|------------|
| `ip dscp set` not supported in bridge family | Approach 2 fails | Test first; fall back to Approach 3 (meta mark + fwmark) |
| Classification rules diverge from MikroTik | Inconsistent QoS between directions | Maintain a single source of truth for classification policy |
| Bridge nf_conntrack overhead | Slight CPU increase on bridge | Minimal for home-scale traffic; NF_CONNTRACK_BRIDGE is lightweight |
| DSCP modification visible to MikroTik | MikroTik Trust/WASH rules may interact | MikroTik Trust rules in prerouting would preserve bridge-set DSCP; WASH only applies to WAN-inbound |

### If Using CAKE fwmark

| Risk | Impact | Mitigation |
|------|--------|------------|
| fwmark overrides endpoint DSCP | VoIP phones' EF marks ignored | Set mark=0 for trusted DSCP traffic so fwmark falls through to DSCP |
| Mark conflict with steering | Steering may use skb->mark | Use non-overlapping mask bits (fwmark 0xf0 for QoS, 0x0f for steering) |
| wanctl code changes required | cake_params.py, linux_cake.py need fwmark support | Moderate effort; well-scoped changes |

---

## Required Kernel Features

| Feature | Kernel Version | Module | Available on 6.17? |
|---------|---------------|--------|---------------------|
| CAKE qdisc | 4.19+ | `sch_cake` | YES |
| CAKE fwmark | ~5.5+ | `sch_cake` | YES |
| tc filter skbedit | 2.6.x+ | `act_skbedit` | YES |
| nftables bridge family | 3.18+ | `nf_tables_bridge` | YES |
| NF_CONNTRACK_BRIDGE | 5.3+ | `nf_conntrack_bridge` | YES |
| act_ctinfo | 5.3+ | `act_ctinfo` | YES (but not applicable) |
| tc BPF classifier | 4.1+ | `cls_bpf` | YES |

All required kernel features are available on kernel 6.17.4 (Debian 13 / Trixie).

---

## Sources

### Primary (HIGH confidence)
- [Linux kernel sch_cake.c](https://github.com/torvalds/linux/blob/master/net/sched/sch_cake.c) -- tin selection logic, fwmark support, priority override mechanism
- [tc-cake(8) man page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- fwmark syntax, diffserv4 tin mapping, classification override documentation
- [tc-cake(8) Arch manual](https://man.archlinux.org/man/tc-cake.8.en) -- fwmark bitmask documentation
- [CAKE custom classification (heistp)](https://github.com/heistp/qdisc-custom-classification) -- practical examples of skbedit priority and eBPF with CAKE
- [tc-ctinfo(8) man page](https://man7.org/linux/man-pages/man8/tc-ctinfo.8.html) -- DSCP restore from connmark mechanism
- Project Phase 133/134 research -- existing analysis of the bridge DSCP gap and MikroTik prerouting fix

### Secondary (MEDIUM confidence)
- [nftables bridge filtering wiki](https://wiki.nftables.org/wiki-nftables/index.php/Bridge_filtering) -- bridge family hooks, conntrack support since kernel 5.3
- [nftables classification to tc](https://wiki.nftables.org/wiki-nftables/index.php/Classification_to_tc_structure_example) -- meta priority set mechanism
- [OpenWrt CAKE + ctinfo gist](https://gist.github.com/heri16/06c94b40f0d30f11e3a82166eca718f3) -- DSCP restore pattern with CONNMARK
- [dscpclassify (jeverley)](https://github.com/jeverley/dscpclassify) -- nftables-based DSCP classification service for OpenWrt
- [QoSmate (hudra0)](https://github.com/hudra0/qosmate) -- nftables + CAKE + ctinfo integration
- [CAKE fwmark patch discussion](https://www.mail-archive.com/netdev@vger.kernel.org/msg288985.html) -- original fwmark implementation

### Tertiary (LOW confidence)
- nftables bridge family `ip dscp set` -- documented in man pages as supported payload modification, but no specific bridge family test cases found. Needs empirical validation on cake-shaper.
- nftables bridge family `meta mark set` -- supported in all families per documentation, but bridge-specific examples are sparse.

---

## Metadata

**Confidence breakdown:**
- Phase 134 MikroTik approach: HIGH -- already designed, validated by Phase 133 audit
- tc filter + skbedit: HIGH -- kernel source verified, documented in man page
- nftables bridge `ip dscp set`: MEDIUM -- mechanism is sound but bridge family payload modification needs empirical test
- CAKE fwmark: HIGH -- verified in kernel source and current man pages
- IFB approach: HIGH (that it won't work) -- architectural mismatch with bridge topology
- eBPF approach: HIGH (that it works, LOW that it's worth the complexity)

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable domain -- kernel CAKE and nftables bridge support change rarely)
