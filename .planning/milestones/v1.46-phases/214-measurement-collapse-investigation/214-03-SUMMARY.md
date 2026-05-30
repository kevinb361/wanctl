---
phase: 214-measurement-collapse-investigation
plan: 03
subsystem: testing
tags: [analyzer, aligner, ndjson, journal, fixtures, tdd]

requires:
  - phase: 214-02
    provides: Fail-closed flent extractor and Wave 0 flent fixtures
provides:
  - Per-second Phase 214 multi-source aligned-window joiner
  - Collapse-while-GREEN health NDJSON fixture aligned to the sample flent window
  - Aligner CLI deriving its time window from phase214-extract.py
affects: [phase214-classify, phase214-matrix-summary, measurement-collapse-investigation]

tech-stack:
  added: []
  patterns: [stdlib gzip/json/csv alignment, importlib sibling script loading, pytest subprocess coverage]

key-files:
  created:
    - scripts/phase214-align.py
    - tests/test_phase214_align.py
    - tests/fixtures/phase214/sample-bad-p99-health.ndjson
  modified:
    - tests/fixtures/phase214/README.md
    - pyproject.toml

key-decisions:
  - "The aligner reuses phase214-extract.py's FlentExtractionError class via a sys.modules-cached importlib load so downstream exception handling sees one canonical class."
  - "The CLI derives the flent window from extract_flent_latency() instead of accepting operator-supplied --flent-t0/--flent-end flags."
  - "The synthesized health fixture is aligned to the committed flent fixture window so end-to-end CLI verification exercises health projection and in_flent_window rows together."

patterns-established:
  - "Aligned rows project live /health `status` into downstream `health_status` while preserving the live fixture key shape."
  - "Journal and alert rows are matched with ±1s bucket tolerance for clock-skew-safe per-second correlation."

requirements-completed: [MEAS-01]

duration: 10min
completed: 2026-05-28
---

# Phase 214 Plan 03: Aligned Window Joiner Summary

**Per-second flent/health/journal/alert alignment with fail-closed extraction, GREEN measurement-collapse fixture coverage, and CLI-derived flent windows.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-28T01:32:47Z
- **Completed:** 2026-05-28T01:43:29Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `sample-bad-p99-health.ndjson`, a 30-row `/health` fixture with `status=healthy`, `download_state=GREEN`, and `measurement_successful_count` cycling `0,0,0,2`.
- Added `scripts/phase214-align.py`, a stdlib-only aligner/CLI that emits one row per integer second across the flent window ± buffers.
- Added nine aligner tests covering row counts, `in_flent_window`, ping bucketing, schema projection, journal tolerance, fail-closed paths, extractor exception identity, `status` → `health_status`, and CLI window derivation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Synthesize collapse health fixture** - `1d51f23` (chore)
2. **Task 2 RED: Add failing aligner tests** - `4e4c7d3` (test)
3. **Task 2 GREEN: Implement aligned window joiner** - `ec09a01` (feat)
4. **Deviation fix: Align health fixture to flent window** - `ab995fb` (fix)

## Files Created/Modified

- `tests/fixtures/phase214/sample-bad-p99-health.ndjson` - 30-second GREEN health fixture with collapsing measurement success counts.
- `tests/fixtures/phase214/README.md` - Fixture provenance and synthesis recipe, including the flent-window-aligned start epoch.
- `tests/test_phase214_align.py` - Aligner unit/subprocess coverage for the documented Wave 0 contract.
- `scripts/phase214-align.py` - Per-second multi-source aligner and CLI.
- `pyproject.toml` - Scoped Ruff `N999` ignore for the plan-required hyphenated `scripts/phase214-align.py` filename.

## Decisions Made

- Used a sys.modules-cached importlib load for `phase214-extract.py` so `FlentExtractionError` identity is shared between extractor and aligner module loads.
- Rejected CLI `--flent-t0` / `--flent-end` inputs; the `.flent.gz` artifact is the source of truth for its own window.
- Kept the live health fixture key as `status` and made the aligner perform the downstream rename to `health_status` exactly once.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added scoped Ruff N999 ignore for required hyphenated aligner filename**
- **Found during:** Task 2 (aligner implementation)
- **Issue:** `.venv/bin/ruff check scripts/phase214-align.py tests/test_phase214_align.py` failed with `N999 Invalid module name: 'phase214-align'` because the plan requires the standalone hyphenated CLI path.
- **Fix:** Added a per-file ignore for `scripts/phase214-align.py = ["N999"]` in `pyproject.toml`.
- **Files modified:** `pyproject.toml`
- **Verification:** `.venv/bin/ruff check scripts/phase214-align.py tests/test_phase214_align.py` passed.
- **Committed in:** `ec09a01`

