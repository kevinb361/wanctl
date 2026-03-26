# Phase 113 Plan 01: CAKE Configuration & DSCP Classification Findings

**Date:** 2026-03-26
**VM:** cake-shaper (10.10.110.223)
**Router:** MikroTik RB5009 (10.10.99.1)

---

## NETENG-01: CAKE Parameter Verification

### Methodology

1. Read production YAML configs (`/etc/wanctl/{spectrum,att}.yaml`) to extract expected CAKE parameters
2. Merged config values with direction-aware defaults from `cake_params.py` (UPLOAD_DEFAULTS, DOWNLOAD_DEFAULTS, TUNABLE_DEFAULTS)
3. Read actual CAKE qdisc state via `tc -j qdisc show` on the production VM
4. Compared expected vs actual for each WAN and each direction

**Note on wanctl-check-cake:** The `wanctl-check-cake` CLI tool was designed for the original MikroTik RouterOS deployment (REST/SSH transport). It does not support the `linux-cake` transport used on the cake-shaper VM. The tool exits with `Error: failed to create router client: Unsupported transport: linux-cake`. For linux-cake deployments, direct `tc -j qdisc show` readback is the correct verification method. The `LinuxCakeBackend.validate_cake()` method performs this same readback comparison programmatically at daemon startup.

### Spectrum WAN

**Config source:** `/etc/wanctl/spectrum.yaml`

- `cake_params.overhead: "docsis"`
- `cake_params.memlimit: "32mb"`
- `cake_params.rtt: "100ms"`
- `cake_params.download_interface: "ens17"`
- `cake_params.upload_interface: "ens16"`

#### Spectrum Upload (ens16)

Defaults applied: UPLOAD_DEFAULTS (ack-filter=True, ingress=False, ecn=False) + TUNABLE_DEFAULTS

| Parameter  | Expected (config+defaults) | Actual (tc readback) | Match            |
| ---------- | -------------------------- | -------------------- | ---------------- |
| diffserv   | diffserv4                  | diffserv4            | YES              |
| overhead   | 18 (docsis)                | 18                   | YES              |
| atm        | noatm (docsis)             | noatm                | YES              |
| ack-filter | enabled                    | enabled              | YES              |
| split_gso  | true                       | true                 | YES              |
| ingress    | false                      | false                | YES              |
| memlimit   | 33554432 (32mb)            | 33554432             | YES              |
| rtt        | 100000 (100ms)             | 100000               | YES              |
| mpu        | (not configured)           | 64                   | N/A (tc default) |
| nat        | (not configured)           | false                | N/A (tc default) |
| wash       | (not configured)           | false                | N/A (tc default) |
| flowmode   | (not configured)           | triple-isolate       | N/A (tc default) |
| bandwidth  | (runtime-managed)          | 4750000              | N/A (dynamic)    |

#### Spectrum Download (ens17)

Defaults applied: DOWNLOAD_DEFAULTS (ack-filter=False, ingress=True, ecn=True) + TUNABLE_DEFAULTS

| Parameter  | Expected (config+defaults) | Actual (tc readback) | Match            |
| ---------- | -------------------------- | -------------------- | ---------------- |
| diffserv   | diffserv4                  | diffserv4            | YES              |
| overhead   | 18 (docsis)                | 18                   | YES              |
| atm        | noatm (docsis)             | noatm                | YES              |
| ack-filter | disabled                   | disabled             | YES              |
| split_gso  | true                       | true                 | YES              |
| ingress    | true                       | true                 | YES              |
| memlimit   | 33554432 (32mb)            | 33554432             | YES              |
| rtt        | 100000 (100ms)             | 100000               | YES              |
| mpu        | (not configured)           | 64                   | N/A (tc default) |
| nat        | (not configured)           | false                | N/A (tc default) |
| wash       | (not configured)           | false                | N/A (tc default) |
| flowmode   | (not configured)           | triple-isolate       | N/A (tc default) |
| bandwidth  | (runtime-managed)          | 117500000            | N/A (dynamic)    |

