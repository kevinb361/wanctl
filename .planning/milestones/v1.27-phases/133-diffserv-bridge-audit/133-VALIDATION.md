---
phase: 133
slug: diffserv-bridge-audit
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-03
---

# Phase 133 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual network forensics (tcpdump, tc, iperf3) |
| **Config file** | N/A -- audit phase, not code phase |
| **Quick run command** | N/A |
| **Full suite command** | N/A |
| **Estimated runtime** | ~30 minutes (manual SSH sessions) |

---

## Sampling Rate

- **Per task:** Manual verification via tcpdump + tc stats on cake-shaper VM
- **Phase gate:** Completed 133-ANALYSIS.md document with hop-by-hop results table and fix strategy

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 133-01-01 | 01 | 1 | QOS-01 | manual | SSH to VM, tcpdump + tc commands | N/A | ⬜ pending |
| 133-01-02 | 01 | 1 | QOS-01 | manual | Review analysis document completeness | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. No test scaffolding needed — this is a manual audit phase producing a documentation artifact.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DSCP marks survive bridge path | QOS-01 | Requires physical network path (MikroTik -> bridge -> CAKE) | Send iperf3 --dscp traffic, tcpdump at 3 points, check tc tin stats |
| Hop-by-hop analysis complete | QOS-01 | Document quality is subjective | Review 133-ANALYSIS.md for completeness |
| Fix strategy identified | QOS-01 | Requires domain judgment | Verify analysis document includes actionable fix strategy for Phase 134 |

---

## Validation Sign-Off

- [x] All tasks have manual verification procedures
- [x] Sampling continuity: every task has a verification step
- [x] Wave 0 covers all MISSING references (none needed)
- [x] No watch-mode flags
- [x] Feedback latency: immediate (manual observation)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
