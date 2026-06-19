---
phase: 241-fping-backend-offline-reflector-quality
plan: 03
subsystem: fping-fixtures
tags: [fping, fixtures, subprocess, pytest, live-capture]
requires:
  - phase: 241-fping-backend-offline-reflector-quality
    provides: offline FpingMeasurement backend and synthetic bootstrap fixture tests
  - phase: 241-fping-backend-offline-reflector-quality
    provides: Phase 241 SAFE-17 verifier and fping config validation
provides:
  - non-mutating live-host fping fixture capture helper
  - six real fping 5.1 fixtures with stdout/stderr/returncode/command metadata
  - CompletedProcess-backed parser/scorer tests for real captures
  - mechanical capture-helper command parity test against FpingMeasurement._build_command
affects: [phase-242-backend-factory-runtime-fallback, phase-243-benchmark, phase-245-ab]
tech-stack:
  added: []
  patterns: [operator-run non-mutating capture, metadata-backed subprocess fixture reconstruction]
key-files:
  created:
    - .planning/phases/241-fping-backend-offline-reflector-quality/241-03-SUMMARY.md
  modified:
    - scripts/capture-fping-fixtures.sh
    - scripts/capture_fping_fixtures.py
    - tests/fixtures/fping/reply.txt
    - tests/fixtures/fping/total_loss.txt
    - tests/fixtures/fping/partial_loss.txt
    - tests/fixtures/fping/partial_line.txt
    - tests/fixtures/fping/banner_noise.txt
    - tests/fixtures/fping/process_death.txt
    - tests/test_fping_measurement.py
    - .claude/context.md
key-decisions:
  - "Ran only the approved non-mutating fping capture path on cake-shaper; no routing, CAKE, qdisc, tc, RouterOS, service, or firewall mutations were made."
  - "Used yandex.com as the natural lossy reflector after 8.8.8.8 stopped producing partial loss during retry capture."
  - "Preserved stdout/stderr metadata fidelity for fping 5.1 -q by truncating partial_line in the stream that actually carries target lines."
patterns-established:
  - "Fixture tests must parse metadata into subprocess.CompletedProcess(args, stdout, stderr, returncode), not pass raw fixture files as stdout."
  - "Capture-helper command parity is proven by invoking --print-command and comparing argv to _build_command()."
requirements-completed: [FPING-04, REFL-01]
duration: 13min continuation
completed: 2026-06-15T22:59:20Z
---

# Phase 241 Plan 03: Real fping Capture Fixtures Summary

**Real fping 5.1 captures from cake-shaper now bind the offline parser/scorer tests through metadata-backed CompletedProcess fixtures.**

## Performance

- **Duration:** 13 min continuation after checkpoint
- **Started:** 2026-06-15T22:46:01Z
- **Completed:** 2026-06-15T22:59:20Z
- **Tasks:** 3 including checkpoint continuation
- **Files modified:** 10

## Accomplishments

- Fixed the capture helper discovered at the checkpoint so `partial_line` truncates whichever stream carries fping target lines; on live fping 5.1 `-q`, those lines landed on stderr.
- Captured six real fping 5.1 fixtures on `cake-shaper` using the approved non-mutating helper path and copied them into `tests/fixtures/fping/`.
- Reworked `tests/test_fping_measurement.py` so fixture-driven tests reconstruct real `subprocess.CompletedProcess(args, stdout, stderr, returncode)` objects from metadata.
- Added the mechanical `test_capture_command_matches_build_command` proof and `test_process_death_fixture_returncode_is_negative` proof.

## Task Commits

Each task/fix was committed atomically:

1. **Task 1: capture helper** - `76435940` (feat)
2. **Rule 1 fix: stderr-host partial_line handling** - `365e5e6f` (fix)
3. **Rule 3 fix: quiet fping banner-noise capture unblock** - `fdaeea72` (fix)
4. **Task 2/3: real fixtures + CompletedProcess tests** - `0e2dce93` (test)

## Files Created/Modified

- `scripts/capture-fping-fixtures.sh` — non-mutating operator wrapper; unchanged from Task 1 after checkpoint.
- `scripts/capture_fping_fixtures.py` — live capture core; now handles target lines on stderr and quiet banner-noise captures.
- `tests/fixtures/fping/reply.txt` — real fping 5.1 all-reply capture.
- `tests/fixtures/fping/total_loss.txt` — real fping 5.1 TEST-NET all-loss capture.
- `tests/fixtures/fping/partial_loss.txt` — real fping 5.1 partial-loss capture using `yandex.com`, with RTT floats and `-` on the same host line.
- `tests/fixtures/fping/partial_line.txt` — real fping 5.1 capture truncated in stderr to exercise incomplete-line tolerance.
- `tests/fixtures/fping/banner_noise.txt` — real fping 5.1 target capture plus real fping version banner noise in stderr.
- `tests/fixtures/fping/process_death.txt` — real fping 5.1 process-death capture with Python returncode `-15`.
- `tests/test_fping_measurement.py` — metadata parser, CompletedProcess fixture path, mechanical command parity, and negative returncode gate proof.
- `.claude/context.md` — local project context updated for capture-helper and real-fixture status.

## Decisions Made

