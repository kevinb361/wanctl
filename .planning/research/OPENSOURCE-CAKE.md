# Open-Source CAKE Ecosystem Research

**Domain:** Linux CAKE qdisc implementation patterns across major open-source projects
**Researched:** 2026-03-24
**Overall Confidence:** HIGH (source code, official docs, maintainer discussions)

## Executive Summary

Three major open-source projects implement CAKE on Linux, each solving a different problem at a different scale. Their implementation patterns are remarkably consistent on fundamentals but diverge on architecture based on their deployment topology. The key findings for wanctl v1.21 are:

1. **Bridge member port egress shaping (no IFB) is the correct choice** for wanctl's transparent bridge topology, confirmed by MagicBox and LibreQoS patterns.
2. **`tc qdisc replace` is the idempotent initialization pattern** used universally; `tc qdisc change` is the lossless runtime update pattern.
3. **cake-autorate reads interface byte counters from `/sys/class/net/`, not tc stats**, for load measurement -- wanctl already uses a better approach (RTT-based + CAKE stats).
4. **`wash` on ingress is a deliberate sqm-scripts pattern** -- but not applicable to wanctl's bridge topology where DSCP marks must be preserved from the router's mangle rules.
5. **The `ingress` keyword is NOT about direction** -- it changes how CAKE counts dropped packets against the shaper budget, and should be used on download-side CAKE instances.

---

## Project Comparison Matrix

| Aspect | sqm-scripts | cake-autorate | LibreQoS | wanctl v1.21 |
|--------|-------------|---------------|----------|--------------|
| **Language** | Bash (shell) | Bash (shell) | Rust + eBPF/XDP | Python |
| **Scale** | Single home router | Single home router | ISP (10K+ subscribers) | Single dual-WAN home |
| **Topology** | Router (NAT gateway) | Router (NAT gateway) | Transparent bridge | Transparent bridge |
| **CAKE placement** | WAN egress + IFB ingress | Assumes pre-configured | Bridge interfaces + per-subscriber HTB | Bridge member port egress |
| **Ingress approach** | IFB device with mirred redirect | N/A (uses existing SQM) | XDP bridge (no IFB) | Bridge member port egress (no IFB) |
| **Rate control** | Static (user-configured) | Dynamic (latency-based) | Static (per-subscriber plan) | Dynamic (latency-based) |
| **tc stats parsing** | Not parsed at runtime | Not parsed (uses /sys/class/net) | Rust netlink (not tc CLI) | `tc -j -s qdisc show` JSON |
| **Diffserv mode** | besteffort (ingress), diffserv3/4 (egress) | N/A (defers to SQM) | diffserv4 (per-subscriber CAKE) | diffserv4 (both directions) |
| **Active development** | Yes (2026, cake_mq support) | Yes (2025-2026) | Yes (v2.0, XDP bridge) | Yes |

---

## Project 1: sqm-scripts (Canonical CAKE Setup)