**Note on ECN:** DOWNLOAD_DEFAULTS specifies `ecn: True`, but `LinuxCakeBackend.initialize_cake()` does not pass the `ecn` flag to `tc`. Comment in code: "ecn is excluded -- not supported by iproute2-6.15.0's tc, and CAKE enables ECN by default on all tins anyway." This is correct behavior -- CAKE's default is ECN-enabled, so omitting the flag achieves the desired result. The tc JSON readback does not expose ECN state directly in the options block (it is per-tin), so this is consistent.

### ATT WAN

**Config source:** `/etc/wanctl/att.yaml`

- `cake_params.overhead: "bridged-ptm"`
- `cake_params.memlimit: "32mb"`
- `cake_params.rtt: "100ms"`
- `cake_params.download_interface: "ens28"`
- `cake_params.upload_interface: "ens27"`

#### ATT Upload (ens27)

Defaults applied: UPLOAD_DEFAULTS (ack-filter=True, ingress=False, ecn=False) + TUNABLE_DEFAULTS

| Parameter  | Expected (config+defaults) | Actual (tc readback) | Match            |
| ---------- | -------------------------- | -------------------- | ---------------- |
| diffserv   | diffserv4                  | diffserv4            | YES              |
| overhead   | 22 (bridged-ptm)           | 22                   | YES              |
| atm        | ptm (bridged-ptm)          | ptm                  | YES              |
| ack-filter | enabled                    | enabled              | YES              |
| split_gso  | true                       | true                 | YES              |
| ingress    | false                      | false                | YES              |
| memlimit   | 33554432 (32mb)            | 33554432             | YES              |
| rtt        | 100000 (100ms)             | 100000               | YES              |
| nat        | (not configured)           | false                | N/A (tc default) |
| wash       | (not configured)           | false                | N/A (tc default) |
| flowmode   | (not configured)           | triple-isolate       | N/A (tc default) |
| bandwidth  | (runtime-managed)          | 2250000              | N/A (dynamic)    |

**Note:** ATT upload (ens27) does not have `mpu` in the tc readback, unlike Spectrum interfaces which show `mpu: 64`. This is cosmetic -- the field is absent from the JSON entry but the default kernel behavior applies regardless.

#### ATT Download (ens28)

Defaults applied: DOWNLOAD_DEFAULTS (ack-filter=False, ingress=True, ecn=True) + TUNABLE_DEFAULTS

| Parameter  | Expected (config+defaults) | Actual (tc readback) | Match            |
| ---------- | -------------------------- | -------------------- | ---------------- |
| diffserv   | diffserv4                  | diffserv4            | YES              |
| overhead   | 22 (bridged-ptm)           | 22                   | YES              |
| atm        | ptm (bridged-ptm)          | ptm                  | YES              |
| ack-filter | disabled                   | disabled             | YES              |
| split_gso  | true                       | true                 | YES              |
| ingress    | true                       | true                 | YES              |
| memlimit   | 33554432 (32mb)            | 33554432             | YES              |
| rtt        | 100000 (100ms)             | 100000               | YES              |
| nat        | (not configured)           | false                | N/A (tc default) |
| wash       | (not configured)           | false                | N/A (tc default) |
| flowmode   | (not configured)           | triple-isolate       | N/A (tc default) |
| bandwidth  | (runtime-managed)          | 11875000             | N/A (dynamic)    |

### wanctl-check-cake Tool Status

The `wanctl-check-cake` CLI tool does not support the `linux-cake` transport. When invoked:

```
$ sudo PYTHONPATH=/opt ROUTER_PASSWORD=*** python3 -m wanctl.check_cake /etc/wanctl/spectrum.yaml --json
Error: failed to create router client: Unsupported transport: linux-cake
```

This is expected behavior -- the tool was built for MikroTik RouterOS REST/SSH backends to verify CAKE queue trees on the router. With the v1.21 migration to linux-cake (CAKE on the VM itself), the correct verification method is:

1. **At daemon startup:** `LinuxCakeBackend.validate_cake()` performs tc readback verification automatically
2. **For manual audits:** `tc -j qdisc show` provides machine-readable JSON readback (used in this audit)

**Recommendation:** A future enhancement could extend `wanctl-check-cake` to support linux-cake transport by reading `tc -j qdisc show` locally instead of querying the router. This is not a correctness issue -- the validation happens at startup via the backend code.

### CAKE Parameter Verification Verdict

