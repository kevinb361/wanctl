---
phase: 243-cycle-budget-benchmark-gate
plan: 02
subsystem: benchmarking
tags: [bench-01, cycle-budget, hygiene-sampler, systemd, ndjson]

requires:
  - phase: 243-cycle-budget-benchmark-gate
    provides: Frozen BENCH-02 thresholds and SAFE-17 preregistration scaffolding from Plan 01
provides:
  - Cycle timing NDJSON rollup with invocation provenance, parse counters, avg/p99 stats, and STALL gap evidence
  - Systemd-unit hygiene sampler emitting fd/zombie/Tasks/cpu_nsec NDJSON with CPUAccounting fail-closed behavior
  - Fixture-driven tests for rollup validity guards, malformed-line counters, stall detection, hygiene shape, and CPU counter monotonicity
affects: [phase-243, bench-01, phase-243-gate-eval, phase-243-bench-run]

tech-stack:
  added: []
  patterns:
    - Thin wrapper over existing profiling_collector_json parser/statistics contract
    - Fail-closed systemd CPUAccounting precheck before per-unit CPUUsageNSec sampling
    - Fixture-driven NDJSON contract tests for offline benchmark evidence tooling

key-files:
  created:
    - scripts/phase243-cycle-rollup.py
    - scripts/phase243-hygiene-sampler.sh
    - tests/test_phase243_cycle_rollup.py
    - tests/test_phase243_hygiene_sampler.py
  modified: []

key-decisions:
  - "Kept cycle percentile semantics aligned with profiling_collector_json.py sorted-index statistics instead of introducing a new percentile implementation."
  - "Recorded invocation_id in the rollup output and required --invocation-id fail-closed so reused systemd unit names cannot contaminate benchmark evidence."
  - "Made CPUAccounting=yes a sampler startup gate and treated nonnumeric CPUUsageNSec rows as bounded failures instead of writing junk cpu_nsec values."

patterns-established:
  - "Cycle rollup profiles include parse_counters and stall blocks alongside collector-compatible autorate_* statistics."
  - "Hygiene rows use cumulative cpu_nsec so downstream gate evaluation can compute per-core CPU percentage deltas from first/last samples."

requirements-completed: [BENCH-01]

duration: 4 min
completed: 2026-06-17
---

# Phase 243 Plan 02: Cycle-Budget Rollup and Hygiene Sampler Summary

**Invocation-scoped cycle-budget rollup plus systemd hygiene NDJSON sampler for BENCH-01 evidence collection.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-17T02:53:37Z
- **Completed:** 2026-06-17T02:57:25Z
- **Tasks:** 3 completed
- **Files modified:** 4 created

## Accomplishments

- Added `scripts/phase243-cycle-rollup.py`, a thin collector-compatible wrapper that requires `--invocation-id`, records it in the profile, emits parse counters, preserves no-cycle/no-autorate guards, and detects inter-cycle STALL gaps over 100ms.
- Added fixture-driven cycle-rollup tests covering normal avg/p99 output, invocation fail-closed behavior, malformed line counters, STALL gaps, empty-stream guard, and missing `cycle_total_ms` guard.
- Added `scripts/phase243-hygiene-sampler.sh`, an executable 1Hz sampler for benchmark unit fd/zombie/Tasks/cpu_nsec rows with CPUAccounting precheck and bounded per-row failure handling.
- Added hygiene sampler contract tests for executable/read-only sampling surface, NDJSON row shape, cpu_nsec monotonicity/delta computability, fd growth detection, and zombie detection.

## Task Commits

Each task was committed atomically:

1. **Task 1: Cycle-budget rollup wrapper + invocation scoping + parse counters + STALL gap detector** — `503adfa9` (`feat`)
2. **Task 2: Cycle-rollup unit tests (fixtures: stats, stall, guard, invocation, parse counters)** — `86019ec1` (`test`)
3. **Task 3: Subprocess-hygiene + CPU soak sampler (CPUAccounting fail-closed) + its NDJSON-shape test** — `b0f2327d` (`feat`)

