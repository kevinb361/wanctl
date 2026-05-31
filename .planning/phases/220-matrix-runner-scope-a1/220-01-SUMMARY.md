---
phase: 220-matrix-runner-scope-a1
plan: 01
subsystem: testing
tags: [pytest, fixtures, matrix-runner, safe-11, stdlib-statistics]
requires:
  - phase: 219-ingestion-rate-observability-scope-d
    provides: v1.47 D-first observability complete before matrix runner work
provides:
  - Wave 0 Phase 220 mutation-boundary test for SAFE-11
  - Matrix YAML scaffold with locked thresholds and live bind-IP note
  - Independent stdlib golden-pin precompute script
  - Aggregator and wrapper pytest scaffold contracts
  - Synthetic signal-sheet, cell-manifest, and scenario fixtures
affects: [phase-220-plan-02, phase-220-plan-03, phase-220-plan-04, phase-221-closeout]
tech-stack:
  added: []
  patterns: [strict-xfail Wave 0 contract, observed-evidence fixture shape, stdlib-only reference statistics]
key-files:
  created:
    - scripts/phase220-matrix.yaml
    - scripts/phase220-precompute-pins.py
    - tests/test_phase220_mutation_boundary.py
    - tests/test_phase220_matrix_aggregator.py
    - tests/test_phase220_matrix_wrapper.py
    - tests/fixtures/phase220/
  modified: []
key-decisions:
  - "Phase 220 Wave 0 keeps controller behavior read-only: no src/wanctl, Phase 213, or Phase 214 script mutations."
  - "Plan 01 matrix YAML intentionally remains a scaffold; Plan 02 owns final base_sha, full 18-cell expansion, and non-empty ATT egress signature."
patterns-established:
  - "Wave 0 tests are committed before implementation and marked strict xfail where future plans must flip them."
  - "Synthetic fixtures use observed signal-sheet/cell-manifest shapes rather than expected_behavior fixture names."
requirements-completed: [SAFE-11, AGGREGATE-01, AGGREGATE-02, AGGREGATE-03, MATRIX-02, MATRIX-03, CRITERIA-01]
duration: 10min
completed: 2026-05-31
---

# Phase 220 Plan 01: Wave 0 Matrix Runner Scaffolds Summary

**Read-only Wave 0 matrix-runner contract with SAFE-11 boundary tests, precomputed statistics pins, and synthetic fixtures for follow-on aggregator/wrapper plans.**

## Performance

- **Duration:** 10min
- **Started:** 2026-05-31T11:21:54Z
- **Completed:** 2026-05-31T11:31:26Z
- **Tasks:** 5 task commits / 4 plan tasks
- **Files modified:** 35

## Accomplishments

- Added `scripts/phase220-matrix.yaml` scaffold with locked thresholds, driver allowlist, live bind-IP verification note, and four wrapper-needed stub cells.
- Added `scripts/phase220-precompute-pins.py`, a stdlib-only independent reference that emits the pre-registered golden pins:
  - `mwu_pin_1.p = 0.0`
  - `mwu_pin_2.p = 0.26748958`
  - `bootstrap_pin_1 = [-2.0, -2.0]`
  - `bootstrap_pin_2 = [-2.0, 1.0]`
- Added SAFE-11 mutation-boundary coverage for Phase 220 with zero `src/wanctl/`, Phase 213 script, and Phase 214 script diffs allowed.
- Added aggregator and wrapper Wave 0 pytest scaffolds plus 10 signal sheets, 10 cell manifests, and 6 scenario YAMLs.

## Wave 0 Pre-Registered Golden Pins (computed before Plan 02)

Command: `.venv/bin/python scripts/phase220-precompute-pins.py`

```json
{
  "mwu_pin_1": {"p": 0.0},
  "mwu_pin_2": {"p": 0.26748958},
  "bootstrap_pin_1": {"ci_lower": -2.0, "ci_upper": -2.0},
  "bootstrap_pin_2": {"ci_lower": -2.0, "ci_upper": 1.0}
}
```

The same literal values are embedded in `tests/test_phase220_matrix_aggregator.py`; no `TODO_FILL_AT_IMPL_TIME` placeholders remain.

## Task Commits

