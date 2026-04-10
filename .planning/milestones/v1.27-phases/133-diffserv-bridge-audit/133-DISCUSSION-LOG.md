# Phase 133: Diffserv Bridge Audit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 133-diffserv-bridge-audit
**Areas discussed:** Audit methodology, Test traffic generation, Documentation format, Fix strategy scope

---

## Audit Methodology

| Option | Description | Selected |
|--------|-------------|----------|
| Hop-by-hop tcpdump + tc stats | Capture at each hop checking DSCP byte, cross-reference with tc tin counters. Pinpoints exact break. | ✓ |
| tc tin stats only | Just send marked traffic and check tin landing. Confirms IF lost, not WHERE. | |
| nftables DSCP counters | nftables rules at bridge ingress/egress counting by DSCP class. Non-invasive but requires nftables expertise. | |

**User's choice:** Hop-by-hop tcpdump + tc stats

### Follow-up: Capture Points

| Option | Description | Selected |
|--------|-------------|----------|
| 3-point: MikroTik, bridge NIC, CAKE ingress | 1) MikroTik sniffer/torch. 2) tcpdump on physical NIC. 3) tcpdump on bridge interface. Plus tc tin stats. | ✓ |
| 2-point: bridge NIC + CAKE tins | Skip MikroTik capture. Faster but can't distinguish MikroTik vs bridge as culprit. | |

**User's choice:** 3-point capture

---

## Test Traffic Generation

| Option | Description | Selected |
|--------|-------------|----------|
| iperf3 --dscp from dev machine | iperf3 with --dscp flag, server on Dallas. Tests real end-to-end path. Same tooling as flent. | ✓ |
| nping with specific TOS bytes | Craft packets with exact TOS/DSCP. More control but not representative of real traffic. | |
| MikroTik mangle test rules | Temporary mangle rules marking all traffic from test IP. Tests actual production marking path. | |

**User's choice:** iperf3 --dscp from dev machine

### Follow-up: DSCP Classes to Test

| Option | Description | Selected |
|--------|-------------|----------|
| All 4 CAKE tins | EF (Voice), CS5/AF41 (Video), CS0 (Best Effort), CS1 (Bulk). Complete diffserv4 coverage. | ✓ |
| Just EF + BE | Minimal: Voice vs default. Fast but incomplete. | |

**User's choice:** All 4 CAKE tins

---

## Documentation Format

| Option | Description | Selected |
|--------|-------------|----------|
| Hop-by-hop results table + fix strategy | Markdown table per hop + Fix Strategy section. In .planning/ as analysis doc feeding Phase 134. | ✓ |
| Full docs/ document | Permanent docs/DIFFSERV_AUDIT.md with diagrams and captures. Heavier, may be overkill. | |

**User's choice:** Hop-by-hop results table + fix strategy

---

## Fix Strategy Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Identify break + recommend fix, no implementation | Document WHERE lost and WHAT fix options are. Phase 134 implements. Clean audit/fix separation. | ✓ |
| Identify break + prototype fix | Also test a candidate fix during audit. Faster validation but blurs phase boundary. | |
| You decide based on findings | Apply trivial fixes during audit, defer complex ones. | |

**User's choice:** Identify break + recommend fix, no implementation

---

## Claude's Discretion

- tcpdump filter expressions for DSCP capture
- MikroTik sniffer/torch configuration
- iperf3 session parameters
- Whether to test both download and upload paths
- Analysis document structure

## Deferred Ideas

None -- discussion stayed within phase scope