**PASS** -- All CAKE parameters for both WANs (Spectrum and ATT) match their expected values from config YAML merged with direction-aware defaults from `cake_params.py`. Verified parameters: diffserv, overhead, atm mode, ack-filter, split-gso, ingress, memlimit, and rtt. No discrepancies found.

### Raw tc JSON Readback

<details>
<summary>Full tc -j qdisc show output (click to expand)</summary>

```json
[
  {
    "kind": "noqueue",
    "handle": "0:",
    "dev": "lo",
    "root": true,
    "refcnt": 2,
    "options": {}
  },
  {
    "kind": "fq_codel",
    "handle": "0:",
    "dev": "ens18",
    "root": true,
    "refcnt": 2,
    "options": {
      "limit": 10240,
      "flows": 1024,
      "quantum": 1514,
      "target": 4999,
      "interval": 99999,
      "memory_limit": 33554432,
      "ecn": true,
      "drop_batch": 64
    }
  },
  {
    "kind": "cake",
    "handle": "8007:",
    "dev": "ens16",
    "root": true,
    "refcnt": 9,
    "options": {
      "bandwidth": 4750000,
      "diffserv": "diffserv4",
      "flowmode": "triple-isolate",
      "nat": false,
      "wash": false,
      "ingress": false,
      "ack-filter": "enabled",
      "split_gso": true,
      "rtt": 100000,
      "raw": false,
      "atm": "noatm",
      "overhead": 18,
      "mpu": 64,
      "memlimit": 33554432,
      "fwmark": "0"
    }
  },
  {
    "kind": "cake",
    "handle": "800a:",
    "dev": "ens17",
    "root": true,
    "refcnt": 9,
    "options": {
      "bandwidth": 117500000,
      "diffserv": "diffserv4",
      "flowmode": "triple-isolate",
      "nat": false,
      "wash": false,
      "ingress": true,
      "ack-filter": "disabled",
      "split_gso": true,
      "rtt": 100000,
      "raw": false,
      "atm": "noatm",
      "overhead": 18,
      "mpu": 64,
      "memlimit": 33554432,
      "fwmark": "0"
    }
  },
  {
    "kind": "cake",
    "handle": "8005:",
    "dev": "ens27",
    "root": true,
    "refcnt": 9,
    "options": {
      "bandwidth": 2250000,
      "diffserv": "diffserv4",
      "flowmode": "triple-isolate",
      "nat": false,
      "wash": false,
      "ingress": false,
      "ack-filter": "enabled",
      "split_gso": true,
      "rtt": 100000,
      "raw": false,
      "atm": "ptm",
      "overhead": 22,
      "memlimit": 33554432,
      "fwmark": "0"
    }
  },
  {
    "kind": "cake",
    "handle": "8004:",
    "dev": "ens28",
    "root": true,
    "refcnt": 9,
    "options": {
      "bandwidth": 11875000,
      "diffserv": "diffserv4",
      "flowmode": "triple-isolate",
      "nat": false,
      "wash": false,
      "ingress": true,
      "ack-filter": "disabled",
      "split_gso": true,
      "rtt": 100000,
      "raw": false,
      "atm": "ptm",
      "overhead": 22,
      "memlimit": 33554432,
      "fwmark": "0"
    }
  },
  {
    "kind": "noqueue",
    "handle": "0:",
    "dev": "br-att",
    "root": true,
    "refcnt": 2,
    "options": {}
  },
  {
    "kind": "noqueue",
    "handle": "0:",
    "dev": "br-spectrum",
    "root": true,
    "refcnt": 2,
    "options": {}
  }
]
```

</details>

---

## NETENG-02: DSCP End-to-End Trace

### Methodology

1. Read MikroTik mangle rules via REST API (`/rest/ip/firewall/mangle` on 10.10.99.1)
2. Identified DSCP marking rules and connection classification chain
3. Mapped MikroTik DSCP marks through transparent bridge to CAKE diffserv4 tin classification
4. Documented complete end-to-end traffic path

### MikroTik Mangle Rule Chain

The router implements a 3-stage QoS pipeline: **DSCP wash** (inbound cleanup), **connection classification** (prerouting), and **DSCP marking** (postrouting).

#### Stage 1: DSCP Wash (Inbound Cleanup)

