---
phase: 220-matrix-runner-scope-a1
plan: 02
subsystem: testing
tags: [matrix-runner, yaml, pytest, mann-whitney-u, bootstrap-ci]
requires:
  - phase: 220-matrix-runner-scope-a1
    provides: Plan 01 Wave 0 xfail scaffolds, golden pins, and synthetic fixtures
provides:
  - Full 18-cell Phase 220 matrix YAML with locked thresholds and ATT egress signature
  - Stdlib-plus-PyYAML cube aggregator with replicate median collapse, axis rollups, MWU, and bootstrap CI
  - Passing Phase 220 aggregator test suite replacing Plan 01 strict xfail scaffolds
affects: [phase-220-plan-03, phase-220-plan-04, phase-221-closeout]
tech-stack:
  added: []
  patterns: [inline atomic JSON writes, stdlib statistics, source-floor base_sha anchor]
key-files:
  created:
    - scripts/phase220-matrix-aggregator.py
  modified:
    - scripts/phase220-matrix.yaml
    - tests/test_phase220_matrix_aggregator.py
    - .planning/phases/220-matrix-runner-scope-a1/220-01-SUMMARY.md
key-decisions:
  - "Kept the aggregator free of src.wanctl imports and used inline tempfile + os.replace atomic JSON writes."
  - "Pinned base_sha to 50f3d5136830c284b190b29de939a84406531ecc as the source-floor anchor for later wrapper drift checks."
patterns-established:
  - "Replicate inputs group by base cell_id with trailing __rN stripped, then median p99 drives cell verdicts."
  - "Driver orthogonality requires shared primary_driver across at least two distinct target/path pairs."
requirements-completed: [MATRIX-01, CRITERIA-01, CRITERIA-02, AGGREGATE-01, AGGREGATE-02, AGGREGATE-03]
duration: 7min
completed: 2026-05-31
---

# Phase 220 Plan 02: Matrix Definition and Aggregator Summary

**18-cell target/path/window matrix definition plus stdlib cube aggregator with replicate-aware verdicts, MWU p-values, and bootstrap median-difference CIs.**

## Performance

- **Duration:** 7min
- **Started:** 2026-05-31T11:35:02Z
- **Completed:** 2026-05-31T11:41:41Z
- **Tasks:** 3 planned tasks + 1 lint fix commit
- **Files modified:** 4

## Accomplishments

- Expanded `scripts/phase220-matrix.yaml` from the 4-cell scaffold to all 18 explicit cells (3 targets × 2 paths × 3 windows), preserving all six locked CRITERIA-01 thresholds.
- Captured and pinned ATT egress signature `99.126.115.47`; `paths[name=att].egress_signature` is now non-empty and schema-validated by the aggregator loader.
- Implemented `scripts/phase220-matrix-aggregator.py` with YAML loading, replicate grouping, median p99 collapse, per-cell verdicts, per-target/path/window rollups, matrix-level orthogonal corroboration, MWU, bootstrap CI, scenario fixture loading, CLI output, and inline atomic JSON writes.
- Flipped `tests/test_phase220_matrix_aggregator.py` from strict xfail scaffolds to 17 passing executable tests using the Plan 01 golden pins.

## Golden Pins Reproduced

- `mwu_pin_1.p = 0.0`
- `mwu_pin_2.p = 0.26748958`
- `bootstrap_pin_1 = [-2.0, -2.0]`
- `bootstrap_pin_2 = [-2.0, 1.0]`

## Matrix Definition Checks

- `base_sha`: `50f3d5136830c284b190b29de939a84406531ecc`
- Cells: 18 explicit unique `target__path__window` entries.
- Driver allowlist: `reflector_loss`, `cake_queue_mismatch`.
- ATT egress signature: `99.126.115.47`.

## Verification

