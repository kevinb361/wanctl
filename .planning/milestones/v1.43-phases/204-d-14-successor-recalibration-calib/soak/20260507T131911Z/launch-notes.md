# CALIB-01 Baseline Soak Launch Notes

timestamp: 2026-05-07T13:19:11Z
soak_ts: 20260507T131911Z
host: cake-shaper
health_url: http://10.10.110.223:9101/health
remote_capture: /var/tmp/wanctl-soak-20260507T131911Z/soak-capture.ndjson
local_soak_dir: .planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/

## Operator Approval

User response: `approved: launch CALIB-01 24h Spectrum baseline soak now`

## Pre-Soak Health Snapshot

Captured before launching the tmux soak session using the Spectrum-bound endpoint
from Plan 204-01.

```json
{"captured_at":"2026-05-07T13:19:17Z","version":"1.43.0","status":"healthy","floor_hit_cycles_total":0,"suppressions_completed_window_count":10,"suppressions_completed_window_by_cause":{"dwell_hold":10,"backlog_recovery":0,"other":0},"suppressions_lifetime_by_cause":{"dwell_hold":9699,"backlog_recovery":707,"other":0},"load_rtt_ms":21.51,"baseline_rtt_ms":22.01}
```

Pre-soak floor-hit count: `0`.

## Launch Evidence

- Uploaded `scripts/soak-capture.sh` to `cake-shaper:/tmp/soak-capture.sh`.
- Launched tmux session `wanctl-soak` with `HEALTH_URL=http://10.10.110.223:9101/health`.
- Startup tmux verification: `wanctl-soak: 1 windows (created Thu May  7 08:19:29 2026)`.
- Initial remote capture line count after launch: `5 /var/tmp/wanctl-soak-20260507T131911Z/soak-capture.ndjson`.
- Follow-up remote capture line count: `15 /var/tmp/wanctl-soak-20260507T131911Z/soak-capture.ndjson`.

## Stop Timer

Scheduled T+24h30m kill timer on cake-shaper:

```text
run-p1311965-i5506233.timer -> run-p1311965-i5506233.service
Fri 2026-05-08 08:49:40 CDT
```

## Awaiting

Let the capture run for the full 24h baseline window. Task 3 may resume after
the wall-clock run completes and should verify the remote line count is at least
86,000 before copying evidence back and aggregating `soak-summary.json`.
