# Feature Research: CAKE Offload to Linux VM

**Domain:** Linux CAKE qdisc management via transparent bridge for dual-WAN bandwidth control
**Researched:** 2026-03-24
**Confidence:** HIGH (kernel docs, iproute2 source, existing wanctl codebase)

## Feature Landscape

### Table Stakes (Users Expect These)

Features that are non-negotiable for the CAKE offload to function correctly. Missing any of these means the system does not work at all or is worse than the current MikroTik-based CAKE.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| LinuxCakeBackend: `set_bandwidth()` | Core control loop requires setting CAKE bandwidth every cycle when rate changes | LOW | `tc qdisc change dev <iface> root cake bandwidth <rate>` -- CAKE supports lossless `change` without packet loss. Direct mapping to existing `RouterBackend.set_bandwidth()` interface. Runs as subprocess call, ~1ms latency (vs 3-8ms REST API). |
| LinuxCakeBackend: `get_queue_stats()` | Multi-signal congestion detection needs drops + queue depth per cycle | MEDIUM | `tc -j -s qdisc show dev <iface>` returns JSON with `tins` array. Parse global `dropped`, `backlog` (bytes+packets), plus per-tin stats. JSON parsing is cleaner than MikroTik text parsing. Must map to existing `CakeStats` dataclass (packets, bytes, dropped, queued_packets, queued_bytes). |
| LinuxCakeBackend: `get_bandwidth()` | Verification after setting limits (existing contract) | LOW | Parse `bandwidth` field from `tc -j qdisc show dev <iface>`. Returns current configured rate in bps. |
| LinuxCakeBackend: `test_connection()` | Health checks verify backend is reachable and CAKE qdisc is present | LOW | Run `tc qdisc show dev <iface>` and verify output contains `cake`. Local subprocess, no network call. |
| Initial CAKE qdisc setup | CAKE must be attached to correct interfaces before control loop starts | MEDIUM | `tc qdisc add dev <iface> root cake bandwidth <rate> diffserv4 ...` on each shaping interface during startup. Must handle "already exists" gracefully (use `replace` for idempotency). Separate from `change` used in control loop. |
| Transparent bridge creation (br-spectrum, br-att) | Traffic must flow between modem and router transparently at L2 | MEDIUM | `ip link add br-spectrum type bridge` + `ip link set nic0 master br-spectrum` + `ip link set nic1 master br-spectrum`. Bridge itself needs no IP (pure L2). Must be persistent across reboots via systemd-networkd or /etc/network/interfaces. |
| CAKE on correct bridge member ports | Upload and download shaping require CAKE on different member ports | MEDIUM | Key architectural decision: **upload CAKE on modem-side port egress** (traffic leaving toward ISP), **download CAKE on router-side port egress** (traffic leaving toward LAN/router). Each bridge needs two CAKE instances, one per direction per physical NIC. No IFB needed -- bridge member ports provide natural bidirectional shaping points. |
| diffserv4 DSCP mapping preservation | RB5009 mangle marks DSCP; CAKE must honor them through L2 bridge | LOW | CAKE `diffserv4` reads DSCP from IP headers. L2 bridge preserves IP headers intact (no NAT, no modification). DSCP marks set by RB5009 mangle rules flow through bridge transparently. Four tins: Bulk (CS1), Best Effort, Video (AF4x/AF3x/CS3/AF2x/CS2), Voice (CS7/CS6/EF/VA/CS5/CS4). |
| Config transport mode: `transport: "linux-cake"` | Config-driven backend selection alongside existing `rest`/`ssh` | LOW | Extend `get_router_client()` factory and `get_backend()` factory to recognize `"linux-cake"`. New config fields: `cake.interface_download`, `cake.interface_upload` (or derive from bridge member names). No router host/password needed. |
| Flash wear protection (write-only-on-change) | Existing invariant: only send tc commands when rate actually changes | LOW | Already implemented via `last_applied_dl_rate`/`last_applied_ul_rate` tracking in WANController. LinuxCakeBackend inherits this behavior -- no code change needed in the controller, only in the backend. |

### Differentiators (Competitive Advantage)

