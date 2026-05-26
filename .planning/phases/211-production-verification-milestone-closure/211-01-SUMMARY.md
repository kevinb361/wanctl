---
phase: 211-production-verification-milestone-closure
plan: 01
subsystem: production-deploy
tags: [wanctl, v1.45, closeout-commit, spectrum, canary-deploy, rollback-snapshot]

# Dependency graph
requires:
  - phase: 210-windowed-peak-accumulator-implementation
    provides: windowed flapping peak accumulator implementation and regression tests
provides:
  - v1.45.0 four-file closeout commit on main
  - Spectrum Snapshot A rollback artifacts for pre-v1.45 deployment state
  - Spectrum v1.45.0 canary deployment activation and health readback
affects: [phase-211-production-verification, plan-211-02-att-deploy-and-observation]

# Tech tracking
tech-stack:
  added: []
  patterns: [four-file release closeout, operator-owned production snapshot, health-readback deploy verification]

key-files:
  created:
    - .planning/phases/211-production-verification-milestone-closure/211-01-SUMMARY.md
  modified:
    - pyproject.toml
    - src/wanctl/__init__.py
    - docker/Dockerfile
    - CHANGELOG.md

key-decisions:
  - "Use the non-loopback production health endpoint http://10.10.110.223:9101/health for Spectrum readback because loopback 127.0.0.1:9101 is not listening in the current production config."
  - "Restart wanctl@spectrum.service after deploy because scripts/deploy.sh copied v1.45.0 code but did not restart the already-running daemon."

patterns-established:
  - "Plan 211-01 records Snapshot A ISO8601, byte sizes, tar readability, deploy invocation, and health endpoint readback before opening the 7d observation window."

requirements-completed: []

# Metrics
duration: 7min
completed: 2026-05-26
---

# Phase 211 Plan 01: v1.45 Closeout Commit and Spectrum Canary Deploy Summary

**v1.45.0 was committed, regression-checked, snapshotted, deployed to Spectrum, restarted, and verified healthy via production health readback.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-26T18:42:40Z
- **Completed:** 2026-05-26T18:49:03Z
- **Tasks:** 5/5 completed
- **Files modified:** 6 tracked files in this plan (`4` closeout files + this summary + CHANGELOG deploy note)

## Accomplishments

- Landed the v1.45.0 closeout commit on `main` with exactly four files: `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`, and `CHANGELOG.md`.
- Re-ran the Phase 210 regression layer at the v1.45.0 commit: alerting/integration slice `132 passed`, hot-path slice `673 passed`.
- Verified Spectrum Snapshot A rollback artifacts on `cake-shaper` with matching ISO8601 `20260526T184731Z` and readable tarball.
- Deployed with the corrected two-argument invocation `./scripts/deploy.sh spectrum cake-shaper`, restarted `wanctl@spectrum.service`, and verified `/health` reports `status=healthy`, `version=1.45.0`.

## Task Commits

Each implementation/doc task was committed atomically where applicable:

1. **Task 211-01-01: Pre-flight checks** — no commit (read-only verification)
2. **Task 211-01-02: Apply v1.45 version bump and closeout commit** — `9cd3b62` (`chore`)
3. **Task 211-01-03: Run regression slices** — no commit (verification-only)
4. **Task 211-01-04: Capture Spectrum Snapshot A artifacts** — no commit (operator production action, verified read-only)
5. **Task 211-01-05: Deploy v1.45 to Spectrum and verify health** — no commit (operator production action, verified read-only)

**Plan metadata:** committed separately after summary/state/roadmap updates and a CHANGELOG deploy-note addition.

## Files Created/Modified

- `pyproject.toml` — project version bumped from `1.44.0` to `1.45.0`.
- `src/wanctl/__init__.py` — runtime `__version__` bumped from `1.44.0` to `1.45.0`.
- `docker/Dockerfile` — Docker image version label bumped from `1.44.0` to `1.45.0`.
- `CHANGELOG.md` — added `v1.45.0 — 2026-05-26` entry for the flapping peak-window repair, payload compatibility, and unchanged cooldown invariant.
- `.planning/phases/211-production-verification-milestone-closure/211-01-SUMMARY.md` — this execution record.
- `CHANGELOG.md` — metadata commit also adds the Spectrum canary activation note under v1.45.0 deploy notes.

## Verification Evidence

### Task 211-01-01 — Pre-flight

- `git status --porcelain | grep -E '^(M|A|D| M| D|\?\?) (src/|tests/)'` returned 0 matches.
- `.planning/phases/210-windowed-peak-accumulator-implementation/210-VERIFICATION.md` exists and contains `11/11`.
- `bash -n scripts/deploy.sh` exited 0.
- `grep -E '^#.*deploy\.sh +(wan1|<wan_name>) +' scripts/deploy.sh` matched the two-positional-arg usage header.

### Task 211-01-02 — Closeout commit

- Branch: `main`.
- Commit: `9cd3b62 chore(211-01): close v1.45 — flapping peak-counter window repair`.
- Exact file-set check passed: `git show --format= --name-only HEAD` exactly matched `CHANGELOG.md`, `docker/Dockerfile`, `pyproject.toml`, `src/wanctl/__init__.py`.
- Version stamps verified:
  - `pyproject.toml`: `version = "1.45.0"`
  - `src/wanctl/__init__.py`: `__version__ = "1.45.0"`
  - `docker/Dockerfile`: `LABEL version="1.45.0"`
  - `CHANGELOG.md`: exactly one `## v1.45.0` heading.

