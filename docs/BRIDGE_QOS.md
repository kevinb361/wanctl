# Bridge QoS: when to enable `allow_wash`

Use this guide when adding or reviewing a WAN that runs CAKE on the bridge host.
The decision is per WAN: preserve markings when the carrier and local network can
use them, and strip them when the upstream path has already collapsed everything
to best effort.

`allow_wash` is a per-WAN `cake_params` flag that lets the CAKE qdisc strip DSCP
markings on egress with the `wash` keyword. It defaults to `false` and is
intentionally opt-in: enabling it on the wrong topology costs you classification
you would otherwise keep.

## When to enable `allow_wash`

Enable `allow_wash: true` when the WAN is a consumer ISP path that does not
preserve DSCP markings beyond the carrier edge, and when your downstream LAN does
not depend on those markings for its own QoS policy. DOCSIS cable and most
consumer fiber deployments are the common cases: CAKE can still shape the link,
but carrying four diffserv tins forward implies a carrier behavior that usually
does not exist.

Keep `allow_wash: false` when the WAN is a transparent bridge, business-class
link, or other path where DSCP survives end-to-end. Also keep the default when
LAN-side gear consumes DSCP locally, such as WMM-tagged Wi-Fi or DSCP-aware
switch policy. In those deployments, `diffserv4` classification remains useful
and `wash` would remove signal that the rest of the path can actually use.

Briefly: `wash` means "stop pretending classification survives the carrier when
it does not." If the carrier preserves markings, keep `nowash`.

## Spectrum vs ATT: a worked contrast

| WAN      | Carrier path                   | DSCP survives? | `diffserv`   | `allow_wash` |
|----------|--------------------------------|----------------|--------------|--------------|
| Spectrum | DOCSIS cable; CMTS rewrites    | No             | `besteffort` | `true`       |
| ATT      | DSL; transparent link behavior | Yes            | `diffserv4`  | `false`      |

Spectrum's DOCSIS path rewrites markings upstream, so running `diffserv4` there
is classification theater: four tins whose labels do not survive the carrier.
`besteffort + wash` aligns the qdisc with what the link actually delivers.

ATT is the opposite worked example. The DSL path preserves useful markings, so
`diffserv4` remains the right shape and `allow_wash: false` protects the
classification that downstream gear can still consume.

## Why DSCP does not survive most consumer ISP topologies

DOCSIS CMTS hardware commonly rewrites or zeros DSCP as part of upstream carrier
policy. Consumer fiber PON deployments often do the same at the provider edge.
By the time packets leave that access network, they usually carry a single
carrier-chosen class, often DSCP `0` / best effort, regardless of what the CPE
marked before the handoff.

On those paths, a local `diffserv4` qdisc can still classify packets inside the
bridge, but the classification does not survive long enough to matter beyond the
access link. The result is extra tin machinery without downstream benefit.
`besteffort + wash` makes that loss explicit and avoids preserving a signal the
carrier will discard anyway.

Transparent bridges and QoS-preserving service classes are the exception. Older
DSL deployments, business circuits, and SLA-backed paths may carry DSCP through
the access network. There the classification the CPE marks is the classification
delivered, and `diffserv4 + nowash` is the safer default.

For deeper context on CAKE's tin model, see [SUBSYSTEMS.md](SUBSYSTEMS.md) and
the `cake` qdisc man page.

## See also

- [CONFIGURATION.md](CONFIGURATION.md) — `cake_params` schema and `allow_wash` entry
- [SUBSYSTEMS.md](SUBSYSTEMS.md) — CAKE tin model and shaper internals
- `configs/spectrum.yaml` — Spectrum worked example (`allow_wash: true`, `diffserv: besteffort`)
- `configs/att.yaml` — ATT worked example (`allow_wash: false`, default `diffserv4`)