## Files Created/Modified

- `scripts/phase243-cycle-rollup.py` — Rollup CLI for Cycle timing NDJSON with invocation provenance, parse counters, collector-compatible stats, and STALL gap detection.
- `tests/test_phase243_cycle_rollup.py` — Six fixture-driven tests for stats, invocation fail-closed, parse counters, stall detection, and validity guards.
- `scripts/phase243-hygiene-sampler.sh` — Read-only systemd `/proc` sampler emitting `{t,fd,tasks,zombies,cpu_nsec}` to `hygiene.ndjson`.
- `tests/test_phase243_hygiene_sampler.py` — Hygiene script contract and NDJSON shape/trend tests.

## Decisions Made

- Reused `profiling_collector_json.py`'s `canonical_label()` and `build_profile()` contract so Plan 03/04 consumers see the same `autorate_cycle_total.count/avg_ms/p99_ms` shape as prior profiling evidence.
- Kept `--invocation-id` required at argparse level and also rejected empty strings, preserving HIGH-3 fail-closed behavior for unscoped journal slices.
- Kept the hygiene sampler read-only against live state: it reads only `systemctl show` and `/proc`, with no controller, qdisc, RouterOS, service-control, or routing mutation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Verification] Fixed ruff failures in new rollup code/tests**
- **Found during:** Task 1 verification
- **Issue:** `ruff check` flagged the planned hyphenated script filename as `N999`, required explicit `zip(..., strict=...)`, and requested `datetime.UTC` in tests.
- **Fix:** Added a file-level `N999` noqa for the planned script filename, used `strict=False` explicitly, and switched the test timestamp helper to `datetime.UTC`.
- **Files modified:** `scripts/phase243-cycle-rollup.py`, `tests/test_phase243_cycle_rollup.py`
- **Verification:** `.venv/bin/ruff check scripts/phase243-cycle-rollup.py tests/test_phase243_cycle_rollup.py` and `.venv/bin/pytest tests/test_phase243_cycle_rollup.py -x -q` passed.
- **Committed in:** `503adfa9` / `86019ec1`

---

**Total deviations:** 1 auto-fixed (Rule 1 verification/lint fix).
**Impact on plan:** No scope change; the fix only made planned artifacts conform to repository lint rules while preserving the requested filenames.

## Issues Encountered

- The pre-commit documentation hook recommended docs updates for new scripts/tests. Hooks were still run normally; `SKIP_DOC_CHECK=1` was used for these advisory prompts without using `--no-verify`, matching prior Phase 243 Plan 01 handling.

## Verification

- `.venv/bin/pytest tests/test_phase243_cycle_rollup.py -x -q` — `6 passed`.
- `.venv/bin/pytest tests/test_phase243_hygiene_sampler.py -x -q` — `4 passed`.
- `.venv/bin/pytest tests/test_phase243_cycle_rollup.py tests/test_phase243_hygiene_sampler.py -q` — `10 passed`.
- `bash -n scripts/phase243-hygiene-sampler.sh` — passed.
- `.venv/bin/ruff check scripts/phase243-cycle-rollup.py tests/test_phase243_cycle_rollup.py tests/test_phase243_hygiene_sampler.py` — passed.

## Known Stubs

None.

## Threat Flags

None — the new trust-boundary surfaces are the ones declared in the plan threat model: journal NDJSON parsing/invocation scoping and read-only `/proc` + `systemctl show` sampling.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03 can consume the profile `autorate_cycle_total`, `parse_counters`, `stall`, and hygiene `{t,fd,tasks,zombies,cpu_nsec}` contracts to implement the benchmark gate evaluator.

## Self-Check: PASSED

- Found all created files on disk.
- Found task commits: `503adfa9`, `86019ec1`, `b0f2327d`.
- Verification commands passed after the lint fix.

---
*Phase: 243-cycle-budget-benchmark-gate*
*Completed: 2026-06-17*