**2. [Rule 1 - Bug] Aligned health fixture start time with committed flent fixture**
- **Found during:** Plan-level end-to-end verification
- **Issue:** The original fixed health start epoch did not overlap the committed sample flent fixture window, so the CLI-derived window could prove `in_flent_window` but could not also project any `measurement_successful_count==0` health rows.
- **Fix:** Re-generated `sample-bad-p99-health.ndjson` at the integer second of `sample-tcp_12down.flent.gz`'s `metadata.T0`, preserving the 30-row GREEN collapse pattern and live key subset.
- **Files modified:** `tests/fixtures/phase214/sample-bad-p99-health.ndjson`, `tests/fixtures/phase214/README.md`
- **Verification:** End-to-end aligner CLI output now has at least one `in_flent_window=true` row and at least one `measurement_successful_count==0` row; aligner tests still pass.
- **Committed in:** `ab995fb`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes preserve the planned stdlib/additive analyzer boundary and make the documented verification executable; no controller source or production behavior changed.

## Issues Encountered

- Pre-commit documentation hooks prompted for documentation review on new analyzer/config files. Commits used the hook-supported `SKIP_DOC_CHECK=1` path, not `--no-verify`; hooks still ran and reported the skip.

## Known Stubs

None - no placeholder UI/data-source stubs, TODO/FIXME markers, or mock data flows were introduced. The only stub-pattern grep hit was the stdlib `newline=""` CSV writer argument.

## Threat Flags

None - the local operator-controlled CLI read/write surface, flent input, health NDJSON input, journal input, and output JSON/CSV paths were already covered by the plan threat model.

## User Setup Required

None - no external service configuration required.

## Verification

- Task 1 fixture checks passed: 30 NDJSON lines, all parse, all `download_state=GREEN`, 23 zero-success rows, live key subset, 1Hz `t_wall`, and no `sampled_utc`/`t_wall_unix` keys.
- RED gate: `.venv/bin/pytest tests/test_phase214_align.py -x -q` failed before implementation because `scripts/phase214-align.py` did not exist.
- GREEN gate: `.venv/bin/pytest tests/test_phase214_align.py -x -q` passed (`9 passed`).
- CLI happy path: `.venv/bin/python3 scripts/phase214-align.py --flent-gz tests/fixtures/phase214/sample-tcp_12down.flent.gz --health-ndjson tests/fixtures/phase214/sample-bad-p99-health.ndjson --output-json /tmp/aligned-plan.json` exited 0; output had 151 rows, `in_flent_window=true` rows, and zero-success health rows.
- CLI fail-closed path: missing-raw-values fixture emitted `FlentExtractionError` and exited nonzero.
- `grep -E -c "(from wanctl|import wanctl|import pandas|import numpy)" scripts/phase214-align.py` returned 0.
- `git diff --name-only HEAD -- src/wanctl/ scripts/phase213-classify.py scripts/phase214-extract.py | wc -l` returned 0.
- `git diff --name-only HEAD -- src/wanctl/ | wc -l` returned 0.
- `.venv/bin/ruff check scripts/phase214-align.py tests/test_phase214_align.py` passed.
- `.venv/bin/pytest tests/ -q` passed (`5160 passed, 6 skipped, 2 deselected`).

## TDD Gate Compliance

- RED commit present: `4e4c7d3` (`test(214-03): add failing aligner tests`).
- GREEN commit present after RED: `ec09a01` (`feat(214-03): implement aligned window joiner`).
- REFACTOR commit: not needed.
- Fixture setup commit present before RED: `1d51f23` (`chore(214-03): add collapse health fixture`).

## Next Phase Readiness

Ready for `214-04-PLAN.md` to consume `align_window()` and the aligned-row schema for driver classification. The aligner is fixture-backed, fail-closed, and leaves `src/wanctl/`, `scripts/phase213-classify.py`, and `scripts/phase214-extract.py` unchanged.

## Self-Check: PASSED

- Found `scripts/phase214-align.py`.
- Found `tests/test_phase214_align.py`.
- Found `tests/fixtures/phase214/sample-bad-p99-health.ndjson`.
- Found `.planning/phases/214-measurement-collapse-investigation/214-03-SUMMARY.md`.
- Found task commits `1d51f23`, `4e4c7d3`, `ec09a01`, and `ab995fb` in git log.

---
*Phase: 214-measurement-collapse-investigation*
*Completed: 2026-05-28*
