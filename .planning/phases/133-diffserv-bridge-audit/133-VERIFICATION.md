---
phase: 133-diffserv-bridge-audit
verified: 2026-04-03T16:00:52Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 133: Diffserv Bridge Audit Verification Report

**Phase Goal:** Operator knows exactly where DSCP marks are lost or preserved in the MikroTik-to-CAKE bridge path
**Verified:** 2026-04-03T16:00:52Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

Must-haves were loaded from `133-01-PLAN.md` frontmatter.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator knows whether MikroTik mangle rules set DSCP on traffic egressing toward cake-shaper | VERIFIED | Analysis §Test Environment §MikroTik Mangle Rules documents 9 relevant mangle rules including Trust EF, Trust AF4x, WASH WAN inbound, and 4 DSCP SET rules in postrouting |
| 2 | Operator can see the TOS byte value at each of 3 capture points for each DSCP class | VERIFIED (with note) | Table in §Hop-by-Hop Results shows TOS values at dev machine and ens17 for all 4 classes. br-spectrum column is "N/A (same path)" — explained in §Detailed Per-Class Results as structurally identical to ens17 at the L2 level. CAKE tin stats on ens16 serve as the third verification point. |
| 3 | Operator knows which CAKE tin receives each DSCP-marked flow | VERIFIED | Hop-by-hop table shows tin deltas for all 4 classes: EF→Voice (+100 pkts), AF41→Video (+113 pkts), CS0→BestEffort (+195 pkts), CS1→Bulk (+219 pkts) |
| 4 | Exact failure point in the DSCP path is identified and documented | VERIFIED | §Failure Point Identification: "There is no failure in the DSCP bridge path." Root cause of v1.26 observation: iperf3 --dscp does not set TOS byte on this Linux system — test tool was broken, not network |
| 5 | Fix strategy for Phase 134 is documented with specific options and tradeoffs | VERIFIED | §Fix Strategy documents 3 options with complexity ratings (Low/Medium/Low); §Recommended for Phase 134 identifies Option 1 (wanctl-check-cake extension) as recommended |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/phases/133-diffserv-bridge-audit/133-ANALYSIS.md` | Hop-by-hop DSCP audit results, failure point identification, fix strategy | VERIFIED | File exists (156 lines). Contains all required sections. All 4 DSCP classes tested with PASS results. No placeholder text found. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| MikroTik mangle rules | cake-shaper ens17 TOS byte | L2 bridge path | VERIFIED | §Detailed Per-Class Results confirms `tos 0xb8`, `tos 0x88`, `tos 0x20` appear on ens17 tcpdump matching source marks |
| ens17 TOS byte | CAKE tin counters | diffserv4 classification | VERIFIED | Tin delta table shows correct classification: all 4 DSCP classes landed in expected tins with quantified packet counts |

### Data-Flow Trace (Level 4)

Not applicable — this phase produces a documentation artifact, not runnable code. The "data" is packet captures and tc stats gathered manually on live equipment.

### Behavioral Spot-Checks

Step 7b SKIPPED — no runnable entry points. Phase deliverable is a documentation artifact (133-ANALYSIS.md), not executable code. The audit itself was the behavioral test; its results are recorded in the analysis document.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| QOS-01 | 133-01-PLAN.md | Operator can verify whether DSCP marks survive the L2 bridge path from MikroTik mangle to CAKE tins | SATISFIED | 133-ANALYSIS.md documents complete hop-by-hop results. All 4 DSCP classes (EF, AF41, CS0, CS1) tested with tcpdump at ens17 + CAKE tin stats. Operator can now verify marks survive (or detect if they stop surviving). |

**Orphaned requirements check:** REQUIREMENTS.md maps QOS-01 to Phase 133. No additional QOS requirements are assigned to Phase 133. QOS-02 and QOS-03 are assigned to Phase 134 and are not claimed by any Phase 133 plan — correctly out of scope.

**ROADMAP.md success criteria:**

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Each hop in the DSCP path (MikroTik mangle -> bridge interface -> CAKE qdisc) has been tested with marked packets | SATISFIED | MikroTik mangle state documented; ens17 captures show TOS bytes; CAKE tin stats show correct classification |
| The exact point where DSCP marks are lost or preserved is documented | SATISFIED | §Failure Point Identification: path is fully healthy; iperf3 --dscp identified as the broken tool |
| A fix strategy is identified (bridge config, ethtool, tc filter, or other) | SATISFIED | §Fix Strategy: 3 options documented. Since path is healthy, strategy pivots to validation tooling for Phase 134 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| 133-ANALYSIS.md | 148 | "Raw Data References" claims "ens17 and br-spectrum showing TOS bytes" but br-spectrum column is N/A throughout the results table | Info | Minor inconsistency in raw data attribution. Does not affect conclusions — the actual result data is correct. |

No blockers found. The discrepancy between the raw data reference and the N/A table cells is cosmetic — the analytical conclusions are fully supported by the ens17 captures and CAKE tin stats.

### Human Verification Required

#### 1. br-spectrum capture gap

**Test:** Confirm that the br-spectrum N/A cells are justified by the test methodology (upload direction flows through ens16 CAKE, not ens17). Verify the analysis document's statement that "bridge forwarding preserves L3 headers" is consistent with observed CAKE tin behavior.
**Expected:** The ens17 TOS values match source, and CAKE tin stats show correct classification — together these bound the bridge as transparent.
**Why human:** The gap between ens17 capture and CAKE tin stats logically implies the bridge is transparent, but no direct br-spectrum tcpdump was captured to confirm. An operator should verify the reasoning is sound for this production network.

#### 2. iperf3 --dscp breakage

**Test:** Run `getcap $(which iperf3)` and compare iperf3 build against one that correctly sets IP_TOS. Confirm whether the "broken iperf3 --dscp" finding applies only to this system or to all environments.
**Expected:** Either a missing capability or a build flag explains why --dscp does not set TOS.
**Why human:** The analysis documents the symptom (iperf3 sends tos=0x0 despite --dscp EF) but does not identify the root cause of the iperf3 breakage. This matters for future flent test validity.

---

## Gaps Summary

No blocking gaps. The phase goal is achieved: the operator now knows exactly where DSCP marks are (or are not) lost in the MikroTik-to-CAKE bridge path. The answer is: nowhere — the entire path works correctly.

The two human verification items are informational refinements, not blockers.

**Finding:** The v1.26 "diffserv tins not separating" observation was a false alarm caused by iperf3 --dscp not setting the TOS byte on this Linux system. The actual network path (MikroTik mangle → L2 bridge → CAKE diffserv4) functions correctly. Phase 134 recommendation is correctly pivoted from "fix tin separation" to "add DSCP verification tooling" (QOS-03).

---

_Verified: 2026-04-03T16:00:52Z_
_Verifier: Claude (gsd-verifier)_
