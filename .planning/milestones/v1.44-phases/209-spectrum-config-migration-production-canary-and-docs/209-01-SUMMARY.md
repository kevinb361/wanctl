---
phase: 209-spectrum-config-migration-production-canary-and-docs
plan: 01
subsystem: backend
tags: [cake, wash, netlink, linux-cake, safe-09, tdd]

requires:
  - phase: 205-tin-agnostic-cake-signal-allow-wash-gate
    provides: allow_wash strict-bool emission gate
  - phase: 206-a-b-replay-harness-rollback-gates
    provides: v1.44 SAFE-09 closeout context
provides:
  - Symmetric wash readback expectations from build_cake_params/build_expected_readback
  - Netlink and tc backend wash drift hard-fail with omitted-off normalization
  - Pyroute2-pinned diffserv enum mapping including besteffort=3
  - Phase 209 SAFE-05 wash/diffserv pin block
affects: [phase-209, safe-09, topology-correct-cake]

tech-stack:
  added: []
  patterns:
    - TDD RED/GREEN commits for controller-internal readback validation
    - Wash-specific hard-fail inside backend validate_cake methods only

key-files:
  created:
    - .planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-01-SUMMARY.md
  modified:
    - src/wanctl/cake_params.py
    - src/wanctl/backends/netlink_cake.py
    - src/wanctl/backends/linux_cake.py
    - tests/test_cake_params.py
    - tests/backends/test_netlink_cake.py
    - tests/backends/test_linux_cake.py
    - tests/test_phase_195_replay.py

key-decisions:
  - "Kept wash hard-fail scoped inside backend validate_cake methods; linux_cake_adapter.py remains unchanged."
  - "Normalized omitted wash readback to False for the wash key only in both backends to protect ATT off-by-omission startup."
  - "Corrected netlink diffserv enum pins to local pyroute2 values, including besteffort=3."

patterns-established:
  - "Explicit False matters: build_cake_params now always emits wash from the strict allow_wash gate."
  - "Phase 209 SAFE-05 pins count wash readback symbols with comment-line filtering."

requirements-completed: [SAFE-09, TOPO-03]

duration: 5min
completed: 2026-05-19
---

# Phase 209 Plan 01: Wash Readback Validation Summary

**Controller-internal CAKE wash readback validation with symmetric ATT/Spectrum assertions and pyroute2-correct diffserv enums.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-19T01:43:21Z
- **Completed:** 2026-05-19T01:49:16Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `build_cake_params()` now always emits `params["wash"]` from the strict `allow_wash is True` gate, so ATT/default configs assert `False` and Spectrum asserts `True`.
- `build_expected_readback()` passes `wash` through when present, preserving transform-only semantics.
- `netlink_cake.validate_cake()` and `linux_cake.validate_cake()` raise `RuntimeError` only on wash mismatches, while non-wash mismatches remain soft-signal `False`.
- Both backends normalize omitted wash readback (`None`) to `False` for the wash key only.
- `_DIFFSERV_NAME_TO_INT` now matches local pyroute2 enum values: `diffserv3=0`, `diffserv4=1`, `diffserv8=2`, `besteffort=3`, `precedence=4`.
- Phase 209 SAFE-05 pins lock wash/diffserv symbol counts.

## Task Commits

1. **Task 1 RED: cake params wash tests** - `e05d26c` (test)
2. **Task 1 GREEN: cake params wash implementation** - `53ca0ad` (feat)
3. **Task 2 RED: netlink wash tests** - `cf8deba` (test)
4. **Task 2 GREEN: netlink wash implementation** - `becf39c` (feat)
5. **Task 3 RED: linux wash tests + SAFE-05 pins** - `916578d` (test)
6. **Task 3 GREEN: linux wash implementation** - `fc4e349` (feat)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `src/wanctl/cake_params.py` - Always emits wash from `allow_wash`; readback transform passes wash through.
- `src/wanctl/backends/netlink_cake.py` - Adds `TCA_CAKE_WASH`, wash hard-fail, omitted-off normalization, and corrected diffserv enum pins.
- `src/wanctl/backends/linux_cake.py` - Adds wash hard-fail and omitted-off normalization.
- `tests/test_cake_params.py` - Adds 7 wash emission/readback tests and updates exact full-scenario params.
- `tests/backends/test_netlink_cake.py` - Adds wash TCA, hard-fail, omitted attr, and production-shaped diffserv/wash tests.
- `tests/backends/test_linux_cake.py` - Adds wash hard-fail and omitted key tests for tc JSON readback.
- `tests/test_phase_195_replay.py` - Adds Phase 209 SAFE-05 symbol count pins.

## Decisions Made

- Local pyroute2 does not expose `TCA_CAKE_WASH` as a module-level constant, but its `sched_cake.options.nla_map` exposes `('TCA_CAKE_WASH', 'uint32')`; the existing code pattern uses string TCA names, so the verified literal string was used.
- `linux_cake_adapter.py` was intentionally not modified; hard-fail behavior lives inside backend `validate_cake()` implementations per D-17.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope creep.

## Issues Encountered

- The local git pre-commit hook is interactive for documentation prompts in non-interactive execution. Commits were made with the hook's supported `SKIP_DOC_CHECK=1` environment variable; hooks still ran, and no `--no-verify` was used.

## Known Stubs

None. Stub scan only found intentional empty-string/list/dict values in test fixtures and mock subprocess outputs.

## Threat Flags

None. The new security-relevant startup hard-fail surface is already covered by the plan threat model (T-209-01-01 through T-209-01-05).

## Verification

- PASS: `.venv/bin/pytest tests/test_cake_params.py tests/backends/test_netlink_cake.py tests/backends/test_linux_cake.py tests/test_phase_195_replay.py -v` — 257 passed.
- PASS: `.venv/bin/ruff check src/wanctl/cake_params.py src/wanctl/backends/netlink_cake.py src/wanctl/backends/linux_cake.py`.
- PASS: `.venv/bin/mypy src/wanctl/cake_params.py src/wanctl/backends/netlink_cake.py src/wanctl/backends/linux_cake.py`.
- PASS: `git diff -- src/wanctl/backends/linux_cake_adapter.py` returned empty.
- PASS: focused hot-path slice — 673 passed.
- INFO: `git diff --name-only 6508d68..HEAD -- src/wanctl/` includes this plan's allowed files plus earlier v1.44 files already present on the branch; Plan 209-04 owns final mechanical SAFE-09 closeout.

## User Setup Required

None - no external service configuration required.

## TDD Gate Compliance

- RED commits present: `e05d26c`, `cf8deba`, `916578d`
- GREEN commits present after RED: `53ca0ad`, `becf39c`, `fc4e349`
- REFACTOR commits: none needed.

## Next Phase Readiness

Ready for Plan 209-02. Wash readback validation is implemented and pinned; Spectrum YAML/config migration can consume the readback contract.

## Self-Check: PASSED

- Summary file exists.
- Task commits found: `e05d26c`, `53ca0ad`, `cf8deba`, `becf39c`, `916578d`, `fc4e349`.

---
*Phase: 209-spectrum-config-migration-production-canary-and-docs*
*Completed: 2026-05-19*
