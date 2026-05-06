---
phase: 203
slug: target-edge-churn-instrumentation-obsv
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
derived_from: 203-RESEARCH.md §Validation Architecture
---

# Phase 203 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Forward-looking: per-task rows are filled in by the planner once 203-01..03 PLAN.md files exist. Requirement-level rows below are authoritative.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Phase-scoped slice** | `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | quick ~43s · phase-scoped slice ~3s · full ~189s |

---

## Sampling Rate

- **After every task commit:** quick hot-path slice + the plan's own test file (e.g. plan 203-01 commits run `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` plus the hot-path slice)
- **After every plan wave:** phase-scoped slice
- **Before `/gsd-verify-work`:** full suite green AND `git diff <phase-202-close>..HEAD -- src/wanctl/` returns empty AND SAFE-05 pin test green
- **Max feedback latency:** ~45s (quick slice)

---

## Requirement → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Wave 0 |
|--------|----------|-----------|-------------------|-------------|--------|
| OBSV-05 | Capture script emits `load_rtt_delta_us` + 6 supporting fields per NDJSON row | unit / contract | `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v -k "load_rtt_delta_us or new_fields"` | ❌ | plan 203-01 |
| OBSV-06 | `soak-summary.json` aggregator emits `load_rtt_delta_us` p50/p95/p99/max + histogram + zone × cause-tag matrix | unit + replay | `.venv/bin/pytest tests/test_phase_203_replay.py -v -k "aggregator_math or by_zone_cause or histogram"` | ❌ | plan 203-02 |
| OBSV-07 | Golden-fixture replay (dual-fixture: capture-projection contract + aggregator-math against synthetic NDJSON) | replay | `.venv/bin/pytest tests/test_phase_203_replay.py -v` and `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` | ❌ | plans 203-01 + 203-02 |
| OBSV-08 | Docs (`docs/SOAK_HARNESS.md`, CHANGELOG `v1.43-dev`) name the new field, the matrix contract, and the no-control-path-change invariant | manual-only | `grep -E "load_rtt_delta_us\|load_rtt_delta_us_by_zone_cause\|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md` returns ≥1 hit per file per pattern | ❌ | plan 203-03 |
| SAFE-07 | No control-path source diff between Phase 201 close and Phase 203 close. v1.40/v1.41/v1.42/v1.42-Phase-202 pin block in `tests/test_phase_195_replay.py` produces identical assertion results. | regression + diff | `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` AND `git diff <phase-202-close>..HEAD -- src/wanctl/` returns no output | ✅ pin test exists | manual diff at closeout |

---

## Per-Task Verification Map

> Filled by planner. Recommended slicing from research §Recommended plan slicing:
> - **203-01** capture script (`scripts/soak-capture.sh`) + capture-projection test (OBSV-05, OBSV-07 capture side)
> - **203-02** aggregator (`scripts/soak_summary_aggregate.py`) + synthetic fixture + replay test + v1.42 backward-compat regression (OBSV-06, OBSV-07 aggregator side)
> - **203-03** docs (`docs/SOAK_HARNESS.md`, CHANGELOG) + SAFE-07 closure verification (OBSV-08, SAFE-07)

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 203-01-XX | 01 | 1 | OBSV-05, OBSV-07 (capture side) | TBD by planner | Capture script emits structured NDJSON with `load_rtt_delta_us` and supporting fields; `HEALTH_URL` mandatory env var (no hardcoded host) | unit + contract | `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` | ❌ Wave 0 | ⬜ pending |
| 203-02-XX | 02 | 1 | OBSV-06, OBSV-07 (aggregator side) | TBD by planner | Aggregator math is pure stdlib; histogram bucket scheme written into output JSON; v1.42 NDJSON regression matches inline-jq baseline within float tolerance | unit + replay | `.venv/bin/pytest tests/test_phase_203_replay.py -v` | ❌ Wave 0 | ⬜ pending |
| 203-03-XX | 03 | 1 | OBSV-08, SAFE-07 | TBD by planner | Docs name the new field, the matrix contract, and the harness-only invariant; `git diff` shows no `src/wanctl/` change across the phase | manual + diff | grep verification + `git diff <phase-202-close>..HEAD -- src/wanctl/` empty | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky / unpinned*

---

## Wave 0 Requirements

- [ ] `tests/test_phase_203_capture_projection.py` — covers OBSV-05; created in plan 203-01.
- [ ] `tests/test_phase_203_replay.py` — covers OBSV-06 + OBSV-07 (aggregator side); created in plan 203-02.
- [ ] `tests/fixtures/phase_203_synthetic_capture.ndjson` — synthetic NDJSON fixture; created in plan 203-02.
- [ ] `tests/fixtures/phase_203_synthetic_summary.json` — golden expected aggregator output; created in plan 203-02.
- [ ] `scripts/soak-capture.sh` — promoted versioned harness; created in plan 203-01.
- [ ] `scripts/soak_summary_aggregate.py` — new aggregator (Python stdlib only); created in plan 203-02.
- [ ] `docs/SOAK_HARNESS.md` — new operator-facing soak harness doc; created in plan 203-03.

No framework install needed — pytest, jq, and python3 stdlib are already standard project tooling. ShellCheck is not currently enforced by CI; if the planner chooses to add `shellcheck scripts/soak-capture.sh` to plan 203-01's tests, that is a small addition with no infra change.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docs/SOAK_HARNESS.md` and CHANGELOG document the v1.43 capture additions, the zone × cause-tag matrix contract, and the harness-only invariant. | OBSV-08 | Doc-presence grep tests churn on every legitimate edit. Verified once at close via `grep -E "load_rtt_delta_us\|load_rtt_delta_us_by_zone_cause\|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md` returning ≥1 hit per file. | `grep -E "load_rtt_delta_us" docs/SOAK_HARNESS.md CHANGELOG.md` returns ≥1 hit per file. Re-run if either file is materially restructured. |
| Phase 203 introduced no controller tuning; `src/wanctl/` byte-identical vs Phase 202 close. | SAFE-07 (cross-cutting) | "No source diff across an entire phase" is git-diff semantics, not unit-test logic. The existing `test_safe05_threshold_name_counts_are_unchanged` test partially automates this: silent token-rename trips the suite. | `git diff <phase-202-close>..HEAD -- src/wanctl/` must be empty. Re-run before Phase 203 closeout. |

---

## Validation Sign-Off

- [ ] OBSV-05, OBSV-06, OBSV-07 fully automated via `tests/test_phase_203_capture_projection.py` + `tests/test_phase_203_replay.py`
- [ ] OBSV-08 manual-only (docs grep) by design — doc-presence tests are low-signal
- [ ] SAFE-07 partially automated via existing pin test; fully verified by manual `git diff` at closeout
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (achievable: each plan has a primary automated test)
- [ ] Wave 0 covers all MISSING references (see list above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s on phase-scoped slice (~3s actual)
- [ ] `nyquist_compliant: true` set in frontmatter — target modulo OBSV-08 / SAFE-07 manual-only carve-outs (parity with Phase 202)

**Approval:** pending — to be set when planner finalizes per-task rows.
