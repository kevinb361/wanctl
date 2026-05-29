---
phase: 216
slug: recovery-refractory-decision
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-29
---

# Phase 216 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Decision-only phase.** Phase 216 ships no code, config, service, or RouterOS change.
> "Validation" here means *confirming the cited evidence and existing tests still hold* —
> not writing new tests. The deliverable is a verdict + `216-REPORT.md` + a thread-status flip.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (project `.venv`) |
| **Config file** | `pyproject.toml` (addopts present; use `-o addopts=''` for focused slices) |
| **Quick run command** | `.venv/bin/pytest tests/test_phase_197_replay.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/test_phase_197_replay.py tests/test_phase213_classify.py -q` |
| **Estimated runtime** | ~10 seconds (focused slice) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_phase_197_replay.py -q`
- **After every plan wave:** Run the full suite command above
- **Before `/gsd:verify-work`:** Both test files green (already verified: 21 passed)
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 216-evidence | 01 | 1 | RECOV-01/03 (D-03) | — | refractory arbitration branches (`queue_during_refractory` / `rtt_fallback_during_refractory`) behave correctly | unit/replay | `.venv/bin/pytest tests/test_phase_197_replay.py -q` | ✅ (21 passed) | ✅ green |
| 216-cascade | 01 | 1 | RECOV-02 (Phase 160) | — | CAKE detection masked during refractory (no cascade) | unit/replay | `.venv/bin/pytest "tests/test_phase_197_replay.py::TestPhase197NoCascadeOnDetection" -q` | ✅ | ✅ green |
| 216-classifier | 01 | 1 | D-02 artifact check | — | classifier emits expected buckets; `backlog_suppressed_delta` provenance understood | unit | `.venv/bin/pytest tests/test_phase213_classify.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* The D-03 / RECOV-02 claims are
already covered by `tests/test_phase_197_replay.py` (21 passed live); the D-02 classifier
behavior is covered by `tests/test_phase213_classify.py`. No new tests are required for a
decision-only close. If the planner seeds an optional classifier-hardening tooling follow-up
(fix the per-WAN merge + WR-02 zero-lag in `phase213-classify.py`), that follow-up — not 216 —
owns any new classifier tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Verdict is evidence-cited and thread closed | RECOV-01 | Editorial/operator judgment — confirming the report cites the proven artifact analysis and flips thread `status: in_progress → closed` is not unit-testable | Read `216-REPORT.md`: confirm it states no-change/resolved-by-197, cites the 14451 merge-artifact proof + the 21-passed replay tests + the WR-02 zero-lag caveat, and records D-04a reopen triggers. Confirm thread file `status: closed`. |
| Reopen trigger is concrete | RECOV-01 (D-04a) | Depends on a future production event that does not yet exist | Confirm report names the exact field `signal_arbitration.refractory_active == true` (with RTT fallback / recovery lag / throughput collapse) as the reopen condition. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing infra sufficient)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-29
