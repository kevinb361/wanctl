---
phase: 219-ingestion-rate-observability-scope-d
plan: 03
subsystem: operator-tooling
tags: [ingestion-rate, operator-summary, digest, tolerance, safe-11]

requires:
  - phase: 219-02
    provides: [per_wan_ingestion_rate_bucketed helper, Phase 219 ingestion-rate envelope]
provides:
  - Compact per-WAN ingestion-rate lines in wanctl-operator-summary --digest
  - D-22 hard-red query failure independence via pre-gathered ingestion rows
  - D-20 dominant-table tie-break rendering with no-space mixed:t1/t2 token
  - D-26 separate ingestion_printed digest counter
affects: [219-04, phase-218-audit-fallback, operator-summary]

tech-stack:
  added: []
  patterns:
    - In-process operator-summary import of wanctl.history.per_wan_ingestion_rate_bucketed for out-of-band CLI reuse
    - Pre-gather -> legacy hard-red loop -> ingestion emit loop tolerance ordering
    - Deterministic monkeypatched operator-summary digest tests

key-files:
  created:
    - .planning/phases/219-ingestion-rate-observability-scope-d/219-03-SUMMARY.md
  modified:
    - src/wanctl/operator_summary.py
    - tests/test_history_ingestion_rate_bucketed.py

key-decisions:
  - "Used an in-process import of per_wan_ingestion_rate_bucketed because both wanctl-history and wanctl-operator-summary are out-of-band CLIs."
  - "Pre-gathered ingestion rows before the hard-red loop so hard-red query failures cannot suppress ingestion-rate lines."
  - "Kept printed hard-red-only and added ingestion_printed as the separate D-26 counter."
  - "Added --db to operator-summary --digest to satisfy the plan-level explicit database smoke without changing discovery defaults."

patterns-established:
  - "Operator digest additions preserve legacy hard-red output accounting while adding separate ingestion accounting."
  - "H5/D-22 regression tests monkeypatch _query_digest_rows failures and assert ingestion output still emits."

requirements-completed: [INGEST-04, SAFE-11]

duration: 6min
completed: 2026-05-30
---

# Phase 219 Plan 03: Operator Digest Ingestion-Rate Summary

**`wanctl-operator-summary --digest` now emits compact per-WAN ingestion-rate lines from the bucketed helper while preserving hard-red digest accounting and failure isolation.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-30T14:19:18Z
- **Completed:** 2026-05-30T14:26:02Z
- **Tasks:** 2 planned tasks + 1 verification fix
- **Files modified:** 2 source/test files + this summary

## Accomplishments

- Added `_format_ingestion_digest_line()` with the four locked dominant-table branches: clear >=1.20x winner, no-space `mixed:t1/t2`, single-table winner, and all-null/zero `n/a`.
- Restructured `print_digest()` to pre-gather ingestion rows before hard-red queries, then emit ingestion lines after the hard-red block so hard-red query failures cannot suppress ingestion visibility.
- Added D-26 `counts["ingestion_printed"]` while preserving legacy `counts["printed"]` as hard-red-only.
- Added `TestOperatorSummaryDigest` with seven deterministic tests covering tie-breaks, per-WAN read-failure tolerance, return-contract shape, and the H5/D-22 independence regression.
- Added `--db` for `wanctl-operator-summary --digest` so the plan-level explicit DB smoke can target one metrics DB without changing normal auto-discovery behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add formatter + pre-gathered digest integration** - `35d5eb7` (feat)
2. **Task 2: Add operator-summary digest tests** - `833881b` (test)
3. **Verification fix: explicit digest DB smoke support** - `d1a05c4` (fix)

**Plan metadata:** committed after this summary is written.

## Files Created/Modified

- `src/wanctl/operator_summary.py` - Adds ingestion digest prefix/formatter, in-process bucketed helper import, D-22 pre-gathered ingestion data flow, D-26 counter, local hard-red query failure tolerance, and `--db` for digest smoke targeting.
- `tests/test_history_ingestion_rate_bucketed.py` - Adds `TestOperatorSummaryDigest` with seven INGEST-04 regression tests.
- `.planning/phases/219-ingestion-rate-observability-scope-d/219-03-SUMMARY.md` - Execution record for this plan.

## Decisions Made

- Used `from wanctl.history import per_wan_ingestion_rate_bucketed` in-process rather than subprocess execution, matching the plan's out-of-band CLI responsibility map.
- Preserved `printed` as hard-red-only and added `ingestion_printed` rather than folding new output into the legacy counter.
- Added `--db` only to the digest path as a targeted verification/support affordance; default digest behavior still auto-discovers WAN DBs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Verification blocker] Added explicit `--db` support to operator-summary digest**
- **Found during:** Plan-level CLI smoke
- **Issue:** The plan's smoke command used `wanctl.operator_summary --digest --db /tmp/none.db`, but the existing CLI had no `--db` option.
- **Fix:** Added an optional digest-only `--db` argument that bypasses discovery with a single explicit path while preserving auto-discovery when omitted.
- **Files modified:** `src/wanctl/operator_summary.py`
- **Verification:** `.venv/bin/python -m wanctl.operator_summary --digest --db /tmp/none.db 2>&1 | head` emitted skip/tolerance lines instead of argparse failure; ruff, mypy, and `TestOperatorSummaryDigest` passed.
- **Committed in:** `d1a05c4`

---

**Total deviations:** 1 auto-fixed (Rule 3 verification blocker)
**Impact on plan:** No controller-path or algorithm scope change. The fix is an additive operator CLI affordance for the digest surface and keeps default behavior unchanged.

## Issues Encountered

- The repository pre-commit documentation hook is interactive in non-interactive commits. Hooks were still run; `SKIP_DOC_CHECK=1` was used for commits where the hook presented its own advisory bypass prompt. No `--no-verify` was used.

## Known Stubs

None.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: file_access | `src/wanctl/operator_summary.py` | Added operator-supplied `--db` digest path for read-only SQLite access; bounded to digest mode and opened through the existing read-only URI path. |

## Verification

Passed:

```bash
.venv/bin/pytest tests/test_history_ingestion_rate_bucketed.py -x
.venv/bin/pytest tests/test_phase219_mutation_boundary.py -x
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
.venv/bin/ruff check src/wanctl/operator_summary.py tests/test_history_ingestion_rate_bucketed.py
.venv/bin/mypy src/wanctl/operator_summary.py
.venv/bin/python -m wanctl.operator_summary --digest --db /tmp/none.db 2>&1 | head
```

Results: bucketed/operator digest suite `13 passed`; mutation boundary `3 passed, 1 skipped`; hot-path slice `673 passed`; ruff and mypy passed; CLI smoke emitted digest skip/tolerance lines for `/tmp/none.db` rather than aborting on argument parsing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `219-04-PLAN.md` to add the cron-callable snapshot writer and documentation. INGEST-04 is now covered by digest implementation plus the H5/D-22 regression guard.

## Self-Check: PASSED

- Found modified files: `src/wanctl/operator_summary.py`, `tests/test_history_ingestion_rate_bucketed.py`.
- Found task commits: `35d5eb7`, `833881b`, `d1a05c4`.
- Final verification commands passed after the explicit digest DB smoke fix.

---
*Phase: 219-ingestion-rate-observability-scope-d*
*Completed: 2026-05-30*
