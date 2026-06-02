---
phase: 223-staging-proof-clean-restart-reproduction
plan: 01
subsystem: testing
tags: [steering, replay-harness, routeros-fake, cake, proof]

requires:
  - phase: 222-steering-drift-audit
    provides: Steering drift audit scope and SAFE-12 source-floor constraints
provides:
  - Offline steering replay harness for PROOF-01
  - FULL I/O SEAL seam inventory and evidence
  - Fixture corpus with hysteresis and confidence-mode coverage
  - Operator-facing replay-results JSON and markdown artifacts
affects: [phase-223, phase-224, steering-runtime-drift-closure]

tech-stack:
  added: []
  patterns:
    - Constructor-injected daemon fakes
    - Tempdir state-file redirection
    - Deterministic replay evidence generation

key-files:
  created:
    - tests/integration/steering_replay/fake_router_transport.py
    - tests/integration/steering_replay/fake_cake_reader.py
    - tests/integration/steering_replay/fake_live_rtt_source.py
    - tests/integration/steering_replay/replay_harness.py
    - tests/integration/steering_replay/test_replay_corpus.py
    - tests/integration/steering_replay/test_io_seal.py
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/seam-inventory.md
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/README.md
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.json
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.md
  modified:
    - tests/integration/__init__.py
    - .claude/context.md

key-decisions:
  - "Selected FULL I/O SEAL option (a): drive SteeringDaemon.run_cycle() end-to-end with all live-I/O seams sealed by fakes or tempdir paths."
  - "Default fixture posture is hysteresis-only, with one confidence-mode smoke fixture deriving cycle budgets from production config."
  - "Used synthesized-from-spine-contract provenance for the Phase 212 anchored fixture because concrete archived per-cycle evidence was not present in this checkout."

patterns-established:
  - "Replay fakes deny undocumented live-I/O calls before raising, with method and cycle recorded."
  - "Replay evidence normalizes timestamps so rerunning the harness does not create timestamp-only churn."

requirements-completed: [PROOF-01]

duration: ~45 min
completed: 2026-06-02
---

# Phase 223 Plan 01: Offline Steering Replay Harness Summary

**Offline SteeringDaemon replay harness with fake RouterOS/CAKE/baseline seams and deterministic PROOF-01 evidence artifacts.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-06-02T17:23:12Z
- **Completed:** 2026-06-02T17:37:40Z
- **Tasks:** 4
- **Files modified:** 20

## Accomplishments

- Inventoried every `SteeringDaemon.run_cycle()` live-I/O seam and documented the FULL I/O SEAL strategy.
- Added fake RouterOS, CAKE, and baseline/RTT sources that prevent live router, socket, HTTP, and production state access.
- Authored six fixture YAML files covering steady-good, onset-degraded, recovery, CAKE-read-failure, provenance fallback, and confidence-mode smoke paths.
- Implemented `replay_harness.py --all` and pytest corpus checks that emit `replay-results.json` and `replay-results.md`.

## Task Commits

Each task was committed atomically:

1. **Task 223-01-01: Inspect existing steering-daemon seams** — `b954cf4` (docs)
2. **Task 223-01-02: Implement fake RouterOS transport and pytest fixtures** — `bfa4603` (test)
3. **Task 223-01-03: Define fixture schema and author corpus** — `e3ca746` (test)
4. **Task 223-01-04: Implement replay harness and replay evidence** — `c93f9a8` (test)
5. **Rule 1 fix: Stable fake interaction timestamps** — `7693f9d` (fix)
6. **Rule 1 fix: Stable transition evidence timestamps** — `875da10` (fix)

**Plan metadata:** pending this commit.

## Files Created/Modified

- `tests/integration/steering_replay/fake_router_transport.py` — RouterOSController-shaped fake exposing only `get_rule_status`, `enable_steering`, and `disable_steering`.
- `tests/integration/steering_replay/fake_cake_reader.py` — scripted `CakeStatsReader` fake for CAKE success, soft failure, and exception paths.
- `tests/integration/steering_replay/fake_live_rtt_source.py` — `FixtureBaselineLoader` sealing baseline, live RTT, and IRTT paths.
- `tests/integration/steering_replay/conftest.py` — pytest tempdir workspace, daemon factory, and urlopen/socket I/O seals.
- `tests/integration/steering_replay/fixtures/*.yaml` — replay fixture corpus with explicit harness mode and provenance metadata.
- `tests/integration/steering_replay/replay_harness.py` — standalone and pytest-callable replay runner.
- `tests/integration/steering_replay/test_replay_corpus.py` — corpus, no-production-path, full-I/O-seal, and confidence-budget tests.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/*` — seam inventory, operator README, and replay results.

## Decisions Made

- Selected FULL I/O SEAL option (a) to preserve daemon-path fidelity for later PROOF-03 claims.
- Disabled confidence scoring by default in fixture runs to isolate spine-contract verdicts from production confidence timing, while retaining one production-parity confidence smoke fixture.
- Labeled the Phase 212 anchored fixture as synthesized with a provenance note because concrete archived per-cycle evidence was not available in this checkout.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stabilized replay evidence timestamps**
- **Found during:** Task 223-01-04 verification
- **Issue:** Re-running `replay_harness.py --all` regenerated timestamp-only differences in `replay-results.json`.
- **Fix:** Normalized fake interaction timestamps and persisted transition timestamps to deterministic per-cycle values.
- **Files modified:** `fake_router_transport.py`, `fake_cake_reader.py`, `fake_live_rtt_source.py`, `replay_harness.py`, `replay-results.json`
- **Verification:** Re-ran `replay_harness.py --all` and confirmed no replay-results diff, then ran the full steering replay pytest suite.
- **Committed in:** `7693f9d`, `875da10`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** Improves evidence repeatability without changing steering behavior or controller-path source.

## Issues Encountered

- Pre-commit documentation hook prompted on security/feature-looking test changes; `.claude/context.md` was updated so hooks could run normally without bypass.
- Phase 212 archived per-cycle source evidence was absent from this checkout, so the anchored fixture was explicitly labeled as synthesized with `provenance_note` rather than silently mislabeling it.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None - no new network endpoint, auth path, file access trust boundary, or production schema was introduced. The harness explicitly blocks live HTTP/socket access and production runtime paths.

## Verification

- `for f in steady-good onset-degraded recovery cake-read-failure onset-degraded-from-phase212 onset-degraded-confidence; do test -f tests/integration/steering_replay/fixtures/$f.yaml || exit 1; done` — PASS
- `.venv/bin/pytest -o addopts='' tests/integration/steering_replay/ -v` — PASS (`17 passed`)
- `.venv/bin/python tests/integration/steering_replay/replay_harness.py --all` — PASS, writes replay evidence
- `.venv/bin/python -m json.tool .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.json >/dev/null` — PASS
- `grep -q "I/O Seal Audit" .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.md` — PASS

## Self-Check: PASSED

- Created files exist: PASS
- Task commits exist: PASS (`b954cf4`, `bfa4603`, `e3ca746`, `c93f9a8`, `7693f9d`, `875da10`)
- Replay evidence regenerates without dirtying committed results: PASS

## Next Phase Readiness

Ready for Plan 223-02 clean-restart reproduction. PROOF-01 is complete; PROOF-02 can append the clean-restart fixture and results into the existing replay evidence structure.

---
*Phase: 223-staging-proof-clean-restart-reproduction*
*Completed: 2026-06-02*
