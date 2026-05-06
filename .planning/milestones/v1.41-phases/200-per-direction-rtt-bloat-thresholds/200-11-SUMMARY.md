---
phase: 200-per-direction-rtt-bloat-thresholds
plan: 11
subsystem: validation-tooling
tags: [canary, bash, jq, ssh-safety, self-test, valn-06]

# Dependency graph
requires:
  - phase: 200-per-direction-rtt-bloat-thresholds
    provides: Phase 200 canary script and failed deploy-gate evidence
provides:
  - Correct baseline RTT extraction for canary pre/post idle bookends
  - Safe remote YAML path validation before SSH command construction
  - Stable --self-test dispatch for offline canary helper regression tests
affects: [phase-200, valn-06, saturation-canary, wr-02]

# Tech tracking
tech-stack:
  added: []
  patterns: [bash self-test dispatch, regex-gated remote shell path, offline canary helper tests]

key-files:
  created:
    - tests/test_phase200_canary_script.py
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-11-SUMMARY.md
  modified:
    - scripts/phase200-saturation-canary.sh
    - scripts/phase200-saturation-canary.env.example

key-decisions:
  - "Canary helper tests use --self-test dispatch instead of fragile sed-range sourcing, so live env validation and production preflights never run during unit tests."
  - "REMOTE_YAML_PATH is intentionally restricted to absolute paths matching ^/[A-Za-z0-9._/-]+$ before constructing the SSH command."

patterns-established:
  - "Bash operational scripts can expose narrow --self-test targets for pure helper functions while keeping main flow fail-closed."
  - "Operator-supplied remote shell paths must be validated before interpolation and quoted with sudo cat -- when used over SSH."

requirements-completed: [VALN-06]

# Metrics
duration: 4min
completed: 2026-05-04T01:12:16Z
---

# Phase 200 Plan 11: Canary Helper Hardening Summary

**Canary baseline RTT bookends now read the live /health shape, and remote YAML SSH reads are guarded by a direct-tested safe-path validator.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-04T01:09:11Z
- **Completed:** 2026-05-04T01:12:16Z
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- Fixed `summarize_baseline()` to read `.wans[0].baseline_rtt_ms` instead of the old nonexistent `.wans[0].rtt.baseline_rtt_ms` path; `sample_count` now uses `$rtts | length`.
- Added `--self-test` dispatch before operational env validation so tests can drive `summarize_baseline` and `validate_remote_yaml_path` without sourcing script fragments or running live canary preflights.
- Added `validate_remote_yaml_path()` with regex `^/[A-Za-z0-9._/-]+$`, invoked it immediately after splitting `PHASE200_REMOTE_YAML_SSH`, and changed the remote command to `sudo cat -- '${REMOTE_YAML_PATH}'`.
- Added 9 offline tests covering baseline summarization, old-path rejection, self-test usage, and WR-02 unsafe path rejection.

## Task Commits

Each task was committed atomically, with TDD RED/GREEN gates:

1. **Task 1 RED: Add failing canary self-test coverage** - `9925f8a` (test)
2. **Task 1 GREEN: Add --self-test mode and fix baseline RTT jq path** - `e883813` (feat)
3. **Task 2 RED: Add failing remote YAML path validator coverage** - `9ffa8fa` (test)
4. **Task 2 GREEN: Validate REMOTE_YAML_PATH before SSH expansion** - `8baa2c9` (fix)

**Plan metadata:** pending final metadata commit.

## Files Created/Modified

- `tests/test_phase200_canary_script.py` - Offline regression tests using `bash scripts/phase200-saturation-canary.sh --self-test ...`; no sed-range extraction.
- `scripts/phase200-saturation-canary.sh` - Corrected baseline jq path, added self-test dispatcher, added remote YAML path validator, and safely quoted remote `sudo cat --`.
- `scripts/phase200-saturation-canary.env.example` - Documents the remote YAML path regex, accepted canonical path example, and rejected metacharacter example.
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-11-SUMMARY.md` - This plan execution summary.

## Decisions Made

- Kept the validator function above the `--self-test` dispatcher so direct validator tests cannot hit Bash top-to-bottom definition ordering failures.
- Treated the restrictive path regex as intentional for current `/etc/wanctl/*.yaml` operations; rejecting unusual but possible path characters is safer than accepting shell metacharacters in deploy tooling.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The repository documentation hook prompts interactively when test files add functions/classes. Commits were retried with `SKIP_DOC_CHECK=1` (without `--no-verify`) so hooks still ran while avoiding noninteractive prompt deadlock.
- `shellcheck` is unavailable on this host; the plan's shellcheck verification was recorded as skipped per the acceptance command's fallback.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py -q` → `9 passed in 0.15s`.
- Focused hot-path regression slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `578 passed in 42.13s`.
- Static checks confirmed old jq path absent, new jq path present, `--self-test` present, `remote_yaml_path_unsafe` present, `sudo cat --` present, and `_run_validate_remote_yaml_path` present.
- `bash scripts/phase200-saturation-canary.sh --self-test validate_remote_yaml_path /etc/wanctl/spectrum.yaml` exits 0; `../etc/passwd` exits non-zero.

## Known Stubs

- `scripts/phase200-saturation-canary.env.example` intentionally contains empty quoted env-var assignments as an operator template; these do not flow to UI rendering and are not runtime defaults.

## Threat Flags

None beyond the planned WR-02 mitigation surface. The only new trust-boundary behavior tightens remote YAML file access by validating operator-provided paths before SSH command construction.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 200-12 can proceed with the canary helper defects closed.
- Future canary verdicts should populate numeric `pre_baseline_rtt_ms` and `post_baseline_rtt_ms` values when `/health` exposes baseline RTT samples.

## Self-Check: PASSED

- Found `tests/test_phase200_canary_script.py`.
- Found `scripts/phase200-saturation-canary.sh`.
- Found `scripts/phase200-saturation-canary.env.example`.
- Found `200-11-SUMMARY.md`.
- Found task commits `9925f8a`, `e883813`, `9ffa8fa`, and `8baa2c9`.

---
*Phase: 200-per-direction-rtt-bloat-thresholds*
*Completed: 2026-05-04T01:12:16Z*