1. **Task 0: Matrix YAML scaffold** — `2969289` (feat)
2. **Task 0b: Golden pin precompute script** — `d3d9be7` (feat)
3. **Task 1: Mutation-boundary test** — `e4968f3` (test)
4. **Task 2: Aggregator/wrapper xfail scaffolds** — `e6bc520`, `2817795` (test)
5. **Task 2: Synthetic fixtures** — `00fb4a7` (test)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `scripts/phase220-matrix.yaml` - Plan 01 scaffold for Plan 02/03 dependency safety.
- `scripts/phase220-precompute-pins.py` - Independent stdlib golden-pin calculator.
- `tests/test_phase220_mutation_boundary.py` - Phase 220 SAFE-11 boundary clone.
- `tests/test_phase220_matrix_aggregator.py` - Wave 0 aggregator contract scaffolds with precomputed pins.
- `tests/test_phase220_matrix_wrapper.py` - Wave 0 wrapper dry-run contract scaffolds.
- `tests/fixtures/phase220/signal-sheets/*.json` - 10 synthetic Phase 214-shaped signal sheets.
- `tests/fixtures/phase220/cell-manifests/*.json` - 10 synthetic Phase 220 cell manifests.
- `tests/fixtures/phase220/scenarios/*.yaml` - 6 scenario inputs for kill/carry/defect/replicate paths.

## Verification

- `.venv/bin/pytest tests/test_phase220_*.py -q` → `5 passed, 12 skipped, 17 xfailed`
- `.venv/bin/pytest tests/test_phase220_matrix_aggregator.py --collect-only -q` → 17 tests collected
- `.venv/bin/pytest tests/test_phase220_matrix_wrapper.py --collect-only -q` → 11 tests collected
- JSON/YAML fixture parse checks passed.
- Fixture counts passed: 10 signal sheets, 10 cell manifests, 6 scenarios.
- `git diff --stat src/wanctl/` → no changes.
- `git diff --stat scripts/phase213-* scripts/phase214-*` → no changes.

## Decisions Made

- Used the live `ip -4 addr show` result from 2026-05-31 to document `spectrum=10.10.110.226` and `att=10.10.110.233` in the YAML scaffold.
- Kept `att.egress_signature` empty only in the Plan 01 scaffold, matching the plan contract that Plan 02 must replace it before Plan 03 consumes the YAML.
- Split Task 2 into two commits (test scaffolds and fixtures) so the repository pre-commit hook could run normally without the interactive documentation prompt triggered by mixing Python test files with YAML/JSON fixtures.

## Deviations from Plan

None - plan executed within the intended Wave 0 scope. Task 2 used two commits for hook-compatible atomicity, but no scope or behavior changed.

## Issues Encountered

- The pre-commit hook is interactive when Python and YAML/JSON fixture changes are staged together; Task 2 was split into test and fixture commits so hooks ran normally without `--no-verify` or hook bypass.

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| `scripts/phase220-matrix.yaml` | `base_sha: "PENDING_PLAN_02_COMMIT"` | Plan 02 finalizes the source-floor anchor. |
| `scripts/phase220-matrix.yaml` | `att.egress_signature: ""` | Plan 02 must live-capture and fill ATT egress before wrapper consumption. |
| `tests/test_phase220_matrix_aggregator.py` | strict xfail scaffolds | Plan 02 implements the aggregator and flips these to passing. |
| `tests/test_phase220_matrix_wrapper.py` | strict xfail / skip scaffolds | Plan 03 implements the wrapper and flips these to passing. |

## Threat Flags

None - new surfaces are test fixtures and local scripts already represented in the plan threat model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 220-02. Plan 02 can consume the YAML scaffold, golden pin literals, and aggregator fixtures; Plan 03 can consume the wrapper scaffold and four-cell YAML stub after Plan 02 finalizes the full YAML.

## Self-Check: PASSED

- Summary path exists.
- All task commits exist: `2969289`, `d3d9be7`, `e4968f3`, `e6bc520`, `00fb4a7`, `2817795`.
- Key created files exist.
- Final Phase 220 test slice passed with expected xfail/skip posture.

---
*Phase: 220-matrix-runner-scope-a1*
*Completed: 2026-05-31*
