# CALIB-01 Rerun Launch Notes

timestamp: 2026-05-09T18:30:37Z
soak_ts: 20260509T183037Z
health_url: http://10.10.110.223:9101/health
decision: approved
operator_pre_floor_hit: 0

## Pre-soak Production State

| Field | Value |
|---|---:|
| `/health.version` | `1.43.0` |
| `floor_hit_cycles_total` | `0` |
| `suppressions_completed_window_count` | `3` |
| `window_start_epoch` | `1778351380.7898624` |

The launch used the Spectrum-bound endpoint `http://10.10.110.223:9101/health` because localhost health is not bound on this deployment.

## Launch Commands Executed

- Created local evidence directory: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/`
- Uploaded current `scripts/soak-capture.sh` to `cake-shaper:/tmp/soak-capture.sh`
- Started remote tmux session `wanctl-soak` with:
  - `HEALTH_URL=http://10.10.110.223:9101/health`
  - `SOAK_TS=20260509T183037Z`
- Scheduled T+24h30m kill timer with `systemd-run --user --on-active=24h30m -- tmux kill-session -t wanctl-soak`.

## Start Verification

| Check | Result |
|---|---|
| Remote tmux session | `wanctl-soak: 1 windows (created Sat May  9 13:30:38 2026)` |
| First line count after ~5s | `5 /var/tmp/wanctl-soak-20260509T183037Z/soak-capture.ndjson` |
| Boundary-marker sanity | Rows included `ul_hysteresis_window_start_epoch`, with epoch advancing from `1778351380.7898624` to `1778351440.797051` in the first 5 rows. |

Sample boundary-marker projection output:

```json
{"count":3,"epoch":1778351380.7898624}
{"count":3,"epoch":1778351380.7898624}
{"count":3,"epoch":1778351380.7898624}
{"count":12,"epoch":1778351440.797051}
{"count":12,"epoch":1778351440.797051}
```

## Next Step

Task 2 should run after the 24h soak window completes: pull `/var/tmp/wanctl-soak-20260509T183037Z/soak-capture.ndjson`, verify `>= 86000` rows, enforce the zero-missing-boundary-marker invariant, regenerate `soak-summary.json`, and collect the four hand-off numerics for Plan 204-08.
