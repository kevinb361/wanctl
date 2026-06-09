# DSCP Survival Trace Map

This is the DSCP-01 path map for Phase 225. It documents where DSCP is set,
preserved, stripped, or only assumed along the Spectrum path before any
production-touching A/B work. No external network gear was mutated, the Spectrum
CAKE mode was not changed, the `bridge qos` nftables table was not reloaded, and
no `tc` probe was attached.

## Stage map

| Direction | Stage | Set / preserve / strip status | Observation point | Evidence status |
| --- | --- | --- | --- | --- |
| DL | Carrier / CMTS to `spec-modem` ingress | Historically strips or zeros upstream DSCP on Spectrum DOCSIS; current packet field must be observed in Phase 225-02 before it can feed a verdict. | Future `spec-modem`/CAKE-ingress capture from 225-02. | Historical premise from v1.44; not live-verified by this map. |
| DL | CRS hardware QoS trust | Preserves endpoint-set marks when configured to trust DSCP. | CRS/Ruckus/RouterOS read-only artifact, if captured separately. | **Documented assumption, not live-verified**; does not feed the DSCP-03 verdict. |
| DL | Ruckus QoS mirroring | May mirror endpoint QoS/DSCP treatment through the Wi-Fi/LAN side. | Ruckus/CRS read-only artifact, if captured separately. | **Documented assumption, not live-verified**; does not feed the DSCP-03 verdict. |
| DL | cake-shaper bridge `spectrum_dl` chain | Preserves non-zero endpoint DSCP via trust-and-skip, then sets EF/AF41/CS1 for matched download flows. | `deploy/nftables/bridge-qos.nft`; runtime read captured by `scripts/phase225-dscp-trace.sh` as `nft-bridge-qos-before.txt`/`after.txt`. | Repo rules verified; runtime counters may be unavailable. |
| DL | CAKE egress on `spec-router` | CAKE can classify by DSCP at enqueue when `diffserv4`; production is currently `besteffort wash`, so tin counters cannot prove survival. | `tc-qdisc-spec-router.txt`, `tc-filter-spec-router.txt`, and 225-02 pre-wash DSCP histogram. | Qdisc/filter state is read-only evidence; 225-02 histogram is authoritative for verdict. |
| UL | `spec-router` ingress / LAN-originated upload | Preserves whatever router/client-originated DSCP reaches the bridge; this phase does not assert CRS/Ruckus state as live fact. | 225-02 UL probe/histogram on path to `spec-modem`. | Future evidence; UL is corroborating-only for the DL verdict. |
| UL | CAKE egress on `spec-modem` | CAKE can classify upload by DSCP if candidate mode is later enabled; current trace only reads qdisc/filter state. | `tc-qdisc-spec-modem.txt`, `tc-filter-spec-modem.txt`. | Read-only evidence; not a Phase 226 unblock by itself. |

## Bridge rules that set or preserve DSCP

The bridge stage is the local point that can invalidate the old “carrier strips
DSCP, so Spectrum diffserv is theater” premise by setting marks locally before
CAKE enqueue.

- `deploy/nftables/bridge-qos.nft:38-88` defines the `spectrum_dl` chain.
- `deploy/nftables/bridge-qos.nft:42` is the trust-and-skip rule:
  `ether type ip ip dscp != 0 accept`. Non-zero endpoint marks pass untouched.
- `deploy/nftables/bridge-qos.nft:47-49` restores DSCP from connection marks:
  EF, AF41, and CS1.
- `deploy/nftables/bridge-qos.nft:53-85` sets EF/AF41/CS1 on matched new or
  large Spectrum download flows.
- `deploy/nftables/bridge-qos.nft:129-133` dispatches Spectrum download traffic
  with `iif spec-modem oif spec-router jump spectrum_dl`, before the CAKE egress
  qdisc on `spec-router`.

The checked-in `ip dscp set` rules do not carry explicit `counter` statements.
Therefore a runtime `nft list table bridge qos` capture may not expose per-rule
packet/byte counters for those rules.

## Live counter snapshot

`scripts/phase225-dscp-trace.sh` writes the live counter channel to
`bridge-mark-counters.txt`. Consumers should read the first two lines verbatim:

```text
COUNTERS_AVAILABLE=<true|false>
COUNTER_MODE=<delta|snapshot|unavailable>
```

Interpretation:

- `COUNTERS_AVAILABLE=false` means no explicit `counter packets <N> bytes <M>`
  clause was present on the runtime `ip dscp set ef|af41|cs1` rules. This maps to
  `bridge_counter_signal=unknown`, **not** `negligible`.
- `COUNTER_MODE=delta` means the script computed before/after per-rule packet and
  byte deltas over the bounded `--counter-window`.
- `COUNTER_MODE=snapshot` means only cumulative state was available; that is also
  `unknown` for verdict purposes because it is stale state, not a load window.

The bridge counter channel is corroborating only. The authoritative DL signal for
the DSCP-03 verdict is the Phase 225-02 pre-wash CAKE-ingress DSCP histogram and
the deliberately marked DL EF probe, with the sample-quality and source-proof
rules from `225-RESEARCH.md`.

## Public-safety and mutation boundary

- Public-safe host aliases and LAN IPs already used in committed project docs are
  acceptable; no private credentials are included here.
- CRS trust and Ruckus QoS mirroring are intentionally labeled as documented
  assumptions unless a future read-only artifact proves them.
- This file does not claim that RouterOS REST at `10.10.99.1` proves CRS or
  Ruckus state; a vague router reference is not device evidence.
