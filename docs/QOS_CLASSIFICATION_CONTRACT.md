# QoS Classification Contract

Status: accepted architecture; implementation tracked by Saga milestone v1.61.

## Decision

The current split edge remains in place:

```text
LAN → RouterOS classifier/NAT/router → cake-shaper bridge/CAKE → WAN
```

RouterOS is the authoritative classifier and WAN route selector. cake-shaper is the authoritative queue enforcer. DSCP is the explicit contract carried from RouterOS to the bridge; Linux bridge conntrack reflects that class onto download replies before CAKE.

This is not “QoS on both boxes.” One system decides intent; the other enforces it at the bottleneck.

## Why

- RouterOS sees original LAN addresses, VLAN/device policy, connection state, and the route decision before NAT.
- cake-shaper sees post-NAT flows and cannot recover LAN host identity. CAKE's `nat` lookup has no practical effect when NAT occurs on another host.
- WAN steering happens before packets reach cake-shaper, so Linux-only classification cannot drive RouterOS policy routing.
- CAKE consumes DSCP and owns the bottleneck queue; it must receive the class before enqueueing each direction.
- Bridge conntrack can learn the class from an outbound request and restore it on the encrypted reply path, including VPN-over-HTTPS traffic that cannot be classified reliably by port alone.

Primary references:

- RFC 2474 — Differentiated Services architecture and boundary marking.
- RFC 4594 — service-class guidance.
- `tc-cake(8)` — DiffServ tins, `wash`, flow isolation, and cross-host NAT limitation.
- `tc-ctinfo(8)` — conntrack-backed DSCP restoration for ingress queueing.
- RouterOS Mangle documentation — internal marks versus transmitted DSCP.

## Contract

| Intent | RouterOS class | DSCP emitted | Bridge ct mark | CAKE diffserv4 tin |
|---|---|---:|---:|---|
| Realtime / critical | `QOS_HIGH` | EF (46) | `0x4` | Voice |
| Interactive / video | `QOS_MEDIUM` | AF31 (26) | `0x2` | Video |
| Normal | `QOS_NORMAL` | CS0 (0) | `0x0` | Best Effort |
| Sustained / scavenger | `QOS_LOW` | CS1 (8) | `0x1` | Bulk |

### Trust boundary

- Trust normalized DSCP only when a packet enters cake-shaper from a router-facing WAN interface.
- Do not trust carrier-provided DSCP. Wash modem-facing download traffic before restoring the local contract.
- An existing nonzero bridge connection mark wins over fallback classification.
- Unclassified traffic remains Best Effort.
- FastTrack on RouterOS must remain disabled or be mechanically proven not to bypass classification.

#### RouterOS client-marker risk acceptance (v1.62)

Early EF/AF4x client-marker trust remains intentionally broad rather than accidentally
unreviewed. A bounded source-attribution window found legitimate EF use by infrastructure,
operator, mobile, and work endpoints; AF4x was quiet during the window despite substantial
historical use, so a safe complete allowlist could not be proven. The operator explicitly
accepted the residual LOW scheduling-abuse risk on 2026-07-20 instead of narrowing blindly.
WAN and IoT ingress are washed first, firewall authorization is unaffected, and CAKE diffserv4
threshold isolation limits starvation. Revisit this acceptance if privileged-tin abuse,
congestion impact, or an untrusted marker source is observed. This acceptance does not authorize
new trust rules or weaken wash ordering.

### Ownership

RouterOS owns:

- host, VLAN, device-list, service, and connection-size policy;
- normalized DSCP emission;
- NAT and WAN routing;
- explicit steering eligibility.

cake-shaper owns:

- WAN DSCP trust enforcement and carrier wash;
- DSCP-to-bridge-conntrack import;
- reply-path class restoration;
- CAKE tin scheduling, AQM, shaping rates, and autorate;
- conservative fallback classification only where the RouterOS-originated half cannot seed state.

## Steering is not QoS

Queue priority answers “which packet should leave the congested queue first?” WAN steering answers “which route should a new connection use?” They must not share an implicit `QOS_HIGH → AT&T` policy.

The target steering behavior is:

- apply only to explicitly eligible new connections;
- preserve established connection path/NAT affinity;
- keep recursive DNS on an intentional stable route unless a separate resolver-failover policy says otherwise;
- preserve forced-WAN source/destination policy independently of QoS class.

## Current implementation status

1. RouterOS application equivalence is live-proven for generic RTP `16384-32767`, WireGuard `51820`, SSH `22`, UDP `3480`, and NNTP `119`; the read-only contract audit is overall PASS.
2. Spectrum and ATT duplicate bridge fallbacks are retired and live-verified. Each broader UDP `3478-3480` fallback is narrowed to `3478-3479` so the non-equivalent STUN ports remain classified.
3. Symmetric AF31 upload import is live on both WANs at reviewed ruleset hash `a6b85d55...04884`. The load-aware v2 canary proved one AF31 import per upload chain, exact immutable rollback, RouterOS audit PASS, wanctl `25/25`, healthy DNS/HTTPS/service state, and preserved CAKE handles/`diffserv4`/four-tin continuity without generated traffic.
4. Existing steering and traffic-shaping documentation still contains stale live-mode and qdisc assumptions outside this bounded retirement slice.
5. The repo/live bridge ruleset has intentionally retained comment-only raw-hash drift. Fresh v1.62 proof shows 55/55 ordered executable lines equal, both files pass nft syntax, and the five-chain/41-rule loaded table is semantically equal to repo. Repo comments are authoritative; no nftables reload is justified solely to converge prose. Any executable, order, chain, or loaded-table mismatch remains fail-closed drift.
6. Disabled `QOS_GAME_DL → CS1` output remains intentionally dormant. It has no producer, script, or scheduler reference and remains at zero counters; disabled state prevents matching and audit overhead. Standalone deletion offers no runtime benefit and would add mutation/rollback risk. Reopen only if its state/counters/fields change, a producer appears, or a broader approved dead-rule cleanup includes exact positional rollback.

