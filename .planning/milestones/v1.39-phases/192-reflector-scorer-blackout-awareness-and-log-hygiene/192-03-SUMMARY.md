---
phase: 192-reflector-scorer-blackout-awareness-and-log-hygiene
plan: 03
subsystem: validation
tags: [health, soak, deployment, versioning, production-validation]
requires:
  - phase: 192-reflector-scorer-blackout-awareness-and-log-hygiene
    provides: blackout-aware scorer gate and fusion-aware protocol log cooldown
  - phase: 192-precondition-waiver
    provides: explicit operator waiver for the still-blocked Phase 191 closure gate
provides:
  - Additive `download.hysteresis.dwell_bypassed_count` health field for the D-08 soak gate
  - Portable env-driven Phase 192 soak capture helper with one JSON object per WAN
  - Phase 192 production deployment, pre/post soak evidence, and v1.39.0 closeout under waiver
affects: [health payload, soak capture, production deployment, v1.39 closeout]
tech-stack:
  added: []
  patterns: [append-only health payload fields, env-driven operator capture scripts, waiver-backed phase closeout]
key-files:
  created:
    - scripts/phase192-soak-capture.sh
    - scripts/phase192-soak-capture.env.example
    - .planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-PRECONDITION-WAIVER.md
    - .planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-VERIFICATION.md
    - .planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-03-SUMMARY.md
  modified:
    - src/wanctl/health_check.py
    - tests/test_health_check.py
    - src/wanctl/__init__.py
    - pyproject.toml
    - docker/Dockerfile
    - CLAUDE.md
    - CHANGELOG.md
    - src/wanctl/wan_controller.py
    - .planning/STATE.md
key-decisions:
  - "Closed Phase 192 under the explicit Phase 191 waiver instead of representing the still-blocked ATT RRUL comparator as complete."
  - "Used the current live 24-hour production journal window as post-soak evidence because production had already been soaking for days."
  - "Deployed from a clean git archive plus intentional overlays rather than using the standard deploy script while unrelated local changes existed."
patterns-established:
  - "Operator-gated soak scripts stay portable by reading WAN names, health URLs, and SSH hosts entirely from environment variables."
  - "Health payload observability additions remain append-only and scoped to the documented consumer path."
requirements-completed: [MEAS-06, OPER-02, SAFE-03, VALN-02, VALN-03]
duration: operator-gated
completed: 2026-04-24
---

# Phase 192 Plan 03: Production soak closeout, health-field surfacing, and v1.39.0 deployment under waiver

**Phase 192 now has the D-08 health field, portable soak capture path, production deployment evidence, and pre/post soak comparison needed to close the blackout-hygiene work under the recorded Phase 191 waiver.**

## Performance

- **Duration:** Operator-gated across implementation, deployment, and soak evidence collection
- **Started:** 2026-04-24T13:33:45Z
- **Completed:** 2026-04-24T14:05:34Z
- **Tasks:** 5
- **Files modified:** 12

## Accomplishments

- Surfaced `download.hysteresis.dwell_bypassed_count` as an append-only `/health` field, with regression tests proving the field is present on download, defaults to zero, and is not added to upload.
- Added `scripts/phase192-soak-capture.sh` and its env example so D-08 evidence can be captured per WAN without hardcoded deployment IPs or WAN names.
- Recorded the explicit Phase 191 precondition waiver and populated `192-VERIFICATION.md` with deployment, local regression, canary, pre/post soak, and version evidence.
- Bumped Phase 192 closeout metadata to `1.39.0` and deployed that version to production.
- Fixed the discovered `WANController.measure_rtt()` real-`RTTCycleStatus` guard before shipping the final production overlay.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add health-field test coverage** - `d9817be` (test)
2. **Task 1: Surface dwell bypass count in download health** - `60ecf81` (fix)
3. **Task 2: Add portable soak capture helper** - `d9568ed` (feat)
4. **Task 3-5: Waiver, deployment verification, version bump, and production guard fix** - `d1c26de` (feat)

## Files Created/Modified

