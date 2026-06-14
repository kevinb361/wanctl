---
phase: 237-hil-failure-injection-harness-closeout
plan: 05
subsystem: testing
tags: [silicom, hil, safety, gap-closure, pytest, bash]

requires:
  - phase: 237-hil-failure-injection-harness-closeout
    provides: Phase 237 HIL harness plus verifier-identified CR-01 and WR-01 safety gaps
provides:
  - CR-01 closure: failover and ab-cake pair allowlist before live gates, result paths, generated Python, or mutation verbs
  - WR-01 closure: bare SILICOM_BYPASS command names resolve through PATH before live-gate comparison
  - Regression coverage for malformed/unknown pairs and PATH-resolved live CLI refusal
affects: [phase-237, silicom-test, harn, safe-16, verification-gap-closure]

tech-stack:
  added: []
  patterns:
    - fail-closed operator pair allowlist before filesystem/live-hardware side effects
    - command-name resolution through command -v before canonical realpath live-gate comparison
    - test-only canonical live CLI seam with production default unchanged

key-files:
  created:
    - .planning/phases/237-hil-failure-injection-harness-closeout/237-05-SUMMARY.md
  modified:
    - scripts/silicom-test
    - tests/test_silicom_test_harness.py
    - .claude/context.md

key-decisions:
  - "Validated only the shipped Silicom pair names att-modem and spec-modem; malformed/unknown pair strings now fail before result directory creation or mutation."
  - "Kept the production live CLI canonical path default at /usr/local/sbin/silicom-bypass while adding SILICOM_TEST_CANONICAL_BYPASS as a test-only seam for dev hosts without the installed binary."
  - "Left controller paths and configs/att.yaml untouched; SAFE-16 protected-path zero-diff still passes against v1.51."

patterns-established:
  - "Every pair-taking HIL command must order arity check -> validate_pair -> require_live_gate -> init_run_dir."
  - "Fake tmp-path Silicom bypass helpers stay exempt unless their resolved path equals the configured canonical live CLI path."

requirements-completed: [HARN-01, HARN-02, HARN-03, HARN-05]

duration: 2 min
completed: 2026-06-14
---

# Phase 237 Plan 05: HIL Harness Gap Closure Summary

**Silicom HIL harness safety hardening rejects unsafe pair names before side effects and gates PATH-resolved live CLI invocations.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-14T00:57:10Z
- **Completed:** 2026-06-14T00:59:59Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Closed **CR-01** by adding `validate_pair()` and placing it before `require_live_gate`, `init_run_dir`, `mark_touched`, generated result JSON, and `silicom-bypass` mutation verbs for `failover` and `ab-cake`.
- Closed **WR-01** by replacing literal-only path comparison with `resolve_command_path()`, which resolves bare command names via `command -v -- "$cmd"` before `realpath` comparison.
- Added RED/GREEN regression coverage for traversal-like pair values, unknown pairs, no result-root creation, no escaped directories, no mutation verbs, and PATH-resolved bare `silicom-bypass` live-gate refusal.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing regressions for pair traversal and PATH-resolved live gate** - `f0608c9d` (test)
2. **Task 2: Validate pairs before result paths and resolve bare commands through PATH** - `68edf79e` (feat)

**Plan metadata:** pending final docs commit

_Note: Both tasks used TDD-style RED/GREEN sequencing for this gap closure._

## Files Created/Modified

- `tests/test_silicom_test_harness.py` - Adds malformed/unknown pair and PATH-resolved bare-command live-gate regressions plus mutation-call helpers.
- `scripts/silicom-test` - Adds pair allowlist validation, fail-closed pair-to-WAN fallback, PATH-resolved command comparison, and a test-only canonical CLI seam.
- `.claude/context.md` - Hook-required current validation note for the Plan 05 CR-01/WR-01 gap-closure surface.

## Gap Closure Evidence

