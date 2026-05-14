# CALIB-04 Rerun Launch Notes

timestamp: 2026-05-10T20:36:42Z
soak_ts: 20260510T203642Z
plan: 204-09
health_url: http://10.10.110.223:9101/health
production_version: 1.43.0
pre_floor_hit_cycles_total: 0

---

## Purpose

Launch the corrected-boundary CALIB-04 rerun verification soak required by
`204-VERIFICATION.md` gaps[2], using the current capture script and the
Branch B CALIB-02 threshold from Plan 204-08.

## CALIB-02 Constants at Launch

Read from `scripts/calib_02_threshold.json` immediately before launch:

| Field | Value |
|-------|-------|
| statistic | `p99` |
| threshold | `150` |
| headroom_factor | `1.5` |
| gate_column | `by_cause.dwell_hold` |
| calib_01_distribution_reference | `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-summary.json` |

## Preflight

- Production `/health.version` via `http://10.10.110.223:9101/health`: `1.43.0`
- Pre-soak floor-hit baseline: `PRE_FH=0`
- `scripts/soak-capture.sh` contains `ul_hysteresis_window_start_epoch`
- No pre-existing remote `wanctl-soak` tmux session was present before launch

## Launch

Remote launch command used the approved health URL rather than localhost:

```bash
ssh cake-shaper "tmux new-session -d -s wanctl-soak \"HEALTH_URL=http://10.10.110.223:9101/health bash /tmp/soak-capture.sh 20260510T203642Z 2>&1 | tee /tmp/soak-capture.log\""
```

## Startup Evidence

- tmux status: `wanctl-soak: 1 windows (created Sun May 10 15:36:42 2026)`
- initial remote line count after ~5s: `5 /var/tmp/wanctl-soak-20260510T203642Z/soak-capture.ndjson`
- cleanup timer: `run-p763570-i9151805.timer` / `run-p763570-i9151805.service` scheduled via `systemd-run --user --on-active=24h30m -- tmux kill-session -t wanctl-soak`

First-row boundary-marker sanity check:

```json
{"count":29,"epoch":1778445383.5211635}
{"count":29,"epoch":1778445383.5211635}
{"count":29,"epoch":1778445383.5211635}
{"count":29,"epoch":1778445383.5211635}
{"count":29,"epoch":1778445383.5211635}
```

## Resume Instructions

After at least 24h wall-clock completion, resume Task 2 with:

- `CALIB_04B_TS=20260510T203642Z`
- `PRE_FH=0`
- remote capture path: `/var/tmp/wanctl-soak-20260510T203642Z/soak-capture.ndjson`
- local soak directory: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/`
- threshold at launch: `150`
- gate column at launch: `by_cause.dwell_hold`
