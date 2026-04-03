# Phase 134: Diffserv Tin Separation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 134-diffserv-tin-separation
**Areas discussed:** Download DSCP strategy, wanctl-check-cake extension, MikroTik mangle rules, Validation methodology

---

## Download DSCP Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| MikroTik prerouting DSCP marking | Add change-dscp rules in prerouting for download. After WASH + connection-mark, re-mark based on connection-mark. Marks survive through bridge to CAKE. | ✓ |
| Accept download BestEffort | CAKE triple-isolate handles download well. Document decision and move on. | |
| tc filter before CAKE on ens17 | Use tc filter with u32 classifiers. Complex, duplicates MikroTik logic. | |

**User's choice:** MikroTik prerouting DSCP marking

### Follow-up: Forward Chain DSCP

| Option | Description | Selected |
|--------|-------------|----------|
| Prerouting only | Mark in prerouting after WASH. Simpler. | |
| Both prerouting and forward | Belt and suspenders. | |
| You decide based on testing | Try prerouting first, pivot if needed. | ✓ |

**User's choice:** Data-driven — try prerouting first

---

## wanctl-check-cake Extension

| Option | Description | Selected |
|--------|-------------|----------|
| Tin distribution threshold | Read per-tin packet counts. Flag if non-BestEffort tins have 0 packets. PASS/WARN verdict. | ✓ |
| Active probe test | Send DSCP-marked test packets, verify correct tin. More thorough but slower. | |
| Both passive + active | Default passive, --active for probe. | |

**User's choice:** Tin distribution threshold (passive)

### Follow-up: AlertEngine Integration

| Option | Description | Selected |
|--------|-------------|----------|
| CLI check only | Manual diagnostic tool. Runtime monitoring in Phase 136. | ✓ |
| Add AlertEngine integration | Discord alert on degenerate distribution. Adds coupling. | |

**User's choice:** CLI check only

---

## MikroTik Mangle Rule Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror postrouting pattern | Same connection-mark→DSCP mapping. Only match in-interface-list=WAN. | ✓ |
| Simplified 2-tier | Just EF + CS1. Less rules, less separation. | |
| You decide based on what works | Try full mirror, fall back if needed. | |

**User's choice:** Mirror postrouting pattern

### Follow-up: Apply Method

| Option | Description | Selected |
|--------|-------------|----------|
| REST API from plan | curl commands to MikroTik REST API. Reproducible, documentable. | ✓ |
| Manual via Winbox/SSH | Manual apply, executor verifies. Safer but not reproducible. | |

**User's choice:** REST API

---

## Validation Methodology

| Option | Description | Selected |
|--------|-------------|----------|
| Python sockets + tc tin stats | Same proven Phase 133 approach. Send DSCP packets, read tin deltas. Test both directions. | ✓ |
| iperf3 data stream + tc stats | More representative but requires careful filtering. | |
| Production traffic observation | Real traffic over 10-30 min. Slowest. | |

**User's choice:** Python sockets + tc tin stats

---

## Claude's Discretion

- Exact MikroTik mangle rule ordering
- Whether prerouting DSCP rules go before or after connection-mark assignment
- Tin distribution threshold percentage
- Whether to also verify with iperf3 -R as secondary

## Deferred Ideas

None -- discussion stayed within phase scope