Features that make the Linux CAKE offload superior to the current MikroTik-based CAKE.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| JSON stats parsing via `tc -j` | Structured JSON output eliminates brittle regex/text parsing | LOW | `tc -j -s qdisc show dev <iface>` returns proper JSON with `tins` array containing per-tin `sent_bytes`, `sent_packets`, `drops`, `ecn_mark`, `backlog_bytes`, `peak_delay_us`, `avg_delay_us`, etc. Much richer than MikroTik queue tree stats. Existing `CakeStatsReader` has JSON path already (`_parse_json_response`). |
| Per-tin statistics visibility | Linux CAKE exposes Bulk/BestEffort/Video/Voice stats individually | MEDIUM | MikroTik only exposes aggregate queue stats. Per-tin drops/delays lets wanctl detect which traffic class is congested. Could feed more nuanced congestion assessment. Store per-tin stats in SQLite for trend analysis. |
| Reduced control loop latency | Local subprocess (~1ms) vs REST API over network (~3-8ms) | LOW | LinuxCakeBackend runs `tc` locally on the same VM as wanctl. No network round-trip, no TLS overhead, no REST API serialization. Frees ~5ms per cycle for other work in the 50ms budget. |
| Bridge link health monitoring | Detect cable disconnection or NIC failure at L2 | MEDIUM | Monitor bridge member port carrier status via `/sys/class/net/<iface>/carrier` or `bridge link show`. Alert on link-down events via existing AlertEngine. Critical for detecting physical layer failures that would silently break shaping. |
| CAKE memory and capacity stats | Linux CAKE reports `memory_used`, `memory_limit`, `capacity_estimate` | LOW | Fields available in `tc -j -s` output. Memory pressure indicates queue sizing issues. Capacity estimate shows CAKE's view of achievable throughput. Expose in health endpoint for diagnostics. |
| Elimination of router CPU bottleneck | RB5009 drops from 55% CPU under RRUL to near-zero | LOW (code) | This is the primary motivation. No code complexity -- the benefit comes from architecture change. MikroTik goes from CAKE+routing to routing-only. Spectrum throughput should increase from ~740Mbps to wire-rate (~940Mbps). |
| ECN mark statistics | Linux CAKE reports ECN marks separately from drops | LOW | `ecn_mark` per-tin field in JSON output. MikroTik does not expose ECN marking stats. Useful for understanding how CAKE is signaling congestion (marks vs drops). |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| IFB (Intermediate Functional Block) for ingress shaping | Standard Linux approach for shaping ingress traffic | **Not needed in bridge topology.** IFB is for routers where you can only shape egress on one interface. With a bridge, each member port has its own egress direction -- modem-side port egresses toward ISP (upload), router-side port egresses toward LAN (download). Two physical ports = two natural egress shaping points. IFB adds complexity, a virtual device, and tc filter redirection for zero benefit. | Attach CAKE directly to bridge member port egress (one for upload, one for download per WAN). |
| CAKE on the bridge interface itself | Simpler config (one qdisc per bridge vs two per member) | Bridge interface egress only sees locally-originated traffic, not bridged/forwarded traffic. Forwarded packets bypass the bridge device qdisc and go directly to the member port qdisc. Shaping on `br-spectrum` would have no effect on transit traffic. | Shape on the individual member ports (`nic0`, `nic1`), not on `br-spectrum`. |
| autorate-ingress mode | CAKE has a built-in `autorate-ingress` keyword for automatic bandwidth detection | Conflicts with wanctl's control loop. wanctl IS the autorate system -- it measures RTT and adjusts bandwidth via `tc qdisc change`. CAKE's built-in autorate would fight with wanctl's decisions, causing oscillation. | Use `bandwidth <rate>` (explicit) and let wanctl manage the rate via `tc qdisc change`. |
| Shaping on the bridge for both directions | Apply one CAKE instance to shape both upload and download | CAKE is an egress qdisc -- it can only shape traffic leaving an interface. You cannot shape both directions with one instance. Even with `ingress` keyword, that just tells CAKE to count drops differently -- it does not enable bidirectional shaping on a single attachment point. | Two CAKE instances per bridge: one on modem-side port (upload shaping), one on router-side port (download shaping). |
| NAT-awareness (`nat` keyword) in CAKE | Fairness per internal host when behind NAT | The shaping VM is a transparent bridge with no NAT. The `nat` keyword tells CAKE to look at conntrack to de-NAT flows for per-host fairness. Since the bridge is pre-NAT (between modem and router), conntrack is not applicable. Using `nat` would add overhead for no benefit. | Use `dual-dsthost` or `triple-isolate` (default) for flow isolation. These work on visible IP headers which are unmodified in the bridge. |
| Generic multi-vendor router backend | "Make LinuxCakeBackend work with any Linux box" | Scope creep. This is specifically for the odin Proxmox VM with PCIe passthrough NICs in a transparent bridge topology. Generalizing to arbitrary Linux routers would require handling routing, NAT, IFB, interface discovery, and many topologies wanctl does not target. | LinuxCakeBackend is purpose-built for the transparent bridge offload use case. Config names bridge member interfaces explicitly. |
| Automatic bridge/NIC setup in wanctl | Let wanctl create bridges and configure NICs | Network topology is infrastructure, not application concern. Bridge setup should happen once during VM provisioning and persist via systemd-networkd. If wanctl tried to manage bridges, a crash/restart could tear down network connectivity. | Provision bridges in VM setup (systemd-networkd or /etc/network/interfaces). wanctl assumes bridges and CAKE qdiscs exist at startup. Validate in `test_connection()`. |

