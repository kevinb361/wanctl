---
phase: 201-docsis-aware-ul-congestion-control
plan: 15
subsystem: production-validation
tags: [phase-201, recanary, valn-06, docsis, soak-baseline, two-snapshot-rollback]

requires:
  - phase: 201-13-health-diagnostic-extension
    provides: Upload /health diagnostics and active red-decay knob echoes used by canary proof
  - phase: 201-14-control-model-amendment
    provides: Bounded DOCSIS RED decay, anti-windup, and safe red-decay validators
provides:
  - Passing Phase 201 re-canary verdict with primary_gate_value=0 and ul_floor_hits_during_load=0
  - T+0 soak baseline floor_hit_cycles_total_loaded_window_end=0 for Plan 201-16
  - Two-snapshot rollback evidence proving Snapshot A rollback-clean and Snapshot B post-gate candidate
  - Build identity binding v1.42.1 on __init__, pyproject, Dockerfile, and /health
affects: [201-16-soak-and-closeout, VALN-06, production-deploy, canary-evidence]

tech-stack:
  added: []
  patterns:
    - Two-snapshot rollback strategy for production canary deploys
    - Canary build identity bound to git SHA and all version surfaces
    - T+0 monotonic counter baseline handoff to downstream soak

key-files:
  created:
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-SUMMARY.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122130Z/build-identity.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122513Z/verdict.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122513Z/loaded_capture.ndjson
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122513Z/idle_capture.ndjson
  modified:
    - src/wanctl/__init__.py
    - pyproject.toml
    - docker/Dockerfile
    - CHANGELOG.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md

key-decisions:
  - "Operator selected PASS after the re-canary reported primary_gate_value=0 and ul_floor_hits_during_load=0."
  - "Plan 201-16 is unblocked using floor_hit_cycles_total_loaded_window_end=0 as the T+0 soak baseline."
  - "No rollback was performed on PASS; Snapshot A and Snapshot B remain retained as evidence only."

patterns-established:
  - "Capture rollback-clean Snapshot A before any reconcile and post-gate Snapshot B only for deploy evidence."
  - "Treat /health-surfaced red_decay_step_pct and red_decay_delta_max_pct as active runtime proof, not YAML text alone."

requirements-completed: [VALN-06]

duration: 30min active continuation; ~1h30m end-to-end canary window
completed: 2026-05-05
---

# Phase 201 Plan 15: Re-Canary Summary

**v1.42.1 DOCSIS upload control passed the production saturation re-canary with zero cycle-level floor hits and handed off a T+0 soak baseline of 0.**

## Performance

- **Duration:** ~30 min active continuation; end-to-end Task 3-7 evidence window from 2026-05-05T12:21Z to 2026-05-05T12:50Z plus 1022s loaded canary.
- **Started:** 2026-05-05T12:21:30Z
- **Completed:** 2026-05-05T12:50:49Z
- **Tasks:** 6/8 complete or resolved (Tasks 2 and 5 checkpoints; Tasks 6 and 8 skipped by PASS path)
- **Files modified:** 9 plan-scoped evidence/code/docs files plus this summary

## Accomplishments

- Bumped all version surfaces to `1.42.1` (`src/wanctl/__init__.py`, `pyproject.toml`, `docker/Dockerfile`, `CHANGELOG.md`) to avoid split canary evidence.
- Captured rollback-clean Snapshot A before reconcile and post-gate Snapshot B after successful candidate YAML reconcile, closing codex NEW-HIGH-1.
- Deployed v1.42.1 to `cake-shaper` and verified live `/health` reports DOCSIS mode active, setpoint `12.0`, anti-windup cycles `60`, red decay step `0.02`, and red decay max delta `0.10`.
- Executed the saturation re-canary at original `PHASE201_SETPOINT_MBPS=12`; verdict PASS with `primary_gate_value=0` and `ul_floor_hits_during_load=0`.
- Captured `floor_hit_cycles_total_loaded_window_end=0` as the T+0 baseline required by Plan 201-16.

## Task Commits

Each completed task was committed atomically:

