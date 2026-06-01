---
phase: 220-matrix-runner-scope-a1
verified: 2026-06-01T15:53:11Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 220: Matrix Runner (Scope A1) Verification Report

**Phase Goal:** Land the target/path/window matrix runner with pre-registered decision criteria and a verified harness so Phase 221 evidence collection runs against immutable rules.
**Verified:** 2026-06-01T15:53:11Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `scripts/phase220-matrix.yaml` is committed with canonical 18-cell target/path/window matrix, pre-registered criteria, locked thresholds, base_sha, and close-with-prejudice rule support. | ✓ VERIFIED | YAML parses with `phase: 220`, `schema_version: 1`, real 40-char `base_sha`, exact six thresholds, driver allowlist, non-empty ATT egress signature, and 18 unique Cartesian cells. Committed history includes Plan 02 matrix commits. |
| 2 | `scripts/phase220-target-path-matrix.sh` dry-run executes a zero-cell rehearsal cleanly with D-14 guard, window gate, Phase 213 delegation, sidecar wiring, and no Phase 213/214 edits. | ✓ VERIFIED | Dry-run returned 0 and printed `DRY-RUN: bash scripts/phase213-baseline-capture.sh --bind-map spectrum=... --host dallas`. Script contains src/wanctl and scripts/phase213-/phase214- drift guards, Phase 214 align/classify invocation, and `phase220-cell.json` sidecar write. |
| 3 | One wet daytime Spectrum + dallas control cell reproduces the Phase 214 canonical anchor via unchanged extractor/aligner/classifier. | ✓ VERIFIED | Evidence files exist and are committed in `5f0c74c`; `phase220-cell.json` records canonical dallas/spectrum/daytime/r1; `signal-sheet.json` verdict `ambiguous`, primary_driver `reflector_loss`; Phase 214 anchor has same fields; `REHEARSAL-VERDICT.md` contains `✓ MATCH`. |
| 4 | Wave 0 tests and pinned statistics fixtures landed before live supplemental-cell collection and now pass with implementation. | ✓ VERIFIED | `tests/test_phase220_matrix_aggregator.py` contains MWU/bootstrap pins (`0.26748958`, `[-2.0, -2.0]`, `[-2.0, 1.0]`) and no xfail/TODO placeholders; recent suite reports 53 Phase 220 tests passing. Spot-check reproduced aggregator scenario and statistics pins. |
| 5 | SAFE-11 mutation boundary remains green: controller surface untouched; docs are CLI-only with no tuning language. | ✓ VERIFIED | `tests/test_phase220_mutation_boundary.py` sets `ALLOWED_SRC_PATHS = []`, forbids src/wanctl and Phase 213/214 drift, and docs token scan exists. Recent focused and regression suites passed; `git status --short` was clean. Anti-pattern scan found no forbidden tuning tokens in Phase 220 docs. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/phase220-matrix.yaml` | Canonical matrix definition with CRITERIA-01 thresholds, close-with-prejudice support, `base_sha`, paths, targets, windows, cells, statistical config | ✓ VERIFIED | 18 unique cells; dallas/Vultr Dallas/Vultr Chicago × Spectrum/ATT × off-peak/daytime/prime-time; ATT egress signature non-empty. |
| `scripts/phase220-matrix-aggregator.py` | Cube rollup, cell verdicts, replicate median grouping, MWU, bootstrap CI, CLI, atomic output | ✓ VERIFIED | Public functions exist; no NumPy/SciPy/pandas; no `src.wanctl` import; scenario and statistics spot-checks passed. |
| `scripts/phase220-target-path-matrix.sh` | Per-cell wrapper composing Phase 213/214 unchanged | ✓ VERIFIED | Executable bash script; delegates to Phase 213, invokes Phase 214 align/classify, writes sidecar, enforces base_sha and ATT egress guards. |
| `tests/test_phase220_*.py` | Wave 0/aggregator/wrapper/mutation tests | ✓ VERIFIED | Tests are substantive and currently passing; no residual xfail/TODO placeholders. |
| `docs/PHASE220-MATRIX-RUNNER.md` | Operator-facing CLI documentation only | ✓ VERIFIED | Exists and references wrapper/aggregator/YAML; anti-pattern scan found no tuning/future-policy language. |
| Wet rehearsal evidence directory | Phase 220 cell sidecar, Phase 214 signal sheet, verdict comparison | ✓ VERIFIED | `phase220-cell.json`, `signal-sheet.json`, `REHEARSAL-VERDICT.md` exist and are committed. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Aggregator | `scripts/phase220-matrix.yaml` | `yaml.safe_load`, `load_matrix_definition()` | ✓ WIRED | Reads thresholds, driver allowlist, cells/paths and validates ATT egress signature. |
| Aggregator | Scenario fixtures / live evidence | `aggregate_scenario()` and `aggregate()` | ✓ WIRED | Reads fixture manifests/signal sheets and live wrapper `run_dir/path/tcp_12down/signal-sheet.json` layout. |
| Wrapper | `scripts/phase220-matrix.yaml` | Python YAML loader | ✓ WIRED | Resolves `base_sha`, cell target/path/window, bind map, egress signature, and threshold metadata. |
| Wrapper | `scripts/phase213-baseline-capture.sh` | Bash array delegate command | ✓ WIRED | Dry-run printed exact delegate command; script invokes delegate in live branch. |
| Wrapper | Phase 214 analyzer chain | `phase214-align.py` then `phase214-classify.py` | ✓ WIRED | Live branch emits `signal-sheet.json`; wet rehearsal evidence proves the chain ran. |
| Rehearsal verdict | Phase 214 anchor | On-disk anchor comparison | ✓ WIRED | Verdict and primary driver matched archived Phase 214 dallas daytime signal sheet. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/phase220-matrix-aggregator.py` | `records` / collapsed `cells` / `summary` | `phase220-cell.json` + `signal-sheet.json` under fixtures or evidence root | Yes | ✓ FLOWING |
| `scripts/phase220-target-path-matrix.sh` | `YAML_BASE_SHA`, `CELL_ID`, `BIND_MAP`, `RUN_DIR`, `signal-sheet.json` | Matrix YAML + delegated Phase 213 capture + Phase 214 align/classify output | Yes | ✓ FLOWING |
| Wet rehearsal evidence | `verdict`, `primary_driver`, `latency.p99_ms` | Live delegated capture and unchanged Phase 214 classifier | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Matrix YAML has full locked contract | Python YAML assertion block | `matrix_yaml_ok` | ✓ PASS |
| Aggregator reproduces scenario/statistics pins | Python import + `aggregate_scenario()` + MWU/bootstrap assertions | `aggregator_ok` | ✓ PASS |
| Wrapper dry-run zero-cell rehearsal | `PHASE220_BASE_SHA=$(...) ./scripts/phase220-target-path-matrix.sh --dry-run --test-hour 12 --cell dallas__spectrum__daytime --replicate 1` | Exit 0; printed Phase 213 delegate command | ✓ PASS |
| Wet rehearsal matches Phase 214 anchor | Python JSON comparison of Phase 220 evidence vs archived Phase 214 anchor | `rehearsal_ok` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| CRITERIA-01 | 220-01, 220-02 | Pre-registered kill/defect criteria before live matrix cells | ✓ SATISFIED | `scripts/phase220-matrix.yaml` has exact locked thresholds and was finalized before rehearsal evidence. |
| CRITERIA-02 | 220-02 / roadmap | Close-with-prejudice rule documented and implemented as verdict vocabulary | ✓ SATISFIED | Aggregator returns `carried_narrower_with_close_with_prejudice_rule`; tests assert carry paths. |
| MATRIX-01 | 220-02, 220-04 | Canonical matrix YAML with control/supplemental targets, path/window axes, base_sha | ✓ SATISFIED | 18-cell Cartesian matrix verified. |
| MATRIX-02 | 220-03, 220-04 | Wrapper composes Phase 214 pattern and edits no Phase 213/214 scripts | ✓ SATISFIED | Wrapper dry-run/delegate wiring verified; mutation-boundary and wrapper drift tests enforce zero edits. |
| MATRIX-03 | 220-03, 220-04 | Source-bind/egress verification and mtr snapshots | ✓ SATISFIED | YAML has ATT egress signature; wrapper hard-fails ATT mismatch/missing signature; rehearsal sidecar has `mtr_snapshot_path`. |
| MATRIX-04 | 220-03, 220-04 | Per-cell run delegates analysis to unchanged Phase 214 extractor/aligner/classifier | ✓ SATISFIED | Wrapper invokes `phase214-align.py` and `phase214-classify.py`; rehearsal signal sheet is Phase 214 output. |
| AGGREGATE-01 | 220-01, 220-02, 220-04 | Stdlib/PyYAML aggregator extends Phase 214 summary to cube rollup | ✓ SATISFIED | Aggregator script exists, no disallowed stats deps, supports CLI and scenario/live evidence aggregation. |
| AGGREGATE-02 | 220-01, 220-02, 220-04 | Distinct per-cell/per-target/per-path/per-window/matrix rollups; canonical separate | ✓ SATISFIED | Aggregator returns `per_cell`, `per_target`, `per_path`, `per_window`; tests assert `canonical_dallas` separation. |
| AGGREGATE-03 | 220-01, 220-02, 220-04 | MWU + bootstrap CI with pinned golden fixtures | ✓ SATISFIED | `mann_whitney_u()` and `bootstrap_ci_median_difference()` implemented; pinned tests and spot-check pass. |
| SAFE-11 | 220-01, 220-03, 220-04 | Expanded mutation boundary and docs restrictions | ✓ SATISFIED | Mutation-boundary test enforces no src/wanctl, Phase 213/214, or tuning-doc drift; recent suite passed. |

No orphaned Phase 220 requirement IDs were found: the 10 IDs named by the user are all present in plan frontmatter and `.planning/REQUIREMENTS.md` maps them to Phase 220.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| — | — | — | — | No Phase 220 TODO/FIXME/placeholders, residual xfail markers, or forbidden docs tuning tokens found in scoped scans. |

### Human Verification Required

None. The formerly human-gated wet daytime rehearsal has committed evidence and a machine-checkable anchor comparison.

### Gaps Summary

No blocking gaps found. A few `gsd-sdk verify.*` frontmatter checks report expected false negatives against superseded intermediate plan text: Plan 01 required xfail markers that Plans 02/03 intentionally removed, Plan 02's older key-link text mentioned `src.wanctl.state_utils` reuse but the final accepted implementation uses inline atomic writes per review resolution, and Plan 04's anchor link wording differs from the exact grep pattern while the anchor path and comparison are present. These do not reduce goal achievement.

---

_Verified: 2026-06-01T15:53:11Z_
_Verifier: the agent (gsd-verifier)_
