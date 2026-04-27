---
phase: 198-spectrum-cake-primary-b-leg-rerun
plan: 01
subsystem: validation
tags: [spectrum, cake-primary, preflight, safe-05, deployment-proof]

requires:
  - phase: 197-queue-primary-refractory-semantics-split-dl-cake-for-detecti
    provides: Phase 197 refractory-aware arbitration fields and metrics
provides:
  - Phase 197 ship SHA and SAFE-05 protected-file baseline
  - Post-restart Spectrum deployment proof for the Phase 197 runtime
  - Initial Spectrum source-bind egress proof for 10.10.110.226
  - Phase-197-aware capture-script preflight evidence
affects: [phase-198, phase-196-closeout, safe-05, valn-04, valn-05a]

tech-stack:
  added: []
  patterns: [operator-evidence-json, phase196-capture-script-reuse, rsync-deployment-proof]

key-files:
  created:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/preflight.json
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/source-bind-egress-proof.json
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/preflight/preflight-20260427T144331Z-summary.json
  modified:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/safe05-baseline.json

key-decisions:
  - "Accepted rsync deployment proof for /opt/wanctl instead of remote git metadata: Phase 197-only /health field, new metric rows, restart timestamp, and operator-approved deploy/restart commands bind the running process to the Phase 197 ship SHA."
  - "Treated cake-primary mode as proven by remote sudo YAML read plus active_primary_signal=queue because /health exposes the live cake_signal snapshot but not a cake_signal.enabled boolean."

patterns-established:
  - "Preflight proof composes safe05-baseline.json, capture-script output, source-bind egress, and deployment-runtime evidence before any 24h soak begins."

requirements-completed: [SAFE-05]

duration: 3min
completed: 2026-04-27
---

# Phase 198 Plan 01: Preflight + Deployment Proof Summary

**Spectrum cake-primary preflight evidence now proves the Phase 197 runtime is live after restart, 10.10.110.226 exits Charter/Spectrum, and SAFE-05 protected files are pinned before the rerun soak.**

## Performance

- **Duration:** 3 min continuation execution (after production deploy/restart recovery)
- **Started:** 2026-04-27T14:43:14Z
- **Completed:** 2026-04-27T14:46:06Z
- **Tasks:** 3/3 complete (Task 2 was the human/operator checkpoint)
- **Files modified:** 9 evidence files across Task 1 and Task 3

## Accomplishments

- Reused Task 1 SAFE-05 baseline (`f3e94f8`) and verified it still passes the plan predicate.
- Re-ran the Phase 196 capture-script preflight after the approved deploy/restart, producing `preflight-20260427T144331Z-summary.json` and raw health/journal/SQLite evidence.
- Recorded composite `preflight.json` with pass verdict, Phase 197 ship SHA `068b804`, restart timestamp `2026-04-27T14:42:31Z`, `signal_arbitration.refractory_active` presence, and 1166 recent `wanctl_arbitration_refractory_active` rows.
- Captured initial source-bind egress proof showing `10.10.110.226` exits Spectrum/Charter (`70.123.224.169`, `AS11427 Charter Communications Inc`).
- Ran the hot-path regression slice with no source changes: 572 tests passed.

## Task Commits

1. **Task 1: Pin Phase 197 ship SHA + capture SAFE-05 baseline** - `f3e94f8` (docs)
2. **Task 2: Operator confirms env vars + no concurrent Spectrum experiment** - checkpoint approved externally; no commit
3. **Task 3: Capture deployment proof + initial egress probe + composite preflight.json** - `84d14a4` (feat)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/safe05-baseline.json` - Phase 197 ship SHA and protected-file blob baseline from Task 1.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/preflight.json` - Composite pass verdict for deployment proof, cake-primary mode, egress proof, and operator no-concurrency confirmation.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/source-bind-egress-proof.json` - Initial Spectrum egress proof for `10.10.110.226`.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/preflight/preflight-20260427T144331Z-summary.json` - Post-restart capture-script preflight summary.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/preflight/raw/preflight-20260427T144331Z-*` - Raw health, journal, fusion transition, and SQLite metric exports used by the summary.

## Verification

- `jq -e '.phase == 198 and (.phase_197_ship_sha | length) >= 7 and (.protected_files | length) == 5 and .working_tree_diff_empty == true' safe05-baseline.json` — PASS
- `jq -e '.verdict == "pass" and .deployment_proof.sha_match == true and .deployment_proof.health_has_refractory_active_field == true and .deployment_proof.metric_wanctl_arbitration_refractory_active_recent_count > 0 and .source_bind_preflight.egress_ip_matches == true and .operator_no_concurrent_spectrum_experiments == true and (.deployed_commit | length) >= 7 and .source_bind_preflight.source_bind_verified == true' preflight.json` — PASS
- `jq -e '.deployed_commit == .deployment_proof.phase_197_ship_sha' preflight.json` — PASS
- `jq -e '.preflight_probe.egress_ip_matches == true and (.preflight_probe.org | test("Charter|AS11427"))' source-bind-egress-proof.json` — PASS
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — PASS (`572 passed in 40.17s`)

## Decisions Made

- Accepted equivalent deployment proof for `/opt/wanctl` because production uses rsync rather than a remote git checkout. The proof records the Phase 197 ship SHA, operator-approved deploy/restart commands, `ActiveEnterTimestamp`, Phase 197-only health field presence, and recent Phase 197 metric rows.
- Used remote sudo YAML read plus active `queue` arbitration as the cake-primary mode proof because `/health` includes a `cake_signal` data block but not a `cake_signal.enabled` boolean.

## Deviations from Plan

None - plan executed exactly as written with the prompt-approved equivalent deployment proof for rsync-based `/opt/wanctl`.

## Issues Encountered

- Earlier Task 3 attempt was stale-runtime and retained only as historical context. Production deploy/restart recovery completed before this continuation, and the post-restart preflight artifact supersedes the failed stale-runtime attempt.
- Remote `/opt/wanctl` is not a git checkout, so `git rev-parse --short HEAD` returned `UNKNOWN`. This was handled by the explicitly allowed rsync deployment proof path.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Next Phase Readiness

Ready for `198-02`: the soak may begin with `preflight.json` verdict `pass`, post-restart capture-script evidence present, Spectrum source-bind verified, and SAFE-05 baseline pinned.

---
*Phase: 198-spectrum-cake-primary-b-leg-rerun*
*Completed: 2026-04-27*

## Self-Check: PASSED

- Found summary, `preflight.json`, `source-bind-egress-proof.json`, `safe05-baseline.json`, and post-restart capture summary on disk.
- Found Task 1 commit `f3e94f8` and Task 3 commit `84d14a4` in git history.
