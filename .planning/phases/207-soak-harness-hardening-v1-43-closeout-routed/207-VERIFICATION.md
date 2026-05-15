---
phase: 207-soak-harness-hardening-v1-43-closeout-routed
verified: 2026-05-15T21:48:59Z
status: passed
score: "5/5 roadmap success criteria verified"
overrides_applied: 0
requirements:
  - HRDN-01
  - HRDN-02
  - HRDN-03
  - HRDN-04
gaps: []
human_verification: []
review_warnings:
  - id: WR-01
    disposition: advisory_not_blocking
    reason: "Unknown aggregate_watchdog gate_column/statistic can false-pass, but Phase 207 must-haves require legacy-key removal and CALIB-02 NO decision documentation; this warning does not invalidate those must-haves."
---

# Phase 207: Soak / harness hardening (v1.43 closeout-routed) Verification Report

**Phase Goal:** Soak harness hardening for v1.43 closeout routed: HRDN-01 fail-closed source-diff verifier, HRDN-02 transient-tolerant soak capture, HRDN-03 removal of `secondary_gate_legacy`, HRDN-04 CALIB-02 YAML promotion NO decision, and SAFE-09 closeout evidence.
**Verified:** 2026-05-15T21:48:59Z
**Status:** passed
**Re-verification:** No — previous verification existed but had no `gaps:` section requiring targeted re-verification; this pass verified actual files on disk.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `scripts/check-safe07-source-diff.sh` exits non-zero for unstaged, staged, and untracked `src/wanctl/` edits; clean tree exits zero with an explicit current ref. | ✓ VERIFIED | Script lines 32-66 check `git diff --quiet`, `git diff --cached --quiet`, and `git ls-files --others --exclude-standard -- src/wanctl/` before committed diff. `tests/test_check_safe07_source_diff.py` has all seven clean/dirty/regression cases. Live dogfood against `P207_BASE=28b8790ad0a97c1375b2801016e3a67f67e39b46` exited 0. |
| 2 | `scripts/soak-capture.sh` tolerates transient curl/HTTP/jq failures under bounded counters and aborts only after threshold breach. | ✓ VERIFIED | Script lines 13-21 document denominator/schema, lines 35-44 validate env vars, lines 61-160 classify failures, append sidecar TSV, increment counters via `$((... + 1))`, and gate on `SOAK_FAIL_RATE_THRESHOLD` after `MIN_SAMPLES_BEFORE_EVAL`. `tests/test_soak_capture_transient_tolerance.py` has 8 cases. |
| 3 | `secondary_gate_legacy` is removed from live aggregator output; only completed-window dual gate remains; legacy regression retired/reworked. | ✓ VERIFIED | `aggregate_watchdog()` returns only `secondary_gate_completed_window` at `scripts/soak_summary_aggregate.py:333-335`; `aggregate_soak()` mirrors only that key at lines 425-438. Live-code grep across `scripts/` + `src/` found zero `secondary_gate_legacy` hits. Positive-removal tests exist in `tests/test_phase_204_watchdog.py:125-147`; replay asserts absence at `tests/test_phase_204_replay.py:55`. |
| 4 | CALIB-02 YAML-promotion has explicit YES/NO decision in CHANGELOG with rationale. | ✓ VERIFIED | `CHANGELOG.md:10-19` records HRDN-04 CALIB-02 threshold YAML promotion — NO, cites soak `20260512T004208Z`, fail-closed JSON-file convention, `T17(b)`, and `SEED-005`. Repo-wide audit found no YAML `calib_02_threshold:` definitions outside allowed paths. |
| 5 | SAFE-09 phase boundary holds: zero controller-path source diff in Phase 207. | ✓ VERIFIED | `git diff 28b8790... --name-only -- src/wanctl/`, staged diff, unstaged diff, and untracked `src/wanctl/` counts all returned `0`; `207-NN-PLAN.md` files declare no `src/wanctl/` modifications. Full pytest and hot-path slice pass. |

