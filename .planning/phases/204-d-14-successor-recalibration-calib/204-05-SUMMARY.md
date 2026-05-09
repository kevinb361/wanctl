---
phase: 204-d-14-successor-recalibration-calib
plan: 05
subsystem: soak-harness-calibration
tags: [calib-04, verification-soak, dual-gate, safe-07, production-soak]

requires:
  - phase: 204-04
    provides: CALIB-03 dual-emission watchdog aggregation and CALIB-02 constants loading
provides:
  - CALIB-04 verification soak evidence for 20260508T161146Z
  - Passing primary D-19 floor-hit gate with delta 0
  - Passing D-14 successor completed-window secondary gate at p99 dwell-hold value 68.0 <= threshold 125
  - Operator-accepted line-count proxy deviation record
affects: [204-06-retro-and-safe07-closeout, CALIB-04, SAFE-07]

tech-stack:
  added: []
  patterns:
    - production 24h soak capture via tmux on cake-shaper
    - dual-gate verdict from soak-summary.json
    - explicit quality-deviation artifact for accepted line-count proxy miss

key-files:
  created:
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/t0-baseline.json
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/launch-evidence.json
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-capture.ndjson
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-summary.json
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/quality-deviation.json
    - .planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md
    - .planning/phases/204-d-14-successor-recalibration-calib/204-05-SUMMARY.md
  modified: []

key-decisions:
  - "Accepted the CALIB-04 line-count proxy miss (84079 < 86000) by operator direction because stronger quality checks passed, matching CALIB-01 precedent."
  - "Recorded CALIB-04 as PASS because primary_gate.delta == 0 and secondary_gate_completed_window.value 68.0 <= threshold 125."

requirements-completed: [CALIB-04]

duration: 24h19m wall-clock soak plus active aggregation/verdict time
completed: 2026-05-09
---

# Phase 204 Plan 05: CALIB-04 Verification Soak Summary

**24h Spectrum verification soak passed the recalibrated D-14 successor gate with floor-hit delta 0 and p99 dwell-hold completed-window value 68.0 <= threshold 125.**

## Performance

- **Started:** 2026-05-08T16:11:46+00:00
- **Completed:** 2026-05-09T16:30:59+00:00
- **Duration:** ~24h19m wall-clock including the production soak
- **Tasks:** 3/3 completed
- **Files modified:** 7 plan-scoped files created

## CALIB-04 Run

- **CALIB_04_TS:** `20260508T161146Z`
- **Health endpoint:** `http://10.10.110.223:9101/health`
- **Production version:** `1.43.0`
- **Local soak dir:** `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/`
- **Remote capture:** `cake-shaper:/var/tmp/wanctl-soak-20260508T161146Z/soak-capture.ndjson`
- **NDJSON line count:** `84079`

## Gate Blocks from soak-summary.json

### primary_gate

```json
{
  "name": "floor_hit_cycles_total_delta_soak_window",
  "threshold": 0,
  "t0": 0,
  "t24": 0,
  "delta": 0,
  "verdict": "pass",
  "reason": null
}
```

### secondary_gate_completed_window

```json
{
  "name": "ul_suppressions_completed_window_count_p99",
  "computation": "p99 of per-completed-window suppression counts over the soak window (gate_column=by_cause.dwell_hold). Replaces secondary_gate_legacy at v1.44.",
  "value": 68.0,
  "threshold": 125,
  "statistic": "p99",
  "headroom_factor": 1.5,
  "gate_column": "by_cause.dwell_hold",
  "verdict": "pass"
}
```

### secondary_gate_legacy

```json
{
  "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
  "computation": "Mean of live-counter snapshots within each 60s window, then mean across windows. Verbatim port of v1.42 Plan 201-16 jq pipeline. PRESERVED FOR ONE TRANSITION CYCLE - drops in v1.44.",
  "value": 7.568669442712299,
  "threshold": 5.0,
  "verdict": "fail",
  "window_count": 1439
}
```