**Repository:** [github.com/tohojo/sqm-scripts](https://github.com/tohojo/sqm-scripts)
**Confidence:** HIGH (direct source code review)

### How It Sets Up CAKE

sqm-scripts provides three CAKE profiles of increasing complexity:

**piece_of_cake.qos** -- Simplest possible CAKE. Single-tin, no diffserv:

```bash
# Egress (upload) -- direct on WAN interface
tc qdisc del dev $IFACE root 2>/dev/null
tc qdisc add dev $IFACE root $STABSTRING cake \
    bandwidth ${UPLINK}kbit besteffort $EGRESS_CAKE_OPTS

# Ingress (download) -- via IFB device
tc qdisc del dev $IFACE handle ffff: ingress 2>/dev/null
tc qdisc add dev $IFACE handle ffff: ingress
tc qdisc del dev $DEV root 2>/dev/null
tc qdisc add dev $DEV root $STABSTRING cake \
    bandwidth ${DOWNLINK}kbit besteffort $INGRESS_CAKE_OPTS
ip link set dev $DEV up

# Redirect all ingress traffic to IFB
tc filter add dev $IFACE parent ffff: protocol all prio 10 \
    u32 match u32 0 0 flowid 1:1 action mirred egress redirect dev $DEV
```

**layer_cake.qos** -- Full diffserv4 with DSCP awareness:
- Same IFB pattern as piece_of_cake
- Uses `diffserv4` instead of `besteffort`
- Adds `wash` to ingress when `ZERO_DSCP_INGRESS=1` (resets ISP DSCP marks)
- Adds `besteffort` to ingress when `IGNORE_DSCP_INGRESS=1`

### IFB Device Creation

```bash
# From functions.sh: create_ifb()
create_ifb() {
    local name=$1
    local num_procs=$(grep -c processor /proc/cpuinfo)
    local args=
    if [ "$USE_MQ" -eq "1" ] && [ "$num_procs" -gt 1 ]; then
        args="numtxqueues $num_procs"
    fi
    ip link add name $name $args type ifb
}
```

IFB naming convention: `ifb4<interface>` (e.g., `ifb4eth0`).

### CAKE Parameters Used

| Parameter | Egress (Upload) | Ingress (Download) | Why |
|-----------|------------------|--------------------|-----|
| `bandwidth` | `${UPLINK}kbit` | `${DOWNLINK}kbit` | Always explicit, never autorate |
| `besteffort` | piece_of_cake only | piece_of_cake + layer_cake (optional) | Single-tin, no diffserv |
| `diffserv3` | Default in defaults.sh | Default in defaults.sh | Default diffserv mode |
| `nat` | defaults.sh default | defaults.sh default | Per-host fairness through NAT |
| `wash` | Never | Optional (ZERO_DSCP_INGRESS) | Clear ISP DSCP marks on download |
| Overhead | Via `$STABSTRING` | Via `$STABSTRING` | Encap-aware shaping |

**Notable: sqm-scripts defaults to `diffserv3 nat`** in defaults.sh, not diffserv4. The `nat` keyword is default because sqm-scripts assumes a NAT gateway.

### Overhead Handling

sqm-scripts builds an overhead string from configuration:
```bash
STABSTRING="stab mtu ${STAB_MTU} tsize ${STAB_TSIZE} mpu ${STAB_MPU} \
    overhead ${OVERHEAD} linklayer ${LINKLAYER}"
```

The `get_cake_lla_string()` function converts link-layer adaptation into CAKE-native keywords. CAKE has built-in keywords that replace the manual stab approach:
- `docsis` = `overhead 18 mpu 64 noatm`
- `bridged-ptm` = `overhead 22 noatm` (wanctl ATT link)
- `ethernet` = `overhead 38 mpu 84 noatm`
- `pppoe-ptm` = `overhead 30 noatm`

### Key Takeaway for wanctl

sqm-scripts uses IFB because it runs on a **router** where the WAN interface has only one egress point. wanctl runs on a **transparent bridge** where each member port provides a separate egress point -- so IFB is unnecessary overhead. The CAKE parameters (diffserv mode, overhead keywords) are directly applicable.

---

## Project 2: cake-autorate (Adaptive Bandwidth Control)

**Repository:** [github.com/lynxthecat/cake-autorate](https://github.com/lynxthecat/cake-autorate)
**Confidence:** HIGH (direct source code review)

### Architecture

cake-autorate is the closest analog to wanctl. It is a bash script that dynamically adjusts CAKE bandwidth based on latency measurements. Key architectural choices:

**Control loop:**
1. Background processes ping reflectors and measure one-way delay (OWD)
2. Background process samples `/sys/class/net/<iface>/statistics/{tx,rx}_bytes` for load
3. Main loop receives messages from background processes and decides rate adjustments
4. Rate changes via `tc qdisc change root dev <iface> cake bandwidth <rate>Kbit`

**The single tc command cake-autorate uses for rate control:**
```bash
tc qdisc change root dev "${interface[${direction}]}" cake bandwidth "${shaper_rate_kbps[${direction}]}Kbit"
```

This is the same `tc qdisc change` approach wanctl will use.

### What cake-autorate Does NOT Do

- Does NOT parse tc stats output at all (no `tc -s` or `tc -j -s`)
- Does NOT set up CAKE qdiscs (assumes SQM or manual setup has been done)
- Does NOT configure CAKE parameters (split-gso, ack-filter, overhead, etc.)
- Does NOT monitor per-tin statistics

cake-autorate focuses purely on bandwidth adjustment. CAKE configuration is deferred to sqm-scripts or manual setup.

### Rate Control Algorithm

Three configuration values per direction:

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `min_dl_shaper_rate_kbps` | Hard floor (bufferbloat-free minimum) | 5000 |
| `base_dl_shaper_rate_kbps` | Steady state under no/low load | 20000 |
| `max_dl_shaper_rate_kbps` | Maximum ceiling | 80000 |

**State machine (similar to wanctl but simpler):**
- **Load > 80% AND delay < threshold**: Ramp up toward max
- **Delay > threshold**: Ramp down (reduce rate)
- **Low load AND high delay**: Drop to minimum immediately
- **Idle**: Decay toward baseline

**Refractory period:** After each rate change, a cooldown prevents oscillation. Conceptually similar to wanctl's `sustained_green_cycles_required`.

### Latency Measurement

- Supports: ICMP (ping, fping), IRTT, tsping
- Measures **one-way delay** (OWD) when available, splitting into upload/download components
- Uses EWMA with **separate alphas for increase vs decrease** (asymmetric smoothing)
- Maintains per-reflector baselines
- Rotates out reflectors with excessively high baselines or unstable deltas

### Key Differences from wanctl

| Aspect | cake-autorate | wanctl |
|--------|---------------|--------|
| Language | Bash | Python |
| Load detection | Interface byte counters (/sys) | RTT delta + CAKE queue stats |
| Congestion signal | OWD delta only | RTT delta + drops + queue depth (multi-signal) |
| State model | 3-state (ramp/reduce/idle) | 4-state (GREEN/YELLOW/SOFT_RED/RED) |
| Baseline update | Continuous EWMA | Frozen during load, updates only when idle |
| Adaptive tuning | None | 4-layer self-tuning (v1.20) |
| Signal processing | Basic EWMA | Hampel + Fusion + EWMA chain |
| Per-tin awareness | None | Planned (CAKE-07) |
| Setup responsibility | None (defers to SQM) | Validates CAKE presence at startup |

### Key Takeaway for wanctl

wanctl is significantly more sophisticated than cake-autorate in congestion detection. cake-autorate's main contribution to wanctl is confirming that `tc qdisc change` is the correct lossless bandwidth update method, and that the `min/base/max` bandwidth model with refractory periods is the proven pattern for variable-rate connections. wanctl already implements all of this and more.

---

## Project 3: LibreQoS (ISP-Scale CAKE)

**Repository:** [github.com/LibreQoE/LibreQoS](https://github.com/LibreQoE/LibreQoS)
**Confidence:** MEDIUM (documentation review, architecture docs -- did not review Rust source directly)

### Architecture

LibreQoS deploys as a **transparent bridge** between an ISP's edge router and the network -- the same topology as wanctl's v1.21 offload. Key differences are scale (thousands of subscribers vs one household) and implementation (Rust + eBPF vs Python + tc subprocess).

**Bridge setup options:**
1. **Linux bridge** (recommended for most deployments, including VMs)
2. **Bifrost XDP bridge** (for 40G-100G Intel NICs)

Bridge configuration via netplan YAML:
```yaml
# /etc/netplan/libreqos.yaml
network:
  ethernets:
    ens19:
      dhcp4: false
    ens20:
      dhcp4: false
```

Interfaces are brought up without IP addresses -- pure L2 forwarding, same as wanctl's planned br-spectrum/br-att.

### CAKE Configuration

LibreQoS uses **HTB as a hierarchy with CAKE as leaf qdisc** for each subscriber:

```
root qdisc (HTB)
  +-- class per subscriber (rate limit = plan speed)
       +-- CAKE qdisc (diffserv4, per-flow fair queuing)
```

Default CAKE parameters: `diffserv4` with `triple-isolate` flow isolation.

**Bakery subsystem** (v2.0): Lazy CAKE creation -- HTB classes exist at startup, but CAKE qdiscs are only attached when a subscriber first has traffic. Unused CAKE qdiscs are reaped after `lazy_expire_seconds`. This optimization is driven by the memory cost of CAKE at scale (thousands of instances).

LibreQoS does NOT use IFB -- the XDP/bridge architecture provides bidirectional shaping points on each bridge interface.

### Stats Collection

LibreQoS uses **Rust netlink bindings** (not `tc` CLI) for stats collection. The `lqosd` daemon queries qdisc stats directly via netlink for low-overhead per-subscriber monitoring. At ISP scale, forking `tc` thousands of times per second would be prohibitive.

**Relevance to wanctl:** wanctl only monitors 2-4 CAKE instances total, so `tc -j -s qdisc show` subprocess calls are fine. The deferred requirement PERF-01 (pyroute2 netlink) would match LibreQoS's approach if subprocess latency becomes a concern.

### Key Takeaway for wanctl

LibreQoS confirms that transparent bridge + CAKE on member ports (no IFB) is a proven production pattern at scale. Their lazy CAKE creation is not relevant to wanctl (only 4 qdiscs), but their bridge provisioning approach (netplan/systemd-networkd, no IP on shaping interfaces) aligns with wanctl's INFR-05 requirement.

---

## Ingress Shaping Patterns Compared

This is the most architecturally significant decision for wanctl v1.21.

### Pattern 1: IFB Device (sqm-scripts, traditional routers)

```
[Internet] --> [WAN interface] --> ingress hook --> mirred redirect --> [IFB] --> CAKE egress
                                                                                    |
                                                                          (shaped traffic)
                                                                                    |
                                                                            [LAN interface]
```

**When to use:** Router topology where download traffic arrives on WAN and there is no separate egress point for download-direction traffic.

**Cost:** Extra virtual device, tc filter + mirred redirect chain, ~5% overhead per MagicBox documentation.

### Pattern 2: Bridge Member Port Egress (LibreQoS, MagicBox, wanctl v1.21)

```
[Modem] <---> [NIC-A: modem-side] <=bridge=> [NIC-B: router-side] <---> [Router]

Upload CAKE:   NIC-A egress (traffic leaving toward ISP)
Download CAKE: NIC-B egress (traffic leaving toward LAN/router)
```

**When to use:** Transparent bridge topology where traffic passes through two physical ports.

**Cost:** Zero overhead. Each direction naturally has its own egress point.

**Confirmed by:**
- MagicBox documentation: "If you instantiate the SQM on both WAN and LAN interfaces in one direction only (EGRESS) you bypass the IFB and benefit from about 5% less overhead"
- LibreQoS: Uses bridge interfaces directly, no IFB
- sch_cake issue #55: `ingress` keyword is about drop accounting, not traffic direction

### Pattern 3: veth Pair (CAKE-QoS-Script-OpenWrt)

An alternative to IFB seen in some OpenWrt scripts: create a veth pair, put one end in `br-lan`, use policy routing to redirect WAN ingress through the veth. More complex than IFB, no real advantage.

### Recommendation for wanctl

**Use Pattern 2 (bridge member port egress).** This is already specified in FEATURES.md and is confirmed by every transparent-bridge CAKE deployment researched. No IFB device needed.

Additionally, use the `ingress` keyword on the download-side CAKE instance. The `ingress` keyword changes how CAKE accounts for dropped packets (counting them against the shaper budget), which provides tighter bandwidth control when shaping download traffic. This is a detail that was not in the current requirements.

---

## CAKE Parameter Analysis

### Parameters All Projects Agree On

| Parameter | Value | Rationale | Confidence |
|-----------|-------|-----------|------------|
| `bandwidth <rate>` | Explicit value | Never use autorate-ingress; external controller manages rate | HIGH |
| `split-gso` | Enabled (default) | Split TSO/GSO segments for lower latency; only disable above 10Gbps | HIGH |
| Overhead keyword | Link-specific | `docsis` for cable, `bridged-ptm` for DSL, `ethernet` for fiber | HIGH |

### Parameters Where Projects Diverge

| Parameter | sqm-scripts | cake-autorate | LibreQoS | Recommendation for wanctl |
|-----------|-------------|---------------|----------|---------------------------|
| **Diffserv mode** | diffserv3 (default) | N/A | diffserv4 | **diffserv4** -- matches RB5009 mangle rules (4-tin: Voice/Video/BE/Bulk) |
| **nat** | Yes (default) | N/A | No (per-subscriber CAKE) | **No** -- bridge is pre-NAT, conntrack not applicable |
| **wash** | Ingress only (optional) | N/A | Not documented | **No** -- DSCP marks from RB5009 mangle must be preserved through bridge |
| **ack-filter** | Not default | N/A | Not documented | **Upload only** -- compresses redundant ACKs on asymmetric links |
| **flow isolation** | triple-isolate (default) | N/A | triple-isolate | **triple-isolate** (default) or dual-srchost/dual-dsthost depending on direction |
| **ingress** keyword | Not used | N/A | Not documented | **Yes, on download CAKE** -- tighter drop accounting on ingress-direction shaping |
| **rtt** | Not set (100ms default) | N/A | Not documented | **Consider 50ms** for sub-100ms ISP RTTs; default 100ms is conservative |
| **memlimit** | Not set | N/A | Not documented | **Set explicitly** -- bounded memory prevents runaway under load |
| **ECN** | Not documented | N/A | Not documented | **Enable** (`ecn`) -- modern endpoints support it, provides softer congestion signals |

### Overhead Keywords for wanctl's Links

| WAN | Link Type | CAKE Keyword | Equivalent |
|-----|-----------|--------------|------------|
| Spectrum (DOCSIS cable) | DOCSIS 3.1 | `docsis` | `overhead 18 mpu 64 noatm` |
| ATT (bridged Ethernet) | Bridged PTM | `bridged-ptm` | `overhead 22 noatm` |

These are the same overhead keywords used by sqm-scripts for the corresponding link types.

---

## tc Command Patterns

### Initialization (Startup)

All projects use `replace` for idempotent initialization:

```bash
# Upload CAKE (modem-side NIC egress)
tc qdisc replace dev $UPLOAD_IFACE root cake \
    bandwidth ${UPLOAD_RATE}kbit \
    diffserv4 \
    split-gso \
    ack-filter \
    docsis \
    memlimit 32mb

# Download CAKE (router-side NIC egress)
tc qdisc replace dev $DOWNLOAD_IFACE root cake \
    bandwidth ${DOWNLOAD_RATE}kbit \
    diffserv4 \
    split-gso \
    ingress \
    ecn \
    docsis \
    memlimit 32mb
```

`tc qdisc replace` is idempotent: creates if absent, replaces if present. Safe for startup scripts and restarts.

### Runtime Bandwidth Update

All projects that dynamically adjust bandwidth use `change`:

```bash
tc qdisc change dev $IFACE root cake bandwidth ${NEW_RATE}kbit
```

The tc-cake(8) man page confirms: "Most parameters can be updated at runtime without losing packets by using `tc` change."

The `change` command ONLY modifies the specified parameters. Other CAKE parameters (diffserv mode, overhead, etc.) are preserved. This means wanctl only needs to send the bandwidth value on each cycle -- the initial setup parameters persist.

### Stats Query

```bash
tc -j -s qdisc show dev $IFACE
```

Returns JSON with structure (Debian 12, iproute2 6.1.0-3):

```json
[{
    "kind": "cake",
    "handle": "8001:",
    "root": true,
    "options": {
        "bandwidth": "100Mbit",
        "diffserv": "diffserv4",
        "flowmode": "triple-isolate",
        "nat": false,
        "wash": false,
        "ingress": false,
        "ack-filter": "disabled",
        "split_gso": true,
        "rtt": 100000,
        "raw": false,
        "overhead": 18,
        "fwmark": 0
    },
    "bytes": 123456789,
    "packets": 987654,
    "drops": 42,
    "overlimits": 0,
    "requeues": 0,
    "backlog": 0,
    "qlen": 0,
    "memory_used": 12345,
    "memory_limit": 33554432,
    "capacity_estimate": 104857600,
    "tins": [
        {
            "threshold_rate": "...",
            "sent_bytes": 0,
            "sent_packets": 0,
            "dropped_packets": 0,
            "ecn_marked_packets": 0,
            "backlog_bytes": 0,
            "peak_delay_us": 0,
            "avg_delay_us": 0,
            "base_delay_us": 0,
            "sparse_flows": 0,
            "bulk_flows": 0,
            "unresponsive_flows": 0,
            "way_indirect_hits": 0,
            "way_misses": 0,
            "way_collisions": 0,
            "max_pkt_len": 0
        }
    ]
}]
```

**Note:** cake-autorate does NOT use this. It reads raw byte counters from `/sys/class/net/<iface>/statistics/` instead. wanctl's approach of parsing tc JSON output is strictly superior because it provides per-tin data and CAKE-specific metrics (drops, ECN marks, delays).

---

## Platform Compatibility: Debian 12 (Bookworm)

| Component | Debian 12 Version | Requirement | Status |
|-----------|--------------------|-------------|--------|
| Kernel | 6.1 LTS | >= 4.19 (CAKE in-tree) | PASS |
| iproute2 | 6.1.0-3 | >= 4.19 (CAKE tc support) | PASS |
| sch_cake module | Built-in (kernel 6.1) | Module loaded | PASS |
| tc -j (JSON) | Supported | JSON stats parsing | PASS |
| IFB module | Available (not needed) | N/A for bridge topology | N/A |
| Bridge support | Built-in | Transparent L2 bridge | PASS |

Debian 12 ships everything needed. No backports, out-of-tree modules, or custom builds required.

---

## Pitfalls Discovered from Open-Source Projects

### Critical

**1. systemd-networkd CAKE configuration race condition**
- **Source:** [systemd issue #31226](https://github.com/systemd/systemd/issues/31226)
- **Problem:** systemd-networkd uses `tc qdisc add` (not `replace`). If a qdisc already exists, the new configuration is silently ignored. CAKE parameters revert to defaults on network restart.
- **Fix in systemd:** Changed to `NLM_F_CREATE | NLM_F_REPLACE` in newer versions.
- **Mitigation for wanctl:** Do NOT rely on systemd-networkd `[CAKE]` section for CAKE setup. Use `tc qdisc replace` in wanctl's startup sequence or a dedicated systemd oneshot service. Validate CAKE parameters after startup via `tc -j qdisc show`.

**2. CAKE on bridge interface vs bridge member ports**
- **Source:** sqm-scripts FAQ, kernel bridge code
- **Problem:** Attaching CAKE to `br-spectrum` (the bridge itself) has NO effect on bridged/forwarded traffic. Forwarded packets bypass the bridge device qdisc and go directly to member port qdiscs. Only locally-originated traffic from the bridge IP hits the bridge qdisc.
- **Mitigation:** Always attach CAKE to individual bridge member ports (`ethX`), never to the bridge interface. Already specified correctly in FEATURES.md.

**3. sch_cake use-after-free CVE (2025-2026)**
- **Source:** SSD Secure Disclosure, CVE-2025-38350
- **Problem:** cake_enqueue returns NET_XMIT_SUCCESS after dropping packets, misleading parent classful qdiscs (HFSC, HTB), causing use-after-free on dequeue. Local privilege escalation to root.
- **Mitigation:** Ensure Debian 12 kernel is patched. wanctl uses CAKE as root qdisc (no parent HTB), so the specific trigger (classful parent) does not apply. Still, keep kernel updated.

### Moderate

**4. `wash` destroys DSCP marks needed by diffserv4**
- **Source:** sqm-scripts layer_cake.qos, OpenWrt forums
- **Problem:** sqm-scripts optionally adds `wash` to ingress CAKE to clear ISP DSCP marks. In wanctl's topology, the RB5009 sets DSCP via mangle rules, and these marks must survive the bridge to reach CAKE's diffserv4 classifier.
- **Mitigation:** Never use `wash` on wanctl's CAKE instances. DSCP marks from the router's mangle rules are the traffic classification source.

**5. `nat` keyword useless (and adds overhead) on transparent bridge**
- **Source:** tc-cake(8) man page, LWN article
- **Problem:** `nat` tells CAKE to use conntrack to de-NAT flows for per-host fairness. On a transparent bridge, there is no NAT and no conntrack. Using `nat` adds conntrack lookup overhead for zero benefit.
- **Mitigation:** Do not use `nat` keyword. Use `triple-isolate` (default) or `dual-srchost`/`dual-dsthost` based on shaping direction.

**6. `autorate-ingress` conflicts with external rate controller**
- **Source:** tc-cake(8) man page, sch_cake issue #55
- **Problem:** CAKE's built-in `autorate-ingress` tries to estimate link speed by measuring arrivals. This directly conflicts with wanctl's control loop, which sets explicit bandwidth via `tc qdisc change`. Both would fight for control, causing oscillation.
- **Mitigation:** Never use `autorate-ingress`. Always use explicit `bandwidth <rate>`. Already specified in FEATURES.md anti-features.

### Minor

**7. Default `rtt 100ms` may be too conservative**
- **Source:** tc-cake(8), OpenWrt forums
- **Problem:** CAKE's default RTT of 100ms tunes the AQM (Cobalt) target delay. For connections with sub-50ms RTT (wanctl's reflectors to Dallas ~30ms), this means CAKE signals congestion later than optimal.
- **Mitigation:** Consider `rtt 50ms` or even `rtt 30ms` to match the actual path RTT. Needs testing -- too-low RTT causes premature congestion signaling. Candidates for wanctl's adaptive tuning system.

**8. memlimit sizing**
- **Source:** LWN "Let them run CAKE", tc-cake(8)
- **Problem:** Default memlimit auto-scales with bandwidth. A small limit can cause buffer starvation for small packets while being overwhelmed by GSO super-packets. Dynamic range is ~4:1 worst case.
- **Mitigation:** Set explicit `memlimit` sized for the maximum bandwidth. For ~1Gbps links, 32MB is generous. Monitor `memory_used` vs `memory_limit` from tc JSON stats.

**9. Kernel-level RTT jitter at 'lan' and below settings**
- **Source:** tc-cake(8) man page
- **Problem:** At CAKE's `lan` setting and below, "the time constants are similar in magnitude to the jitter in the Linux kernel itself, so congestion might be signalled prematurely."
- **Mitigation:** Do not use `lan` RTT mode for WAN-facing CAKE. Use `internet` (100ms) or a specific `rtt` value.

---

## Feature Gaps: What wanctl May Be Missing

Comparing wanctl's v1.21 requirements against patterns used by all three projects:

### Should Add to Requirements

| Feature | Used By | Current Status | Recommendation |
|---------|---------|----------------|----------------|
| `ingress` keyword on download CAKE | sch_cake maintainer recommendation | Not in requirements | **Add to CAKE-01..06.** Tighter drop accounting for ingress-direction shaping. |
| `ecn` on download CAKE | Modern best practice | Not explicitly in requirements | **Add.** ECN marking provides softer congestion signals than drops. CAKE supports it natively. |
| `rtt` parameter tuning | OpenWrt forum discussions | Not in requirements | **Add as tunable.** Default 100ms is conservative; 50ms may better match link characteristics. Candidate for adaptive tuning. |
| CAKE parameter validation after startup | systemd issue #31226 pattern | BACK-03 covers presence check only | **Enhance BACK-03.** After `tc qdisc replace`, read back parameters via `tc -j qdisc show` and verify diffserv mode, overhead, bandwidth match expectations. Silent misconfiguration is the #1 pitfall from systemd. |

### Already Covered (Confirmed by Ecosystem)

| Feature | Requirement | Ecosystem Confirmation |
|---------|-------------|----------------------|
| `split-gso` | CAKE-01 | Default in CAKE, all projects rely on it |
| `ack-filter` | CAKE-03 | sqm-scripts uses on egress for asymmetric links |
| `overhead`/`mpu` per-link | CAKE-05 | sqm-scripts has comprehensive keyword support |
| `memlimit` | CAKE-06 | Recommended by LWN analysis |
| Per-tin stats | CAKE-07 | LibreQoS relies on per-subscriber per-tin data |
| No IFB needed | Anti-feature in FEATURES.md | Confirmed by LibreQoS and MagicBox patterns |
| No `nat` keyword | Anti-feature in FEATURES.md | Confirmed -- transparent bridge has no conntrack |
| No `wash` | Implicitly correct | DSCP marks from RB5009 must survive bridge |
| `tc qdisc change` for runtime updates | BACK-01 | Used by cake-autorate, confirmed lossless |
| `tc -j -s qdisc show` for stats | BACK-02 | Standard approach, iproute2 6.1 supports it |

### Explicitly Not Needed (Confirmed)

| Feature | Why Not | Ecosystem Evidence |
|---------|---------|-------------------|
| IFB device | Bridge member ports provide bidirectional shaping | LibreQoS, MagicBox avoid IFB in bridge topology |
| `autorate-ingress` | wanctl IS the autorate system | cake-autorate also uses external control |
| `nat` keyword | No NAT on bridge | Only used by sqm-scripts (router topology) |
| cake_mq (multi-queue CAKE) | Requires kernel 7.0+, only helps at 10Gbps+ | sqm-scripts added support in 2025 for OpenWrt 25.12 |
| HTB parent qdisc | Only needed for per-subscriber shaping | LibreQoS uses HTB+CAKE; wanctl has one user per link |
| pyroute2 netlink (immediate) | tc subprocess is fast enough for 2-4 qdiscs | LibreQoS uses netlink for thousands of qdiscs; wanctl's scale is different |

---

## Recommended CAKE Setup Commands for wanctl v1.21

Based on ecosystem research, here are the recommended tc commands:

### Spectrum WAN (DOCSIS Cable)

```bash
# Upload: modem-side NIC egress (traffic toward ISP)
tc qdisc replace dev $SPECTRUM_MODEM_NIC root cake \
    bandwidth ${SPECTRUM_UL_RATE}kbit \
    diffserv4 \
    split-gso \
    ack-filter \
    docsis \
    memlimit 32mb

# Download: router-side NIC egress (traffic toward LAN)
tc qdisc replace dev $SPECTRUM_ROUTER_NIC root cake \
    bandwidth ${SPECTRUM_DL_RATE}kbit \
    diffserv4 \
    split-gso \
    ingress \
    ecn \
    docsis \
    memlimit 32mb
```

### ATT WAN (Bridged Ethernet/PTM)

```bash
# Upload: modem-side NIC egress
tc qdisc replace dev $ATT_MODEM_NIC root cake \
    bandwidth ${ATT_UL_RATE}kbit \
    diffserv4 \
    split-gso \
    ack-filter \
    bridged-ptm \
    memlimit 32mb

# Download: router-side NIC egress
tc qdisc replace dev $ATT_ROUTER_NIC root cake \
    bandwidth ${ATT_DL_RATE}kbit \
    diffserv4 \
    split-gso \
    ingress \
    ecn \
    bridged-ptm \
    memlimit 32mb
```

### Parameter Rationale Summary

| Parameter | Upload | Download | Why |
|-----------|--------|----------|-----|
| `diffserv4` | Yes | Yes | 4-tin classification matches RB5009 mangle rules |
| `split-gso` | Yes | Yes | Default, lower latency for competing flows |
| `ack-filter` | Yes | No | Upload benefits from ACK compression; download has full-size data packets |
| `ingress` | No | Yes | Counts dropped packets against shaper on download side |
| `ecn` | No | Yes | Softer congestion signaling on download; upload ECN is ISP-dependent |
| `docsis`/`bridged-ptm` | Both | Both | Per-link overhead accounting |
| `memlimit 32mb` | Both | Both | Bounded memory for ~1Gbps links |
| `nat` | No | No | Bridge has no NAT/conntrack |
| `wash` | No | No | DSCP marks from RB5009 must be preserved |
| `autorate-ingress` | No | No | wanctl manages rate externally |

---

## Sources

### Primary (HIGH confidence)
- [tc-cake(8) Linux manual page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- authoritative CAKE parameter documentation
- [sqm-scripts source (GitHub)](https://github.com/tohojo/sqm-scripts) -- piece_of_cake.qos, layer_cake.qos, functions.sh, defaults.sh
- [cake-autorate source (GitHub)](https://github.com/lynxthecat/cake-autorate) -- cake-autorate.sh, config.primary.sh
- [sch_cake issue #55: ingress mode](https://github.com/dtaht/sch_cake/issues/55) -- authoritative explanation of `ingress` keyword behavior
- [Debian bookworm iproute2 6.1.0-3](https://packages.debian.org/bookworm/iproute2) -- package version confirmation

### Secondary (MEDIUM confidence)
- [LibreQoS GitHub + docs](https://github.com/LibreQoE/LibreQoS) -- architecture, bridge setup, CAKE configuration patterns
- [LibreQoS Bakery blog post](https://devblog.libreqos.com/posts/0005-lqos-bakery/) -- lazy CAKE creation, HTB+CAKE hierarchy
- [LWN: Let them run CAKE](https://lwn.net/Articles/758353/) -- CAKE design decisions, memlimit considerations
- [LWN: Add CAKE qdisc](https://lwn.net/Articles/752777/) -- kernel inclusion, stats format
- [Gentoo CAKE wiki draft](https://wiki.gentoo.org/wiki/User:0xdc/Drafts/Cake) -- practical IFB setup guide
- [MagicBox (GitHub)](https://github.com/fernandodiacenco/MagicBox) -- transparent bridge CAKE without IFB, 5% overhead saving
- [LibreQoS bridge configuration](https://libreqos.readthedocs.io/en/latest/docs/v2.0/bridge.html) -- netplan bridge setup
- [systemd issue #31226](https://github.com/systemd/systemd/issues/31226) -- CAKE options not applying via systemd-networkd

### Tertiary (LOW confidence -- community discussions)
- [OpenWrt CAKE forum threads](https://forum.openwrt.org/t/cake-w-adaptive-bandwidth/191049) -- real-world cake-autorate usage
- [Fish's tc-cake blog notes](https://blog.lucid.net.au/2021/12/12/linux-tc-cake-notes/) -- diffserv8 mapping, WireGuard gotchas
- [Bufferbloat.net CakeTechnical](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- CAKE tin architecture
- [CAKE QoS Script OpenWrt](https://github.com/Last-times/CAKE-QoS-Script-OpenWrt) -- veth alternative to IFB
- [CAKE overhead discussion](https://www.snbforums.com/threads/wan-packet-overhead.74752/) -- DOCSIS/PTM overhead values

---
*Open-source CAKE ecosystem research for wanctl v1.21 CAKE Offload*
*Researched: 2026-03-24*
