---
phase: 209-spectrum-config-migration-production-canary-and-docs
plan: 02
subsystem: tooling
tags: [safe-08, safe-09, shell, pytest, phase206, rollback-gates]

requires:
  - phase: 207-soak-harness-hardening-v1-43-closeout-routed
    provides: HRDN-01 dirty-tree fail-closed source diff verifier
  - phase: 206-a-b-replay-harness-rollback-gates
    provides: Phase 206 rollback-gate script with TOPO-05 gap record
provides:
  - SAFE-08 ATT config byte-identity verifier via scripts/check-safe07-source-diff.sh --att-config-whitelist
  - SAFE-09 v1.44 controller-source allowlist verifier for Plan 209-04 closeout
  - Phase 206 finite window-hours guard rejecting inf/nan restart windows
affects: [phase-209, safe-08, safe-09, phase-206, topo-05]

tech-stack:
  added: []
  patterns:
    - Mode-flag dispatch in the existing SAFE verifier rather than a sibling script
    - tmp_path git fixtures for source-diff verifier contracts
    - finite positive numeric guard with math.isfinite before restart-rate division

key-files:
  created:
    - .planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-02-SUMMARY.md
  modified:
    - scripts/check-safe07-source-diff.sh
    - tests/test_check_safe07_source_diff.py
    - scripts/phase206-gate-check.py
    - tests/test_phase206_predeploy_gate.py

key-decisions:
  - "Extended scripts/check-safe07-source-diff.sh as the single SAFE verifier entry point instead of adding a sibling ATT script."
  - "Default-mode live-repo SAFE-09 rc=0 remains deferred to Plan 209-04 because the 1.44.0 version bump has not landed yet."
  - "Closed the Phase 206 non-finite window-hours gap mechanically here while leaving TOPO-05 formally owned by Phase 206."

patterns-established:
  - "SAFE-08 mode checks only configs/att.yaml; configs/examples/att-*.yaml remains documentation scope."
  - "SAFE-09 default mode accepts only the v1.44 seven-file control-path allowlist and the 1.43.0 -> 1.44.0 version anchor."

requirements-completed: [SAFE-08, SAFE-09]

duration: 6min
completed: 2026-05-19
---

# Phase 209 Plan 02: SAFE Verifier and Phase 206 Gate Summary

**Single-entry SAFE verifier now covers ATT config byte-identity and v1.44 source allowlist contracts, with Phase 206 restart-window non-finite inputs closed fail-closed.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-19T01:52:18Z
- **Completed:** 2026-05-19T01:57:56Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- Added `--att-config-whitelist` mode to `scripts/check-safe07-source-diff.sh`, with `PHASE_209_ATT_REF` override and default ref `6508d68`.
- Added fail-closed dirty/staged and committed-diff checks for `configs/att.yaml` only; `configs/examples/att-*.yaml` is intentionally out of scope per D-03.
- Expanded default-mode source-diff verification to SAFE-09 with `V144_ALLOWLIST_RE` at `scripts/check-safe07-source-diff.sh:172`.
- Advanced the source-diff version anchor to `1.43.0 -> 1.44.0`; live default-mode rc=0 is intentionally deferred to Plan 209-04 after the version bump lands.
- Added `math.isfinite(args.window_hours)` at `scripts/phase206-gate-check.py:349`, rejecting `inf` and `nan` restart windows before rate math.
- Extended pytest coverage to 17 source-diff verifier tests and 56 combined plan tests.

## Task Commits

1. **Task 1: Add ATT config whitelist mode** - `d5f8948` (feat)
2. **Task 2: pytest harness for SAFE-08 mode** - `8473944` (test)
3. **Task 3: Expand default-mode SAFE-09 allowlist** - `9e4179b` (feat)
4. **Task 4: Phase 206 finite-window guard** - `d70112f` (fix)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `scripts/check-safe07-source-diff.sh` - Adds `--att-config-whitelist`, SAFE-08 ATT byte-identity checks, default ref `6508d68`, and the SAFE-09 v1.44 allowlist regex.
- `tests/test_check_safe07_source_diff.py` - Covers existing HRDN-01 behavior, ATT mode clean/dirty/staged/committed/env/bad-ref/examples cases, and v1.44 allowlist happy/fail cases.
- `scripts/phase206-gate-check.py` - Adds `import math` and rejects non-finite restart windows before computing restart rate.
- `tests/test_phase206_predeploy_gate.py` - Adds inf/nan fail-closed tests and a finite-positive regression path.

## Decisions Made

- Kept the verifier as one script (`scripts/check-safe07-source-diff.sh`) per D-01; no sibling SAFE-08 script was introduced.
- Preserved the process-control nature of the ATT ref override: `PHASE_209_ATT_REF` and positional refs remain available, but Plan 209-04 must cite/review the ref used.
- Treated Task 4 as cross-phase tooling cleanup only; no Phase 209 requirement was added for TOPO-05.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope creep.

## Issues Encountered

- `shellcheck` is not installed in this execution environment (`command -v shellcheck` returned no path). Bash syntax checks and pytest coverage passed; shellcheck-specific verification remains unavailable here.
- The live default-mode `bash scripts/check-safe07-source-diff.sh` rc=0 check was intentionally not run as a success gate in this plan. Per plan output note, it requires `src/wanctl/__init__.py == "1.44.0"`, which lands in Plan 209-04.
- Commits used the hook-supported `SKIP_DOC_CHECK=1` environment variable to avoid the interactive documentation prompt; hooks still ran and `--no-verify` was not used.

## Known Stubs

- `tests/test_check_safe07_source_diff.py:43` writes `# placeholder` into a synthetic tmp-repo script fixture; this is intentional test scaffolding, not product behavior.

## Threat Flags

None. The modified surfaces match the plan threat register: CLI argv/env ref resolution, git dirty-tree checks, and allowlist regex behavior.

## Verification

- PASS: `bash -n scripts/check-safe07-source-diff.sh`.
- PASS: `bash scripts/check-safe07-source-diff.sh --att-config-whitelist 6508d68` — `SAFE-08 OK: no configs/att.yaml diff vs 6508d68`.
- PASS: `.venv/bin/pytest tests/test_check_safe07_source_diff.py tests/test_phase206_predeploy_gate.py -v` — 56 passed.
- PASS: `.venv/bin/pytest tests/test_phase206_predeploy_gate.py -v -k "window_hours or window-hours"` — 5 passed.
- PASS: `git diff -- src/wanctl/ --exit-code` — no working-tree controller-source edits from this plan.
- INFO: `shellcheck scripts/check-safe07-source-diff.sh` could not be run because `shellcheck` is not installed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 209-03. SAFE-08 and SAFE-09 verifier mechanics are available for docs/closeout planning, and Plan 209-04 can consume the default-mode SAFE-09 gate after the version bump lands.

## Self-Check: PASSED

- Summary file exists.
- Task commits found: `d5f8948`, `8473944`, `9e4179b`, `d70112f`.
- Key implementation lines verified: `V144_ALLOWLIST_RE` at `scripts/check-safe07-source-diff.sh:172`; `math.isfinite(args.window_hours)` at `scripts/phase206-gate-check.py:349`.

---
*Phase: 209-spectrum-config-migration-production-canary-and-docs*
*Completed: 2026-05-19*
