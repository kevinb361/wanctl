---
phase: 234
slug: planning-metadata-reconciliation-closeout
status: planned
nyquist_compliant: true
wave_0_complete: true
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

> Git-visibility note (drives verification design, post-Codex-review): SEED-006 and both `completed/` silicom copies and 11/12 quick-archive slugs are git-UNTRACKED. `git diff --quiet` / `git status --porcelain` are BLIND to these and can false-pass. Where a file must be proven unchanged, validation uses `git hash-object` before/after. Where deletion must be caught, validation asserts the exact expected on-disk name set.

---

## Sampling Rate

- **After every task commit:** Run per-criterion file assertions (sub-second); for the SAFE-15-bearing task (234-02 Task 3), re-run boundary + milestone-close scripts + `git status --porcelain -- src/wanctl/` (must be empty)
- **After every plan wave:** Full assertion set for all four criteria; emit SAFE-15 JSON (boundary + milestone-close)
- **Before `/gsd:verify-work`:** SAFE-15 JSON `passed: true` + `git diff --quiet v1.50..HEAD -- <protected set>` exit 0 + milestone-close `head_commit == HEAD`
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 234-01-T1 | 234-01 | 1 | META-01 | T-234-01 | No silent deletion of quick-archive slugs (incl. untracked) | file assertion | Python heredoc: on-disk slug set EXACTLY equals the expected 12-name set (fail-closed, catches untracked-slug deletion git status cannot see) + `quick-archive-index.json` slug set == expected 12, `none_deleted==true`, 1 PLAN-only, 1 tracked | ✅ | ⬜ pending |
| 234-01-T2 | 234-01 | 1 | META-02 | T-234-02 | SEED-006 not false-closed; single canonical state; byte-unchanged proven by hash | file assertion (hash compare) | Python heredoc: `git hash-object` after-hash == recorded before-hash for SEED-006 + both `completed/` copies (NOT `git diff --quiet` — untracked) + pending absent + closed present with `closed_by_phase: 234` + SEED-006/v1.52 pointer | ✅ | ⬜ pending |
| 234-02-T1 | 234-02 | 2 | META-03 | T-234-05, T-234-06 | Waiver drafted with rationale, `Accepted: pending` (NOT self-signed); archive append-only addendum | file assertion + test green | `test -e .../phase-230-nyquist-waiver.md` + `grep -q 'Sign-Off'` + `grep -q 'Accepted: pending'` + `! grep -q 'Accepted: YES'` + `230-VALIDATION.md` still `nyquist_compliant: false` + references waiver + pytest 5 passed + STATE META-01/02 RESOLVED, META-03 PENDING | ✅ | ⬜ pending |
| 234-02-T2 | 234-02 | 2 | META-03 | T-234-06 | Operator approval gates `Accepted: YES`; META-03 RESOLVED only after sign-off | checkpoint:human-verify (blocking-human) | MANUAL: operator replies `approved`/`override`/issues; on approve → waiver `Accepted: YES` + footnote + STATE META-03 row `RESOLVED.*Phase 234.*META-03`; agent never self-signs | n/a | ⬜ pending |
| 234-02-T3 | 234-02 | 2 | SAFE-15 | T-234-04, T-234-07 | Controller path zero-diff at boundary AND fresh HEAD-bound at close; BOUND-01 generated | git + JSON assertion | `phase225-safe13-boundary-check.sh --anchor v1.50` boundary + milestone-close JSON both `passed: true`/`diff 0`; `check-cleanup-boundary.sh` generates `cleanup-boundary-234-final.json` `overall_pass: true`; milestone-close `head_commit == HEAD`; `git diff --quiet v1.50..HEAD -- <protected set>` exit 0; `git status --porcelain -- src/wanctl/` empty | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Note: META-01/META-02 ledger flips happen in 234-02-T1; the META-03 ledger flip to RESOLVED happens in 234-02-T2 ONLY after operator checkpoint approval. The SAFE-15 proofs in 234-02-T3 run last so they capture every metadata commit including the approved waiver flip.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. `tests/test_soak_monitor_att_coverage.py` already exists and passes 5/5; no new tests needed (this phase writes planning metadata + evidence, not testable `src/` behavior). All artifacts to create are metadata/evidence, not test gaps. The two read-only proof scripts (`phase225-safe13-boundary-check.sh`, `check-cleanup-boundary.sh`) already exist.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| META-03 waiver operator sign-off | META-03 | A waiver is a risk-acceptance record; operator authority required, agent must not self-sign | 234-02-T2 checkpoint: operator reads the waiver + green test + append-only addendum, replies `approved` (waiver → `Accepted: YES`) or `override` (retroactive validate) |
| META-02 reconciliation does not false-close operationally real bypass work | META-02 | Judgment call on canonical-state semantics | Read SEED-006 and the closed todos; confirm SEED-006 remains the dormant v1.52 carrier and closure pointers cite it rather than claiming the work is done |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (234-02-T2 is a checkpoint with manual operator verification + a post-approval assertion)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — all infra exists)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Untracked-file proofs use `git hash-object` / exact-set assertions, not `git diff --quiet` (Codex review fix)
- [x] Waiver sign-off is operator-gated at a blocking-human checkpoint (Codex review fix)
- [x] `cleanup-boundary-234-final.json` is generated + asserted; SAFE-15 milestone-close is a fresh HEAD-bound capture (Codex review fixes)

**Approval:** planned
