---
phase: 260-dry-run-observation-rerun-canary-readiness
plan: 03
subsystem: network-operations
tags: [routeros, live-proof, observation, canary-readiness, safe21]
requires:
  - phase: 260-dry-run-observation-rerun-canary-readiness
    provides: Phase 260 observation harness and offline safety tests
provides:
  - live 636-second cake-shaper observation evidence bundle
  - canary-readiness packet superseding Phase 257
affects: [phase-260, canary-readiness, route-management]
tech-stack:
  added: []
  patterns: [operator-gated-live-proof, fail-closed-readiness-packet]
key-files:
  created:
    - .planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-readiness-packet.md
    - .planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-readiness-packet-20260625T175756Z.md
    - .planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-observation-raw.json
    - .planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-observation-transcript.md
  modified: []
key-decisions:
  - "The live observation verdict is not-ready, not a failure of SAFE-21; the packet records one cross-check divergence and requests no active canary."
  - "Netwatch remains owner; no route, Netwatch, qdisc, service restart, config edit, or owner flip occurred during the proof."
patterns-established:
  - "Detached remote execution on cake-shaper with local artifact pullback is reliable for >600s observation windows when Hermes foreground timeout is too low."
requirements-completed: [OBSERVE-01, OBSERVE-02, OBSERVE-03, SAFE-21]
duration: 17min live window plus setup
completed: 2026-06-25
---

# Phase 260 Plan 03: Live Observation Evidence Summary

**Live cake-shaper bounded observation produced a not-ready canary-readiness packet with clean SAFE-21 no-mutation proof and one recorded Netwatch cross-check divergence**

## Performance

- **Duration:** 17 min live window plus setup
- **Started:** 2026-06-25T17:46:50Z
- **Completed:** 2026-06-25T17:57:56Z
- **Tasks:** 2
- **Files modified:** 4 evidence artifacts

## Accomplishments

- Ran the Phase 260 observation harness from `cake-shaper` against deployed `/opt/wanctl` imports and the real `127.0.0.1:9102/health` endpoint.
- Captured 11 live samples across the bounded 636-second observation window.
- Confirmed the two Phase 257 blockers are now resolved: `ownership_inspection.inspector_status=ok` with `match=True`, and REST read-only inventory succeeded with `route=17`, `netwatch=3`, `script=20`.
- Produced the four-artifact evidence bundle in the phase evidence directory and a packet that explicitly supersedes Phase 257.
- Preserved SAFE-21: `MUTATION_TOKEN_HITS: []`, Netwatch remains owner, no route owner flip, no RouterOS/Netwatch/qdisc mutation, and no active canary approval.

## Task Commits

1. **Task 1-2: Live observation + packet finalization** - `b7b938fe` (`docs(260-03): capture live observation evidence packet`)

**Plan metadata:** committed with this summary.

## Files Created/Modified

- `.planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-readiness-packet.md` - Canonical readiness packet with `OBSERVE_VERDICT: not-ready`.
- `.planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-readiness-packet-20260625T175756Z.md` - Timestamped copy from the live run.
- `.planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-observation-raw.json` - Raw 11-sample dump plus cross-check/divergence data.
- `.planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-observation-transcript.md` - Validator tokens, issued commands, and verdict block.

## Decisions Made

- Kept the verdict as `not-ready` because the direct cross-check found `netwatch.route_mutating_active_count` disagreement: `ownership_inspection=4` versus direct RouterOS cross-check `0`.
- Treated the divergence as evidence only. No remediation or route mutation was attempted.

## Deviations from Plan

### Auto-fixed Issues

**1. Long remote run supervision path**
- **Found during:** Task 1 live observation execution
- **Issue:** Hermes background SSH wrappers exited immediately without leaving remote output for the >600s run, while foreground short runs worked.
- **Fix:** Created a remote temporary wrapper on `cake-shaper`, launched it detached with `nohup`, then polled the remote log/artifact directory directly.
- **Files modified:** none in repo for the wrapper; evidence artifacts were generated and pulled back.
- **Verification:** Remote log showed deployed `/opt/wanctl` imports, validator tokens, final verdict block, and four evidence artifacts.
- **Committed in:** `b7b938fe`

---

**Total deviations:** 1 auto-fixed (execution-tool supervision workaround).
**Impact on plan:** No safety boundary changed. The live proof still ran on `cake-shaper`, used only validated read-only commands, and produced the planned evidence bundle.

## Issues Encountered

- Final verdict is intentionally `not-ready`: D-07 cross-check divergence on `netwatch.route_mutating_active_count` (`ownership_inspection=4`, direct RouterOS cross-check `0`). This is a readiness blocker, not a mutation or failed run.

## User Setup Required

None - the live proof was executed and artifacts were captured. No active canary approval is requested.

## Verification

- Remote harness printed `wanctl.__file__=/opt/wanctl/__init__.py` and `route_ownership_inspector.__file__=/opt/wanctl/steering/route_ownership_inspector.py`.
- Remote harness printed `READONLY_COMMANDS_VALIDATED` and `READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED` before live commands.
- Packet grep gate passed: `OBSERVE_VERDICT: not-ready`, supersession statement present, `NETWATCH_REMAINS_OWNER: true` present.
- Raw JSON parse gate passed: `verdict=not-ready`, `sample_count=11`, `divergence_count=1`, `mutation_token_hits=[]`, issued commands exactly `/tool netwatch print detail`, `/system script print detail`, `/ip route print`.

## Next Phase Readiness

Phase 260 has fulfilled OBSERVE-01/02/03 with a safe negative readiness result. The next work should diagnose the Netwatch route-mutating count mismatch before any future active route-management canary request.

---
*Phase: 260-dry-run-observation-rerun-canary-readiness*
*Completed: 2026-06-25*
