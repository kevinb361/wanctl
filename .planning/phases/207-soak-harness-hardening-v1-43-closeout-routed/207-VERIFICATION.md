---
phase: 207-soak-harness-hardening-v1-43-closeout-routed
verified: 2026-05-15T21:31:44Z
status: passed
score: "5/5 success criteria verified"
requirements: [HRDN-01, HRDN-02, HRDN-03, HRDN-04]
---

# Phase 207: Soak / harness hardening (v1.43 closeout-routed) — Verification Report

**Phase Goal:** The v1.43-deferred soak/harness debt is closed: source-diff verifier is trustworthy without manual compensation, soak captures survive transient curl/jq blips, the dual-gate legacy block is gone, and CALIB-02's YAML-promotion question has an explicit YES/NO answer with rationale.

**Status:** passed
**Phase 207 baseline ref:** `28b8790ad0a97c1375b2801016e3a67f67e39b46` (parent of `b44a1b4dbe75857005956c54b120c1f3bffec9d6`, the first commit touching this phase directory)

## Success Criteria

| # | Criterion (ROADMAP wording) | Status | Evidence |
|---|------------------------------|--------|----------|
| 1 | `scripts/check-safe07-source-diff.sh` exits non-zero on uncommitted/staged/untracked `src/wanctl/` edits; clean tree exits zero (when invoked with a current ref). | ✓ VERIFIED | Plan 207-01: HRDN-01 three-surface dirty-tree pre-check added (unstaged + staged + untracked); `tests/test_check_safe07_source_diff.py` covers seven scenarios; all PASSED. Live self-test: `bash scripts/check-safe07-source-diff.sh "28b8790ad0a97c1375b2801016e3a67f67e39b46"` exited 0. |
| 2 | `scripts/soak-capture.sh` survives a single transient curl/jq failure under a bounded counter; aborts only when failure rate exceeds threshold. | ✓ VERIFIED | Plan 207-02: SOAK_FAIL_RATE_THRESHOLD (default 0.01), MIN_SAMPLES_BEFORE_EVAL (default 60), sidecar TSV at ${CAPTURE_DIR}/soak-capture-errors.tsv. Env-var validation, temp-file truncation per iteration, TSV scrubbing, arithmetic counter increments all in place. `tests/test_soak_capture_transient_tolerance.py` covered transient modes, sustained-abort, env-var validation, and NDJSON schema stability; focused slice PASSED. NDJSON schema unchanged. |
| 3 | `secondary_gate_legacy` removed from `aggregate_watchdog()`; only completed-window dual gate remains; legacy regression retired or rewritten; full test suite passes. | ✓ VERIFIED | Plan 207-03: atomic 5-site sweep (aggregator + 2 test files + docs + CHANGELOG). `TestV142WatchdogRegression` retired; `TestLegacyGateRemovalContract` added; live-code grep gate (`scripts/` + `src/`, NOT `tests/`) returns 0 lines; tests/ audit allowlist enforced. Distribution test audit confirmed already on new contract. Full pytest green. |
| 4 | CALIB-02 YAML-promotion has explicit YES/NO decision in CHANGELOG with rationale. | ✓ VERIFIED | Plan 207-04: NO route documented; three rationale anchors (CALIB-04 PASS at 175 from soak `20260512T004208Z`; fail-closed JSON-file convention; T17(b) gated on SEED-005). `scripts/calib_02_threshold.json` byte-identical at phase close (verified via `git diff --exit-code`). Repo-wide L-3 audit confirmed no accidental YAML-key introduction. |
| 5 | SAFE-09 phase-boundary: zero control-path source diff in this phase. | ✓ VERIFIED | See "SAFE-09 Four-Surface Boundary Diff" section below — all four surfaces empty at gate-time (Block 2) AND at report-write time (Block 6, M-5 belt-and-suspenders). Plus defensive plan-grep PASS. |

**Score:** 5/5 success criteria verified

## SAFE-09 Four-Surface Boundary Diff (Gate — Block 2)

P207_BASE: `28b8790ad0a97c1375b2801016e3a67f67e39b46`. Phase 207 touches no `src/wanctl/` files by construction; all four git surfaces MUST be empty.