**Score:** 5/5 roadmap success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/check-safe07-source-diff.sh` | Fail-closed verifier for dirty `src/wanctl/` surfaces | ✓ VERIFIED | Exists, substantive, syntax-valid; dirty-tree pre-check is wired before committed-diff logic. |
| `tests/test_check_safe07_source_diff.py` | Regression tests for HRDN-01 | ✓ VERIFIED | Exists with seven subprocess/temp-git tests; focused pytest passed. |
| `scripts/soak-capture.sh` | Transient-tolerant soak capture with sidecar TSV and stable NDJSON | ✓ VERIFIED | Exists, substantive, syntax-valid; sidecar path, threshold, counters, validation, temp truncation, and scrub all present. |
| `tests/test_soak_capture_transient_tolerance.py` | Regression tests for HRDN-02 | ✓ VERIFIED | Exists with eight transient/sustained/env/schema tests; focused pytest passed. |
| `scripts/soak_summary_aggregate.py` | Aggregator with legacy gate removed | ✓ VERIFIED | AST-valid; `aggregate_watchdog()` and `aggregate_soak()` no longer emit `secondary_gate_legacy`. |
| `tests/test_phase_204_watchdog.py` | Positive-removal contract tests | ✓ VERIFIED | `TestLegacyGateRemovalContract` asserts exact key set and top-level omission. |
| `tests/test_phase_204_replay.py` | Replay test asserts legacy-key absence | ✓ VERIFIED | Contains absence assertion and completed-window assertion; no old oracle value remains. |
| `docs/SOAK_HARNESS.md` | Docs with legacy section removed / past-tense note | ✓ VERIFIED | Remaining legacy mentions are removal/history text; no live legacy JSON section. |
| `CHANGELOG.md` | HRDN-03 removal and HRDN-04 NO decision entries | ✓ VERIFIED | v1.44 Unreleased contains HRDN-03 Removed and HRDN-04 Decisions sections. |
| `207-VERIFICATION.md` | SAFE-09 closeout evidence | ✓ VERIFIED | This report updates status and evidence with current verification. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `check-safe07-source-diff.sh` | git worktree/index/untracked surfaces | `git diff`, `git diff --cached`, `git ls-files --others` | ✓ WIRED | Checks run before committed diff and exit 1 with per-surface diagnostics. |
| `tests/test_check_safe07_source_diff.py` | `check-safe07-source-diff.sh` | `subprocess.run(["bash", script, ref])` | ✓ WIRED | Seven tests exercise script behavior in temporary git repos. |
| `soak-capture.sh` | `${CAPTURE_DIR}/soak-capture-errors.tsv` | `printf ... >> "$SIDECAR_TSV"` | ✓ WIRED | Header initialized and failure rows appended after message scrub. |
| `soak-capture.sh` | `${CAPTURE_DIR}/soak-capture.ndjson` | `jq -c ... > "$out_tmp"` then `cat >> soak-capture.ndjson` | ✓ WIRED | Success path appends unchanged NDJSON projection; failures do not emit sentinel rows. |
| `tests/test_soak_capture_transient_tolerance.py` | `soak-capture.sh` | fake `curl` PATH shim + subprocess | ✓ WIRED | Tests execute real script and parse generated NDJSON/TSV. |
| `aggregate_watchdog()` | `aggregate_soak()` | return dict consumed at `watchdog["secondary_gate_completed_window"]` | ✓ WIRED | Top-level summary mirrors only completed-window gate. |
| `CHANGELOG.md` HRDN-04 | `scripts/calib_02_threshold.json` / T17(b) | explicit text references | ✓ WIRED | Decision entry cites JSON artifact, operator approval link, `T17(b)`, and `SEED-005`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `scripts/soak-capture.sh` | `row_failed`, mode counters, NDJSON rows | real `curl` `/health` body -> `jq` projection; tests use fake `curl` to simulate modes | Yes | ✓ FLOWING |
| `scripts/soak_summary_aggregate.py` | completed-window gate value | `aggregate_completed_window_distribution(rows)` from loaded NDJSON rows | Yes | ✓ FLOWING |
| `CHANGELOG.md` HRDN-04 | decision rationale | documented evidence and deferred requirement references | N/A docs | ✓ VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SAFE-09 four surfaces are clean | `git diff "$P207_BASE" --name-only -- src/wanctl/`; cached; unstaged; untracked | All counts `0` | ✓ PASS |
| HRDN-01 dogfood passes with explicit phase baseline | `bash scripts/check-safe07-source-diff.sh "28b8790ad0a97c1375b2801016e3a67f67e39b46"` | `SAFE-07 OK: no src/wanctl/ diff...` | ✓ PASS |
| Phase 207 focused tests pass | `.venv/bin/pytest tests/test_check_safe07_source_diff.py tests/test_soak_capture_transient_tolerance.py tests/test_phase_204_watchdog.py tests/test_phase_204_replay.py -q` | `23 passed, 1 warning in 28.03s` | ✓ PASS |
| Hot-path regression slice passes | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` | `673 passed in 35.25s` | ✓ PASS |
| Full test suite passes | `.venv/bin/pytest tests/ -q` | `5060 passed, 6 skipped, 2 deselected in 226.20s` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HRDN-01 | 207-01, 207-05 | Source-diff verifier fails non-zero on uncommitted/staged `src/wanctl/` edits; manual compensation no longer required. | ✓ SATISFIED | Implementation also covers untracked files; seven tests; live dogfood passed. |
| HRDN-02 | 207-02 | Soak capture survives single transient curl/jq failure and aborts only above documented threshold. | ✓ SATISFIED | Bounded counters, sidecar TSV, env validation, and 8 tests including sustained abort/schema stability. |
| HRDN-03 | 207-03 | `secondary_gate_legacy` removed; only completed-window gate remains; legacy regression retired/reworked. | ✓ SATISFIED | Aggregator output has one key; tests assert absence; live-code grep zero; full suite green. |
| HRDN-04 | 207-04 | CALIB-02 YAML promotion evaluated with explicit YES/NO decision + rationale. | ✓ SATISFIED | CHANGELOG records NO with required rationale anchors; no YAML key or validator/schema edit introduced. |