## Feature Dependencies

```
[Transport config: "linux-cake"]
    |
    +--requires--> [LinuxCakeBackend class]
    |                  |
    |                  +--requires--> [tc qdisc setup (initial CAKE add)]
    |                  |                  |
    |                  |                  +--requires--> [Transparent bridge provisioned]
    |                  |                                     |
    |                  |                                     +--requires--> [PCIe NIC passthrough on odin]
    |                  |
    |                  +--requires--> [tc command execution (subprocess)]
    |                  |
    |                  +--requires--> [tc JSON output parsing]
    |
    +--requires--> [Config schema extension (cake.interface_*)]
    |
    +--requires--> [Backend factory update (get_backend)]

[Per-tin stats visibility]
    +--requires--> [LinuxCakeBackend get_queue_stats()]
    +--enhances--> [CongestionAssessment (richer signals)]
    +--enhances--> [Health endpoint (per-tin section)]
    +--enhances--> [SQLite metrics (per-tin persistence)]

[Bridge link health monitoring]
    +--requires--> [Transparent bridge provisioned]
    +--enhances--> [AlertEngine (link-down alerts)]
    +--enhances--> [Health endpoint (bridge status)]

[RB5009 queue tree removal]
    +--requires--> [LinuxCakeBackend verified working]
    +--conflicts--> [MikroTik CAKE (cannot run both simultaneously)]
```

### Dependency Notes

- **LinuxCakeBackend requires bridge provisioned:** The backend needs to know interface names (e.g., `nic0`, `nic1`) to attach CAKE qdiscs. These must exist before wanctl starts.
- **Per-tin stats enhances CongestionAssessment:** Current assessment uses aggregate drops + RTT. Per-tin data is additive, not required. Can be deferred to a later phase.
- **RB5009 removal conflicts with MikroTik CAKE:** During migration, both cannot shape simultaneously (double-shaping causes severe throughput loss). Cutover is atomic: disable MikroTik queues, enable Linux CAKE.
- **Bridge link health enhances AlertEngine:** Uses existing alert infrastructure. Not required for basic operation but critical for production reliability.

## MVP Definition

### Launch With (v1.21 Core)

Minimum viable CAKE offload -- what is needed to move shaping from RB5009 to Linux VM.

- [ ] LinuxCakeBackend implementing `RouterBackend` interface (set_bandwidth, get_bandwidth, get_queue_stats, test_connection) -- core control loop compatibility
- [ ] tc JSON output parsing for stats (`tc -j -s qdisc show`) -- reliable stats extraction
- [ ] tc qdisc change for bandwidth control -- lossless runtime rate adjustment
- [ ] Config transport: `"linux-cake"` with interface name config -- backend selection
- [ ] Backend factory integration (`get_backend()` + `get_router_client()` updated) -- zero changes to WANController/steering
- [ ] Initial CAKE qdisc setup validation (verify CAKE exists on expected interfaces at startup) -- fail-fast on misconfiguration
- [ ] Bridge provisioning documentation/scripts (systemd-networkd config) -- infrastructure prerequisite

### Add After Validation (v1.21.x)

Features to add once core CAKE offload is working in production.

- [ ] Per-tin statistics in health endpoint -- trigger: first production deployment stable for 24h
- [ ] Per-tin statistics in SQLite metrics -- trigger: per-tin health endpoint verified useful
- [ ] Bridge link carrier monitoring with alerts -- trigger: first cable disconnection goes undetected
- [ ] CAKE memory/capacity stats in health endpoint -- trigger: observability needs during initial tuning
- [ ] ECN mark tracking in metrics -- trigger: want to understand CAKE mark-vs-drop behavior
- [ ] `wanctl-check-cake` adaptation for Linux CAKE audit -- trigger: need operational validation tool for Linux CAKE params

### Future Consideration (v2+)

Features to defer until Linux CAKE offload is proven stable.

