---
phase: 204
slug: d-14-successor-recalibration-calib
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 204 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py tests/test_soak_summary_aggregate.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~12s quick / ~60s full |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Populated by gsd-planner. Each task references the plan + wave + REQ-ID + automated command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | CALIB-01..05, SAFE-07 | TBD | N/A (no auth/data-exfil paths in soak harness) | TBD | TBD | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Existing test infrastructure (`pytest`, `tests/test_phase_195_replay.py`, `scripts/soak_summary_aggregate.py` test suite) covers the projected Phase 204 surface. New fixtures expected:
- [ ] Replay fixture for `aggregate_watchdog()` legacy-vs-new dual emission (CALIB-03)
- [ ] Distribution-analysis script test against synthetic CALIB-01 NDJSON (if scripted per Open Q9)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 24h Spectrum baseline soak (CALIB-01) | CALIB-01 | Production wall-clock + operator approval | Operator runs `scripts/soak-capture.sh` after Deploy 1 lands; harness completes 24h capture; aggregator runs against capture |
| Operator approval signature on threshold | CALIB-02 | Human judgment locks the number | Operator writes `204-CALIB-02-OPERATOR-APPROVAL.md` with rationale referencing CALIB-01 distribution |
| Two-snapshot rollback drill (Deploy 1, Deploy 2) | SAFE-07 (cross-cutting) | Production deploy on cake-shaper | Pre-deploy `check-safe07-source-diff.sh` returns clean; post-deploy `/health` smoke; rollback rehearsed per v1.42 Plan 201-15/16 |
| 24h verification soak dual gate (CALIB-04) | CALIB-04 | Production wall-clock | After Deploy 2: D-19 stays 0 floor hits AND D-14-successor passes recalibrated threshold |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (or are flagged `autonomous: false` for the four manual-only items above)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner populates the per-task table)

**Approval:** pending