1. **Task 1: Bump version to 1.42.1 in all surfaces** — `311c9a4` (`chore`)
2. **Task 2: Predeploy approval checkpoint** — no commit; operator approved and prerequisite checks passed
3. **Task 3: Snapshot A → predeploy gate → Snapshot B → deploy v1.42.1** — `b48ec24` (`chore`)
4. **Task 4: Execute saturation canary and capture verdict** — `57b0fb7` (`test`)
5. **Task 5: Operator verdict decision** — checkpoint; operator selected `pass`
6. **Task 7: Finalize PASS verdict and T+0 soak baseline** — `6b52e28` (`docs`)

**Skipped by decision path:** Task 6 rollback (FAIL path) and Task 8 abort preservation (ABORT path).

**Plan metadata:** final docs/state commit created after this SUMMARY.

## Files Created/Modified

- `src/wanctl/__init__.py` — Version surface updated to `1.42.1`.
- `pyproject.toml` — Project version updated to `1.42.1`.
- `docker/Dockerfile` — Docker label version updated to `1.42.1`.
- `CHANGELOG.md` — Added 1.42.1 re-canary/gap-closure entry.
- `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md` — Operator-readable two-snapshot timeline, active knob table, canary PASS, and soak T+0 baseline.
- `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122130Z/build-identity.json` — Git SHA and version-surface binding at deploy time.
- `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122513Z/verdict.json` — Canonical PASS verdict with zero primary and secondary floor-hit gates.
- `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122513Z/loaded_capture.ndjson` — Loaded-window health capture with Plan 201-13 rev 3 diagnostics.
- `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122513Z/idle_capture.ndjson` — Idle bookend capture.

## Verification

- `test_health_check.py` passed after the version bump.
- Predeploy gate first run BLOCKed on rejected v1.41 keys, YAML reconcile was applied, and second run PASSed.
- Snapshot A YAML Phase 201 key count: `0`; Snapshot B Phase 201 key count: `5`.
- Post-deploy `/health.version == "1.42.1"` and active control knobs matched expected values via `/health` plus YAML SSH grep.
- Canary verdict: `verdict=pass`, `primary_gate=floor_hit_cycles_total_delta_loaded_window`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`.
- Loaded capture first row contained `max_delay_delta_us`, `red_streak`, `zone_trace`, `anti_windup_cycles`, `anti_windup_triggers`, `headroom_exhausted_streak`, `red_decay_step_pct`, and `red_decay_delta_max_pct`.
- Final PASS-path checks confirmed verdict PASS fields, `Soak T+0 baseline`, and live `/health.version == "1.42.1"`.

## Decisions Made

- Operator selected PASS at Task 5 because both canary gates were zero.
- The soak baseline is the cycle-fidelity counter bookend value from the passing canary: `floor_hit_cycles_total_loaded_window_end=0`.
- Snapshot A remains the only rollback target if a future rollback is required; Snapshot B is deploy evidence only.

## Deviations from Plan

None - PASS path executed as specified. The only branch-dependent deviations were planned skips: Task 6 rollback and Task 8 abort handling did not run because Task 5 selected `pass`.

## Issues Encountered

- Pre-existing unrelated working-tree change remained untouched: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-REVIEWS.md`.
- `build-identity.json` recorded `git_status_clean=false` because of the unrelated pre-existing planning edit; the file documents this explicitly and all version surfaces still bind to `1.42.1`.

## Known Stubs

None. The plan changed production code version surfaces and canary evidence only; no placeholder/TODO/mock UI flow was introduced in plan-scoped files.

## Threat Flags

None. This plan deployed existing production control code and wrote validation evidence; it introduced no new network endpoint, auth path, file access pattern, or schema trust boundary.

## User Setup Required

None - no external service configuration required. Plan 201-16 can proceed against the already deployed v1.42.1 service.

## Next Phase Readiness

Plan 201-16 is unblocked. It should start its 24h soak using:

- Re-canary run ID: `20260505T122513Z`
- T+0 baseline: `floor_hit_cycles_total_loaded_window_end=0`
- Deployed version: `/health.version == "1.42.1"`
- Gate context: zero floor-hit canary PASS at setpoint `12`

## Self-Check: PASSED

- Summary file found at `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-SUMMARY.md`.
- Verdict file found at `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md`.
- Canonical canary verdict found at `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122513Z/verdict.json`.
- Task commits found: `311c9a4`, `b48ec24`, `57b0fb7`, and `6b52e28`.
- Final PASS-path checks confirmed `verdict=pass`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`, and live `/health.version == "1.42.1"`.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-05*
