---
phase: 214-measurement-collapse-investigation
plan: 01
subsystem: testing
tags: [matrix, harness, orchestration, window-gate, mutation-guard, journal-capture]

requires:
  - phase: 213-experience-baseline-harness
    provides: baseline capture orchestrator, health polling, alert windows, steering snapshots, source-bind egress checks
provides:
  - Phase 214 per-window Spectrum tcp_12down wrapper
  - D-14 src/wanctl mutation guard covering unstaged, staged, committed-since-base, and untracked synthetic dirty cases
  - Per-test journal-window.ndjson capture and phase214-window.json sidecar provenance
affects: [phase214-classify, phase214-align, phase214-report, measurement-collapse-investigation]

tech-stack:
  added: []
  patterns: [bash strict mode, Phase 213 delegation, jq sidecar manifest, bounded journalctl capture]

key-files:
  created: [scripts/phase214-flent-matrix.sh]
  modified: []

key-decisions:
  - "Kept Phase 214 capture as a thin wrapper over phase213-baseline-capture.sh rather than duplicating traffic generation, health polling, alert pulls, steering snapshots, or egress probes."
  - "Extended the D-14 source mutation guard to refuse untracked src/wanctl files as part of the unstaged dirty regression, while preserving the planned three git diff checks."

patterns-established:
  - "Phase 214 window wrappers emit run-root and per-test phase214-window.json sidecars so downstream analyzers can resolve window metadata locally."
  - "Journal evidence is captured after Phase 213 returns using each per-test manifest's test_start_unix/test_end_unix window."

requirements-completed: [MEAS-01]

duration: 3min
completed: 2026-05-28
---

# Phase 214 Plan 01: Matrix Wrapper Summary

**Spectrum tcp_12down matrix wrapper with enforced window discipline, src/wanctl mutation refusal, bounded journal capture, and per-test provenance sidecars.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-28T01:12:26Z
- **Completed:** 2026-05-28T01:15:01Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created executable `scripts/phase214-flent-matrix.sh` with `off-peak`, `daytime`, and `prime-time` window gates plus `--dry-run --test-hour` regression hooks.
- Delegated live Spectrum `tcp_12down` evidence capture to `scripts/phase213-baseline-capture.sh` with the required bind map, WAN/test narrowing, duration, host, and Phase 214 evidence root.
- Added post-run journal capture into each per-test directory as `journal-window.ndjson` using the per-test manifest time bounds.
- Wrote `phase214-window.json` at both run root and per-test directories with window, duration, git/base SHA, mutation posture, and `journalctl_command` provenance.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement phase214-flent-matrix.sh wrapper** - `a0d5c27` (feat)

## Files Created/Modified

- `scripts/phase214-flent-matrix.sh` - Phase 214 per-window Spectrum `tcp_12down` wrapper, dry-run hook, D-14 guard, journal capture, and sidecar emission.

## Decisions Made

- Used Phase 213 delegation for all traffic generation and baseline evidence capture to avoid duplicating source-bind egress probes, health polling, alert pulls, or steering snapshots.
- Kept the planned three `git diff --quiet` checks literally present, and added an untracked-file refusal so the synthetic dirty `touch src/wanctl/_dirty_test.py` regression cannot slip through.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Refused untracked src/wanctl files in the D-14 guard**
- **Found during:** Task 1 (wrapper implementation)
- **Issue:** The plan's three `git diff --quiet` checks cover unstaged tracked edits, staged edits, and committed-since-base edits, but the required dirty-tree acceptance case creates an untracked `src/wanctl/_dirty_test.py`. Git diff does not report untracked files.
- **Fix:** Added a `git status --porcelain -- src/wanctl/ | grep '^??'` guard that exits 4 and names the unstaged-check path when untracked controller files exist.
- **Files modified:** `scripts/phase214-flent-matrix.sh`
- **Verification:** Synthetic untracked and staged `src/wanctl/_dirty_test.py` checks both exited 4, cleanup restored a clean `src/wanctl/` tree, and `grep -c 'git diff --quiet'` still returns 3.
- **Committed in:** `a0d5c27`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The fix strengthens the D-14 safety guard and is directly tied to the plan's acceptance criteria; no production behavior or controller code changed.

## Issues Encountered

None.

## Known Stubs

None - only normal bash variable initialization (`TEST_HOUR=""`, etc.) was found; no UI/data-source stubs were introduced.

## User Setup Required

None - no external service configuration required. Operators still need to set `PHASE214_BASE_SHA` before live/dry-run wrapper invocation, as documented by the script usage.

## Verification

- `test -x scripts/phase214-flent-matrix.sh` passed.
- `bash -n scripts/phase214-flent-matrix.sh` passed.
- `bash scripts/phase214-flent-matrix.sh --help` exited 0 and listed all three window labels.
- With `PHASE214_BASE_SHA=$(git rev-parse HEAD)`, dry-run window gates passed for off-peak hour 03, daytime hour 14, and prime-time hour 20.
- Off-peak hour 09 exited 2, and `--test-hour` without `--dry-run` exited 7.
- Synthetic untracked and staged `src/wanctl/_dirty_test.py` guard checks exited 4 and were cleaned up.
- Mutation hygiene grep returned 0 for `systemctl restart|mikrotik|routeros|/etc/wanctl/.*\.yaml`.
- Structural greps confirmed `phase214-window.json`, `phase213-baseline-capture.sh`, `journal-window.ndjson`, `journalctl`, `test_start_unix`, `test_end_unix`, three `git diff --quiet` checks, per-test sidecar copy, and `journalctl_command` provenance.

## Next Phase Readiness

Ready for `214-02-PLAN.md` to build the Phase 214 flent extractor against the evidence shape this wrapper will produce.

## Self-Check: PASSED

- Found `scripts/phase214-flent-matrix.sh`.
- Found `.planning/phases/214-measurement-collapse-investigation/214-01-SUMMARY.md`.
- Found task commit `a0d5c27` in git log.

---
*Phase: 214-measurement-collapse-investigation*
*Completed: 2026-05-28*
