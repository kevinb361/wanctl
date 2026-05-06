---
phase: 203
slug: target-edge-churn-instrumentation-obsv
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-06
audited: 2026-05-06
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
| OBSV-05 | Capture script emits `load_rtt_delta_us` + 6 supporting fields per NDJSON row | unit / contract | `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v -k "load_rtt_delta_us or new_fields"` | ✅ | plan 203-01 ✅ |
| OBSV-06 | `soak-summary.json` aggregator emits `load_rtt_delta_us` p50/p95/p99/max + histogram + zone × cause-tag matrix | unit + replay | `.venv/bin/pytest tests/test_phase_203_replay.py -v -k "aggregator_math or by_zone_cause or histogram"` | ✅ | plan 203-02 ✅ |
| OBSV-07 | Golden-fixture replay (dual-fixture: capture-projection contract + aggregator-math against synthetic NDJSON) | replay | `.venv/bin/pytest tests/test_phase_203_replay.py -v` and `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` | ✅ | plans 203-01 + 203-02 ✅ |
| OBSV-08 | Docs (`docs/SOAK_HARNESS.md`, CHANGELOG `v1.43-dev`) name the new field, the matrix contract, and the no-control-path-change invariant | manual-only | `grep -E "load_rtt_delta_us\|load_rtt_delta_us_by_zone_cause\|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md` returns ≥1 hit per file per pattern | ✅ | plan 203-03 ✅ |
| SAFE-07 | No control-path source diff between Phase 201 close and Phase 203 close. v1.40/v1.41/v1.42/v1.42-Phase-202 pin block in `tests/test_phase_195_replay.py` produces identical assertion results. | regression + diff (now scripted) | `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` AND `bash scripts/check-safe07-source-diff.sh` (default vs `b72b463`) | ✅ pin test + gate script | scripted at closeout (WR-01 residual: gate ignores uncommitted edits) |

---

## Per-Task Verification Map

> Filled by planner. Recommended slicing from research §Recommended plan slicing:
> - **203-01** capture script (`scripts/soak-capture.sh`) + capture-projection test (OBSV-05, OBSV-07 capture side)
> - **203-02** aggregator (`scripts/soak_summary_aggregate.py`) + synthetic fixture + replay test + v1.42 backward-compat regression (OBSV-06, OBSV-07 aggregator side)
> - **203-03** docs (`docs/SOAK_HARNESS.md`, CHANGELOG) + SAFE-07 closure verification (OBSV-08, SAFE-07)

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 203-01 | 01 | 1 | OBSV-05, OBSV-07 (capture side) | T-OBSV-05 (no public-safe leakage; mandatory `HEALTH_URL`) | Capture script emits structured NDJSON with `load_rtt_delta_us` and supporting fields; `HEALTH_URL` mandatory env var (no hardcoded host); public-safe grep clean | unit + contract | `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` | ✅ | ✅ green |
| 203-02 | 02 | 1 | OBSV-06, OBSV-07 (aggregator side) | T-OBSV-06 (golden-fixture drift; null-safety in histogram math) | Aggregator math is pure stdlib; histogram bucket scheme written into output JSON; deterministic generator + golden fixture; v1.42 NDJSON regression matches inline-jq baseline within float tolerance | unit + replay | `.venv/bin/pytest tests/test_phase_203_replay.py -v` | ✅ | ✅ green |
| 203-03 | 03 | 1 | OBSV-08, SAFE-07 | T-SAFE-07 (silent control-path change) | Docs name the new field, the matrix contract, and the harness-only invariant; `scripts/check-safe07-source-diff.sh` is committed and re-runnable | manual grep + scripted diff | `grep -E "load_rtt_delta_us\|load_rtt_delta_us_by_zone_cause\|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md` AND `bash scripts/check-safe07-source-diff.sh` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky / unpinned*

---

## Wave 0 Requirements

- [x] `tests/test_phase_203_capture_projection.py` — covers OBSV-05; created in plan 203-01.
- [x] `tests/test_phase_203_replay.py` — covers OBSV-06 + OBSV-07 (aggregator side); created in plan 203-02.
- [x] `tests/fixtures/phase_203_synthetic_capture.ndjson` — synthetic NDJSON fixture; created in plan 203-02.
- [x] `tests/fixtures/phase_203_synthetic_summary.json` — golden expected aggregator output; created in plan 203-02.
- [x] `tests/fixtures/_phase_203_generator.py` — deterministic fixture generator (seed=42); created in plan 203-02 (added during execution).
- [x] `scripts/soak-capture.sh` — promoted versioned harness; created in plan 203-01.
- [x] `scripts/soak_summary_aggregate.py` — new aggregator (Python stdlib only); created in plan 203-02.
- [x] `scripts/check-safe07-source-diff.sh` — re-runnable SAFE-07 source-diff gate; added in plan 203-03 (promotes SAFE-07 from manual to scripted).
- [x] `docs/SOAK_HARNESS.md` — new operator-facing soak harness doc; created in plan 203-03.

