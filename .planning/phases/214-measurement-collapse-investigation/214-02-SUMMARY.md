---
phase: 214-measurement-collapse-investigation
plan: 02
subsystem: testing
tags: [analyzer, extractor, flent, fail-closed, fixtures, tdd]

requires:
  - phase: 214-01
    provides: Phase 214 matrix wrapper and per-window evidence layout
provides:
  - Fail-closed Phase 214 flent latency and throughput extractor
  - Raw `raw_values['Ping (ms) ICMP']` percentile contract with pinned fixture values
  - Wave 0 `.flent.gz` fixtures and provenance README
affects: [phase214-align, phase214-classify, phase214-matrix-summary, measurement-collapse-investigation]

tech-stack:
  added: []
  patterns: [stdlib gzip/json extraction, subprocess-driven pytest, fail-closed CLI errors]

key-files:
  created:
    - scripts/phase214-extract.py
    - tests/test_phase214_flent_extract.py
    - tests/fixtures/phase214/sample-tcp_12down.flent.gz
    - tests/fixtures/phase214/sample-no-raw-values.flent.gz
    - tests/fixtures/phase214/README.md
  modified:
    - .gitignore
    - pyproject.toml

key-decisions:
  - "Phase 214 owns a new fail-closed extractor rather than back-editing Phase 213's zero-fill classifier path."
  - "The extractor uses raw flent ping samples and a fixed sorted-index percentile contract, with pinned values locking the method."
  - "A scoped Ruff N999 per-file ignore preserves the required hyphenated CLI filename while keeping lint acceptance clean."

patterns-established:
  - "Wave 0 flent fixtures live under tests/fixtures/phase214/ with a .gitignore whitelist so they are committed without git add -f."
  - "Extractor CLIs report FlentExtractionError to stderr and exit nonzero instead of silently returning zero-valued summaries."

requirements-completed: [MEAS-01]

duration: 9min
completed: 2026-05-28
---

# Phase 214 Plan 02: Flent Extractor Summary

