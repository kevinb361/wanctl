---
phase: 234
slug: planning-metadata-reconciliation-closeout
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-11
---

# Phase 234 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo-pinned, `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q -o addopts=''` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (quick) |

> Known full-suite noise: 21–23 pre-existing Phase 220/221 boundary tests fail on committed `src/wanctl/` drift since `PHASE214_BASE_SHA` (documented historical failures, STATE.md decision [233-04]). Phase 234 adds ZERO `src/wanctl/` changes and cannot worsen this count. SAFE-15 + META evidence are the binding gates.

---

## Sampling Rate

- **After every task commit:** Run per-criterion file assertions (sub-second); for the SAFE-15-bearing task, re-run boundary script + `git status --porcelain -- src/wanctl/` (must be empty)
- **After every plan wave:** Full assertion set for all four criteria; emit SAFE-15 JSON
- **Before `/gsd:verify-work`:** SAFE-15 JSON `passed: true` + `git diff --quiet v1.50..HEAD -- <protected set>` exit 0
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (filled by planner) | — | — | META-01 | — | No silent deletion of quick-archive slugs | file assertion | `test $(ls -d .planning/milestones/quick-archive/*/ \| wc -l) -eq 12` + manifest lists all 12 + `git status --porcelain .planning/milestones/quick-archive/` shows no deletions | ✅ | ⬜ pending |
| (filled by planner) | — | — | META-02 | — | SEED-006 not false-closed; single canonical state | file assertion | `test ! -e .planning/todos/pending/2026-04-28-add-silicom-bypass-*.md` + `grep -q 'closed_by_phase: 234' .planning/todos/closed/2026-04-28-add-silicom-bypass-*.md` + SEED-006 pointer present + `git diff --quiet -- .planning/seeds/SEED-006-v145-silicom-bypass-tooling-and-harness.md` | ✅ | ⬜ pending |
| (filled by planner) | — | — | META-03 | — | Resolution recorded with rationale, not silent | file assertion + test green | waiver doc exists in `.planning/decisions/` (or `nyquist_compliant: true` in archived 230-VALIDATION.md) + `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q -o addopts=''` → 5 passed | ✅ | ⬜ pending |
| (filled by planner) | — | — | SAFE-15 | — | Controller path zero-diff vs v1.50 anchor | git + JSON assertion | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out .planning/phases/234-planning-metadata-reconciliation-closeout/evidence/safe15-boundary-234.json` → `passed: true`, `controller_path_diff_count: 0`; independent `git diff --quiet v1.50..HEAD -- <protected set>` exits 0 | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. `tests/test_soak_monitor_att_coverage.py` already exists and passes 5/5; no new tests needed (this phase writes planning metadata + evidence, not testable `src/` behavior).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| META-02 reconciliation does not false-close operationally real bypass work | META-02 | Judgment call on canonical-state semantics | Read SEED-006 and the closed todos; confirm SEED-006 remains the dormant v1.52 carrier and closure pointers cite it rather than claiming the work is done |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