No framework install needed — pytest, jq, and python3 stdlib are already standard project tooling. ShellCheck is not currently enforced by CI; if the planner chooses to add `shellcheck scripts/soak-capture.sh` to plan 203-01's tests, that is a small addition with no infra change.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docs/SOAK_HARNESS.md` and CHANGELOG document the v1.43 capture additions, the zone × cause-tag matrix contract, and the harness-only invariant. | OBSV-08 | Doc-presence grep tests churn on every legitimate edit. Verified once at close via `grep -E "load_rtt_delta_us\|load_rtt_delta_us_by_zone_cause\|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md` returning ≥1 hit per file. | `grep -E "load_rtt_delta_us" docs/SOAK_HARNESS.md CHANGELOG.md` returns ≥1 hit per file. Verified at audit: 19 hits across both files. Re-run if either file is materially restructured. |
| Phase 203 introduced no controller tuning; `src/wanctl/` byte-identical vs Phase 202 close. | SAFE-07 (cross-cutting) | "No source diff across an entire phase" is git-diff semantics, not unit-test logic. The existing `test_safe05_threshold_name_counts_are_unchanged` test partially automates this; the new `scripts/check-safe07-source-diff.sh` automates the diff itself. | `bash scripts/check-safe07-source-diff.sh` (default base `b72b463`) must print `SAFE-07 OK`. WR-01 residual: gate ignores uncommitted/staged `src/wanctl/` edits — verifier compensates with `git diff` / `git diff --cached -- src/wanctl/` at closeout. |

---

## Validation Sign-Off

- [x] OBSV-05, OBSV-06, OBSV-07 fully automated via `tests/test_phase_203_capture_projection.py` + `tests/test_phase_203_replay.py` (56 passed in 3.06s at audit)
- [x] OBSV-08 manual-only (docs grep) by design — doc-presence tests are low-signal; closeout grep returned 19 hits across both files
- [x] SAFE-07 scripted via `scripts/check-safe07-source-diff.sh` (committed, executable, `bash -n` clean) plus the existing `safe05_threshold_name_counts` pin test; WR-01 residual handled by closeout `git diff` checks
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (each of 203-01/02/03 has a primary automated test or scripted gate)
- [x] Wave 0 covers all MISSING references (all artifacts now exist; see list above)
- [x] No watch-mode flags
- [x] Feedback latency < 60s on phase-scoped slice (3.06s actual)
- [x] `nyquist_compliant: true` set in frontmatter — OBSV-08 manual-only by design; SAFE-07 now scripted (parity with / improvement on Phase 202)

**Approval:** validated 2026-05-06 — phase 203 is Nyquist-compliant; the only residual is WR-01 (uncommitted-edit blind spot in `check-safe07-source-diff.sh`), already tracked as a residual risk in `203-VERIFICATION.md` and `203-REVIEW.md`.

---

## Validation Audit 2026-05-06

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Already covered | 5 (OBSV-05, OBSV-06, OBSV-07, OBSV-08 manual-by-design, SAFE-07 scripted) |

**Audit notes:**

- All Wave 0 artifacts exist on disk; statuses moved from ⬜ pending → ✅ green and File Exists ❌ → ✅.
- Phase test slice green: `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` → `56 passed in 3.06s`.
- SAFE-07 gate green: `bash scripts/check-safe07-source-diff.sh` → `SAFE-07 OK: no src/wanctl/ diff vs b72b463`.
- OBSV-08 doc grep: `grep -E "load_rtt_delta_us|load_rtt_delta_us_by_zone_cause|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md` → 19 hits (≥1 per file per pattern).
- SAFE-07 promoted from "manual diff at closeout" to scripted via `scripts/check-safe07-source-diff.sh`, which is committed, executable, and re-runnable; this is a strict improvement over the pre-execution plan.
- No `gsd-nyquist-auditor` spawn required — zero MISSING / PARTIAL items.
- Residual: WR-01 (gate ignores uncommitted/staged `src/wanctl/` edits). Tracked in `203-VERIFICATION.md` Residual Risks; not blocking.
