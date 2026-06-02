---
phase: 221
slug: matrix-evidence-closeout-scope-a2
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-01
---

# Phase 221 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase 221 has no novel code — validation is mutation-boundary pytest + source/shell assertions in plan acceptance criteria.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (`.venv/bin/pytest`) |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | quick ~3s, full ~60s |

---

## Sampling Rate

- **After every task commit:** `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -q`
- **After every plan wave:** `.venv/bin/pytest tests/ -q && .venv/bin/ruff check tests/`
- **Before `/gsd:verify-work`:** full suite + ruff + mutation-boundary pytest + ledger/closeout source assertions per plan acceptance criteria
- **Max feedback latency:** 5 seconds (mutation-boundary only) / 60 seconds (full suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 221-01-01 | 01 | 0 | SAFE-11 | T-221-01 | mutation-boundary green from first commit | unit | `.venv/bin/pytest tests/test_phase221_mutation_boundary.py::test_no_forbidden_controller_path_diff -x` | ❌ W0 | ⬜ pending |
| 221-01-02 | 01 | 0 | SAFE-11 | T-221-01 | scripts/phase221* allowlist empty (no new phase221 scripts) | unit | `.venv/bin/pytest tests/test_phase221_mutation_boundary.py::test_phase221_scripts_allowlist -x` | ❌ W0 | ⬜ pending |
| 221-01-03 | 01 | 0 | SAFE-11 | T-221-01 | docs/ diff has no threshold-tuning language | unit | `.venv/bin/pytest tests/test_phase221_mutation_boundary.py::test_phase221_docs_have_no_threshold_tuning_tokens -x` | ❌ W0 | ⬜ pending |
| 221-01-04 | 01 | 0 | CLOSEOUT-01 | — | EVIDENCE-LEDGER.md scaffold with 18 cell rows pending | source | `grep -c '^| ' .planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md` ≥ 19 (header + 18 rows) | ❌ W0 | ⬜ pending |
| 221-02-01 | 02 | 1 | CLOSEOUT-01, CLOSEOUT-02 | — | ledger reflects all completed replicates | source | `find .planning/phases/220-matrix-runner-scope-a1/evidence -path '*__r*/signal-sheet.json' \| wc -l` equals replicate count summed across ledger `replicates` column | ⏳ ledger | ⬜ pending |
| 221-02-02 | 02 | 1 | CLOSEOUT-01 | — | ledger session-update commits cite session timestamp | source | `git log --grep='ledger update' --format=%s` shows one commit per operator session | ⏳ ledger | ⬜ pending |
| 221-03-01 | 03 | 2 | CLOSEOUT-01, CLOSEOUT-02 | — | aggregator emits CLOSEOUT.json with schema_version=1 | source | `.venv/bin/python -c "import json; d=json.load(open('.planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.json')); assert d['schema_version']==1"` | ⏳ closeout | ⬜ pending |
| 221-03-02 | 03 | 2 | CLOSEOUT-01 | — | CLOSEOUT.md contains exactly one verdict token | source | `grep -cE '^(\*\*Verdict\*\*:\|verdict:) (defect_located\|hypothesis_killed\|carried_narrower_with_close_with_prejudice_rule)$' .planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md` equals 1 | ⏳ closeout | ⬜ pending |
| 221-03-03 | 03 | 2 | CLOSEOUT-01, CLOSEOUT-02 | — | CLOSEOUT.md cites Phase 220 YAML SHA | source | `grep -c 'phase220-matrix.yaml.*[0-9a-f]\{40\}' .planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md` ≥ 1 | ⏳ closeout | ⬜ pending |
| 221-03-04 | 03 | 2 | CLOSEOUT-02 | — | §3 Table 1 has 6 canonical rows; §4 Table 2 has 12 supplemental rows | source | shell parser counts table rows under §3 and §4 headers | ⏳ closeout | ⬜ pending |
| 221-04-01 | 04 | 3 | CLOSEOUT-03 | — | folded todo moved via `git mv` (rename detected) | source | `git log --follow --format=%H .planning/todos/closed/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` returns history pre-dating Phase 221 | ⏳ closeout | ⬜ pending |
| 221-04-02 | 04 | 3 | CLOSEOUT-03 | — | YAML frontmatter has closed_by_phase, verdict, close_with_prejudice fields | source | `.venv/bin/python -c "import yaml; from pathlib import Path; c=Path('.planning/todos/closed/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md').read_text().split('---',2)[1]; d=yaml.safe_load(c); assert d['closed_by_phase']==221 and d['verdict'] in {'defect_located','hypothesis_killed','carried_narrower_with_close_with_prejudice_rule'} and isinstance(d['close_with_prejudice'], bool)"` | ⏳ todo-move | ⬜ pending |
| 221-04-03 | 04 | 3 | CLOSEOUT-03 | — | todo body contains `## Phase 221 Closeout` section | source | `grep -c '^## Phase 221 Closeout$' .planning/todos/closed/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` equals 1 | ⏳ todo-move | ⬜ pending |
| 221-04-04 | 04 | 3 | CLOSEOUT-03, CRITERIA-02 | — | on carry verdict, todo body contains CRITERIA-02 verbatim | source | `grep -A 5 'Close-With-Prejudice Rule' .planning/todos/closed/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` matches REQUIREMENTS.md CRITERIA-02 text verbatim (conditional — applies only on `carried_narrower_*` verdict) | ⏳ todo-move | ⬜ pending |
| 221-04-05 | 04 | 3 | CLOSEOUT-01 | — | CLOSEOUT.md amended with todo-move commit SHA | source | `grep -cE 'closeout_commit_for_todo: [0-9a-f]{7,40}' .planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md` equals 1 | ⏳ todo-move | ⬜ pending |
| 221-04-06 | 04 | 3 | SAFE-11 | T-221-02 | mutation-boundary green at phase close | unit | `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -x -q` | ⏳ phase-close | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase221_mutation_boundary.py` — clone of Phase 220 boundary test with Phase 221 allowlist
- [ ] `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md` — scaffold with 18 cell rows (status: pending) + 1 row preserved for the Phase 220 rehearsal cell (status: complete)
- [ ] `pyproject.toml` / `conftest.py` — no changes (existing infrastructure covers Phase 221)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 54 evidence runs executed by operator over multiple calendar days | CLOSEOUT-01, CLOSEOUT-02 | Live network capture across off-peak (01–05) / daytime (10–16) / prime-time (19–22) gates; cannot be automated under v1.47 read-only milestone scope | Operator invokes `./scripts/phase220-target-path-matrix.sh --cell <id> --replicate <N>` per CONTEXT D-02 calendar spread; Claude updates 221-EVIDENCE-LEDGER.md per session per CONTEXT D-03; aggregator + closeout fire only when ledger reads 54/54 or matrix-fail trigger fires per CONTEXT D-09 |
| Operator decision on D-12 base_sha re-pin (exceptional) | CLOSEOUT-01 | Mid-matrix controller-path hotfix scenario; operator decides whether to pause matrix and re-pin | Operator follows CONTEXT D-12 protocol; closeout report records SHA boundary explicitly per D-05 per-cell `base_sha` column |
| Matrix-fail abort decision (CONTEXT D-09) | CLOSEOUT-01 | Operator/Claude observability decision when canonical cell INCOMPLETE or > 2 supplemental cells INCOMPLETE | Plan 03 acceptance asserts that if 221-MATRIX-INVALID.md exists, no 221-CLOSEOUT.md is written; phase reopens for replan |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or operator-Manual reference
- [ ] Sampling continuity: SAFE-11 re-runs after every commit; no 3 consecutive tasks without automated verify
- [ ] Wave 0 lands the mutation-boundary test FIRST so all subsequent commits cite it
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s for SAFE-11; < 60s for full suite
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
