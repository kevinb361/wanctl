---
phase: 217
slug: production-cycle-budget-baseline
status: approved
nyquist_compliant: n/a-measurement-phase
wave_0_complete: n/a
created: 2026-05-29
approved: 2026-05-29
---

# Phase 217 — Validation Strategy

> Per-phase validation contract. **This phase ships no `src/` code** — it is a measurement + decision phase (capture a production cycle-budget profile, attribute subsystem cost, write a runbook, close-or-promote a pending todo). The Nyquist sampling contract (test framework, watched suite, Wave-0 stubs) does not apply. Validation is **artifact-shape**, not test-runtime.

---

## Why `nyquist_compliant: n/a-measurement-phase`

The standard Nyquist contract assumes a code phase with a test framework (`pytest`, `jest`, `vitest`, etc.) producing fast-feedback signal on every task commit. Phase 217 ships:

- One **operator runbook** (`docs/PROFILING.md`).
- One **offline helper script** (`scripts/profiling_categorize.py`) — fixture-verifiable inline.
- One **captured artifact** + **summary** in `.planning/perf/` (data, not code).
- One **todo lifecycle move** (`pending/` → `done/`).

There is no production-path code to regression-test. The phase's correctness is established by:
1. The retrieved log spans ≥1h with parseable DEBUG samples (Plan 02 Task 3).
2. The helper script's dominance verdict matches a fixture-driven expectation (Plan 01 Task 2).
3. The summary states the D-03/D-04 verdict with real measured numbers (Plan 03 Task 2).
4. The todo file ends in `done/` with the verdict recorded (Plan 03 Task 3).

Each task carries an inline `<verify><automated>...</automated></verify>` block — that is the sampling rate for this phase.

---

## Per-Task Verification Map

Drawn from the `<automated>` blocks already in the three PLAN.md files. Status updates during execute-phase.

| Task ID | Plan | Wave | Requirement | Verify Type | Automated Command (from PLAN.md) | Status |
|---------|------|------|-------------|-------------|----------------------------------|--------|
| 217-01-01 | 01 | 1 | PERF-01 | scaffold | `test -d .planning/perf && test -f .planning/perf/.gitkeep` | ⬜ pending |
| 217-01-02 | 01 | 1 | PERF-02 | unit-fixture | `.venv/bin/python scripts/profiling_categorize.py <fixture.json> --budget 50` exits 0; output shows category roll-up + `>40%` verdict | ⬜ pending |
| 217-01-03 | 01 | 1 | PERF-01 | doc-shape | `grep -qE "--profile.*--debug\|--debug.*--profile" docs/PROFILING.md && grep -q "systemctl revert" docs/PROFILING.md && grep -q "40%" docs/PROFILING.md` | ⬜ pending |
| 217-02-01 | 02 | 1 | PERF-01 | pre-flight (operator) | `ssh <host> 'head -1 /var/log/wanctl/spectrum.log'` returns non-JSON; `systemctl cat wanctl@spectrum` editable; `/health` reachable | ⬜ pending |
| 217-02-02 | 02 | 1 | PERF-01 | live capture (operator) | `systemctl cat wanctl@spectrum` shows drop-in with `--profile --debug`; ≥1h elapsed; `systemctl revert` succeeded; `.planning/perf/spectrum-capture-raw.log` retrieved | ⬜ pending |
| 217-02-03 | 02 | 1 | PERF-01 | artifact-shape | `grep -c "autorate_cycle_total:" .planning/perf/spectrum-capture-raw.log` ≥ 60000 (≥~50min at 20Hz, raised from 36000 per checker W4); router-write coverage present OR recorded gap; `test -f .planning/perf/spectrum-health-midwindow.json` | ⬜ pending |
| 217-03-01 | 03 | 2 | PERF-02 | analysis-shape | `.profile.json` exists and contains `autorate_cycle_total`; analyzer markdown produced; categorize verdict produced | ⬜ pending |
| 217-03-02 | 03 | 2 | PERF-02, PERF-03 | summary-shape | `grep` checks: cycle_total, `40%`, `observer`, `storage`, `deprioritiz`/`promote`; if router-write count == 0, verdict is qualified or PROMOTE (per checker W5) | ⬜ pending |
| 217-03-03 | 03 | 2 | PERF-01 | todo-lifecycle | `test -f .planning/todos/done/2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` AND not in `pending/` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Artifacts (no test stubs needed)

- `.planning/perf/.gitkeep` — created by Plan 01 Task 1.
- `scripts/profiling_categorize.py` — created by Plan 01 Task 2 with inline fixture verification.
- No test framework install, no `conftest.py`, no Wave-0 test stubs — this phase ships no `src/` code.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Drop-in enable + ≥1h live capture on the Spectrum production host | PERF-01 | Touches a 24/7 production daemon; requires operator judgment + SSH | Plan 02 Task 2 `<how-to-verify>` step-by-step |
| Driven RRUL/upload segment inside the capture window (D-02) | PERF-01 | Run from dev VM against external test target | `scripts/phase213-baseline-capture.sh --host dallas --flent-duration 60 --tests tcp_upload,rrul --wans spectrum` |
| Pre-commit secret/IP scrub of `.planning/perf/spectrum-capture-raw.log` and `spectrum-health-midwindow.json` (T-217-05) | PERF-01 | Adversarial inspection of operator artifacts | Operator reviews diff before `git commit`; no `secrets`/`credentials` content; non-secret operating points acceptable |

---

## Validation Sign-Off

- [x] Every task has an inline `<automated>` verify OR a documented manual operator step
- [x] No 3 consecutive tasks without automated verify (all 9 tasks carry inline verifies)
- [x] No watch-mode flags (none applicable — no test suite)
- [x] Artifact-shape acceptance criteria are falsifiable (file existence, grep counts, JSON-parse, exit codes)
- [x] `nyquist_compliant: n/a-measurement-phase` justified above

**Approval:** approved 2026-05-29 (orchestrator, post plan-checker round 1)
