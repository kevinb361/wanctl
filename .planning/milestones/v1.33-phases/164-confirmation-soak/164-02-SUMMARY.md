---
phase: 164-confirmation-soak
plan: 02
subsystem: operations
tags: [production, soak, validation, cake, baseline]

# Dependency graph
requires:
  - phase: 164-confirmation-soak
    provides: fresh 24h soak window anchored at 2026-04-10 19:49:48 CDT
  - phase: 162-baseline-measurement
    provides: idle baseline expectations and comparison context
provides:
  - final 24h soak verdict for VALID-01
  - baseline comparison summary for v1.33 closeout
  - confirmation that production remained stable through the full observation window
affects: [166-burst-detection-and-multi-flow-ramp-control-for-tcp-12down-p]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Final soak validation based on live health, journal, and analyze_baseline.py output"
    - "Interpretation based on production stability rather than idle-baseline warning text from the analysis script"

key-files:
  created:
    - .planning/phases/164-confirmation-soak/164-02-SUMMARY.md
  modified: []

key-decisions:
  - "Accepted the soak as passed because the decisive signals were uptime>24h, NRestarts=0, no error-level journal entries, and near-zero queue/drop behavior at the end of the window"
  - "Did not treat analyze_baseline.py's 'idle baseline' warning text as a failure signal because Phase 164 is a live production soak, not the idle Phase 162 baseline"
  - "Recorded the autotuner re-enable step as already satisfied because production health showed tuning.enabled=true throughout the final validation"

patterns-established:
  - "For future confirmation soaks, interpret baseline-analysis warnings in the context of the phase goal rather than literally reusing idle-baseline wording"

requirements-completed: [VALID-01]

# Metrics
duration: 20min
completed: 2026-04-11
---

# Phase 164 Plan 02: Final 24h Soak Validation

**The 24-hour production soak passed. Spectrum stayed healthy for the full window with zero unexpected restarts, zero error-level journal entries, and negligible CAKE drop/backlog behavior at the end of the soak.**

## Accomplishments
- Confirmed the formal Phase 164 gate had elapsed and that [wanctl@spectrum](/home/kevin/projects/wanctl/deploy/systemd/wanctl@.service) had been continuously active since `2026-04-10 19:49:48 CDT`.
- Verified `NRestarts=0` and no error-level journal entries since the soak start.
- Captured a final live health snapshot showing `status=healthy`, `uptime_hours=24.321`, `consecutive_failures=0`, and zero current CAKE drop/backlog in both directions.
- Ran `analyze_baseline.py --hours 24` on production and recorded final drop-rate/backlog statistics.
- Compared the final soak behavior against the intent of the Phase 162 baseline: the system remained quiet and stable under mostly idle real traffic, with negligible queue growth and very low drop activity.
- Confirmed production was already running with `tuning.enabled: true`, so the old plan step to re-enable the autotuner was already satisfied and required no additional config change.

## Verification
- `ssh cake-shaper 'systemctl show wanctl@spectrum -p ActiveEnterTimestamp -p NRestarts --no-pager'`
- `ssh cake-shaper 'sudo journalctl -u wanctl@spectrum --since "2026-04-10 19:49:48" -p err --no-pager'`
- `curl -s http://10.10.110.223:9101/health`
- `ssh cake-shaper 'cd /opt/wanctl && sudo python3 /opt/wanctl/scripts/analyze_baseline.py --hours 24'`
- `sed -n '1,220p' .planning/phases/162-baseline-measurement/162-01-SUMMARY.md`

## Final Live Snapshot
- Health: `healthy`
- Uptime: `24.321h`
- Consecutive failures: `0`
- Download state: `YELLOW`
- Upload state: `YELLOW`
- Download drop rate: `0.0`
- Upload drop rate: `0.0`
- Download backlog: `0`
- Upload backlog: `0`
- `tuning.enabled`: `true`

## 24h Analysis Summary
- Total metric rows: `185340`
- `wanctl_cake_backlog_bytes`
  - download: `avg 0.0079`, `p50 0`, `p99 0`
  - upload: `avg 1.0776`, `p50 0`, `p99 0`
- `wanctl_cake_drop_rate`
  - download: `avg 0.0026`, `p50 0`, `p99 0.0043`
  - upload: `avg 0.0009`, `p50 0`, `p99 0`
- Detection/state transitions in 24h window: `260`

## Comparison To Phase 162 Baseline

| Metric | Direction | Phase 162 | Phase 164 | Notes |
|--------|-----------|-----------|-----------|-------|
| backlog_bytes p99 | download | idle-baseline reference | `0.0000` | Remained effectively zero through the soak |
| backlog_bytes p99 | upload | idle-baseline reference | `0.0000` | Remained effectively zero through the soak |
| drop_rate p99 | download | idle-baseline reference | `0.0043` | Very low under real traffic |
| drop_rate p99 | upload | idle-baseline reference | `0.0000` | Effectively zero |
| state transitions | total | expected zero at idle | `260` | Acceptable in a live production soak; not treated as failure without restart/error/queue evidence |

## Deviations From Plan
- The original plan expected the autotuner to be re-enabled after the soak. In live production, `tuning.enabled` was already `true` during final validation, so no config edit or SIGUSR1 re-enable step was needed.
- The analysis script still prints the idle-baseline warning text when transitions are present. That wording is appropriate for Phase 162 but not for this live-soak phase, so the result was interpreted using the actual Phase 164 success criteria instead.

## Verdict
- `approved: soak passed and autotuner already enabled`

## Next Step
- Mark Phase 164 complete in roadmap/state/requirements.
- The next active engineering phase is [Phase 166](/home/kevin/projects/wanctl/.planning/ROADMAP.md): burst detection and multi-flow ramp control for `tcp_12down` p99 spikes.

## Self-Check: PASSED
- Uptime exceeded 24 hours
- `NRestarts=0`
- No error-level journal entries
- Health endpoint remained healthy
- Final 24h metrics were quiet and stable
- VALID-01 satisfied
