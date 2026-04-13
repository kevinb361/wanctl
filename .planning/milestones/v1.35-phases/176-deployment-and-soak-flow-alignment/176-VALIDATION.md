---
phase: 176
slug: deployment-and-soak-flow-alignment
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-13
---

# Phase 176 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | shell syntax checks plus grep-based artifact verification |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `bash -n <script> && rg '<required pattern>' <files...>` |
| **Full suite command** | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_wan_controller.py tests/test_cake_signal.py tests/test_queue_controller.py -q` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** run the task-local `bash -n` and `rg` checks from the plan.
- **After every plan wave:** rerun the relevant syntax checks for all modified scripts in that wave.
- **Before `/gsd-verify-work`:** confirm the docs/scripts now describe and surface the migration-aware deploy flow, operator-summary CLI, and multi-service soak evidence path.
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 176-01-01 | 01 | 1 | DEPL-01 | T-176-01 | install metadata matches shipped version | artifact | `rg -n 'VERSION=\"1.35.0\"' scripts/install.sh` | ✅ | ⬜ pending |
| 176-01-02 | 01 | 1 | DEPL-01, SOAK-01 | T-176-02 | operator-summary CLI is deploy-surfaced through a stable wrapper | syntax+artifact | `bash -n scripts/deploy.sh scripts/wanctl-operator-summary && rg -n 'wanctl-operator-summary' scripts/deploy.sh scripts/wanctl-operator-summary` | ✅ / ❌ W0 | ⬜ pending |
| 176-02-01 | 02 | 2 | STOR-01, DEPL-01 | T-176-03 | deploy flow makes migration and restart/canary order explicit without auto-running risky steps | syntax+artifact | `bash -n scripts/deploy.sh && rg -n 'migrate-storage|canary|restart|steering.service' scripts/deploy.sh docs/DEPLOYMENT.md docs/GETTING-STARTED.md` | ✅ | ⬜ pending |
| 176-03-01 | 03 | 3 | STOR-03, SOAK-01 | T-176-04 | soak evidence path covers all claimed services, including steering when enabled | syntax+artifact | `bash -n scripts/soak-monitor.sh && rg -n 'spectrum|att|steering.service' scripts/soak-monitor.sh docs/RUNBOOK.md docs/DEPLOYMENT.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

No new test harness is required because this phase changes deploy/ops shell scripts and docs rather than controller logic. Fast syntax checks plus targeted grep assertions are sufficient for continuous feedback.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Review the printed operator sequence for production safety | STOR-01, DEPL-01 | Human judgment is needed to confirm wording does not imply unsafe auto-migration/restart behavior | Read `scripts/deploy.sh` next-step output path and `docs/DEPLOYMENT.md`; verify the sequence is explicit but non-automated |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-13