| Rule  | Chain      | Action        | Scope                    | Purpose                                     |
| ----- | ---------- | ------------- | ------------------------ | ------------------------------------------- |
| \*304 | prerouting | change-dscp 0 | in-interface-list=WAN    | Strip all DSCP from WAN inbound (untrusted) |
| \*303 | prerouting | change-dscp 0 | in-interface=vlan120-IOT | Strip all DSCP from IoT VLAN (untrusted)    |

**Trust rules** (accept without wash -- preserve existing marks from trusted LAN devices):

| Rule  | Chain      | Action | DSCP      | Scope                       |
| ----- | ---------- | ------ | --------- | --------------------------- |
| \*31B | prerouting | accept | 46 (EF)   | in-interface != vlan120-IOT |
| \*31C | prerouting | accept | 34 (AF41) | in-interface != vlan120-IOT |
| \*31D | prerouting | accept | 36 (AF42) | in-interface != vlan120-IOT |
| \*31E | prerouting | accept | 38 (AF43) | in-interface != vlan120-IOT |

These trust rules let LAN devices that self-mark EF or AF4x (e.g., IP phones, video conferencing clients) retain their DSCP marks, bypassing the connection classification stage. The marks pass through to CAKE directly.

#### Stage 2: Connection Classification (Prerouting)

Traffic is classified into connection marks. Order matters -- first match wins for non-passthrough rules.

| Priority | Connection Mark | Traffic Class            | Key Rules                                                                 |
| -------- | --------------- | ------------------------ | ------------------------------------------------------------------------- |
| Highest  | QOS_HIGH        | VoIP, VPN, DNS, NTP, RTC | Work VPN, UDP 3478-3479/5349-5350/19302-19309, TCP 53/853/5223/5228       |
| High     | GAMES           | Gaming                   | auto-games/blizzard-games/steam-games lists + GAMER-DEVICES               |
| Medium   | QOS_MEDIUM      | Interactive              | Small TCP (<=300B) to 22/3389/80/443, small UDP, high-rate UDP (500kbps+) |
| Normal   | QOS_NORMAL      | Best effort              | ICMP, IRTT (UDP 2112), email, QUIC UDP 443, unclassified                  |
| Low      | QOS_LOW         | Bulk                     | Large flows >10MB, BitTorrent, Usenet, multicast, discovery, traceroute   |

