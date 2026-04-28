# Performance And Profiling

This document is the current reference for wanctl runtime timing, cycle-budget
expectations, and profiling. Historical interval experiments and one-off analysis
reports are archived under [`docs/archive/`](archive/).

## Production Standard

- Autorate control interval: `50ms` (`20Hz`).
- Congestion response target: sub-second under normal operating conditions.
- The autorate interval is controlled by source code, not YAML.
- Steering uses configured sample counts and measurement interval to preserve
  stable wall-clock activation and recovery behavior.

The 50ms interval is the active production standard because it provides fast
congestion detection while preserving controller stability and acceptable router
load in the validated deployment.

## Operational Guardrails

- Do not change polling interval, EWMA timing, thresholds, or recovery counts as
  casual tuning. These are control-path behavior changes.
- Treat sustained cycle-budget overruns as an operational signal before changing
  algorithm behavior.
- Queue limit writes should remain change-only; avoiding redundant router writes
  is part of the flash-wear and cycle-budget safety model.
- Background cleanup, downsampling, and startup maintenance must remain bounded
  so `/health` and watchdog readiness are not delayed.

## Expected Runtime Profile

At 50ms, the controller is intentionally close to the hot path. Typical budget
consumers are:

| Area | Expected behavior |
| --- | --- |
| RTT measurement | Usually the dominant cost; background measurement reduces hot-path blocking. |
| Router/backend writes | Near-zero on most cycles because rates are only applied when changed. |
| State classification | Small CPU cost; should not dominate cycle time. |
| SQLite writes | Deferred through the storage worker and should not block the control loop. |
| Maintenance | Bounded and time-budgeted, especially during startup. |

Investigate if p95/p99 cycle time repeatedly exceeds the 50ms budget, if the
cycle-budget health status degrades, or if watchdog readiness is delayed by
storage work.

## Profiling Workflow

Both daemons support profiling instrumentation. Enable it temporarily, collect a
bounded window, then remove it.

```bash
sudo systemctl edit wanctl@spectrum
```

Use an override that adds `--profile` to the autorate command, restart the
service, and collect journal output for the target window. Revert the override
after collection:

```bash
sudo systemctl revert wanctl@spectrum
sudo systemctl restart wanctl@spectrum
```

Useful checks while profiling:

```bash
journalctl -u wanctl@spectrum --since "10 min ago" | grep "Profiling Report"
journalctl -u wanctl@spectrum -f
```

Archived profiling instructions include older parser commands and historical
baseline expectations; use them for forensics, not as current deployment policy.

## Historical Context

Archived files that fed this summary:

- [`PRODUCTION_INTERVAL.md`](archive/PRODUCTION_INTERVAL.md): original 50ms interval decision record.
- [`PROFILING.md`](archive/PROFILING.md): detailed profiling collection guide.
- [`FASTER_RESPONSE_INTERVAL.md`](archive/FASTER_RESPONSE_INTERVAL.md): earlier 500ms analysis.
- [`INTERVAL_TESTING_250MS.md`](archive/INTERVAL_TESTING_250MS.md): 250ms validation record.
- [`INTERVAL_TESTING_50MS.md`](archive/INTERVAL_TESTING_50MS.md): 50ms validation record.
