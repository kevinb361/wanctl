---
phase: 201-docsis-aware-ul-congestion-control
plan: 16
subsystem: production-validation
tags: [phase-201, soak, valn-06, docsis, d19, d14, closeout, gap-closure]

requires:
  - phase: 201-15-recanary
    provides: Passing v1.42.1 recanary, T+0 floor-hit baseline, and active control-knob evidence
provides:
  - 24h soak evidence copied from cake-shaper for run 20260505T132736Z
  - D-19 primary floor-hit verdict and D-14 secondary suppression watchdog verdict
  - Phase 201 gap-found closeout state pending operator next-action decision
affects: [VALN-06, phase-201-closeout, v1.43-follow-up, production-validation]

tech-stack:
  added: []
  patterns:
    - Uploaded capture script with positional SOAK_TS arg for remote tmux soak capture
    - Timestamp-windowed suppression-rate computation using $rows-bound jq selection
    - Split primary/secondary soak gates with explicit operator-approved D-19 provenance

key-files:
  created:
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/t24-baseline.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson
    - .planning/phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/suppression-stats.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/diagnostic-distribution.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-summary.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SUMMARY.md
  modified:
    - .claude/context.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "The soak verdict is FAIL because D-14 secondary watchdog failed even though the operator-approved D-19 primary floor-hit gate passed."
  - "Phase 201 remains gaps_found pending an operator decision between A5-style controlled reattempt and v1.43+ follow-up."

patterns-established:
  - "Preserve gate disagreement honestly: primary PASS does not override secondary FAIL."
  - "Keep D-19 approval as a pre-soak artifact reference, not a planner-authored verdict claim."

requirements-completed: []
duration: 24h soak + ~1h active closeout
completed: 2026-05-06
---

# Phase 201 Plan 16: Soak and Closeout Summary

**v1.42.1 completed the 24h DOCSIS upload soak with zero floor-hit cycles but failed the preserved D-14 suppression watchdog.**

## Performance

- **Duration:** 24h soak plus ~1h active evidence copy/computation/closeout
- **Started:** 2026-05-05T13:15:37Z (D-19 approval); soak T+0 at 2026-05-05T13:27:36Z
- **Completed:** 2026-05-06T13:40:36Z evidence bookend; closeout committed 2026-05-06
- **Tasks:** 3/3 executed; FAIL verdict routes to operator decision checkpoint
- **Files modified:** 12 files in Task 3 commit plus this summary

## Accomplishments

- Captured T+24 floor-hit and anti-windup counters (`0` / `0`) and copied `84117` NDJSON rows back from `cake-shaper`.
- Computed suppression windows using the `$rows`-bound jq-compatible logic required by codex NEW-HIGH-3.
- Wrote `soak-summary.json` and `201-16-SOAK-VERDICT.md` with explicit D-19 approval provenance.
- Updated `201-VERIFICATION.md`, `REQUIREMENTS.md`, `STATE.md`, `ROADMAP.md`, and `201-CONTEXT.md` for the FAIL path.

## Task Commits

1. **Task 1: D-19 operator approval** — `3fbb0cd` (`docs`)
2. **Task 2: 24h soak start-state evidence** — `4851522` (`test`)
3. **Task 3: Compute soak verdict and update closeout artifacts** — `c0df8d8` (`docs`)

**Plan metadata:** this summary is committed separately after Task 3.

## Files Created/Modified

- `soak/20260505T132736Z/t24-baseline.json` — T+24 floor-hit and anti-windup counter bookend.
- `soak/20260505T132736Z/soak-capture.ndjson` — copied 24h remote capture from cake-shaper.
- `soak/20260505T132736Z/suppression-stats.json` — timestamp-windowed 60s suppression distribution.
- `soak/20260505T132736Z/diagnostic-distribution.json` — RTT integral, CAKE delay, red streak, and headroom diagnostics.
- `soak/20260505T132736Z/soak-summary.json` — canonical gate summary and overall verdict.
- `201-16-SOAK-VERDICT.md` — operator-readable soak verdict.
- `201-VERIFICATION.md`, `REQUIREMENTS.md`, `STATE.md`, `ROADMAP.md`, `201-CONTEXT.md`, `.claude/context.md` — FAIL-path traceability and operator next-action state.

## Soak Verdict

| Gate | Required | Actual | Result |
|---|---:|---:|---|
| D-19 primary floor-hit delta | `0` | `0` | PASS |
| D-14 secondary suppression mean | `<5.0` | `6.466842364880155` | FAIL |

Overall verdict: **FAIL** (`soak_gates_disagreement_primary_pass_secondary_fail`).

Additional metrics:

