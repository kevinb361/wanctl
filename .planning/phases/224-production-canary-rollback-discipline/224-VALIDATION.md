---
phase: 224
slug: production-canary-rollback-discipline
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-02
---

# Phase 224 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing project venv) + shellcheck + bash -n |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `.venv/bin/pytest tests/test_phase224_gate_eval.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (gate-eval slice) / ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run quick command for the slice the task touched (shellcheck for shell scripts; pytest slice for gate-eval).
- **After every plan wave:** Run `.venv/bin/pytest -o addopts='' tests/test_phase224_gate_eval.py tests/integration/steering_replay/ -q` (Phase 223 + Phase 224 logic regression).
- **Before `/gsd:verify-work`:** Full pytest suite must be green AND `safe12-boundary-check.json` `passed: true`.
- **Max feedback latency:** 10 seconds (gate-eval slice).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 224-01-01 | 01 | 1 | CANARY-01 | T-224-01 / T-224-02 | Snapshot script delegates to existing helper, no host mutation | shell-static | `shellcheck scripts/phase224-snapshot-a.sh && bash -n scripts/phase224-snapshot-a.sh` | ❌ W0 (script not yet written) | ⬜ pending |
| 224-01-02 | 01 | 1 | CANARY-01 | T-224-03 / T-224-04 | Rollback script delegates to canary-check, measures duration | shell-static + integration | `shellcheck scripts/phase224-rollback.sh && bash -n scripts/phase224-rollback.sh && test -f .planning/phases/224-production-canary-rollback-discipline/evidence/rehearsal-budget.md` | ❌ W0 | ⬜ pending |
| 224-02-01 | 02 | 1 | CANARY-02 | T-224-05 / T-224-06 | Spine probe read-only, no controller-path refs | shell-static | `shellcheck scripts/phase224-spine-probe.sh && bash -n scripts/phase224-spine-probe.sh` | ❌ W0 | ⬜ pending |
| 224-02-02 | 02 | 1 | CANARY-02 / CANARY-03 | T-224-07 / T-224-08 / T-224-09 | Gate-eval distinguishes restart-window from steady-state | unit | `.venv/bin/pytest tests/test_phase224_gate_eval.py -v` | ❌ W0 (test stub created in this task) | ⬜ pending |
| 224-03-01 | 03 | 2 | CANARY-01 | T-224-14 | Risk-acceptance signed before snapshot | shell-check | `test -f .planning/phases/224-production-canary-rollback-discipline/evidence/risk-acceptance-signed.redacted.md` | ✅ created in task | ⬜ pending |
| 224-03-02 | 03 | 2 | CANARY-01 | T-224-04 | Snapshot + Leg A captured cleanly, no pre-deploy drift | shell + python | (see plan verify block — manifest grep + spine-probe pre-deploy check) | ✅ in task | ⬜ pending |
| 224-03-03 | 03 | 2 | CANARY-02 | T-224-10 / T-224-11 / T-224-12 / T-224-13 | Deploy + restart inside 30s budget + Leg B captured, no controller-path mutation | shell + python + git | (see plan verify block) | ✅ in task | ⬜ pending |
| 224-04-01 | 04 | 3 | CANARY-02 | T-224-15 / T-224-16 | Observation samples captured at documented cadence | shell + python | (see plan verify block) | ✅ in task | ⬜ pending |
| 224-04-02 | 04 | 3 | CANARY-02 / CANARY-03 | T-224-18 | verdict.json shape valid, outcome ∈ {kept_aligned, rollback} | python | (see plan verify block) | ✅ in task | ⬜ pending |
| 224-04-03 | 04 | 3 | CANARY-03 | T-224-17 | If rollback: duration ≤ 300s + post-revert /health proof | python (conditional) | (see plan verify block) | ✅ in task | ⬜ pending |
| 224-05-01 | 05 | 3 | SAFE-12 | T-224-21 | SAFE-12 boundary check passes at HEAD vs v1.47 anchor | python + git | (see plan verify block) | ✅ in task | ⬜ pending |
| 224-05-02 | 05 | 3 | CANARY-01 / CANARY-02 / CANARY-03 | T-224-20 / T-224-22 / T-224-23 | 224-REPORT.md exists with all required sections, cites verdict + decision artifact | shell (grep) | (see plan verify block) | ✅ in task | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_phase224_gate_eval.py` — stubs for CANARY-02 / CANARY-03 gate logic (created in Plan 02 Task 2 alongside the script itself — this satisfies Wave 0 because the test file is created in the same task that creates the production code, with the test contract specified first per the action block's behavior list).
- [x] Existing pytest infrastructure (Phase 223 baseline) covers the steering replay corpus regression.
- [x] No new framework install needed — `.venv/bin/pytest` already configured.

*Note:* Plan 01's shell scripts are validated by `shellcheck` + `bash -n` (static checks, no pytest needed). Plan 03/04 verify blocks use inline `python3` snippets that check schema and file existence; no new test files needed because these are evidence-validation gates, not behavior tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Operator sign-off on `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` | CANARY-01 governance | Human decision — operator accepts risk window or invokes Override Path. Cannot be automated. | Plan 03 Task 1 (checkpoint:human-action). Verify by file existence of `evidence/risk-acceptance-signed.redacted.md`. |
| Production deploy execution + observation window | CANARY-01 / CANARY-02 / CANARY-03 | Single production-mutation event; operator must be at the keyboard for the deploy gate and rollback gate. | Plan 03 Task 3 + Plan 04 Task 3. Verified by deploy-summary.json and verdict.json shape checks. |
| Rollback execution (conditional) | CANARY-03 | Operator must observe gate verdict and execute rollback if it fires. | Plan 04 Task 3 (checkpoint:human-action). Verified by rollback-summary.json and post-revert spine probe. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are checkpoint:human-action (Plan 03 Task 1, Plan 04 Task 3 — both have evidence-existence automated checks behind the human gate).
- [x] Sampling continuity: every plan has at least one automated check per task; no 3-task run without automated verify across the entire phase.
- [x] Wave 0 covers all MISSING references (gate-eval test file created in same task as gate-eval script per TDD inside-the-task pattern; shell scripts validated by static checks).
- [x] No watch-mode flags (`pytest -v`, `--watchAll` absent).
- [x] Feedback latency < 10 seconds (gate-eval slice).
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-02