## Implementation sequence

1. Complete and test AF31 import on both WAN upload chains. **Repo-verified 2026-07-17; live-verified 2026-07-18.**
2. Prove the full four-class mapping and Best Effort fallback mechanically. **Repo-verified 2026-07-17; live-verified 2026-07-18.**
3. Add a read-only RouterOS contract audit before changing live mangle policy. **Implemented and live-verified 2026-07-17 in `infra-ansible`; RouterOS unchanged.**
4. Separate steering eligibility from QoS class; preserve new-connection-only behavior and stable DNS routing. **Live-verified 2026-07-17: the daemon toggles only `ADAPTIVE: Work VPN eligible for ATT`, reconciles that exact rule to its persisted logical state once at startup, and the broad QoS-coupled route and installer are retired. Approval-gated migration, demigration, remigration, and final 50/50 DNS probes per resolver passed.**
5. Remove duplicated bridge classifiers incrementally only after equivalent contract coverage is proven. **Completed and live-verified Spectrum-first then ATT on 2026-07-18.**
6. Deploy one WAN at a time with immutable rollback snapshots and controlled-load verification. **Completed with immutable backups; the prior controlled-load proof and bounded natural/load-aware checks remain recorded in the milestone evidence.**

## Verification contract

The RouterOS side is audited from the canonical automation boundary:

```bash
cd ~/projects/infra-ansible
make routeros-qos-contract-audit
python3 scripts/routeros-qos-contract-audit.py --strict
```

The audit uses the vaulted `ai-readonly` wrapper and checks FastTrack, the four-class DSCP
map, wash-before-trust ordering, and QoS-independent steering eligibility. The normal mode
reports warnings without blocking inspection; strict mode exits nonzero for warnings and
failures.

A live canary is not successful until evidence shows:

- DNS remains responsive during a sustained Bulk transfer;
- the work VPN connects and an inner service remains reachable;
- Voice, Video, Best Effort, and Bulk CAKE counters move as expected;
- Spectrum and AT&T behave consistently;
- established connections do not switch WAN unexpectedly;
- rollback restores the previous ruleset and healthy forwarding.

### Bounded four-class packet proof

`scripts/qos-spectrum-packet-proof.sh` is the action-gated Spectrum proof surface for the
transmitted contract. Dry-run prints the exact plan without SSH or traffic. Live mode requires
both `QVT-002` and `SAFE-25` confirmation tokens plus an operator-controlled target. It sends
five short flows for TCP/22, TCP/443, TCP/119, and UDP/9, then requires exact EF(46), AF31(26),
CS1(8), and CS0(0) observations at `cake-shaper/spec-router` ingress. TCP evidence is restricted
to new SYN packets so established traffic cannot contaminate a selector; the analyzer accepts
the live multiline `tcpdump -vv` record shape. CAKE must remain healthy and `diffserv4` before
and after, and after-snapshots are retained even when packet analysis fails. The harness has no
bulk payload, throughput target, config mutation, service restart, or implicit authorization to
run.

### IoT wash proof

`scripts/qos-iot-wash-proof.sh` retains the separately gated one-packet QVT-003 proof surface.
Dry-run emits no SSH or traffic. Live mode requires exact `QVT-003` and `SAFE-25` tokens, an
exact applied-policy SHA-256 before and after, and one EF-marked ICMP echo from the existing
VLAN-120 source to its local gateway. Acceptance targets the exact source-subnet canary—not the
known-unreachable legacy rule—and requires exact fields/order, source TOS `0xb8`, canary +1
packet with positive bytes, and continued EF/AF4x exclusion of `vlan120-IOT`.

**Current live status (2026-07-20):** the original approved source capture proved one
EF-marked VLAN120 request while the interface-matched wash stayed at zero. Read-only flow
inspection attributed that mismatch to using logical `vlan120-IOT` as a prerouting ingress
matcher on the tagged bridge/trunk path. A separately approved additive source-subnet wash is
now active immediately before the untouched legacy rule. Two read-only stats snapshots ten
seconds apart showed the exact canary move `1429/377172 → 1458/385374` while the legacy rule
remained `0/0`, with strict audit PASS and stable applied policy hash. This natural traffic
closes the selector/action-path ambiguity without another generated packet. Because organic
IoT traffic moved the canary by 29 packets during ten seconds, an exact +1 packet attribution
would not be deterministic; no re-proof execution is approved or needed for QVT-003. The
harness remains fail-closed rather than weakening acceptance to “at least one.” Permanent
promotion or legacy-rule removal remains a separate mutation decision.

## Structural limitation

Because RouterOS performs NAT on another host, cake-shaper cannot provide true per-LAN-host CAKE fairness from the addresses it sees. Solving that requires a topology change, not more nftables classification. That work is outside v1.61.

## Saga records

- Roadmap: `.planning/ROADMAP.md` — v1.61
- Requirements: `.planning/REQUIREMENTS.md` — REQ-001 through REQ-006
- Decision: `.planning/decisions/2703-routeros-classifies-cake-enforces.md`
- Context glossary: `.planning/CONTEXT.md`
