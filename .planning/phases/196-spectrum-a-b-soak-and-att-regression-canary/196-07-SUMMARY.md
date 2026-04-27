---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
plan: 07
subsystem: production-validation
tags: [gap-closure, spectrum, cake-primary, soak, comparison]

requires:
  - phase: 196-06
    provides: passed Spectrum rtt-blend A-leg on same deployment token
provides:
  - Spectrum cake-primary B-leg start and finish evidence on the same deployment token
  - Machine-checkable B-leg primary-signal audit with failed verdict
  - Explicit VALN-04/VALN-05 Spectrum blockers preventing overclaim
affects: [phase-196, VALN-04, VALN-05, SAFE-05]

tech-stack:
  added: []
  patterns: [production evidence manifest, timestamped SQLite audit, blocked downstream validation]

key-files:
  created:
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit.json
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/cake-primary-finish-20260427T092154Z-summary.json
  modified:
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/manifest.json
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md

key-decisions:
  - "Spectrum throughput and A/B comparison were not run because the cake-primary B-leg primary-signal audit failed."
  - "VALN-04 and VALN-05 remain blocked; SAFE-05 remains satisfied because no protected controller source changed."

patterns-established:
  - "Failed production validation artifacts are committed and used to block downstream evidence collection rather than overclaiming requirement satisfaction."
  - "B-leg audit treats any non-exact queue-primary arbitration metric sample as a failed audit unless every sample has a timestamped exception explanation."

requirements-completed: []
requirements-addressed: [VALN-04, VALN-05, SAFE-05]

duration: 24h 6m elapsed, ~16m active
completed: 2026-04-27
---

# Phase 196 Plan 07: Spectrum cake-primary B-Leg Evidence Summary

**Spectrum cake-primary 24h B-leg captured on the A-leg deployment, but queue-primary audit failed and blocked throughput/A-B closeout**

## Performance

- **Duration:** 24h 6m elapsed, ~16m active execution
- **Started:** 2026-04-26T09:16:19Z
- **Completed:** 2026-04-27T09:36:00Z
- **Tasks:** 3/3 executed; downstream Tasks 2-3 blocked by failed Task 1 audit as planned
- **Files modified:** 17 planning/evidence files across start/finish captures and verification

## Accomplishments

- Started and finished the Spectrum `cake-primary` B-leg on the same deployment token as the A-leg: `cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`.
- Captured a 24.0244-hour B-leg window from `2026-04-26T09:20:26Z` to `2026-04-27T09:21:54Z` with start and finish health/journal/SQLite evidence.
- Built `primary-signal-audit.json`; it failed because 153 arbitration metric samples were not exactly queue-primary (`1.0`) even though both captured health samples reported `active_primary_signal=queue`.
- Correctly blocked Spectrum throughput and A/B comparison: no `throughput-summary.json` or `ab-comparison.json` was created after the failed B-leg audit.

## Task Commits

Each task outcome was committed atomically:

1. **Task 1 start: Start Spectrum cake-primary B-leg** - `e27e1c5` (docs)
2. **Task 1 finish: Finish B-leg and produce primary-signal audit** - `e8db816` (docs)
3. **Task 2: Capture throughput** - `7c321cc` (docs; blocked, no flent run after failed audit)
4. **Task 3: Write A/B comparison** - `ca2bf16` (docs; blocked, no comparison artifact after failed audit)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/manifest.json` - B-leg start/end manifest with same deployment token, expected queue-primary mode, and capture pointers.
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit.json` - B-leg queue-primary audit with duration, health counters, metric counters, 153 timestamped non-queue metric samples, and `verdict: fail`.
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/cake-primary-start-20260426T092026Z-summary.json` - Start capture summary.
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/cake-primary-finish-20260427T092154Z-summary.json` - Finish capture summary.
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/raw/*` - Raw health, journal, fusion transition, and SQLite metric evidence for start/finish capture.
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md` - Updated with B-leg failed audit, Task 2/3 blockers, and VALN-04/VALN-05 blocked state.

## Decisions Made

- Throughput was not run after the B-leg audit failed, matching the plan's safety gate and avoiding production load that could not satisfy VALN-05.
- A/B comparison was not created because the B-leg audit failed, so VALN-04 remains blocked and no comparison verdict is overclaimed.

## Deviations from Plan

None - plan gates were followed as written. The plan explicitly allowed downstream validation to stop when the B-leg primary-signal audit failed.

## Issues Encountered

- The B-leg audit failed: `metric_non_queue_samples: 153` out of `75646` arbitration metric samples. The failed samples were recorded with timestamps in `primary-signal-audit.json`.
- Git's documentation hook flagged planning evidence containing security-ish words such as `token`; commits proceeded with the hook's documented skip/acknowledgement path because these were phase evidence artifacts, not user-facing docs.

## User Setup Required

None - no external service configuration required for this completed blocked validation plan.

## Known Stubs

None found in files created or modified by this plan.

## Threat Flags

None - this plan added production evidence artifacts only. It did not introduce network endpoints, auth paths, file-access code paths, or schema changes.

## Next Phase Readiness

- Phase 196 remains blocked for VALN-04 and VALN-05 because the Spectrum `cake-primary` B-leg audit failed.
- A follow-up decision is needed before rerunning Spectrum validation or changing the evidence interpretation; no controller thresholds, state machine, or timing behavior were modified.
- ATT canary remains separately blocked by Phase 191 closure.

## Self-Check: PASSED

- Found `196-07-SUMMARY.md`, `soak/cake-primary/manifest.json`, `primary-signal-audit.json`, and the finish capture summary on disk.
- Verified task commits `e27e1c5`, `e8db816`, `7c321cc`, and `ca2bf16` exist in git history.
- Re-ran overall Plan 196-07 failed-audit verification: manifest exists, B-leg audit verdict is `fail`, `duration_hours >= 24`, `metric_non_queue_samples == 153`, and downstream `throughput-summary.json` / `ab-comparison.json` are absent.

---
*Phase: 196-spectrum-a-b-soak-and-att-regression-canary*
*Completed: 2026-04-27*