- `src/wanctl/health_check.py` - Adds the download-only additive health field consumed by the soak gate.
- `tests/test_health_check.py` - Locks the download field, missing-counter default, existing hysteresis keys, and upload non-surfacing contract.
- `scripts/phase192-soak-capture.sh` - Captures dwell, burst, fusion-transition, and protocol-deprioritization counters into one JSON file per WAN.
- `scripts/phase192-soak-capture.env.example` - Documents required environment variables without embedding production defaults.
- `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-PRECONDITION-WAIVER.md` - Records the operator waiver for proceeding while Phase 191 remains blocked.
- `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-VERIFICATION.md` - Records local tests, production deployment, canary evidence, pre/post soak captures, and the soak comparison.
- `src/wanctl/__init__.py`, `pyproject.toml`, `docker/Dockerfile`, `CLAUDE.md`, `CHANGELOG.md` - Carry the `1.39.0` closeout version.
- `src/wanctl/wan_controller.py` - Adds the production-discovered guard for real `RTTCycleStatus` in `measure_rtt()`.

## Decisions Made

- Treated the Phase 191/191.1 closure precondition as waived only for Phase 192, preserving Phase 191 as blocked in state and verification history.
- Accepted the current live 24-hour production journal window as post-soak evidence because the operator confirmed the deployed system had already been soaking for days.
- Used a clean `git archive` deployment plus intentional overlays so unrelated local worktree edits could not be shipped accidentally.
- Kept the soak helper env-driven and overwrite-idempotent, with raw logs as side artifacts rather than the source of truth.

## Deviations from Plan

### Operator-approved gate bypass

- **Found during:** Task 3 production closeout
- **Issue:** Phase 191 still had a failed ATT RRUL comparator and therefore could not honestly satisfy the original hard precondition.
- **Fix:** Recorded `192-PRECONDITION-WAIVER.md` and closed Phase 192 only under that explicit waiver.
- **Verification:** `192-VERIFICATION.md` preserves Phase 191 as blocked and limits the waiver to Phase 192.
- **Committed in:** `d1c26de`

### Existing soak substituted for a new wait

- **Found during:** Task 4 soak collection
- **Issue:** The plan expected a fresh 24-hour post-merge wait, but production had already been soaking for days before closeout.
- **Fix:** Captured the current live 24-hour journal window and documented that the newly exposed dwell field has no reconstructable pre-exposure history.
- **Verification:** Pre/post D-08 and OPER-02 counters are recorded in `192-VERIFICATION.md`; zero baselines remained zero and protocol-deprioritization counts changed by less than 1 percent.
- **Committed in:** `d1c26de`

## Issues Encountered

- The repo canary script reported steering unhealthy because it queries `127.0.0.1:9102` from the dev machine. Direct production-host verification showed `steering.service` active and `/health` healthy.
- The standard deploy script was intentionally avoided because unrelated local edits existed at the time; production received a clean archive plus specific overlays instead.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q -k "DwellBypassedCount or hysteresis"`: `9 passed, 162 deselected`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`: `513 passed`
- `.venv/bin/pytest tests/ -q`: `4650 passed, 2 deselected`
- `bash -n scripts/phase192-soak-capture.sh`: passed
- Missing-env script behavior: exited `2` as expected
- Production Spectrum and ATT `/health`: `version="1.39.0"`, `status="healthy"`, `download.hysteresis.dwell_bypassed_count=0`

## User Setup Required

None - no external service configuration required. Future reruns of the soak helper require the environment variables documented in `scripts/phase192-soak-capture.env.example`.

## Next Phase Readiness

- Phase 192 is ready for downstream v1.40 work that depends on corrected blackout-aware scoring and serialized Spectrum soak evidence.
- Phase 191 remains blocked on the ATT RRUL comparator and was not closed by this phase.
- Phase 196 remains gated on Phase 191 closure for its ATT canary rule.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-03-SUMMARY.md`
- Verification file exists at `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-VERIFICATION.md`
- Commits `d9817be`, `60ecf81`, `d9568ed`, and `d1c26de` exist in git history
- Production deployment evidence records both WANs healthy on `1.39.0`

---
*Phase: 192-reflector-scorer-blackout-awareness-and-log-hygiene*
*Completed: 2026-04-24*
