---
phase: 204-d-14-successor-recalibration-calib
plan: 01
subsystem: deploy
tags: [safe-07, production-deploy, cake-shaper, health, v1.43]

requires:
  - phase: 202
    provides: METRIC-01 completed-window suppression fields in the v1.43 binary
  - phase: 203
    provides: OBSV-05 health fields and SAFE-07 source-diff helper
provides:
  - v1.43.0 binary running on cake-shaper for Spectrum
  - two-snapshot rollback evidence for Deploy 1
  - postdeploy health evidence with METRIC-01 and OBSV-05 fields live
affects: [204-02-calib01-baseline-soak, CALIB-01, SAFE-07]

tech-stack:
  added: []
  patterns:
    - Plan 201-15 two-snapshot production deploy ritual
    - SAFE-07 gate with exact planned version-bump allowance
    - Spectrum-bound health endpoint verification

key-files:
  created:
    - .planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md
    - .planning/phases/204-d-14-successor-recalibration-calib/204-01-postdeploy-health.json
  modified:
    - src/wanctl/__init__.py
    - pyproject.toml
    - docker/Dockerfile
    - scripts/check-safe07-source-diff.sh

key-decisions:
  - "Use 1.43.0 for Deploy 1 version surfaces per Phase 204 research recommendation."
  - "Use the Spectrum-bound health endpoint http://10.10.110.223:9101/health because this deployment does not bind /health to 127.0.0.1."
  - "Allow only the exact planned src/wanctl/__init__.py version literal diff in SAFE-07 while continuing to reject all other src/wanctl changes."

patterns-established:
  - "SAFE-07 deploy-time version bump exception must be exact-path and exact-literal, not a blanket src/wanctl allowance."
  - "Production health checks should use the bound per-WAN endpoint when localhost is not bound."

requirements-completed: [CALIB-01, SAFE-07]

duration: 22min active execution plus checkpoint wait
completed: 2026-05-07
---

# Phase 204 Plan 01: Predeploy Gate and Deploy 1 Summary

**v1.43.0 deployed to cake-shaper with rollback snapshots and live METRIC-01/OBSV-05 `/health` evidence for the Spectrum baseline soak.**

## Performance

- **Duration:** ~22 min active execution plus checkpoint wait
- **Started:** 2026-05-07T00:43:46Z
- **Completed:** 2026-05-07T01:05:00Z
- **Tasks:** 4/4 completed
- **Files modified:** 6 plan-scoped files plus remote cake-shaper snapshots/deploy

## Accomplishments

- Bumped all version surfaces to `1.43.0`: package metadata, module `__version__`, and Docker label.
- Captured rollback-clean Snapshot A and evidence Snapshot B under deploy timestamp `20260507T010313Z`.
- Deployed v1.43.0 to cake-shaper and restarted `wanctl@spectrum.service` successfully.
- Verified Spectrum `/health` reports version `1.43.0` and includes completed-window suppression counters plus `load_rtt_ms` / `baseline_rtt_ms` source fields.
- Wrote deploy verdict and committed full postdeploy health JSON evidence.

## Task Commits

1. **Task 1: Bump version surfaces to 1.43.0** — `ad820f6` (`chore`)
2. **Task 2: Operator pre-deploy approval gate** — no file commit; approval captured in continuation prompt and deploy verdict
3. **Task 3: Execute T0/T1/T2/T3/T4 two-snapshot deploy** — remote production mutation; evidence captured in Task 4 artifact commit
4. **Task 3 deviation fix: SAFE-07 script planned-version allowance** — `89b99be` (`fix`)
5. **Task 4: Post-deploy /health smoke + deploy verification artifact** — `834a420` (`docs`)

## Files Created/Modified

- `src/wanctl/__init__.py` — bumped `__version__` from `1.42.1` to `1.43.0`.
- `pyproject.toml` — bumped project version from `1.42.1` to `1.43.0`.
- `docker/Dockerfile` — bumped container label from `1.42.1` to `1.43.0`.
- `scripts/check-safe07-source-diff.sh` — permits only the exact planned `src/wanctl/__init__.py` version literal diff while rejecting all other `src/wanctl/` changes.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md` — deploy verdict, snapshot paths, deviations, smoke results, rollback commands.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-01-postdeploy-health.json` — full postdeploy Spectrum `/health` JSON from cake-shaper.

## Decisions Made

