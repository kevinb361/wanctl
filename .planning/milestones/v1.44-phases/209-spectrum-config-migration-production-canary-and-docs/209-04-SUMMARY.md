---
phase: 209-spectrum-config-migration-production-canary-and-docs
plan: 04
subsystem: production-canary
tags: [spectrum, cake, besteffort, wash, safe-08, safe-09, v1.44]

# Dependency graph
requires:
  - phase: 205-tin-agnostic-cake-signal-allow-wash-gate
    provides: allow_wash emission and tin-agnostic CAKE signal support
  - phase: 206-a-b-replay-harness-rollback-gates
    provides: Phase 206 predeploy/post-soak rollback gate harness
  - phase: 207-soak-harness-hardening-v1-43-closeout-routed
    provides: fail-closed SAFE source-diff verifier foundation
  - phase: 208-carry-on-quick-tasks
    provides: TOOL-02 wanctl-history operator tooling drift included in SAFE-09 closeout
  - phase: 209-spectrum-config-migration-production-canary-and-docs
    provides: Plans 209-01 through 209-03 wash validation, SAFE verifier, and docs prerequisites
provides:
  - Spectrum config migration to 920Mbit besteffort wash
  - v1.44.0 version bump closeout across package, module, and Docker surfaces
  - 24h production soak evidence for cake-shaper running v1.44.0
  - Phase 206 post-soak rollback-gate PASS verdict
  - SAFE-08 and SAFE-09 mechanical closeout PASS verdicts
affects: [v1.44-closeout, spectrum-production, safe-08, safe-09, phase-209]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Two-snapshot production canary closeout with Snapshot A rollback target and Snapshot B deploy evidence
    - Mechanical SAFE closeout via scripts/check-safe07-source-diff.sh instead of manual git-diff review
    - Phase 206 post-soak gate as binding comparator for production soak verdicts

key-files:
  created:
    - .planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-04-SUMMARY.md
    - .planning/phases/209-spectrum-config-migration-production-canary-and-docs/soak/20260521T222622Z/soak-capture.ndjson
    - .planning/phases/209-spectrum-config-migration-production-canary-and-docs/soak/20260521T222622Z/ab-replay-summary-20260521T222622Z.json
    - .planning/phases/209-spectrum-config-migration-production-canary-and-docs/soak/20260521T222622Z/soak-summary-20260521T222622Z.json
    - .planning/phases/209-spectrum-config-migration-production-canary-and-docs/task4b-evidence/20260522T233944Z/safe-closeout-rerun.md
  modified:
    - configs/spectrum.yaml
    - pyproject.toml
    - src/wanctl/__init__.py
    - docker/Dockerfile
    - CHANGELOG.md
    - scripts/check-safe07-source-diff.sh
    - tests/test_check_safe07_source_diff.py

key-decisions:
  - "Task 4b final verdict is PASS after rerunning SAFE-08 and SAFE-09 mechanically against v1.43 close ref 6508d68."
  - "The SAFE-09 verifier allowlist includes src/wanctl/history.py because Phase 208 verified it as intentional TOOL-02 operator-tooling drift, not controller-path drift."
  - "Phase 206 post-soak gate rc=0 is the binding canary comparator; the zone × cause-tag soak summary remains informational for operator review."

patterns-established:
  - "SAFE closeout reruns must be evidence-backed: unit test the verifier allowlist, then run both SAFE-08 and SAFE-09 gates against the same anchor."
  - "Production canary summaries should distinguish rollback-clean Snapshot A from deploy-evidence Snapshot B."

requirements-completed: [TOPO-03, TOPO-06, SAFE-08, SAFE-09]

# Metrics
duration: 48s continuation; multi-day operator-gated canary/soak elapsed
completed: 2026-05-22
---

# Phase 209 Plan 04: Spectrum Migration Canary and SAFE Closeout Summary

**Spectrum now runs the v1.44.0 `920Mbit besteffort wash` migration with 24h production soak evidence, Phase 206 rollback gates clear, and SAFE-08/SAFE-09 mechanical closeout passing against `6508d68`.**

## Performance

- **Duration:** 48s continuation; multi-day operator-gated canary/24h soak elapsed
- **Started:** 2026-05-22T23:41:00Z
- **Completed:** 2026-05-22T23:41:48Z
- **Tasks:** 5 plan tasks completed (Task 1, Task 4a, Task 2, Task 3, Task 4b)
- **Files modified/created:** 7 key repo files plus production-evidence artifacts

## Accomplishments

- Closed the v1.44.0 Spectrum migration with the locked 5-file closeout commit: `configs/spectrum.yaml`, `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`, and `CHANGELOG.md`.
- Captured and committed 24h production soak evidence from cake-shaper on v1.44.0; the Phase 206 post-soak gate exited `0` with rollback gates clear.
- Recorded final Task 4b PASS: SAFE-08 and SAFE-09 both pass mechanically after the approved verifier allowlist correction for `src/wanctl/history.py`.

## Final Task 4b Verdict

**PASS** — recorded in `task4b-evidence/20260522T233944Z/safe-closeout-rerun.md`.

Validation rerun:

```text
$ .venv/bin/pytest tests/test_check_safe07_source_diff.py -q
17 passed in 1.08s

$ bash scripts/check-safe07-source-diff.sh --att-config-whitelist 6508d68
SAFE-08 OK: no configs/att.yaml diff vs 6508d68

$ bash scripts/check-safe07-source-diff.sh 6508d68
SAFE-09 OK: diff vs 6508d68 bounded to v1.44 allowlist
```

ATT identity was also checked via `git diff --quiet 6508d68..HEAD -- configs/att.yaml`; the command returned success.

