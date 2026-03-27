---
phase: 113-network-engineering-audit
verified: 2026-03-26T20:45:00Z
status: gaps_found
score: 5/5 must-haves verified (all substantive), 1 tracking inconsistency
re_verification: false
gaps:
  - truth: "REQUIREMENTS.md correctly reflects NETENG-03 and NETENG-04 as complete"
    status: failed
    reason: "NETENG-03 and NETENG-04 remain marked [ ] Pending in REQUIREMENTS.md despite being completed. The NETENG-03/04 checkbox updates were made in commit 924a8a1 but were lost when the Wave 1 merge (e71000e) resolved conflicts without including REQUIREMENTS.md changes. The phase 113 summary list in ROADMAP.md also remains [ ] unchecked."
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "Lines 25-26 show [ ] for NETENG-03 and NETENG-04; lines 92-93 show Pending. Should be [x] Complete."
      - path: ".planning/ROADMAP.md"
        issue: "Line 19 shows '- [ ] **Phase 113: Network Engineering Audit**' -- the checklist marker was never updated to [x] after phase completion."
    missing:
      - "Mark NETENG-03 [x] complete in REQUIREMENTS.md checkbox list and status table"
      - "Mark NETENG-04 [x] complete in REQUIREMENTS.md checkbox list and status table"
      - "Mark Phase 113 [x] complete in ROADMAP.md summary list (line 19)"
human_verification:
  - test: "Confirm production CAKE qdiscs are still running with correct parameters"
    expected: "tc -j qdisc show on cake-shaper (10.10.110.223) shows 4 CAKE qdiscs with overhead=18/22, diffserv4, memlimit=33554432"
    why_human: "Production system -- cannot SSH from verifier; parameters may drift if wanctl was restarted or reconfigured since audit"
---

# Phase 113: Network Engineering Audit Verification Report

**Phase Goal:** CAKE configuration, DSCP mapping, steering logic, and measurement methodology are verified correct on the production VM
**Verified:** 2026-03-26T20:45:00Z
**Status:** gaps_found (tracking inconsistency only -- all substantive work complete)
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CAKE parameters per WAN verified via tc -j qdisc show readback | VERIFIED | 113-01-findings.md contains 4 comparison tables (Spectrum UL/DL, ATT UL/DL) with YES for all tracked params; raw JSON readback included |
| 2 | DSCP end-to-end trace documented (EF=Voice, AF41=Video, CS1=Bulk) | VERIFIED | 113-01-findings.md contains complete 4-stage MikroTik mangle pipeline, DSCP-to-tin table, end-to-end flow diagram, and classification summary table |
| 3 | Steering logic audit: confidence weights, degrade timers, CAKE-primary invariant | VERIFIED | 113-02-findings.md documents all 10 ConfidenceWeights values, full timer comparison table (11/11 match), 6-point CAKE-primary invariant evidence |
| 4 | Measurement methodology validated: reflector selection, signal chain, IRTT vs ICMP paths | VERIFIED | 113-02-findings.md contains full signal chain flow (7 steps), IRTT/ICMP/TCP path documentation with rationale, reflector scoring parameters, production config capture |
| 5 | Queue depth and memory pressure baseline documented from production tc -s qdisc show | VERIFIED | 113-03-findings.md contains idle and load statistics for all 4 qdiscs, memory pressure table (1.6%-60.9%), per-tin breakdown, drop/ECN analysis |
| 6 | REQUIREMENTS.md reflects all 5 NETENG requirements as complete | FAILED | NETENG-03 and NETENG-04 remain [ ] Pending due to merge conflict residue (commit e71000e dropped REQUIREMENTS.md updates from 924a8a1) |