- Sample coverage ratio: `0.9735842767244641`
- Suppression p95: `21.10169491525424`
- Suppression max: `69.91379310344827`
- Anti-windup trigger delta: `0`
- Anti-windup log count: `0`
- Diagnostic max delay delta max: `161281us`

## Decisions Made

- Preserved the actual plan-defined verdict instead of treating the D-19 primary PASS as sufficient; the D-14 secondary gate remained mandatory and failed.
- Routed Phase 201 to an operator next-action decision rather than marking VALN-06 satisfied.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing remote tmux dependency**
- **Found during:** Task 2 (soak launch)
- **Issue:** Planned tmux launch initially failed on `cake-shaper` because tmux was unavailable.
- **Fix:** Installed tmux on the capture host so the planned on-host detached capture could run.
- **Files modified:** none in repo beyond `soak-start-status.json` evidence.
- **Verification:** `soak-start-status.json` records `/usr/bin/tmux` and the tmux session launch status.
- **Committed in:** `4851522`

**2. [Rule 3 - Blocking] Installed missing remote jq dependency**
- **Found during:** Task 2 (capture script execution)
- **Issue:** Uploaded capture script required jq on `cake-shaper`; initial run failed with `jq: command not found`.
- **Fix:** Installed jq on the capture host.
- **Files modified:** none in repo beyond `soak-start-status.json` evidence.
- **Verification:** `soak-start-status.json` records `/usr/bin/jq`; NDJSON capture contains valid JSON rows.
- **Committed in:** `4851522`

**3. [Rule 1 - Bug] Switched capture URL to reachable health endpoint**
- **Found during:** Task 2 (capture loop startup)
- **Issue:** `http://127.0.0.1:9101/health` was unreachable from cake-shaper while the planned live health endpoint `http://10.10.110.223:9101/health` was reachable.
- **Fix:** Updated the persisted capture script to use the reachable health URL without changing controller behavior.
- **Files modified:** `soak/20260505T132736Z/soak-capture.sh`
- **Verification:** Capture produced `84117` valid rows with `t_wall` and numeric `t_monotonic`.
- **Committed in:** `4851522`

**4. [Rule 1 - Bug] Corrected jq update precedence while preserving $rows-bound logic**
- **Found during:** Task 3 (suppression stats computation)
- **Issue:** The verbatim plan pipeline hit `Cannot index array with string "windows"` in the local jq version after `.windows |= ...` precedence changed the downstream shape.
- **Fix:** Bound the reduced object as `$stats` after filtering null windows, while preserving the critical `$rows[]` inner selection semantics.
- **Files modified:** `suppression-stats.json`, `soak-summary.json`
- **Verification:** `suppression-stats.json` reports `samples_total=84117`, `window_count=1439`, and includes the `$rows`-computed mean used by the verdict.
- **Committed in:** `c0df8d8`

**Total deviations:** 4 auto-fixed (3 blocking/bug fixes in capture/computation).  
**Impact on plan:** All fixes were required to collect or compute the contracted evidence; no controller behavior or production configuration was changed.

## Issues Encountered

- The captured sample count (`84117`) is below the plan's nominal `>=86000` acceptance line, but the monotonic timestamp coverage ratio is `0.9735842767244641`, above the plan-defined `<0.95` warning threshold. The verdict was computed from the captured evidence without threshold massage.
- The preserved secondary gate failed even though the stricter D-19 primary gate passed. This is the key outcome and requires operator routing.

## Known Stubs

None. The plan produced evidence and planning artifacts only; no placeholder or mock runtime surface was introduced.

## Threat Flags

None. This closeout copied validation evidence and updated planning documents. It introduced no new endpoint, auth path, file access pattern, or schema trust boundary in production code.

## User Setup Required

Operator next-action decision required:

1. **A5-style controlled reattempt** — authorize another canary/soak cycle with revised operational parameters.
2. **v1.43+ follow-up** — leave Phase 201 at `gaps_found` and plan a control-model or suppression-watchdog follow-up before any new soak.

## Next Phase Readiness

Phase 201 is not ready to close as satisfied. The evidence is complete enough for a decision checkpoint: primary floor-hit behavior held for 24h, but suppression-rate behavior did not meet D-14.

## Self-Check: PASSED

- Found `201-16-SOAK-VERDICT.md`.
- Found `soak/20260505T132736Z/soak-summary.json` with `verdict=fail`.
- Found `soak/20260505T132736Z/suppression-stats.json` with `$rows`-computed secondary metrics.
- Found Task commits `3fbb0cd`, `4851522`, and `c0df8d8` in git log.
- Verified no plan-scope tracked deletions were introduced by Task 3.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-06*
