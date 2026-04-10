---
phase: 133
plan: 01
status: complete
started: 2026-04-03
completed: 2026-04-03
---

# Plan 133-01: DSCP Path Audit — Summary

## One-liner

DSCP marks survive the entire MikroTik→bridge→CAKE path; v1.26 "tins not separating" was caused by broken iperf3 --dscp, not a network issue

## What Was Built

Conducted a 3-point DSCP audit of the MikroTik-to-CAKE bridge path using tcpdump captures and CAKE tin stats. Tested all 4 diffserv4 classes (EF, AF41, CS0, CS1) using Python sockets with explicit IP_TOS. Discovered that:

1. **Bridge preserves DSCP marks** — TOS bytes survive MikroTik routing + Linux bridge unchanged
2. **CAKE diffserv4 classifies correctly** — EF→Voice, AF41→Video, CS1→Bulk, CS0→BestEffort
3. **iperf3 --dscp is broken** on this system — doesn't actually set TOS byte, causing false v1.26 findings
4. **MikroTik mangle rules are comprehensive** — Trust rules for existing DSCP, connection-mark-based DSCP SET in postrouting

## Key Decisions

- Used Python `socket.setsockopt(IPPROTO_IP, IP_TOS, ...)` instead of iperf3 --dscp after discovering iperf3 doesn't set TOS
- Tested upload direction on ens16 CAKE (where Python test packets are shaped) rather than ens17 (download)
- Pivoted Phase 134 recommendation from "fix tin separation" to "validate and automate DSCP verification"

## Key Files

### Created
- `.planning/phases/133-diffserv-bridge-audit/133-ANALYSIS.md` — Complete audit results with hop-by-hop table, failure analysis, and fix strategy

## Deviations

- **iperf3 --dscp doesn't work** — the original plan called for iperf3-based testing. Switched to Python sockets for definitive results.
- **No bridge DSCP failure found** — the audit proved the path is healthy. Phase 134 recommendation pivoted from "fix" to "validate and automate."
- **Tasks executed by orchestrator directly** — checkpoint tasks were run by the orchestrator via SSH rather than requiring human paste-back, per user instruction.

## Issues Encountered

None — all diagnostic commands completed successfully. The biggest surprise was that the "problem" from v1.26 doesn't exist.

## Self-Check: PASSED

- [x] 133-ANALYSIS.md exists with hop-by-hop results
- [x] All 4 DSCP classes tested (EF, AF41, CS0, CS1)
- [x] Failure point identified (none — path is healthy)
- [x] Fix strategy documented with Phase 134 recommendations
- [x] QOS-01 satisfied: operator can verify DSCP marks survive bridge path