No additional Phase 207 requirement IDs were found in `.planning/REQUIREMENTS.md`; all four plan-declared IDs are accounted for.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_check_safe07_source_diff.py` | 43 | `# placeholder` in a temp-repo fixture file | ℹ️ Info | Test fixture content only; not production/user-visible. |
| `scripts/soak_summary_aggregate.py` | 303-325 | Code review WR-01: unknown watchdog gate column/statistic can false-pass | ⚠️ Warning | Advisory hardening issue. It does not invalidate Phase 207 must-haves (legacy-key removal and HRDN-04 NO decision), but should be addressed in a later harness validation task. |

### Human Verification Required

None. Phase 207 is offline scripts/tests/docs/CHANGELOG work; no visual flow, deploy, or external service behavior is required for goal verification.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | SAFE-09 script rebadge/default-ref bump and ATT whitelist mode | Phase 209 | ROADMAP Phase 209 SC #1/#4 explicitly owns extended source-diff verifier and SAFE-09 mechanical closeout. |
| 2 | T17(b) deeper CALIB-02 YAML knob shape evaluation | Future v1.45+ | REQUIREMENTS Future Requirements: `T17(b)` gated on `SEED-005`; CHANGELOG HRDN-04 cites this deferral. |

### Gaps Summary

No blocking gaps. Phase 207 achieves its goal: HRDN-01 verifier is fail-closed across dirty git surfaces, HRDN-02 soak capture is transient-tolerant under a bounded counter, HRDN-03 removes the legacy watchdog gate from live output, HRDN-04 records the CALIB-02 YAML-promotion NO decision, and SAFE-09 phase-boundary checks are clean. Code review WR-01 remains advisory and does not invalidate these must-haves.

---

_Verified: 2026-05-15T21:48:59Z_
_Verifier: the agent (gsd-verifier)_