- Used `1.43.0` rather than `1.43-dev` or `1.42.2`, matching the Phase 204 research recommendation and version-distinguishability lesson from Plan 201-15.
- Used `http://10.10.110.223:9101/health` for Spectrum health checks because read-only inspection showed `/health` is bound on per-WAN addresses, not localhost.
- Re-ran the successful deploy with fresh timestamp `20260507T010313Z` after fixing SAFE-07, leaving the aborted `20260507T005026Z` Snapshot A as discarded failed-attempt evidence.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] SAFE-07 helper rejected the planned version-only diff**
- **Found during:** Task 3 (T1 predeploy gate)
- **Issue:** `scripts/check-safe07-source-diff.sh` still used Phase 203 harness-only semantics and rejected any `src/wanctl/` diff, including the plan-approved `src/wanctl/__init__.py` version bump.
- **Fix:** Patched the helper to allow only the exact `__version__ = "1.42.1"` → `"1.43.0"` diff in `src/wanctl/__init__.py`; all other `src/wanctl/` paths/diffs still fail.
- **Files modified:** `scripts/check-safe07-source-diff.sh`
- **Verification:** `bash scripts/check-safe07-source-diff.sh`; SAFE-05 pin test; hot-path slice (`667 passed`).
- **Committed in:** `89b99be`

**2. [Rule 3 - Blocking] Stale localhost health endpoint check**
- **Found during:** Task 2 predeploy verification
- **Issue:** Plan specified `127.0.0.1:9101`, but this deployment binds health on `10.10.110.223:9101` for Spectrum and `10.10.110.227:9101` for ATT.
- **Fix:** Operator approved proceeding with the bound Spectrum endpoint; all pre/post deploy health checks used `http://10.10.110.223:9101/health`.
- **Files modified:** `204-01-DEPLOY-VERIFICATION.md`, `204-01-postdeploy-health.json`
- **Verification:** Predeploy endpoint returned `1.42.1`; postdeploy endpoint returned `1.43.0` and required fields.
- **Committed in:** `834a420`

**3. [Rule 3 - Blocking] YAML snapshot file required sudo for existence verification**
- **Found during:** Task 3 Snapshot A verification
- **Issue:** Plain `ls` could not read `/etc/wanctl/spectrum.yaml.prephase204-deploy1-*-snapA` because it is mode `0640`.
- **Fix:** Used `sudo ls` for snapshot verification; snapshot creation and rollback commands remained unchanged.
- **Files modified:** `204-01-DEPLOY-VERIFICATION.md`
- **Verification:** `sudo ls` showed Snapshot A and B YAML files and binary archives.
- **Committed in:** `834a420`

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All deviations were required to execute the approved production deploy safely. No control-path behavior, thresholds, timing, or YAML tuning changed.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: production_deploy | `/opt/wanctl` on cake-shaper | Existing production deployment trust boundary exercised via `scripts/deploy.sh`; covered by plan threat model T-204-01-01/T-204-01-02 and Snapshot A rollback. |
| threat_flag: health_endpoint_binding | `204-01-DEPLOY-VERIFICATION.md` | Health verification used bound Spectrum address `10.10.110.223:9101` instead of localhost; no new endpoint introduced, but the documented verification surface changed. |

## Issues Encountered

- The first deploy attempt stopped at SAFE-07 after Snapshot A and rolled back cleanly. Post-rollback service was `active` and Spectrum health version was `1.42.1`.
- `scripts/deploy.sh` printed non-blocking warnings for missing `docs/PROFILING.md`, missing `wanctl-history`, and unknown `linux-cake-netlink` validation transport; deployment verification still passed and service restarted active.

## Known Stubs

None found in created/modified plan files.

## Auth Gates

None.

## Verification

- `bash scripts/check-safe07-source-diff.sh` → `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`
- `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` → `1 passed`
- Hot-path slice → `667 passed`
- `ssh cake-shaper "systemctl is-active wanctl@spectrum.service"` → `active`
- `curl http://10.10.110.223:9101/health` → `.version == "1.43.0"` and required METRIC-01/OBSV-05 fields present

## User Setup Required

None - Deploy 1 is complete. Operator should proceed to Plan 204-02 baseline soak using the Spectrum-bound health endpoint.

## Next Phase Readiness

Plan 204-02 (CALIB-01 baseline soak and distribution) is unblocked. Production Spectrum is running v1.43.0 with completed-window suppression counters and target-edge RTT source fields live in `/health`.

## Self-Check: PASSED

- Verified key files exist: version surfaces, SAFE-07 helper, deploy verdict, postdeploy health JSON, and this summary.
- Verified task commits exist: `ad820f6`, `89b99be`, `834a420`.

---
*Phase: 204-d-14-successor-recalibration-calib*
*Completed: 2026-05-07*
