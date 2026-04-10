# Phase 141: Bridge Download DSCP Classification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 141-bridge-download-dscp-classification
**Areas discussed:** Classification Ruleset Scope, Endpoint DSCP Interaction, Dual-WAN Deployment, Persistence and Lifecycle

---

## Classification Ruleset Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Moderate + conntrack (Recommended) | 15-25 rules with NF_CONNTRACK_BRIDGE. Voice, Bulk demotion, large-flow via ct bytes. | ✓ |
| Minimal stateless | 5-10 rules, port matching only. Simple but no large-flow demotion. | |
| Full MikroTik mirror | 40+ rules replicating full hierarchy. Maximum parity but high maintenance. | |

**User's choice:** Moderate + conntrack (Recommended)
**Notes:** Enables the biggest practical win (large-flow demotion) without the maintenance burden of a full mirror.

---

## Endpoint DSCP Interaction

| Option | Description | Selected |
|--------|-------------|----------|
| Trust and skip (Recommended) | Check existing DSCP first -- if non-zero, accept. Only classify DSCP 0. | ✓ |
| Always override | Bridge rules always set DSCP regardless. Would break VoIP phone EF. | |
| Selective trust | Trust EF and AF4x, override everything else. More complex. | |

**User's choice:** Trust and skip (Recommended)
**Notes:** Preserves existing VoIP phone EF marks that already work through the bridge. Matches MikroTik's Trust EF design.

---

## Dual-WAN Deployment

| Option | Description | Selected |
|--------|-------------|----------|
| Both WANs (Recommended) | Spectrum and ATT bridges, same base ruleset with iif/oif guards. | ✓ |
| Spectrum only | Only Spectrum bridge. ATT stays 100% Best Effort on download. | |
| Both with WAN-specific rules | Shared base plus WAN-specific additions. More complex. | |

**User's choice:** Both WANs (Recommended)
**Notes:** Both WANs benefit from download QoS. Work VPN on ATT gets proper Voice classification on download too.

---

## Persistence and Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Systemd oneshot service (Recommended) | wanctl-bridge-qos.service, rule file at /etc/wanctl/bridge-qos.nft. | ✓ |
| /etc/nftables.conf | System nftables config. Simpler but mixes with potential firewall rules. | |
| Integrate into wanctl startup | Python code changes, couples to wanctl lifecycle. | |

**User's choice:** Systemd oneshot service (Recommended)
**Notes:** Follows established pattern from wanctl-nic-tuning.service (v1.25). Independent of wanctl lifecycle.

---

## Claude's Discretion

- Rule ordering and chain priority
- Single chain vs per-WAN chains
- NF_CONNTRACK_BRIDGE module loading approach
- Large-flow demotion threshold tuning
- Video tin classification (deferred)

## Deferred Ideas

- Video tin classification for streaming (port 443 ambiguity)
- wanctl-check-cake integration for bridge QoS verification
- Address-list-style matching on bridge (gaming server IPs)
- ATT-specific Work VPN download classification