## Production Soak and Gate Evidence

- **Soak ID:** `20260521T222622Z`
- **Soak capture:** `.planning/phases/209-spectrum-config-migration-production-canary-and-docs/soak/20260521T222622Z/soak-capture.ndjson`
- **Rows:** `82954`
- **Version:** all rows reported `1.44.0`
- **Status:** all rows reported `healthy`
- **Wall-clock span:** `23.99972222222222` hours
- **Parse errors:** `0`
- **Missing boundary-marker rows:** `0`
- **Journal wash/readback RuntimeError count:** `0`

Phase 206 post-soak gate:

```text
post-soak gate rc: 0
[phase206-gate-check INFO] RRUL comparison source=controller_rate_p99_mbps
[phase206-gate-check INFO] RRUL p99: -0.0% (within +/-5.0%) (source: controller_rate_p99_mbps)
[phase206-gate-check INFO] Daemon restart-rate: 0.00/h (matches baseline)
[phase206-gate-check INFO] Pressure-state transition-rate: 49.83/h (baseline 77.17/h, +-35.4%)
[phase206-gate-check INFO] PASS: Phase 206 rollback gates clear
```

The operator-readable zone × cause-tag summary was generated at `soak/20260521T222622Z/soak-summary-20260521T222622Z.json`; the binding comparator remains the Phase 206 post-soak gate above.

## Task Commits

Each task or evidence segment was committed atomically:

1. **Task 4a: Closeout commit (5-file v1.44 shape)** — `e12202e` (`chore`)
2. **Task 3: Preserve post-soak gate evidence** — `76891f2` (`test`)
3. **Task 4b: Include history tooling in SAFE-09 allowlist** — `9ca83e2` (`fix`)

**Plan metadata:** committed after this summary/tracking update.

## Files Created/Modified

- `configs/spectrum.yaml` — Spectrum migration to `ceiling_mbps: 920`, `diffserv: besteffort`, and `allow_wash: true`.
- `pyproject.toml` — package version bumped to `1.44.0`.
- `src/wanctl/__init__.py` — module version bumped to `1.44.0`.
- `docker/Dockerfile` — Docker label version bumped to `1.44.0`.
- `CHANGELOG.md` — v1.44.0 heading date finalized in the closeout commit.
- `scripts/check-safe07-source-diff.sh` — SAFE-09 v1.44 allowlist corrected to include verified TOOL-02 `src/wanctl/history.py` drift.
- `tests/test_check_safe07_source_diff.py` — verifier happy-path coverage updated for `history.py`.
- `.planning/phases/209-spectrum-config-migration-production-canary-and-docs/soak/20260521T222622Z/*` — 24h soak, A/B replay, baseline, summary, gate, quality, and journal evidence.
- `.planning/phases/209-spectrum-config-migration-production-canary-and-docs/task4b-evidence/20260522T233944Z/safe-closeout-rerun.md` — final Task 4b PASS evidence.

## Decisions Made

- The approved SAFE-09 verifier fix is accepted as closeout remediation because `src/wanctl/history.py` is Phase 208 TOOL-02 operator tooling, not controller threshold/algorithm drift.
- SAFE-08 and SAFE-09 verdicts are mechanical and anchored to `6508d68`; no manual git-diff substitute was used for the final verdict.
- Phase 209 closes PASS rather than rollback/gaps_found because the production post-soak Phase 206 gate returned rc `0`, SAFE-08 returned rc `0`, and SAFE-09 returned rc `0`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected SAFE-09 verifier allowlist for Phase 208 TOOL-02 drift**
- **Found during:** Task 4b (SAFE-08 / SAFE-09 mechanical closeout)
- **Issue:** Initial SAFE-09 closeout failed because `src/wanctl/history.py` was omitted from the v1.44 allowlist even though Phase 208 intentionally modified it for `wanctl-history --ingestion-rate`.
- **Fix:** Added `src/wanctl/history.py` to `scripts/check-safe07-source-diff.sh` and updated the verifier happy-path unit test.
- **Files modified:** `scripts/check-safe07-source-diff.sh`, `tests/test_check_safe07_source_diff.py`, `task4b-evidence/20260522T233944Z/safe-closeout-rerun.md`
- **Verification:** `tests/test_check_safe07_source_diff.py` passed; SAFE-08 and SAFE-09 both returned OK against `6508d68`.
- **Committed in:** `9ca83e2`

---

**Total deviations:** 1 auto-fixed blocking verifier issue.
**Impact on plan:** No production mutation or rollback occurred; the verifier now matches the already-approved v1.44 source-diff scope.

## Issues Encountered

- Initial Task 4b SAFE-09 verdict failed before the approved verifier fix because `src/wanctl/history.py` was missing from the allowlist. The failure is preserved at `task4b-evidence/20260522T233502Z/verdict.md`; the final rerun PASS supersedes it.

## User Setup Required

None - no additional external service configuration is required after closeout. Production canary and soak were already operator-gated and completed.

## Known Stubs

None.

## Threat Flags

None.

## Next Phase Readiness

Phase 209 Plan 04 is complete. Phase 209 can now be marked complete, and v1.44 is ready for milestone closeout / verification review.

## Self-Check: PASSED

- Summary file exists: `FOUND: summary`
- Task commits exist in git log: `e12202e`, `76891f2`, `9ca83e2`
- Final local verification rerun passed: SAFE verifier unit tests, SAFE-08, SAFE-09, and ATT identity check.

---
*Phase: 209-spectrum-config-migration-production-canary-and-docs*
*Completed: 2026-05-22*
