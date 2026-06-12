---
phase: 233
slug: gated-repo-hygiene-sweep
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-11
---

# Phase 233 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (project `.venv`) |
| **Config file** | `pyproject.toml` (addopts present; override with `-o addopts=''` for focused runs) |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | quick ~5s; full suite ~2-4 min |

---

## Sampling Rate

- **After every task commit:** Run `bash scripts/check-cleanup-boundary.sh` (BOUND-01 guard, exit 0) + `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q`; if deploy/scripts touched, also `bash -n` / `shellcheck` on touched files
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v` + SAFE-15 boundary check
- **Before `/gsd:verify-work`:** Full suite green, BOUND-01 guard green, SAFE-15 zero-diff JSON evidence committed
- **Max feedback latency:** ~240 seconds (full suite); ~10s per-task

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 233-xx | TBD | TBD | SWEEP-01 | — | No denylisted/protected surface touched by removal | gate | `bash scripts/check-cleanup-boundary.sh --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/cleanup-boundary-233.json` (exit 0) + `git grep -l <removed-name>` returns nothing tracked | ✅ | ⬜ pending |
| 233-xx | TBD | TBD | SWEEP-01 | — | Guard test suite stays green after removal | unit | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q` | ✅ (9 passed) | ⬜ pending |
| 233-xx | TBD | TBD | SWEEP-02 | — | Annotated docs mention external cake-autorate mode | grep sweep | `grep -ciE 'cake-autorate|external mode' docs/PROFILING.md docs/PERFORMANCE.md docs/RUNBOOK.md` (each ≥1 after edit) | ✅ | ⬜ pending |
| 233-xx | TBD | TBD | SWEEP-02 | — | Native deploy docs not collaterally damaged | gate | boundary guard (DEPLOYMENT.md/UPGRADING.md `must-exist` rows, exit 0) | ✅ | ⬜ pending |
| 233-xx | TBD | TBD | SWEEP-03 | — | Spectrum hardcoding removed; native path untouched; units still valid | gate + lint | boundary guard exit 0 + `bash -n`/`shellcheck` on touched unit/scripts + systemd unit syntax check | ✅ | ⬜ pending |
| 233-xx | TBD | TBD | SAFE-15 | — | Controller-path zero-diff at phase boundary | gate | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/safe15-boundary-233.json` + `git diff --quiet v1.50..HEAD -- <controller paths>` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:
- `scripts/check-cleanup-boundary.sh` — exists, exit 0 verified this session
- `scripts/phase225-safe13-boundary-check.sh` — exists, SAFE-15 passed this session
- `tests/test_cleanup_boundary_guard.py` — exists, 9 passed

Only setup item: create evidence dir `.planning/phases/233-gated-repo-hygiene-sweep/evidence/` for `cleanup-boundary-233.json` and `safe15-boundary-233.json` (mirrors Phase 232 layout).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SWEEP-01 delete-vs-archive disposition for untracked trial files | SWEEP-01 | Untracked files are outside guard manifest; deletion is destructive filesystem op | Operator confirms `rm` of `.planning/cake-autorate-trials/run_*` after reviewing `git grep` zero-reference proof |
| SWEEP-02 disposition of historical docs (CABLE_TUNING, STEERING, SILICOM-BYPASS) | SWEEP-02 | Annotate vs leave-as-historical is operator judgment | Operator reviews per-doc inventory in RESEARCH.md and approves disposition |
| SWEEP-03 Spectrum baseline RTT default value | SWEEP-03 | Pinning `WANCTL_EXTERNAL_BASELINE_RTT` in the unit must match intended live value | Operator confirms value against live deployment before unit edit |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none missing)
- [x] No watch-mode flags
- [x] Feedback latency < 240s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