**Score:** 5/5 substantive must-haves verified. 1 tracking document inconsistency.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/phases/113-network-engineering-audit/113-01-findings.md` | CAKE parameter verification + DSCP trace | VERIFIED | 505 lines, contains NETENG-01 and NETENG-02 sections with comparison tables, raw JSON, MikroTik mangle rules, flow diagram |
| `.planning/phases/113-network-engineering-audit/113-02-findings.md` | Steering logic + measurement methodology | VERIFIED | 370 lines, contains NETENG-03 and NETENG-04 sections with scoring formula, timer table, signal chain, IRTT/ICMP/TCP paths |
| `.planning/phases/113-network-engineering-audit/113-03-findings.md` | Queue depth and memory pressure baseline | VERIFIED | 241 lines, contains NETENG-05 section with idle/load stats, memory pressure analysis, per-tin breakdown |
| `.planning/REQUIREMENTS.md` (NETENG-03, NETENG-04) | Marked [x] complete | FAILED | Lines 25-26 show [ ] Pending; lines 92-93 show "Pending" in status table. Caused by merge e71000e dropping REQUIREMENTS.md changes from 924a8a1. |
| `.planning/ROADMAP.md` (Phase 113 list marker) | Marked [x] complete | FAILED | Line 19 shows "- [ ] **Phase 113:**" -- never updated to [x] after completion. Status table at line 117 correctly shows "Complete". |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `/etc/wanctl/spectrum.yaml` | tc -j qdisc show | CAKE param readback comparison | WIRED | Findings show config values (docsis->overhead=18, memlimit=32mb) matched against actual tc JSON (overhead:18, memlimit:33554432). Raw JSON included. |
| `/ip/firewall/mangle` | CAKE diffserv4 tins | DSCP classification chain | WIRED | 56 mangle rules captured; EF(46)->Tin3(Voice), AF31(26)->Tin2(Video), CS0(0)->Tin1(BE), CS1(8)->Tin0(Bulk) confirmed |
| `steering_confidence.py` | `daemon.py` | ConfidenceController integration | WIRED | Code search confirms ConfidenceWeights class at line 27 with all 10 values; daemon.py uses steer_threshold=55, recovery_threshold=20 as code defaults |
| `signal_processing.py` | `autorate_continuous.py` | SignalProcessor in WANController | WIRED | `SignalProcessor.process()` exists (line 124); called at autorate_continuous.py line 2663 as `signal_result = signal_processor.process(...)` |
| `reflector_scorer.py` | `autorate_continuous.py` | ReflectorScorer in WANController | WIRED | `ReflectorScorer` exists with `get_active_hosts()`, min_score=0.8 default; used for reflector selection before ICMP pings |

### Data-Flow Trace (Level 4)

These are documentation artifacts (findings files), not dynamic rendering components. Level 4 data-flow tracing applies to components that render dynamic data from APIs. The findings files contain captured static data from production systems (tc readback JSON, mangle rules, config YAML). Not applicable.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ConfidenceWeights values match findings documentation | grep on steering_confidence.py | RED_STATE=50, SOFT_RED_SUSTAINED=25, YELLOW_STATE=10, WAN_RED=25, RTT_DELTA_HIGH=15, RTT_DELTA_SEVERE=25, DROPS_INCREASING=10, QUEUE_HIGH_SUSTAINED=10 -- all match 113-02-findings.md exactly | PASS |
| CAKE defaults match findings documentation | grep on cake_params.py | UPLOAD_DEFAULTS ack-filter=True, DOWNLOAD_DEFAULTS ack-filter=False, TUNABLE_DEFAULTS memlimit=32mb, OVERHEAD_READBACK docsis=18/bridged-ptm=22 -- all match 113-01-findings.md | PASS |
| Baseline uses ICMP-only (not fused RTT) | Read autorate_continuous.py lines 2664-2669 | `fused_rtt` used for load EWMA; `signal_result.filtered_rtt` (ICMP) passed to `_update_baseline_if_idle()` -- matches findings claim | PASS |
| steer_threshold/recovery_threshold code defaults | grep on daemon.py | steer_threshold default=55, recovery_threshold default=20, sustain_duration_sec default=2.0, hold_down_duration_sec default=30.0 -- all match 113-02-findings.md timer table | PASS |
| CAKE-primary invariant in daemon.py | grep on daemon.py | Lines 182-183: `state_good = f"{primary_wan.upper()}_GOOD"`, `state_degraded = f"{primary_wan.upper()}_DEGRADED"` -- confirms topology drives state names | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| NETENG-01 | 113-01-PLAN.md | CAKE parameters verified per WAN (overhead, diffserv4, ack-filter, split-gso, memlimit) | SATISFIED | 113-01-findings.md CAKE parameter tables show all params verified PASS for Spectrum (docsis) and ATT (bridged-ptm); commit a87ccfd |
| NETENG-02 | 113-01-PLAN.md | DSCP end-to-end trace (MikroTik mangle -> CAKE tins, EF/AF/CS1 mappings) | SATISFIED | 113-01-findings.md documents 4-stage mangle pipeline, DSCP-to-tin table with EF->Voice, AF41->Video, CS1->Bulk; commit 05076cb |
| NETENG-03 | 113-02-PLAN.md | Steering logic correctness audited (confidence scoring, degrade timers, CAKE-primary invariant) | SATISFIED (tracking stale) | 113-02-findings.md contains complete audit; REQUIREMENTS.md still shows [ ] Pending due to merge residue |
| NETENG-04 | 113-02-PLAN.md | Measurement methodology validated (reflector selection, signal chain, IRTT vs ICMP paths) | SATISFIED (tracking stale) | 113-02-findings.md contains full signal chain and measurement path documentation; REQUIREMENTS.md still shows [ ] Pending |
| NETENG-05 | 113-03-PLAN.md | Queue depth and memory pressure baseline documented from production tc -s qdisc show | SATISFIED | 113-03-findings.md contains idle/load statistics for all 4 qdiscs, memory pressure analysis; commit 023f584 |

**Orphaned requirements:** None. All 5 NETENG requirements assigned to Phase 113 in REQUIREMENTS.md are covered by the 3 plans.

**REQUIREMENTS.md tracking gap:** NETENG-03 and NETENG-04 checkboxes and status table entries were updated in commit 924a8a1 but lost in merge commit e71000e. The work is complete; the tracking document is stale.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `.planning/REQUIREMENTS.md` lines 25-26, 92-93 | NETENG-03 and NETENG-04 marked Pending despite completion | Warning | Misleads future readers about phase 113 completion; does not affect production correctness |
| `.planning/ROADMAP.md` line 19 | Phase 113 summary marker is [ ] unchecked; phase detail table (line 117) correctly says Complete | Info | Minor inconsistency in ROADMAP summary list; detail table and plan checkboxes are correct |

No code stubs, placeholder implementations, or anti-patterns found in source files. The `wanctl-check-cake` tool limitation (unsupported on linux-cake transport) is documented and explained correctly in the findings -- it is not a gap, as `LinuxCakeBackend.validate_cake()` provides the same verification at daemon startup.

### Human Verification Required

#### 1. Production CAKE Parameter Drift Check

**Test:** SSH to cake-shaper (10.10.110.223) and run `sudo tc -j qdisc show` to confirm all 4 CAKE qdiscs are still running with the documented parameters.
**Expected:** ens16/ens17 show overhead=18 (docsis), ens27/ens28 show overhead=22 (ptm); all show diffserv=diffserv4, memlimit=33554432.
**Why human:** Cannot SSH from verifier to production VM. Parameters could have drifted if wanctl was restarted with a config change after the audit was performed.

### Gaps Summary

The phase goal is substantively achieved. All 5 success criteria are met with evidence in the findings documents, all source code references are accurate (verified against actual code), and all commits exist with correct content.

The single gap is a tracking document inconsistency caused by a merge conflict resolution: commit `924a8a1` updated NETENG-03 and NETENG-04 checkboxes in REQUIREMENTS.md, but the Wave 1 merge commit (`e71000e`) did not include those REQUIREMENTS.md changes, leaving them at their pre-work state (Pending). This is a 2-line fix to REQUIREMENTS.md (mark lines 25-26 as `[x]` and update lines 92-93 from Pending to Complete) plus marking Phase 113 as `[x]` in ROADMAP.md line 19.

**Root cause:** Worktree-based parallel execution with merge commit -- REQUIREMENTS.md was modified in a worktree branch but the merge conflict resolution only brought in the findings/summary files, not the tracking updates.

---

_Verified: 2026-03-26T20:45:00Z_
_Verifier: Claude (gsd-verifier)_