| Gap | Evidence | Status |
|-----|----------|--------|
| CR-01 | `test_rejects_malformed_pairs_before_result_dir_creation`, `test_rejects_unknown_pair_before_ab_cake_result_dir_creation`, `validate_pair()` before `init_run_dir` in both pair-taking commands | CLOSED |
| WR-01 | `test_live_gate_resolves_bare_silicom_bypass_through_path`, `resolve_command_path()` with `command -v -- "$cmd"`, live gate refuses without `SILICOM_TEST_LIVE_CONFIRM` | CLOSED |
| SAFE-16 | `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` | PASS |

## Decisions Made

- Pair allowlist is exactly `att-modem|spec-modem`, matching Phase 235/237 recorded decisions and avoiding broad pair-name interpretation in the HIL harness.
- The test-only `SILICOM_TEST_CANONICAL_BYPASS` seam exists only to prove PATH live-gate behavior on dev hosts where `/usr/local/sbin/silicom-bypass` is absent; production default remains `/usr/local/sbin/silicom-bypass`.
- `pair_to_wan()` now fails closed for unexpected input instead of echoing the unknown pair through to downstream helpers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added hook-required context documentation**
- **Found during:** Task 1 commit
- **Issue:** The repository documentation hook blocked the RED regression commit because new helper/test functions were added without a recognized docs/context update.
- **Fix:** Updated `.claude/context.md` with a Plan 05 RED regression note and recommitted through normal hooks.
- **Files modified:** `.claude/context.md`
- **Verification:** Pre-commit hook reported `Documentation updated - looking good!`.
- **Committed in:** `f0608c9d`

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** Context-note only; no controller path, config, deploy behavior, or live card state changed.

## Issues Encountered

- The canonical live CLI is absent on the dev VM, so the WR-01 regression uses the planned test-only canonical seam instead of requiring `/usr/local/sbin/silicom-bypass` to exist locally.

## TDD Gate Compliance

- RED commit present: `f0608c9d` (`test(237-05): add failing silicom harness safety regressions`) — focused command failed with 3 expected failures before implementation.
- GREEN commit present after RED: `68edf79e` (`feat(237-05): harden silicom-test pair and live gates`) — focused and full harness tests passed.
- REFACTOR commit: not needed.

## Known Stubs

- `scripts/silicom-test:7` still contains the pre-existing planned default `SILICOM_TEST_PROBE` netperf placeholder string. This is intentional and unchanged from Plan 02; operators override `SILICOM_TEST_PROBE` for live A/B probes.

## User Setup Required

None - no external service configuration required.

## Verification

- `.venv/bin/pytest tests/test_silicom_test_harness.py -k "malformed_pairs or unknown_pair or bare_silicom" -q` — RED before implementation (`3 failed, 8 deselected`), then PASS after implementation (`3 passed, 8 deselected`).
- `shellcheck scripts/silicom-test` — PASS.
- `.venv/bin/pytest tests/test_silicom_test_harness.py -q` — PASS (`11 passed`).
- `.venv/bin/pytest tests/ -k invariant -q` — PASS (`8 passed, 5476 deselected`).
- `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` — PASS.
- Acceptance ordering check — PASS: `cmd_failover` and `cmd_ab_cake` both order arity check -> `validate_pair "$pair"` -> `require_live_gate "$pair"` -> `init_run_dir`.

## Threat Flags

None - all touched trust-boundary surfaces were declared in the plan threat model: operator pair arg to filesystem/generated Python, env `SILICOM_BYPASS` to live CLI detection, and harness mutation verbs.

## Next Phase Readiness

Phase 237 gap closure is complete. Re-run verification should now pass CR-01 and WR-01 while preserving SAFE-16 protected-path zero-diff.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/237-hil-failure-injection-harness-closeout/237-05-SUMMARY.md`.
- Task commits exist: `f0608c9d`, `68edf79e`.
- Required files exist and contain `validate_pair`, `command -v -- "$cmd"`, and all three new regression test names.
- Final verification claims above were run after task commits.

---
*Phase: 237-hil-failure-injection-harness-closeout*
*Completed: 2026-06-14*