**Raw flent ping percentile extractor with fail-closed missing-series handling, throughput fallback extraction, and pinned Wave 0 fixture coverage.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-28T01:19:26Z
- **Completed:** 2026-05-28T01:28:04Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added Phase 214 `.flent.gz` fixtures: a verbatim known-good `tcp_12down` artifact with 647 raw ping samples and a synthesized missing-raw-values negative fixture.
- Implemented `scripts/phase214-extract.py`, a stdlib-only CLI/module that extracts latency percentiles from `raw_values['Ping (ms) ICMP']`, computes throughput from the documented results fallback chain, and fails closed on missing data.
- Added five pytest cases covering happy path extraction, fail-closed behavior, throughput extraction, raw-not-results percentile guarding, and exact pinned values (`p50=31.2`, `p95=60.3`, `p99=124.0`, `n=647`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Stage Wave 0 fixtures and provenance README** - `41660d8` (chore)
2. **Task 2 RED: Add failing flent extractor tests** - `9644369` (test)
3. **Task 2 GREEN: Implement fail-closed flent extractor** - `7a0abdf` (feat)

## Files Created/Modified

- `.gitignore` - Whitelists `tests/fixtures/phase214/*.flent.gz` below the blanket flent artifact ignore rule.
- `tests/fixtures/phase214/sample-tcp_12down.flent.gz` - Verbatim copy of the verified repo-root `tcp_ndown-2026-04-16T035903...` artifact.
- `tests/fixtures/phase214/sample-no-raw-values.flent.gz` - Negative fixture with valid JSON but no ping raw-values series.
- `tests/fixtures/phase214/README.md` - Fixture provenance and synthesis recipe.
- `tests/test_phase214_flent_extract.py` - TDD coverage for the extractor CLI and fixture contracts.
- `scripts/phase214-extract.py` - Phase 214-owned fail-closed flent latency/throughput extractor and CLI.
- `pyproject.toml` - Scoped Ruff per-file ignore for the plan-required hyphenated CLI filename.
- `.planning/phases/214-measurement-collapse-investigation/deferred-items.md` - Out-of-scope full-suite timing failure note.

## Decisions Made

- Kept Phase 214 extraction additive and separate from `scripts/phase213-classify.py`, preserving D-11 and avoiding back-edits to Phase 213 artifacts.
- Used the plan's sorted-list index percentile method exactly (`n//2`, `int(n*0.95)`, `int(n*0.99)` with clamp) and locked it with pinned numeric fixture tests.
- Added a narrow Ruff per-file ignore for `scripts/phase214-extract.py` because the plan-required hyphenated filename triggers `N999`; no broader lint relaxation was added.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added scoped Ruff N999 ignore for required hyphenated extractor filename**
- **Found during:** Task 2 (extractor implementation)
- **Issue:** `.venv/bin/ruff check scripts/phase214-extract.py tests/test_phase214_flent_extract.py` failed with `N999 Invalid module name: 'phase214-extract'` because the plan requires the CLI path `scripts/phase214-extract.py`.
- **Fix:** Added a per-file ignore for `scripts/phase214-extract.py = ["N999"]` in `pyproject.toml`, then let Ruff organize imports.
- **Files modified:** `pyproject.toml`, `scripts/phase214-extract.py`, `tests/test_phase214_flent_extract.py`
- **Verification:** `.venv/bin/ruff check scripts/phase214-extract.py tests/test_phase214_flent_extract.py` passed.
- **Committed in:** `7a0abdf`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The deviation is tooling-only and preserves the plan-required file path; no production controller behavior changed.

## Issues Encountered

- Pre-commit documentation hook prompts are interactive for detected security/config/function changes. Commits were made with the hook's supported `SKIP_DOC_CHECK=1` environment path, not `--no-verify`; hooks still ran and reported the skip.
- Full suite verification found an out-of-scope timing-sensitive failure: `tests/test_autorate_metrics_recording.py::TestPerformanceOverhead::test_many_cycles_no_degradation` measured max write time `10.04ms` vs `<5ms` after `5,150 passed, 6 skipped, 2 deselected`. This is unrelated to Phase 214 extractor/fixture changes and was recorded in `deferred-items.md` rather than fixed.
- The first metadata commit accidentally included unrelated pre-existing `.planning` changes/deletions. This was immediately corrected by restore commit `20170ca`, and the final working tree is clean with those unrelated files restored.

## Known Stubs

None - no placeholder UI/data-source stubs or TODO/FIXME markers were introduced.

## Threat Flags

None - the local operator-controlled CLI file-read/write surface was already identified in the plan threat model; no additional trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Verification

- Task 1 fixture checks passed: known-good fixture opened with 647 raw ping samples; negative fixture opened and lacked `raw_values['Ping (ms) ICMP']`; README mentions both fixtures; `git check-ignore` returns nonzero for both `.flent.gz` fixtures; `.gitignore` contains the whitelist.
- RED gate: `.venv/bin/pytest tests/test_phase214_flent_extract.py -x -q` failed before implementation because `scripts/phase214-extract.py` did not exist.
- GREEN gate: `.venv/bin/pytest tests/test_phase214_flent_extract.py -x -q` passed (`5 passed`).
- CLI happy path: `.venv/bin/python3 scripts/phase214-extract.py --flent-gz tests/fixtures/phase214/sample-tcp_12down.flent.gz --output-json /tmp/phase214-extract-test.json` exited 0 and `jq '.latency.p99_ms > 0 and .latency.p95_ms >= .latency.p50_ms'` returned `true`.
- CLI fail-closed path: missing-raw-values fixture emitted `FlentExtractionError` / `missing or empty` and exited nonzero.
- `grep -E -c "from wanctl|import wanctl" scripts/phase214-extract.py` returned 0.
- `git diff --name-only HEAD -- src/wanctl/ scripts/phase213-classify.py | wc -l` returned 0.
- `.venv/bin/ruff check scripts/phase214-extract.py tests/test_phase214_flent_extract.py` passed.
- `.venv/bin/mypy scripts/phase214-extract.py` passed.
- `.venv/bin/pytest tests/ -q` found one unrelated performance timing failure; see Issues Encountered and `deferred-items.md`.

## TDD Gate Compliance

- RED commit present: `9644369` (`test(214-02): add failing flent extractor tests`).
- GREEN commit present after RED: `7a0abdf` (`feat(214-02): implement fail-closed flent extractor`).
- REFACTOR commit: not needed.

## Next Phase Readiness

Ready for `214-03-PLAN.md` to consume `extract_flent_latency()` / `extract_flent_throughput()` when building the aligned-window joiner. The extractor is fixture-backed, fail-closed, and does not touch `src/wanctl/` or Phase 213 classifier code.

## Self-Check: PASSED

- Found `scripts/phase214-extract.py`.
- Found `tests/test_phase214_flent_extract.py`.
- Found `tests/fixtures/phase214/sample-tcp_12down.flent.gz`.
- Found `tests/fixtures/phase214/sample-no-raw-values.flent.gz`.
- Found `tests/fixtures/phase214/README.md`.
- Found `.planning/phases/214-measurement-collapse-investigation/214-02-SUMMARY.md`.
- Found task commits `41660d8`, `9644369`, and `7a0abdf` in git log.

---
*Phase: 214-measurement-collapse-investigation*
*Completed: 2026-05-28*