- `.venv/bin/pytest tests/test_phase220_matrix_aggregator.py tests/test_phase220_mutation_boundary.py -q` → `22 passed, 1 skipped`
- `.venv/bin/python -c "import yaml; d=yaml.safe_load(open('scripts/phase220-matrix.yaml')); assert d['phase']==220 and len(d['cells'])==18"` → passed
- `.venv/bin/ruff check scripts/phase220-matrix-aggregator.py` → passed
- `.venv/bin/mypy --ignore-missing-imports scripts/phase220-matrix-aggregator.py` → passed
- `git diff --stat src/wanctl/` → no changes
- `git diff --stat scripts/phase213-* scripts/phase214-*` → no changes

## Task Commits

1. **Task 1: Expand matrix YAML** — `31e81a0` (feat)
2. **Task 2: Implement matrix aggregator and flip tests** — `50f3d51` (feat)
3. **Task 3: Replace base_sha placeholder** — `b405752` (fix)
4. **Verification fix: Aggregator lint compliance** — `b5fca6f` (fix)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `scripts/phase220-matrix.yaml` - Full matrix definition, thresholds, driver allowlist, ATT egress signature, and source-floor anchor.
- `scripts/phase220-matrix-aggregator.py` - Cube aggregator public API and CLI.
- `tests/test_phase220_matrix_aggregator.py` - Passing tests for scenarios, rollups, replicate behavior, MWU, bootstrap CI, and driver allowlist loading.
- `.planning/phases/220-matrix-runner-scope-a1/220-01-SUMMARY.md` - Traceability note that Plan 02 reproduced the pre-registered golden pins.

## Decisions Made

- Kept the aggregator free of `src.wanctl.*` imports, following the Plan 02 no-wanctl-import resolution even though earlier research mentioned `atomic_write_json` reuse.
- Treated `base_sha` as a source-floor anchor, not an exact-HEAD requirement; later Phase 220 commits may move HEAD ahead as long as protected paths do not drift.
- Added explicit ruff noqa for `N999`/`N803` because the hyphenated script name and `B` bootstrap parameter are part of the plan contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed aggregator lint failures discovered during plan verification**
- **Found during:** Overall verification after Task 3
- **Issue:** `ruff` rejected the hyphenated script module name, the plan-required `B` parameter name, and a `ValueError` for invalid YAML root type.
- **Fix:** Added targeted file-level ruff exceptions for the plan-constrained names and changed the invalid root-type exception to `TypeError`.
- **Files modified:** `scripts/phase220-matrix-aggregator.py`
- **Verification:** `.venv/bin/ruff check scripts/phase220-matrix-aggregator.py` and Phase 220 tests passed.
- **Committed in:** `b5fca6f`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug).
**Impact on plan:** Verification-only cleanup; no scope or behavior change.

## Issues Encountered

- The project pre-commit documentation hook is interactive for new Python functions. The non-interactive executor could not answer its tty prompt, so the hook's documented `SKIP_DOC_CHECK=1` environment gate was used for commit `50f3d51`; hooks still ran and no `--no-verify` bypass was used.

## Known Stubs

None - Plan 02 goals are fully wired. Plan 03 wrapper scaffolds remain strict xfail from Plan 01, but they are outside this plan's goal and owned by 220-03.

## Threat Flags

None - new YAML parsing and JSON output surfaces were included in the plan threat model and verified with safe loading plus atomic writes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 220-03. The wrapper can now consume finalized YAML with a real `base_sha`, non-empty ATT egress signature, full cell lookup table, and driver allowlist. Plan 04 can later consume both the aggregator and wrapper for the wet daytime control rehearsal.

## Self-Check: PASSED

- Summary path exists: `.planning/phases/220-matrix-runner-scope-a1/220-02-SUMMARY.md`.
- Task commits exist: `31e81a0`, `50f3d51`, `b405752`, `b5fca6f`.
- Key created/modified files exist.
- Final verification commands passed.

---
*Phase: 220-matrix-runner-scope-a1*
*Completed: 2026-05-31*