### Surface 1 — Committed diff vs P207_BASE

```text
$ git diff 28b8790ad0a97c1375b2801016e3a67f67e39b46 --name-only -- src/wanctl/ | sort -u

$ git diff 28b8790ad0a97c1375b2801016e3a67f67e39b46 --name-only -- src/wanctl/ | sort -u | wc -l
0
```

### Surface 2 — Staged-but-not-committed diff

```text
$ git diff --cached --name-only -- src/wanctl/ | sort -u

$ git diff --cached --name-only -- src/wanctl/ | sort -u | wc -l
0
```

### Surface 3 — Working-tree unstaged edits

```text
$ git diff --name-only -- src/wanctl/ | sort -u

$ git diff --name-only -- src/wanctl/ | sort -u | wc -l
0
```

### Surface 4 — Untracked files under src/wanctl/

```text
$ git ls-files --others --exclude-standard -- src/wanctl/ | sort -u

$ git ls-files --others --exclude-standard -- src/wanctl/ | wc -l
0
```

### Diagnostic: short status under src/wanctl/

```text
$ git status --short -- src/wanctl/
```

### Diagnostic (L-4): ignored entries under src/wanctl/

```text
$ git status --ignored --short -- src/wanctl/
!! src/wanctl/__pycache__/
!! src/wanctl/backends/__pycache__/
!! src/wanctl/dashboard/__pycache__/
!! src/wanctl/dashboard/widgets/__pycache__/
!! src/wanctl/steering/__pycache__/
!! src/wanctl/storage/__pycache__/
!! src/wanctl/tuning/__pycache__/
!! src/wanctl/tuning/strategies/__pycache__/
```

The ignored entries are diagnostic-only Python bytecode cache directories; they are not acceptance-gated and are excluded from `git ls-files --others --exclude-standard`.

## SAFE-09 Four-Surface Re-Check (Report-Write Time — Block 6, M-5)

Belt-and-suspenders: re-running the four surface checks immediately before writing this report. All four MUST still report 0.

```text
$ git diff 28b8790ad0a97c1375b2801016e3a67f67e39b46 --name-only -- src/wanctl/ | sort -u | wc -l
0
$ git diff --cached --name-only -- src/wanctl/ | sort -u | wc -l
0
$ git diff --name-only -- src/wanctl/ | sort -u | wc -l
0
$ git ls-files --others --exclude-standard -- src/wanctl/ | wc -l
0
```

All four surface counts at report-write time match the gate-time values (all `0`). Phase has not drifted between gate and write.

## HRDN-01 self-test (dogfood against P207_BASE — H-1 resolution)