## Verdict

- **Verdict:** `pass`
- **Branch:** PASS path; no FAIL branch selected.
- **Next action:** Plan 204-06 RETRO + SAFE-07 closeout may proceed.

## Task Commits

1. **Task 1: Launch CALIB-04 production soak** — `9cf26f9`
2. **Task 2: Pull capture, aggregate, and evaluate dual gate** — `0c0c795`
3. **Task 3: Write CALIB-04 soak verdict** — `d366471`

## Files Created/Modified

- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/t0-baseline.json` — pre-soak D-19 floor-hit baseline (`0`).
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/launch-evidence.json` — remote tmux launch and cleanup timer evidence.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-capture.ndjson` — completed 24h production capture.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-summary.json` — aggregator output with primary and secondary gate blocks.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/quality-deviation.json` — accepted line-count proxy deviation record.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md` — operator-readable PASS verdict.

## Decisions Made

- Accepted the `84079 < 86000` line-count proxy miss per operator direction because the full wall-clock and stronger evidence-quality checks passed.
- Treated `secondary_gate_legacy.verdict == "fail"` as informational only, per CALIB-03/04 contract; actual secondary pass criterion is `secondary_gate_completed_window.verdict == "pass"`.

## Deviations from Plan

### Auto-fixed Issues

None.

### Operator-Accepted Deviations

**1. [Accepted evidence-quality deviation] CALIB-04 line-count proxy miss**
- **Found during:** Task 2
- **Issue:** The completed capture had `84079` lines, below the plan's strict `>= 86000` proxy.
- **Operator decision:** Proceed with aggregation/evaluation; do not rerun or extend.
- **Rationale:** Same as CALIB-01: stronger evidence-quality checks passed — full 24h wall-clock window, zero parse errors, 1441 minute buckets, 1361 completed-window value changes, floor-hit delta 0, and service healthy on v1.43.0.
- **Files modified:** `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/quality-deviation.json`, `204-05-CALIB-04-SOAK-VERDICT.md`, this summary.
- **Committed in:** `0c0c795`, `d366471`

## Auth Gates

None.

## Known Stubs

None found in created/modified plan files.

## Threat Flags

None. This plan consumed the already-modeled production soak capture and verdict trust boundaries; no new endpoint, auth path, schema trust boundary, or controller source surface was introduced.

## Verification

- Remote capture verified before copy: `count=84079`, `parse_errors=0`, first `2026-05-08T16:11:47+00:00`, last `2026-05-09T16:11:46+00:00`, `minute_buckets=1441`, `completed_window_value_changes=1361`.
- Current health check at evaluation: `version=1.43.0`, post floor-hit counter `0`.
- Aggregator produced `secondary_gate_legacy` and `secondary_gate_completed_window`.
- Primary gate was added with `t0=0`, `t24=0`, `delta=0`, `verdict=pass`.
- Dual-gate jq passed: `primary_gate.verdict == "pass" and primary_gate.delta == 0 and secondary_gate_completed_window.verdict == "pass"`.
- Verdict verification passed: verdict file exists and contains `verdict: pass`.
- `bash scripts/check-safe07-source-diff.sh` → `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`.
- Hot-path regression slice → `667 passed`.

## Next Phase Readiness

Plan 204-06 is unblocked. CALIB-04 is satisfied; closeout should write the RETRO threshold-basis hygiene lesson and run the SAFE-07 milestone closeout checklist.

## Self-Check: PASSED

- Verified created files exist: `t0-baseline.json`, `launch-evidence.json`, `soak-capture.ndjson`, `soak-summary.json`, `quality-deviation.json`, `204-05-CALIB-04-SOAK-VERDICT.md`, and this summary.
- Verified task commits exist: `9cf26f9`, `0c0c795`, `d366471`.
- Verified dual-gate PASS and SAFE-07/hot-path checks are recorded above.
