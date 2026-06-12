---
phase: 232
slug: cleanup-boundary-guard-tooling-fixes
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-10
---

# Phase 232 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo venv, Python 3.11+) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py tests/test_phase231_rollback.py tests/test_operator_digest.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | quick ~5s; full ~120s |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest -o addopts='' tests/test_phase231_rollback.py tests/test_operator_digest.py -q` (plus `tests/test_cleanup_boundary_guard.py` once it exists)
- **After every plan wave:** Run hot-path slice `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- **Before `/gsd:verify-work`:** Full suite must be green AND SAFE-15 evidence JSON shows pass
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 232-01-01 | 01 | 1 | BOUND-01 | T-232-01 | Guard exits non-zero on denylist removal/modification; exit 2 on bad ref | integration | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q` | ❌ W0 (same plan) | ⬜ pending |
| 232-01-02 | 01 | 1 | BOUND-01 | T-232-01 | Guard wired into default pytest suite (sweep gate) | integration | `.venv/bin/pytest tests/ -q --collect-only -q \| grep test_cleanup_boundary_guard` | ❌ W0 (same plan) | ⬜ pending |
| 232-02-01 | 02 | 1 | FIX-01 | T-232-02 | Remote confirm payload fail-fast; external writer verified inactive post-rollback | integration (SSH shim) | `.venv/bin/pytest -o addopts='' tests/test_phase231_rollback.py -q` | ✅ | ⬜ pending |
| 232-02-02 | 02 | 1 | FIX-01 | T-232-03 | Preflight/dry-run provably read-only (negative mutation-verb assertions) | integration (SSH shim) | `.venv/bin/pytest -o addopts='' tests/test_phase231_rollback.py tests/test_phase231_migration_held.py -q` | ✅ | ⬜ pending |
| 232-03-01 | 03 | 2 | FIX-02 | — | Digest tolerance pinned by tests; evidence recorded; todo closed | unit + evidence | `.venv/bin/pytest -o addopts='' tests/test_operator_digest.py -q` | ✅ | ⬜ pending |
| 232-03-02 | 03 | 2 | SAFE-15 | — | Controller-path zero diff vs v1.50 at phase boundary | script + evidence | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out .planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cleanup_boundary_guard.py` — covers BOUND-01; created in the same plan (232-01) and same wave as the guard script itself, so no separate Wave 0 plan is required.

All other phase requirements are covered by existing test infrastructure (`tests/test_phase231_rollback.py`, `tests/test_operator_digest.py`) plus the existing `scripts/phase225-safe13-boundary-check.sh` evidence path.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Optional live unprivileged `--digest` run (supplementary evidence only) | FIX-02 | Live host DB permissions (0640 wanctl:wanctl) cannot be reproduced deterministically in CI; Phase 208 D-15 forbids chmod-based tests | `ssh kevin@10.10.110.223 'wanctl-operator-summary --digest; echo rc=$?'` — read-only; expect per-WAN digest lines or stable skip lines, rc=0. Best-effort: if host unreachable, record fallback note; tests remain the primary evidence |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
