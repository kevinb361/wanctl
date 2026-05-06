---
phase: 203-target-edge-churn-instrumentation-obsv
plan: 01
subsystem: observability
tags: [soak-harness, jq, pytest, ndjson, safe-07]

requires:
  - phase: 202-ul-suppression-metric-semantics
    provides: additive upload suppression cause-tag fields exposed through /health
provides:
  - Canonical versioned soak-capture harness with v1.43 target-edge churn projection keys
  - Capture-side projection contract test for synthesized /health payloads
affects: [phase-203, phase-204, soak-harness, obs-v143]

tech-stack:
  added: []
  patterns:
    - jq projection extracted from the versioned script during tests to avoid duplicate schema sources
    - harness-only SAFE-07 verification via source diff against Phase 202 close reference

key-files:
  created:
    - scripts/soak-capture.sh
    - tests/test_phase_203_capture_projection.py
  modified: []

key-decisions:
  - "Promoted the v1.42 evidence-only soak capture script into a public-safe, versioned harness requiring HEALTH_URL from the operator environment."
  - "Kept capture-projection tests coupled to the script body by extracting the jq object literal before running synthesized /health payloads through jq."

patterns-established:
  - "Capture-side contract tests exercise the same jq projection that production soak capture runs."

requirements-completed: [OBSV-05, OBSV-07, SAFE-07]

duration: 2 min
completed: 2026-05-06
---

# Phase 203 Plan 01: Soak Capture Script and Projection Test Summary

**Versioned soak capture harness now emits the v1.43 target-edge churn NDJSON fields, with pytest coverage that runs the script's jq projection against synthesized `/health` payloads.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-06T22:40:05Z
- **Completed:** 2026-05-06T22:42:33Z
- **Tasks:** 3 completed
- **Files modified:** 2 plan files (+ planning metadata after summary)

## Accomplishments

- Created executable `scripts/soak-capture.sh` with mandatory `HEALTH_URL`, optional `SOAK_DURATION_SEC` / `CAPTURE_DIR`, and no hardcoded endpoint.
- Preserved the v1.42 projection keys and added the seven Phase 203 keys: `load_rtt_ms`, `baseline_rtt_ms`, `load_rtt_delta_us`, `last_zone`, `ul_suppressions_completed_window_count`, `ul_suppressions_completed_window_by_cause`, and `ul_suppressions_lifetime_by_cause`.
- Added `tests/test_phase_203_capture_projection.py` with 10 tests covering new keys, v1.42 key preservation, null input handling, and negative delta behavior.
- Verified the hot-path regression slice, SAFE-05 pin check, and SAFE-07 source-diff check.

## Task Commits

Each task was handled atomically:

1. **Task 1: Create canonical soak capture harness** — `c33fe47` (feat)
2. **Task 2: Create capture projection contract tests** — `7549d44` (test)
3. **Task 3: Hot-path regression slice + SAFE-07 source-diff verification** — verification-only task; no file changes to commit separately.

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `scripts/soak-capture.sh` — Canonical versioned soak capture harness that writes v1.43 NDJSON rows from `/health`.
- `tests/test_phase_203_capture_projection.py` — Capture-side contract tests that extract the script's jq projection and run synthesized payloads through jq.

## Verification

- `test -x scripts/soak-capture.sh` — passed.
- `bash -n scripts/soak-capture.sh` — passed.
- Public-safe grep for RFC1918 literals, `.local` names, and `cake-shaper` in `scripts/soak-capture.sh` — passed with zero matches.
- `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` — 10 passed in 0.12s.
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — 667 passed in 40.42s.
- `.venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts"` — 1 passed, 24 deselected in 0.27s.
- `git diff b72b463 -- src/wanctl/` — empty.

## Decisions Made

- Used mandatory `HEALTH_URL` with no default to keep the harness public-safe and portable across deployments.
- Implemented `load_rtt_delta_us` as integer microseconds with the plan-locked null guard for missing source values.
- Extracted the jq projection from `scripts/soak-capture.sh` in tests to avoid a second projection source of truth.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. The script's `docs/SOAK_HARNESS.md` reference intentionally points to the Phase 203 Plan 03 documentation deliverable.

## Issues Encountered

- The repository pre-commit documentation hook recommended docs for the new test helper functions. Plan 203-03 owns soak harness documentation, so the test commit used the hook's supported `SKIP_DOC_CHECK=1` path while still running the hook; no `--no-verify` was used.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 203-02. The capture row schema is now locked for the aggregator and synthetic replay fixture work.

## Self-Check: PASSED

- Found `scripts/soak-capture.sh`.
- Found `tests/test_phase_203_capture_projection.py`.
- Found this summary file.
- Found task commit `c33fe47`.
- Found task commit `7549d44`.

---
*Phase: 203-target-edge-churn-instrumentation-obsv*
*Completed: 2026-05-06*
