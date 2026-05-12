# Phase 204 — CALIB-04 FAIL-A Branch Rerun Launch Notes

timestamp: 2026-05-12T00:42:08+00:00
soak_ts: 20260512T004208Z
branch_context: FAIL-A continuation after Plan 204-09 just-over result
health_url: http://10.10.110.223:9101/health
production_version: 1.43.0
threshold_at_launch: 175
gate_column_at_launch: by_cause.dwell_hold
statistic_at_launch: p99
headroom_factor_at_launch: 1.5
rounding_policy_at_launch: ceil_to_nearest_25
pre_floor_hit_baseline: 0
remote_capture_path: /var/tmp/wanctl-soak-20260512T004208Z/soak-capture.ndjson
local_evidence_dir: .planning/phases/204-d-14-successor-recalibration-calib/soak/20260512T004208Z
expected_completion_utc: 2026-05-13T00:42:08+00:00
cleanup_timer: run-p2021905-i10410131.timer

---

## Rationale

Plan 204-09 produced a corrected-boundary CALIB-04 FAIL-A just-over verdict:

- `primary_gate_delta = 0` (primary gate passed)
- `secondary_gate_value = 151.0`
- prior `secondary_gate_threshold = 150`
- miss amount = `1.0` (`0.67%` over threshold)

The operator selected Branch A and approved a new CALIB-02 threshold of `175`, the next `ceil_to_nearest_25` threshold above observed `151.0`, while preserving `statistic=p99`, `headroom_factor=1.5`, `rounding_policy=ceil_to_nearest_25`, and `gate_column=by_cause.dwell_hold`.

## Preflight

| Check | Result |
|---|---|
| `/health.version` | `1.43.0` |
| Threshold JSON | `threshold=175`, `statistic=p99`, `headroom_factor=1.5`, `rounding_policy=ceil_to_nearest_25`, `gate_column=by_cause.dwell_hold` |
| Pre-soak floor-hit baseline | `PRE_FH=0` |
| Existing `wanctl-soak` tmux session | none |
| Capture script boundary marker | `scripts/soak-capture.sh:55` projects `ul_hysteresis_window_start_epoch` |

## Launch Evidence

Commands executed by the executor:

```bash
scp scripts/soak-capture.sh cake-shaper:/tmp/soak-capture.sh
ssh cake-shaper "chmod +x /tmp/soak-capture.sh"
ssh cake-shaper "tmux new-session -d -s wanctl-soak \"HEALTH_URL=http://10.10.110.223:9101/health bash /tmp/soak-capture.sh 20260512T004208Z 2>&1 | tee /tmp/soak-capture.log\""
ssh cake-shaper "systemd-run --user --on-active=24h30m -- tmux kill-session -t wanctl-soak"
```

Launch verification:

```text
tmux_status: wanctl-soak: 1 windows (created Mon May 11 19:42:08 2026)
initial_line_count: 5 /var/tmp/wanctl-soak-20260512T004208Z/soak-capture.ndjson
timer_output: Running timer as unit: run-p2021905-i10410131.timer; Will run service as unit: run-p2021905-i10410131.service
```

Boundary-marker sanity check from first five rows:

```json
{"count":10,"epoch":1778546483.4558673}
{"count":10,"epoch":1778546483.4558673}
{"count":10,"epoch":1778546483.4558673}
{"count":10,"epoch":1778546483.4558673}
{"count":10,"epoch":1778546483.4558673}
```

## Post-24h Resume Instructions

Do not fabricate post-soak evidence. After the soak window completes, resume with:

1. Confirm capture completion and line count:
   `ssh cake-shaper "wc -l /var/tmp/wanctl-soak-20260512T004208Z/soak-capture.ndjson"`
2. Pull capture to:
   `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260512T004208Z/soak-capture.ndjson`
3. Validate boundary-marker invariant: zero rows with completed-window count and missing `ul_hysteresis_window_start_epoch`.
4. Run `scripts/soak_summary_aggregate.py`; it must load `scripts/calib_02_threshold.json::threshold == 175`.
5. Add `primary_gate` using `PRE_FH=0` and the post-soak floor-hit counter.
6. Evaluate the dual gate and overwrite `204-05-CALIB-04-SOAK-VERDICT.md` only from actual post-soak evidence.
