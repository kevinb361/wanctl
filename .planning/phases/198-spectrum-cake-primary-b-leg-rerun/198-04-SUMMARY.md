---
phase: 198-spectrum-cake-primary-b-leg-rerun
plan: 04
subsystem: validation
tags: [spectrum, closeout, ab-comparison, safe-05, blocked]

requires:
  - phase: 198-spectrum-cake-primary-b-leg-rerun
    plan: 02
    provides: Phase 197 primary-signal audit and B-leg soak evidence
  - phase: 198-spectrum-cake-primary-b-leg-rerun
    plan: 03
    provides: Three-run throughput verdict for VALN-05a
provides:
  - Blocked Phase 198 closeout with failed throughput preserved
  - Six-delta A/B comparison artifact against Phase 196 rtt-blend evidence
  - SAFE-05 source-tree diff artifact
  - Accurate Phase 196 verification update without false closure
affects: [phase-198, phase-196-closeout, valn-04, valn-05a, safe-05]

tech-stack:
  added: []
  patterns: [blocked-closeout, evidence-json, safe05-diff-json]

key-files:
  created:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/ab-comparison.json
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/safe05-diff.json
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md
  modified:
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md

key-decisions:
  - "Recorded Phase 198 as blocked after operator decision because VALN-05a failed under the locked throughput rule."
  - "Did not mark VALN-04 or VALN-05a closed; Phase 196 now references Phase 198 evidence as failed/blocked rather than closure."

requirements-completed: [SAFE-05]
requirements-blocked: [VALN-04, VALN-05a]

duration: ~10m
completed: 2026-04-28T15:55:00Z
---

# Phase 198 Plan 04: Blocked Evidence Closeout Summary

**Phase 198 closeout artifacts now preserve the failed VALN-05a result, publish the A/B and SAFE-05 evidence, and keep VALN-04/VALN-05a blocked rather than falsely closed.**

## Performance

- **Started:** 2026-04-28T15:45:13Z
- **Completed:** 2026-04-28T15:55:00Z
- **Tasks:** 3/3 complete
- **Regression slice:** 584 tests passed
- **Outcome:** blocked closeout per operator decision

## Accomplishments

- Created `ab-comparison.json` with all six requested deltas, Phase 196 rtt-blend comparator references, copied throughput verdict, and top-level `comparison_verdict: fail`.
- Created `safe05-diff.json` showing zero protected-path diffs across `queue_controller.py`, `cake_signal.py`, `fusion_healer.py`, `wan_controller.py`, and `health_check.py` from Phase 197 ship SHA `068b804` to closeout.
- Authored `198-VERIFICATION.md` with `status: blocked`, explicit gaps for failed throughput and failed A/B comparison, and requirement coverage that keeps VALN-04/VALN-05a blocked.
- Updated `196-VERIFICATION.md` to cite Phase 198 evidence accurately as failed/blocked, not closed.

## Evidence Results

| Artifact | Verdict | Notes |
|---|---|---|
| `ab-comparison.json` | `fail` | All six deltas exist; throughput is `FAIL`; dwell bypass and queue-primary coverage gated deltas fail. |
| `safe05-diff.json` | `pass` | `protected_path_diffs: 0`, `diff_empty: true`. |
| `throughput-verdict.json` | `FAIL` | Medians `450.468331`, `681.802267`, `494.834220`; `medians_above_532: 1`; median-of-medians `494.834220`. |
| `198-VERIFICATION.md` | `blocked` | Operator-selected blocked closeout; no retry and no false requirement closure. |

## Task Commits

1. **Task 1: Build ab-comparison.json** — `6a138ec`
2. **Task 2: SAFE-05 source-tree diff vs Plan 01 baseline** — `e46467c`
3. **Task 3: Author 198-VERIFICATION.md and update 196-VERIFICATION.md** — `3abc52a`

## Verification

- `jq -e '.comparison_verdict == "fail" and .throughput.verdict == "FAIL" and (.deltas | has("rtt_distress_event_counts") and has("burst_trigger_counts") and has("dwell_bypass_responsiveness") and has("fusion_state_transitions") and has("queue_primary_coverage_pct") and has("refractory_fallback_rate"))' ab-comparison.json` — PASS
- `jq -e '.protected_path_diffs == 0 and .diff_empty == true and .verdict == "pass"' safe05-diff.json` — PASS
- `grep -q 'status: blocked' 198-VERIFICATION.md` — PASS
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_197_replay.py -q` — PASS (`584 passed in 39.40s`)

## Decisions Made

- Followed the operator decision to record a blocked closeout after VALN-05a failed; no throughput retry was attempted.
- Treated Phase 198 `ab-comparison.json` as required evidence but not closure because `comparison_verdict` is `fail`.
- Preserved SAFE-05 as satisfied because the protected source-tree diff is clean.

## Deviations from Plan

### Auto-fixed / Operator-Directed Adjustments

**1. [Operator decision] Blocked closeout instead of closure wording**
- **Found during:** Plan start, after Plan 03 throughput verdict failed.
- **Issue:** Original Plan 04 wording expected VALN-04/VALN-05a closure, but the evidence does not support closure.
- **Fix:** Authored `198-VERIFICATION.md` as blocked and updated `196-VERIFICATION.md` to reference Phase 198 as failed/blocked evidence.
- **Files modified:** `198-VERIFICATION.md`, `196-VERIFICATION.md`
- **Commit:** `3abc52a`

## Issues Encountered

- VALN-05a remains failed under the locked rule: only one of three corrected Spectrum-bound medians met 532 Mbps, and median-of-medians was below 532 Mbps.
- `ab-comparison.json` also failed because not all gated operational deltas passed and throughput verdict was `FAIL`.
- Existing untracked `graphify-out/` is unrelated and was left untouched.

## Known Stubs

None.

## Threat Flags

None.

## Next Phase Readiness

Phase 198 is complete as a blocked closeout. Follow-up work is required before VALN-04 or VALN-05a can close.

---
*Phase: 198-spectrum-cake-primary-b-leg-rerun*
*Completed: 2026-04-28T15:55:00Z*

## Self-Check: PASSED

- Found `ab-comparison.json`, `safe05-diff.json`, `198-VERIFICATION.md`, and updated `196-VERIFICATION.md` on disk.
- Found task commits `6a138ec`, `e46467c`, and `3abc52a` in git history.
- Verified no `src/wanctl/` files were modified and SAFE-05 protected diffs are zero.
