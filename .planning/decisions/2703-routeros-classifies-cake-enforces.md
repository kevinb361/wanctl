# RouterOS classifies traffic and cake-shaper enforces the class

## Symptom
RouterOS already identifies host-aware QoS classes and WAN-routing intent, while cake-shaper owns the actual CAKE bottleneck queues. The bridge previously failed to import some RouterOS classes, causing encrypted VPN replies to fall into Bulk, while duplicated port and byte classifiers on both systems created asymmetric policy and drift risk.

References: `deploy/nftables/bridge-qos.nft`, `tests/test_bridge_qos_nft.py`, `docs/plans/2026-07-02-bridge-qos-dscp-trust-review.md`.

## Blast Radius
- Time window / scope: All internet flows crossing either inline WAN bridge after the contract is deployed.
- Recovery / reversal mechanism: Restore the pre-deploy bridge ruleset and RouterOS export, restart only the affected QoS service, and verify Best Effort forwarding before re-enabling differentiated treatment.
- Frequency: Steady-state classification and every adaptive-steering transition.
- Not affected: NAT ownership, route ownership, CAKE rates, autorate thresholds, VLAN policy, and the accepted split-edge topology.

## Evidence Links
- `deploy/nftables/bridge-qos.nft`
- `tests/test_bridge_qos_nft.py`
- `.planning/REQUIREMENTS.md` — v1.61 REQ-001 through REQ-006 and SAFE-24
- `docs/STEERING.md` — new-connection steering invariant
- `https://man7.org/linux/man-pages/man8/tc-cake.8.html` — DSCP tins and cross-host NAT limitation
- `https://man7.org/linux/man-pages/man8/tc-ctinfo.8.html` — conntrack-backed ingress DSCP restoration

## Default Disposition
Keep the accepted split edge. RouterOS is the authoritative classifier and WAN route selector because it sees pre-NAT host identity. DSCP is the normalized cross-system contract. cake-shaper is the authoritative queue enforcer: it validates router-originated classes, records them in bridge conntrack, washes untrusted carrier DSCP, restores the class on replies, and feeds CAKE. Bridge-local classification is fallback-only and must not duplicate host/application policy without a documented exception.

QoS priority and steering eligibility are independent policy dimensions. A high-priority class alone does not authorize a WAN change.

## Override Path
To move classification entirely onto cake-shaper, first approve a separate topology decision that gives Linux pre-NAT LAN identity by moving routing/NAT or relocating the shaper. That proposal must satisfy the existing DIY-router migration gates and revalidate fail-open behavior, routing, firewalling, per-host fairness, and both-WAN rollback.

Rollback for v1.61 is configuration-level: restore immutable pre-change nftables and RouterOS snapshots, validate syntax offline, deploy one WAN at a time, and confirm DNS/VPN/Best Effort forwarding before continuing. No live mutation is authorized by this record alone.

## Sign-Off
Accepted: YES — RouterOS classifies, DSCP carries intent, and cake-shaper enforces; steering remains separate.   Date: 2026-07-17   Operator: Kevin Blalock

> Authorized via the current Hermes session on 2026-07-17. Default Disposition accepted; Override Path NOT invoked. Recorded by Hermes Agent on operator instruction.