- Kept the capture non-mutating and limited live host interaction to SSH staging, `fping` reads, and `/tmp` cleanup.
- Switched the partial-loss target from `8.8.8.8` to `yandex.com` after repeated read-only captures showed `8.8.8.8` no longer produced the required mixed RTT/`-` line.
- Accepted a helper-side banner-noise composition using the real captured `fping --version` banner when the byte-identical `-q` runtime command suppressed non-host noise in this environment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed partial_line stdout-only truncation**
- **Found during:** Task 2 live capture continuation.
- **Issue:** fping 5.1 with `-q` emitted target summary lines on stderr, so `truncate_stdout()` left stdout empty and `partial_line` validation failed.
- **Fix:** Added `truncate_target_stream()` to locate the stream containing target lines, truncate that stream in place, and validate against the preserved stdout/stderr split.
- **Files modified:** `scripts/capture_fping_fixtures.py`, `.claude/context.md`
- **Verification:** `bash -n scripts/capture-fping-fixtures.sh`; `.venv/bin/python -m py_compile scripts/capture_fping_fixtures.py`; `.venv/bin/ruff check scripts/capture_fping_fixtures.py`; live `partial_line` capture succeeded.
- **Committed in:** `365e5e6f`

**2. [Rule 3 - Blocking] Unblocked banner_noise under quiet fping**
- **Found during:** Task 2 live capture continuation after partial_line was fixed.
- **Issue:** The byte-identical runtime command includes `-q`; on this host, banner/noise text was suppressed and only target summary lines were emitted, so the banner_noise shape could not be written.
- **Fix:** Added `ensure_banner_noise()` to prepend the real captured `fping --version` banner to stderr only when the capture lacks a non-host line, without changing the fping target command or mutating live state.
- **Files modified:** `scripts/capture_fping_fixtures.py`, `.claude/context.md`
- **Verification:** `bash -n scripts/capture-fping-fixtures.sh`; `.venv/bin/python -m py_compile scripts/capture_fping_fixtures.py`; `.venv/bin/ruff check scripts/capture_fping_fixtures.py`; live `banner_noise` capture succeeded.
- **Committed in:** `fdaeea72`

**Total deviations:** 2 auto-fixed issues (Rule 1 bug, Rule 3 blocking).  
**Impact on plan:** Both were required to complete real fping 5.1 capture under the planned byte-identical `-q` invocation; no live routing/shaping mutations or controller-path behavior changes were introduced.

## Issues Encountered

- `8.8.8.8` had produced natural partial loss during the orchestrator scan but returned all replies during repeated capture attempts. A read-only fping candidate scan found `yandex.com`, which eventually produced `yandex.com : 187 194 184 - 191`.
- Full test suite remains blocked by pre-existing `tests/test_cleanup_boundary_guard.py::test_guard_passes_on_real_repo` BOUND-01 failures against Phase 241's committed validator changes (`src/wanctl/check_config_validators.py`, `tests/test_check_config.py`). This is outside Plan 03's fixture/test surface.
- Full `ruff check src/ tests/` and `mypy src/wanctl/fping_measurement.py` still report pre-existing lint/type issues outside this plan's edit surface, including `src/wanctl/rtt_measurement.py:325` `RttSample` forward-reference noise already recorded in prior summaries.

## Auth Gates

None.

## Known Stubs

None. The synthetic bootstrap markers are gone; all six fixture files now begin with `# REAL FPING CAPTURE` metadata.

## User Setup Required

None - the authorized live capture was completed and remote `/tmp/wanctl-fping-capture.*` staging directories were removed afterward.

## Verification

- `bash -n scripts/capture-fping-fixtures.sh && .venv/bin/python -m py_compile scripts/capture_fping_fixtures.py` → passed
- `.venv/bin/ruff check scripts/capture_fping_fixtures.py tests/test_fping_measurement.py` → passed
- `.venv/bin/pytest -o addopts='' tests/test_fping_measurement.py -q` → `24 passed`
- `rg -i "synthetic bootstrap" tests/fixtures/fping || true` → no matches
- `.venv/bin/pytest tests/ -q -x` → failed on pre-existing BOUND-01 guard drift after `2329 passed, 2 skipped, 2 deselected`; first failure: `tests/test_cleanup_boundary_guard.py::test_guard_passes_on_real_repo`
- `.venv/bin/ruff check src/ tests/` → failed on pre-existing repo-wide lint findings outside Plan 03 changed files
- `.venv/bin/mypy src/wanctl/fping_measurement.py` → failed through imported pre-existing `src/wanctl/rtt_measurement.py:325` `RttSample` forward-reference

## Threat Flags

None. The only live-host surface was the planned non-mutating operator capture helper; no new network endpoint, auth path, file trust boundary, or schema surface was added beyond the plan threat model.

## Next Phase Readiness

- Plan 04 can run the Phase 241 SAFE-17 boundary closeout with real fping fixtures now committed.
- Phase 242 can consume these fixtures when wiring factory/fallback behavior, but should keep the existing deferred steering-side fping validator parity concern visible.

## Self-Check: PASSED

- Created/modified files exist: `scripts/capture_fping_fixtures.py`, `tests/test_fping_measurement.py`, all six `tests/fixtures/fping/*.txt`, and this summary.
- Task commits found in git history: `76435940`, `365e5e6f`, `fdaeea72`, `0e2dce93`.

---
*Phase: 241-fping-backend-offline-reflector-quality*
*Completed: 2026-06-15T22:59:20Z*