### Task 211-01-03 — Regression slices

- Alerting + integration slice: `.venv/bin/pytest tests/test_alert_engine.py tests/integration/test_flapping_integration.py -q` → `132 passed in 6.67s`.
- Hot-path slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `673 passed in 39.41s`.
- `git status --short tests/` returned no output; no tests were created or modified.

### Task 211-01-04 — Spectrum Snapshot A

Operator/orchestrator action evidence, verified read-only via SSH:

- Host alias: `cake-shaper`.
- ISO8601: `20260526T184731Z`.
- Tar artifact: `/opt/wanctl-prephase211-20260526T184731Z.tar.gz`.
- Tar size: `1524867` bytes.
- Config artifact: `/etc/wanctl/spectrum.yaml.prephase211-20260526T184731Z`.
- Config size: `12801` bytes.
- `sudo tar -tzf /opt/wanctl-prephase211-20260526T184731Z.tar.gz` succeeded (`tar ok`).

### Task 211-01-05 — Spectrum deploy and health readback

Operator/orchestrator action evidence, verified read-only via SSH:

- Deploy invocation used: `./scripts/deploy.sh spectrum cake-shaper`.
- Deploy completed successfully with non-blocking warnings:
  - missing `docs/PROFILING.md`
  - missing `scripts/wanctl-history`
  - pre-startup validation warning for unknown transport `linux-cake-netlink` while critical checks passed
- Deploy copied code but did not restart the already-running daemon; version initially remained `1.44.0` until service restart.
- Activation action: restarted `wanctl@spectrum.service`.
- Service state: `systemctl is-active wanctl@spectrum.service` → `active`.
- Health endpoint: `http://10.10.110.223:9101/health`.
- Health readback: `status=healthy`, `version=1.45.0`.
- Loopback note: `http://127.0.0.1:9101/health` is not listening in the current production config.
- Observation-window start: approximately `2026-05-26T18:48:06Z`.

## Decisions Made

- Used the production-bound health endpoint `http://10.10.110.223:9101/health` instead of loopback because loopback is not listening in current Spectrum config.
- Treated the post-deploy service restart as required activation because `scripts/deploy.sh` did not restart the already-running daemon.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used production-bound health endpoint for Spectrum readback**
- **Found during:** Task 211-01-05 (post-deploy health verification)
- **Issue:** Plan expected loopback `127.0.0.1:9101`, but current production config binds the health endpoint at `http://10.10.110.223:9101/health`; loopback does not listen.
- **Fix:** Verified `/health` via the bound production address and recorded the endpoint difference for downstream Plan 211-02/211-03 operators.
- **Files modified:** `.planning/phases/211-production-verification-milestone-closure/211-01-SUMMARY.md`
- **Verification:** SSH readback returned `healthy` and `1.45.0`; loopback check returned `URLError`.
- **Committed in:** plan metadata commit.

**2. [Rule 3 - Blocking] Restarted service to activate deployed v1.45 code**
- **Found during:** Task 211-01-05 (post-deploy version readback)
- **Issue:** `scripts/deploy.sh spectrum cake-shaper` completed but did not restart the already-running daemon, so `/health.version` initially remained `1.44.0`.
- **Fix:** Orchestrator restarted `wanctl@spectrum.service` to activate deployed code.
- **Files modified:** `.planning/phases/211-production-verification-milestone-closure/211-01-SUMMARY.md`
- **Verification:** `systemctl is-active wanctl@spectrum.service` returned `active`; `/health.version` returned `1.45.0`.
- **Committed in:** plan metadata commit.

---

**Total deviations:** 2 auto-fixed (2 blocking/verification-environment issues).  
**Impact on plan:** No controller behavior or code scope changed. Deviations were operational activation/readback adjustments needed to prove the deploy landed.

## Issues Encountered

- Pre-existing unrelated `.planning/` edits and pending todo deletions were present before this plan started. They were preserved and not included in the v1.45 four-file closeout commit.
- Deploy emitted non-blocking warnings for missing optional documentation/script files and an unknown `linux-cake-netlink` validation warning; critical checks passed and service health was verified after restart.

## User Setup Required

None for this completed plan. Operator production access was used by the orchestrator for Snapshot A and deploy.

## Known Stubs

None.

## Threat Flags

None beyond the plan's documented production SSH/deploy trust boundaries. This summary introduces no new network endpoints, auth paths, file access patterns, or schema changes.

## Next Phase Readiness

- Ready for Plan 211-02 after the required T+24h minimum from Spectrum activation (`2026-05-26T18:48:06Z` approximate) if the operator proceeds with ATT.
- Spectrum 7d observation window is open; downstream evidence collection should use the v1.45 deployment timestamp and the bound health endpoint note above.

## Self-Check: PASSED

- FOUND: `.planning/phases/211-production-verification-milestone-closure/211-01-SUMMARY.md`
- FOUND: task commit `9cd3b62`
- VERIFIED: Snapshot A artifact sizes and tar readability on `cake-shaper`
- VERIFIED: Spectrum service active and health readback `version=1.45.0`

---
*Phase: 211-production-verification-milestone-closure*  
*Completed: 2026-05-26*