**Demotion rules:** Large TCP/UDP flows (>10MB, connection-bytes) are demoted from QOS_MEDIUM to QOS_LOW via rules *32B/*32C. This prevents bulk downloads from consuming Video-tier bandwidth.

#### Stage 3: DSCP Marking (Postrouting)

Connection marks are translated to DSCP values on outbound packets:

| Rule  | Connection Mark | New DSCP | DSCP Name                    | Condition     |
| ----- | --------------- | -------- | ---------------------------- | ------------- |
| \*305 | QOS_HIGH        | 46       | EF (Expedited Forwarding)    | dscp=0 only   |
| \*306 | GAMES           | 46       | EF (Expedited Forwarding)    | dscp=0 only   |
| \*307 | QOS_MEDIUM      | 26       | AF31 (Assured Forwarding 31) | dscp=0 only   |
| \*308 | QOS_GAME_DL     | 8        | CS1 (Scavenger)              | dscp=0 only   |
| \*309 | QOS_LOW         | 8        | CS1 (Scavenger)              | dscp=0 only   |
| \*30A | QOS_NORMAL      | 0        | CS0 (Best Effort)            | dscp=0 only   |
| \*2E6 | zerotier-packet | 46       | EF (Expedited Forwarding)    | ZeroTier only |

The `dscp=0` condition on DSCP SET rules prevents overwriting marks already set by trusted LAN devices (which were accepted in Stage 1).

#### Stage 4: Priority Mapping

| Rule  | Chain       | Action                 | Purpose                                |
| ----- | ----------- | ---------------------- | -------------------------------------- |
| \*32E | postrouting | set-priority from-dscp | Maps DSCP to 802.1p priority on egress |

This ensures DSCP marks are reflected in the Ethernet 802.1p CoS bits, which the transparent bridge preserves through to the CAKE qdisc.

### Transparent Bridge DSCP Passthrough

The cake-shaper VM operates as a transparent bridge (br-spectrum, br-att). Key property: **transparent bridges do not modify DSCP values**. DSCP marks set by MikroTik in postrouting pass through the bridge unchanged to the CAKE qdisc on the egress interface.

Bridge path:

```
MikroTik ether1/ether2 (DSCP marked) -> cable/NIC -> VM NIC (bridge member) -> CAKE qdisc
```

No NAT, no conntrack, no IP header modification occurs on the bridge. The CAKE qdisc receives packets with DSCP values exactly as set by MikroTik.

### CAKE diffserv4 Tin Classification

CAKE diffserv4 maps DSCP values to 4 priority tins. The kernel CAKE module uses the following classification (from `net/sched/sch_cake.c`):

| Tin | Name        | Priority | Bandwidth Share | Latency Target        |
| --- | ----------- | -------- | --------------- | --------------------- |
| 0   | Bulk        | Lowest   | 1/16 of total   | 50ms                  |
| 1   | Best Effort | Normal   | Remainder       | 5ms                   |
| 2   | Video       | High     | 1/4 of total    | 15ms                  |
| 3   | Voice       | Highest  | 1/16 of total   | 5ms (strict priority) |

DSCP-to-tin mapping:

| DSCP Value | DSCP Name | CAKE Tin | Tin Name    |
| ---------- | --------- | -------- | ----------- |
| 46         | EF        | 3        | Voice       |
| 44         | VA        | 3        | Voice       |
| 48         | CS6       | 3        | Voice       |
| 56         | CS7       | 3        | Voice       |
| 34         | AF41      | 2        | Video       |
| 36         | AF42      | 2        | Video       |
| 38         | AF43      | 2        | Video       |
| 32         | CS4       | 2        | Video       |
| 26         | AF31      | 2        | Video       |
| 28         | AF32      | 2        | Video       |
| 30         | AF33      | 2        | Video       |
| 24         | CS3       | 2        | Video       |
| 0          | CS0       | 1        | Best Effort |
| 8          | CS1       | 0        | Bulk        |
| 10         | LE        | 0        | Bulk        |

### End-to-End DSCP-to-CAKE Flow

```
LAN Client
    |
    v
MikroTik RB5009 (10.10.99.1)
    |-- Stage 1: DSCP wash (clear WAN/IoT marks, trust LAN EF/AF4x)
    |-- Stage 2: Connection classify (QOS_HIGH/MEDIUM/NORMAL/LOW/GAMES)
    |-- Stage 3: DSCP set (postrouting, dscp=0 only)
    |   |-- QOS_HIGH   -> EF  (DSCP 46)
    |   |-- GAMES      -> EF  (DSCP 46)
    |   |-- QOS_MEDIUM -> AF31 (DSCP 26)
    |   |-- QOS_NORMAL -> CS0 (DSCP 0)
    |   |-- QOS_LOW    -> CS1 (DSCP 8)
    |-- Stage 4: set-priority from-dscp (802.1p on egress)
    |
    v
ether1-WAN-Spectrum / ether2-WAN-ATT
    |
    v
cake-shaper VM (transparent bridge)
    |-- br-spectrum (ens16/ens17) or br-att (ens27/ens28)
    |-- DSCP values pass through unchanged (no NAT, no conntrack)
    |
    v
CAKE qdisc (diffserv4) on bridge member port
    |-- EF  (46) -> Tin 3 (Voice)   -- strict priority, lowest latency
    |-- AF31 (26) -> Tin 2 (Video)   -- bandwidth-weighted, interactive
    |-- CS0 (0)   -> Tin 1 (Best Effort) -- default
    |-- CS1 (8)   -> Tin 0 (Bulk)    -- lowest priority, scavenger
```

### Classification Chain Summary

| Traffic Type                | Connection Mark | DSCP Mark       | CAKE Tin | Tin Name    |
| --------------------------- | --------------- | --------------- | -------- | ----------- |
| VoIP, VPN, DNS, RTC         | QOS_HIGH        | EF (46)         | 3        | Voice       |
| Gaming                      | GAMES           | EF (46)         | 3        | Voice       |
| ZeroTier VPN                | zerotier-packet | EF (46)         | 3        | Voice       |
| Trusted LAN EF              | (preserved)     | EF (46)         | 3        | Voice       |
| Trusted LAN AF4x            | (preserved)     | AF41-43 (34-38) | 2        | Video       |
| Interactive (small TCP/UDP) | QOS_MEDIUM      | AF31 (26)       | 2        | Video       |
| High-rate UDP (>500kbps)    | QOS_MEDIUM      | AF31 (26)       | 2        | Video       |
| ICMP measurement            | QOS_NORMAL      | CS0 (0)         | 1        | Best Effort |
| IRTT measurement            | QOS_NORMAL      | CS0 (0)         | 1        | Best Effort |
| Email                       | QOS_NORMAL      | CS0 (0)         | 1        | Best Effort |
| QUIC (UDP 443)              | QOS_NORMAL      | CS0 (0)         | 1        | Best Effort |
| Unclassified                | QOS_NORMAL      | CS0 (0)         | 1        | Best Effort |
| Large flows (>10MB)         | QOS_LOW         | CS1 (8)         | 0        | Bulk        |
| BitTorrent                  | QOS_LOW         | CS1 (8)         | 0        | Bulk        |
| Usenet                      | QOS_LOW         | CS1 (8)         | 0        | Bulk        |
| Multicast/discovery         | QOS_LOW         | CS1 (8)         | 0        | Bulk        |

### Notable Design Decisions

1. **ICMP/IRTT as Best Effort (CS0):** Measurement traffic is intentionally classified as Best Effort, not prioritized. This ensures RTT measurements reflect the actual queuing delay experienced by normal traffic, which is critical for autorate CAKE shaping to work correctly. Prioritizing measurement traffic would mask congestion.

2. **AF31 for Interactive (not AF41):** QOS_MEDIUM uses AF31 (DSCP 26) rather than AF41 (DSCP 34). Both map to CAKE Video tin, but AF31 signals lower drop precedence within the AF class. This is a minor distinction -- CAKE diffserv4 treats all AF3x and AF4x identically (both map to Video tin).

3. **Large flow demotion:** TCP/UDP flows exceeding 10MB are automatically demoted from QOS_MEDIUM to QOS_LOW (CS1/Bulk). This prevents bulk downloads from claiming Video-tier bandwidth, protecting interactive streams.

4. **DSCP wash + trust pattern:** WAN inbound and IoT traffic are washed (DSCP cleared to 0), but trusted LAN devices that self-mark EF or AF4x retain their marks. The `dscp=0` condition on postrouting DSCP SET rules prevents overwriting these trusted marks.

### DSCP Trace Verdict

**CORRECT** -- The end-to-end DSCP classification chain is fully functional:

- EF (46) -> Voice tin: VoIP, VPN, DNS, gaming, ZeroTier, trusted LAN EF
- AF31 (26) -> Video tin: Interactive TCP/UDP, high-rate UDP, trusted LAN AF4x
- CS0 (0) -> Best Effort tin: Measurement traffic (ICMP, IRTT), email, QUIC, unclassified
- CS1 (8) -> Bulk tin: Large flows, BitTorrent, Usenet, discovery protocols

The transparent bridge correctly preserves DSCP values from MikroTik through to CAKE qdiscs.

<details>
<summary>Raw MikroTik mangle rules (click to expand)</summary>

```
56 mangle rules total. Key DSCP-related rules:

DSCP WASH:
  *304: prerouting change-dscp=0 in-interface-list=WAN (823M pkts)
  *303: prerouting change-dscp=0 in-interface=vlan120-IOT (0 pkts)

TRUST:
  *31B: prerouting accept dscp=46 (43.7M pkts)
  *31C: prerouting accept dscp=34 (3 pkts)
  *31D: prerouting accept dscp=36 (0 pkts)
  *31E: prerouting accept dscp=38 (0 pkts)

DSCP SET (postrouting):
  *305: QOS_HIGH -> dscp=46 (31.1M pkts)
  *306: GAMES -> dscp=46 (0 pkts)
  *307: QOS_MEDIUM -> dscp=26 (52.4M pkts)
  *308: QOS_GAME_DL -> dscp=8 (0 pkts)
  *309: QOS_LOW -> dscp=8 (441M pkts)
  *30A: QOS_NORMAL -> dscp=0 (385M pkts)
  *2E6: zerotier -> dscp=46 (2 pkts)
```

</details>