- [ ] Per-tin congestion assessment (use per-tin drops to detect which traffic class is overloaded) -- requires research into whether per-tin signals improve steering decisions
- [ ] mq-cake (multi-queue CAKE, Linux 7.0+) -- requires kernel upgrade, only relevant at 10GbE speeds
- [ ] Automatic failback to MikroTik CAKE if bridge/VM health degrades -- complex, requires maintaining MikroTik queue tree in disabled state and re-enabling on failure detection

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| LinuxCakeBackend (set/get bandwidth) | HIGH | LOW | P1 |
| tc JSON stats parsing (get_queue_stats) | HIGH | MEDIUM | P1 |
| Config transport: "linux-cake" | HIGH | LOW | P1 |
| Backend factory integration | HIGH | LOW | P1 |
| Initial CAKE qdisc validation | HIGH | LOW | P1 |
| diffserv4 preservation verification | HIGH | LOW | P1 |
| Bridge provisioning docs/scripts | HIGH | MEDIUM | P1 |
| Per-tin stats in health endpoint | MEDIUM | LOW | P2 |
| Bridge link carrier monitoring | MEDIUM | MEDIUM | P2 |
| Per-tin stats in SQLite | MEDIUM | MEDIUM | P2 |
| CAKE memory/capacity in health | LOW | LOW | P2 |
| ECN mark tracking | LOW | LOW | P2 |
| wanctl-check-cake Linux adaptation | MEDIUM | MEDIUM | P2 |
| Per-tin congestion assessment | MEDIUM | HIGH | P3 |
| Automatic MikroTik failback | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch -- CAKE offload does not work without these
- P2: Should have, add once P1 is stable in production
- P3: Nice to have, future consideration after production hardening

## Existing System Feature Analysis

How current wanctl features map to the Linux CAKE offload:

| Feature | Current (MikroTik) | Linux CAKE Backend | Migration Impact |
|---------|--------------------|--------------------|-----------------|
| set_bandwidth | REST API: `/queue/tree/set max-limit=<rate>` | `tc qdisc change dev <iface> root cake bandwidth <rate>` | New backend method, same interface |
| get_bandwidth | REST API: `/queue/tree/print` + parse max-limit | `tc -j qdisc show dev <iface>` + parse bandwidth field | New backend method, same interface |
| get_queue_stats | REST API: `/queue/tree/print stats` + parse JSON/text | `tc -j -s qdisc show dev <iface>` + parse JSON tins | New backend method, richer data available |
| RTT measurement | icmplib ping to reflectors | **Unchanged** -- pings from VM through bridge | Zero migration impact |
| Signal processing | Hampel, EWMA, fusion | **Unchanged** -- operates on RTT data | Zero migration impact |
| Adaptive tuning | 4-layer rotation | **Unchanged** -- operates on metrics | Zero migration impact |
| Steering (mangle rules) | REST/SSH to RB5009 mangle | **Unchanged** -- steering stays on RB5009 | Steering daemon still talks to router |
| CakeStatsReader | Uses FailoverRouterClient (REST/SSH) | Replaced by LinuxCakeBackend.get_queue_stats() | Steering daemon needs adaptation for linux-cake transport |
| Health endpoint | Reports queue stats from MikroTik | Reports queue stats from local tc | Same data structure, different source |
| check-cake CLI | Audits MikroTik CAKE params via REST | Needs Linux CAKE variant (tc qdisc show + validate) | New code path in check-cake tool |

### Steering Daemon Specifics

The steering daemon currently creates its own `CakeStatsReader` with a `FailoverRouterClient` to read CAKE stats from MikroTik. With linux-cake transport:

- **CakeStatsReader must support linux-cake transport** -- either extend CakeStatsReader to call `tc` locally, or have it delegate to LinuxCakeBackend.get_queue_stats(). The cleanest approach: CakeStatsReader detects transport type and uses the appropriate backend.
- **Steering mangle rules stay on MikroTik** -- the steering daemon still needs a router client for enable_rule/disable_rule. This means the steering config keeps `router.transport: "rest"` for mangle rules even when autorate uses `transport: "linux-cake"`.
- **Implication:** Steering config and autorate config have different transport needs. Autorate config gets `transport: "linux-cake"`, steering config keeps `router.transport: "rest"` for mangle rules but needs linux-cake for CAKE stats reading.

## Sources

- [tc-cake(8) Linux manual page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- authoritative CAKE qdisc documentation
- [iproute2 q_cake.c source](https://github.com/iproute2/iproute2/blob/main/tc/q_cake.c) -- JSON output field names and structure
- [Gentoo CAKE draft wiki](https://wiki.gentoo.org/wiki/User:0xdc/Drafts/Cake) -- practical IFB setup examples
- [sch_cake issue #40 (output format)](https://github.com/dtaht/sch_cake/issues/40) -- tc output column alignment and parsing considerations
- [sch_cake issue #55 (ingress mode)](https://github.com/dtaht/sch_cake/issues/55) -- ingress keyword behavior
- [Bufferbloat.net CakeTechnical](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- CAKE design and per-tin architecture
- [OpenWrt CAKE tc -s questions](https://forum.openwrt.org/t/cake-tc-s-qdisc-questions/193546) -- real-world tc output examples
- [LWN: Add CAKE qdisc](https://lwn.net/Articles/752777/) -- kernel inclusion and statistics format
- [bridge(8) Linux manual page](https://man7.org/linux/man-pages/man8/bridge.8.html) -- bridge monitoring commands

---
*Feature research for: CAKE offload from MikroTik to Linux transparent bridge VM*
*Researched: 2026-03-24*