The post-HRDN-01 script is invoked with the explicit P207_BASE ref (NOT the stale default `b72b463` — D-07 keeps that for Phase 209's bump). The script's three-surface pre-check (unstaged + staged + untracked) confirms the worktree is clean AND the committed diff vs `28b8790ad0a97c1375b2801016e3a67f67e39b46` is empty.

```text
$ bash scripts/check-safe07-source-diff.sh "28b8790ad0a97c1375b2801016e3a67f67e39b46"
SAFE-07 OK: no src/wanctl/ diff vs 28b8790ad0a97c1375b2801016e3a67f67e39b46
exit=0
```

## Defensive plan-grep (files_modified frontmatter)

Every `207-NN-PLAN.md` was scanned. No plan declares a `files_modified` entry under `src/wanctl/`. SAFE-09 holds by construction.

```text
$ .venv/bin/python3 ... (see Block 4 in Plan 05 Task 1)
PASS: no 207-NN-PLAN.md declares files_modified under src/wanctl/
```

Plans inspected:
- 207-01-PLAN.md (HRDN-01): `scripts/check-safe07-source-diff.sh`, `tests/test_check_safe07_source_diff.py`
- 207-02-PLAN.md (HRDN-02): `scripts/soak-capture.sh`, `tests/test_soak_capture_transient_tolerance.py`
- 207-03-PLAN.md (HRDN-03): `scripts/soak_summary_aggregate.py`, `tests/test_phase_204_watchdog.py`, `tests/test_phase_204_replay.py`, `docs/SOAK_HARNESS.md`, `CHANGELOG.md`
- 207-04-PLAN.md (HRDN-04): `CHANGELOG.md`
- 207-05-PLAN.md (this plan): `.planning/phases/207-soak-harness-hardening-v1-43-closeout-routed/207-VERIFICATION.md`

None under `src/wanctl/`.

## Test Evidence

Full pytest suite:

```text
$ .venv/bin/pytest tests/ -q
........................................................................ [ 96%]
........................................................................ [ 98%]
........................................................................ [ 99%]
..........................                                               [100%]
5060 passed, 6 skipped, 2 deselected in 217.37s (0:03:37)
```

Hot-path slice (per CLAUDE.md):

```text
$ .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
........................................................................ [ 74%]
........................................................................ [ 85%]
........................................................................ [ 96%]
.........................                                                [100%]
673 passed in 41.20s
```

Phase-207-focused slice:

```text
$ .venv/bin/pytest tests/test_check_safe07_source_diff.py tests/test_soak_capture_transient_tolerance.py tests/test_phase_204_watchdog.py tests/test_phase_204_replay.py -q
.......................                                                  [100%]
=============================== warnings summary ===============================
tests/test_soak_capture_transient_tolerance.py:189
  /home/kevin/projects/wanctl/tests/test_soak_capture_transient_tolerance.py:189: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.slow

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
23 passed, 1 warning in 26.81s
```

## Requirements Coverage

| Requirement | Source Plan | Status | Closure evidence |
|-------------|-------------|--------|------------------|
| HRDN-01 | 207-01 | ✓ SATISFIED | `scripts/check-safe07-source-diff.sh` carries three-surface dirty-tree pre-check (unstaged + staged + untracked); 7 pytest cases PASS; live self-test against P207_BASE exited 0. |
| HRDN-02 | 207-02 | ✓ SATISFIED | `scripts/soak-capture.sh` carries bounded-counter logic + sidecar TSV + env-var validation + temp-file truncation + TSV scrubbing + arithmetic counter increments; focused pytest cases PASS; NDJSON schema unchanged. |
| HRDN-03 | 207-03 | ✓ SATISFIED | 5-site atomic sweep complete; live-code grep gate (scripts/ + src/) returns 0 lines; tests/ audit allowlist enforced; distribution test M-3 audit confirmed; full pytest green. |
| HRDN-04 | 207-04 | ✓ SATISFIED | CHANGELOG.md HRDN-04 NO entry with three rationale anchors; `scripts/calib_02_threshold.json` byte-identical via `git diff --exit-code`; `src/wanctl/check_config_validators.py` byte-identical; L-3 repo-wide YAML-key audit clean. |

## Anti-Patterns Found

None. Phase 207 is scripts/tests/docs/CHANGELOG only — no `src/wanctl/` edits across any of the four git surfaces (verified twice — gate + report-time), no controller-threshold/algorithm changes, no `/health` field additions.

## Human Verification Required

None. Phase 207 is offline harness + docs; no deploy or visual behavior to verify.

## Gaps Summary

No blocking gaps. Phase 207 achieves its goal: source-diff verifier hardened end-to-end (now covering all three pre-commit surfaces), soak-capture transient-tolerant under a bounded threshold with edge-case hardening, legacy gate retired across all 5 sites, CALIB-02 YAML-promotion routed to NO with rationale. SAFE-09 invariant holds across all four git surfaces (verified twice); HRDN-01's verifier dogfoods cleanly on this phase's head against P207_BASE.

Follow-up (deferred per CONTEXT.md):
- T17(b) CALIB-02 deep schema-design work — gated on SEED-005 outcomes, deferred to v1.45+.
- Phase 209 SAFE-09 mechanical closeout — rebadging `check-safe07-source-diff.sh` to SAFE-09, default-ref bump from `b72b463`, and ATT-config whitelist mode are Phase 209's deliverables.

---

_Verified: 2026-05-15T21:31:44Z_
_Verifier: Plan 207-05 closeout task_
