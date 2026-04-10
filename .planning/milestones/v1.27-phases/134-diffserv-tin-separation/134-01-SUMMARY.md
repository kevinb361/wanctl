---
phase: 134
plan: 01
status: complete
started: 2026-04-03
completed: 2026-04-03
---

# Plan 134-01: MikroTik Prerouting DSCP SET DL — Summary

## One-liner

Prerouting DSCP marking attempted but can't reach download CAKE — bridge processes packets before MikroTik; endpoint-set DSCP (EF for VoIP) works; download BestEffort accepted as architectural reality

## What Was Built

Attempted to add 4 MikroTik prerouting `change-dscp` rules for download direction. Rules were created via REST API, repositioned before the `passthrough=false` packet-mark rules, and confirmed matching traffic (2,487 HIGH, 478 MEDIUM, 26,510 LOW, 12,711 NORMAL in 60s). However, ens17 CAKE tin stats showed no change in Video/Bulk tins because:

**Architectural limitation confirmed:** CAKE on ens17 egress processes download packets as they leave the bridge toward the router. MikroTik's prerouting runs AFTER the packet has already been through CAKE. The DSCP marks arrive too late.

**What does work:**
- Upload DSCP: MikroTik postrouting marks survive through bridge to ens16 CAKE (confirmed Phase 133)
- Endpoint-set DSCP: Applications that set their own DSCP (VoIP EF, VPN EF) survive the bridge and land in correct CAKE tins on download
- Voice tin: 96M packets (8.1% of download) from endpoint-set EF marks

**Decision: Accept download BestEffort.** CAKE's `triple-isolate` flow fairness handles download bufferbloat. Endpoint-set DSCP provides Voice tin separation for the traffic that matters most (VoIP/VPN).

## Key Decisions

- MikroTik prerouting DSCP SET DL rules created, tested, and rolled back
- Discovered `passthrough=false` on WAN packet-mark rules required repositioning (rules 9-10 terminate chain)
- After repositioning, rules matched traffic but CAKE tin stats proved marks arrive after CAKE processing
- Accepted download BestEffort as the correct architectural decision for bridge-before-router topology

## Key Files

### Created
- (none — MikroTik runtime state changes, all rolled back)

## Deviations

- **Prerouting approach failed:** Rules matched traffic but CAKE processes packets before MikroTik touches them. This was the core hypothesis from Phase 133 Option 1 — now definitively disproven.
- **Rollback executed:** All 4 DSCP SET DL rules deleted. MikroTik prerouting chain restored to original 44 rules.
- **Scope change:** QOS-02 success criterion 1 met via "documented acceptance of current architecture" path (the alternative success criterion in the roadmap).

## Issues Encountered

- `passthrough=false` on WAN packet-mark rules (positions 9-10) initially prevented DSCP SET DL rules from executing — required moving rules before packet marks
- Even after correct positioning, the fundamental bridge-before-router architecture means download CAKE can't see MikroTik-applied DSCP

## Self-Check: PASSED

- [x] MikroTik prerouting DSCP approach tested and documented
- [x] Architectural limitation confirmed with data (rule counters vs tin stats)
- [x] Rules rolled back cleanly
- [x] QOS-02 criterion 1 met via "documented acceptance" path
- [x] Upload direction confirmed working (no regression)
