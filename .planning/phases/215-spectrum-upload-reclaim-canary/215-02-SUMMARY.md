---
phase: 215-spectrum-upload-reclaim-canary
plan: 02
subsystem: production-evidence
tags: [snapshot-a, spectrum, rollback-anchor, redaction, health, sqlite]

requires:
  - phase: 215-spectrum-upload-reclaim-canary
    provides: Plan 01 reclaim gate tooling and evidence scaffold
  - phase: 211-production-verification-milestone-closure
    provides: bound Spectrum health endpoint and deploy/restart rollback precedent
provides:
  - redacted Snapshot A rollback-anchor artifact set for Spectrum ceiling=18
  - targeted single-key revert sequence for `continuous_monitoring.upload.ceiling_mbps`
  - read-only DB query evidence showing the retained config-snapshot row is absent
affects: [phase-215-plan-03, spectrum-upload-reclaim-canary, rollback-evidence]

tech-stack:
  added: []
  patterns: [read-only production evidence capture, redacted committed artifacts, absent-row-as-evidence rollback anchor]

key-files:
  created:
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/MANIFEST.md
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/repo-spectrum.redacted.yaml
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/deployed-spectrum.redacted.yaml
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/state.redacted.json
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/snapshot-a-health.redacted.json
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/db-query.redacted.json
  modified:
    - .planning/phases/215-spectrum-upload-reclaim-canary/215-02-PLAN.md

key-decisions:
  - "Plan 02 acceptance now allows an absent retained `wanctl_config_snapshot` DB row when repo config, deployed config, and bound `/health` evidence establish the pre-mutation rollback anchor."
  - "Snapshot A remained strictly read-only: no deploy, restart, config mutation, production write, or traffic generation."
  - "Rollback instructions use a targeted single-key `ceiling_mbps` restore to 18, not a whole-file worktree checkout."

patterns-established:
  - "Absent production-retention evidence is recorded as evidence/deviation instead of becoming a hard stop when independent read-only anchors are present."
  - "Snapshot evidence commits only `.redacted.yaml` / `.redacted.json` payload files plus a manifest."

requirements-completed: [RECLAIM-01, RECLAIM-02]

duration: 4min
completed: 2026-05-29
---

# Phase 215 Plan 02: Snapshot A Summary

**Read-only Spectrum Snapshot A rollback anchor with redacted repo/deployed/state/health evidence and absent DB-row handling.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-29T14:40:48Z
- **Completed:** 2026-05-29T14:44:10Z
- **Tasks:** 1
- **Files modified:** 8

## Accomplishments

- Captured Snapshot A under `evidence/snapshot-a/20260529T144229Z/` without production mutation.
- Confirmed repo and deployed Spectrum configs both retain `continuous_monitoring.upload.ceiling_mbps: 18`.
- Captured bound `/health` from `http://10.10.110.223:9101/health` with `version=1.45.0`, `uptime_seconds=244463.8`, and `upload_rate_mbps=18.0` in the summary row.
- Ran the exact read-only config-snapshot query; it exited 0 but returned no retained `wanctl_config_snapshot` row, so the absence is recorded as evidence and the rollback anchor is repo config + deployed config + bound `/health`.
- Recorded a targeted revert sequence that restores only the single upload ceiling key to 18, then deploys, restarts `wanctl@spectrum.service`, verifies bound `/health`, re-runs the DB query when present, and runs `scripts/canary-check.sh --ssh cake-shaper`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Capture Snapshot A** - `11d7446` (docs)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `.planning/phases/215-spectrum-upload-reclaim-canary/215-02-PLAN.md` - Revised acceptance/evidence logic for absent retained config-snapshot rows after the decision checkpoint.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/MANIFEST.md` - Snapshot manifest with artifact list, bound endpoint, version/uptime, DB query, absent-row finding, no-mutation attestation, and targeted revert sequence.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/repo-spectrum.redacted.yaml` - Redacted repo Spectrum config, ceiling 18.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/deployed-spectrum.redacted.yaml` - Redacted deployed Spectrum config, ceiling 18.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/state.redacted.json` - Redacted production state file snapshot.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/snapshot-a-health.redacted.json` - Redacted bound `/health` baseline.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/20260529T144229Z/db-query.redacted.json` - Exact read-only DB query result, recording `absent_config_snapshot_row`.

## Decisions Made

- Revised the Plan 02 acceptance path per the checkpoint decision: the retained DB row is useful proof when present, but its absence is not a hard stop when the repo config, deployed config, and bound `/health` evidence all anchor the pre-mutation state.
- Kept the no-mutation boundary intact; only read-only `ssh sudo -n cat`, `sqlite3 -readonly`, and bound-endpoint `curl` were used.
- Preserved REVIEW-4 rollback hygiene by documenting only a targeted single-key restore, explicitly not a whole-file worktree checkout.

## Deviations from Plan

### User-Directed Checkpoint Revision

**1. Revised Snapshot A acceptance for absent config-snapshot row**
- **Found during:** Decision checkpoint before Task 1
- **Issue:** The original plan treated a retained `wanctl_config_snapshot` row proving ceiling 18 as mandatory. User directed that an absent row should be evidence/deviation, not a hard stop.
- **Fix:** Updated `215-02-PLAN.md` and `MANIFEST.md` logic to allow repo config + deployed config + bound `/health` as the rollback anchor when the exact read-only DB query returns no row.
- **Files modified:** `.planning/phases/215-spectrum-upload-reclaim-canary/215-02-PLAN.md`, Snapshot A manifest and DB evidence.
- **Verification:** Exact query recorded in `db-query.redacted.json` with `return_code: 0`, `status: absent_config_snapshot_row`; repo/deployed config ceilings recorded as 18; bound `/health` recorded from `10.10.110.223:9101`.
- **Committed in:** `11d7446`

---

**Total deviations:** 1 user-directed checkpoint revision.
**Impact on plan:** Safer execution: Snapshot A remains read-only and reversible without blocking on retention history that is absent from the production metrics DB.

## Issues Encountered

- The first DB query attempt used incorrect shell quoting and produced a SQLite parse error in the local evidence file. It was immediately corrected by re-running the exact read-only query successfully (`return_code: 0`, no row) and updating `db-query.redacted.json`/`MANIFEST.md` before commit.
- The documentation pre-commit hook prompted for doc review because security-shaped evidence changed. The commit used the hook's documented `SKIP_DOC_CHECK=1` path without `--no-verify`, matching the existing Plan 01 precedent for non-user-facing evidence commits.
- Pre-existing untracked `scripts/libreqos-cli.mjs` remains uncommitted and untouched.

## Known Stubs

None.

## Authentication Gates

None.

## Verification

- `ls .planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/*/snapshot-a-health.redacted.json` — PASS.
- `! grep -RiE 'ROUTER_PASSWORD|DISCORD_WEBHOOK|password:[^#]*[A-Za-z0-9]' .planning/phases/215-spectrum-upload-reclaim-canary/evidence/snapshot-a/` — PASS.
- `git diff --name-only | grep -cE '^(src/wanctl/|configs/)' || true` — PASS (`0`).
- `grep -R "10.10.110.223:9101/health" .../snapshot-a/*/MANIFEST.md` — PASS.
- `grep -R "absent_config_snapshot_row\|upload_ceiling_mbps')" .../snapshot-a/*/{MANIFEST.md,db-query.redacted.json}` — PASS.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03 can proceed to the human-approved mutation path with Snapshot A available. The rollback anchor is valid under the revised acceptance logic: repo config ceiling 18 + deployed config ceiling 18 + bound `/health` baseline, with the absent config-snapshot DB row explicitly recorded.

## Self-Check: PASSED

- Key evidence files exist: manifest, repo/deployed redacted YAML, state redacted JSON, health redacted JSON, DB query redacted JSON.
- Task commit found: `11d7446`.

---
*Phase: 215-spectrum-upload-reclaim-canary*
*Completed: 2026-05-29*
