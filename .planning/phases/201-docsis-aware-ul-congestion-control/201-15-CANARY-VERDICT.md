# Phase 201 Plan 15 — Re-Canary Verdict (VALN-06 Primary Gate)

**Re-canary timestamp:** `20260505T122130Z`  
**Status:** predeploy/deploy complete; canary pending  
**Capture path:** `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122130Z/`

## Build Identity

```json
{
  "git_sha": "311c9a484abbc1fd66e0adb3b8fba1d701b7b02e",
  "git_status_clean": false,
  "version_init_py": "1.42.1",
  "version_pyproject": "1.42.1",
  "version_dockerfile": "1.42.1",
  "build_utc": "2026-05-05T12:21:30+00:00",
  "recanary_ts": "20260505T122130Z"
}
```

`git_status_clean=false` is expected for this continuation because an unrelated pre-existing planning edit (`.planning/phases/200-per-direction-rtt-bloat-thresholds/200-REVIEWS.md`) was present before Task 3 and was left untouched.

## Two-Snapshot Rollback Timeline

| Time | Step | Result |
|---|---|---|
| T0 | Snapshot A rollback-clean captured before any reconcile | `/opt/wanctl-prephase201-recanary-20260505T122130Z-snapA.tar.gz` and `/etc/wanctl/spectrum.yaml.prephase201-recanary-20260505T122130Z-snapA` created |
| T0 verification | Snapshot A Phase 201 key count | `0` — rollback-clean confirmed |
| T1 | Predeploy gate run #1 | `BLOCK` on rejected v1.41 upload keys `target_bloat_ms` and `warn_bloat_ms` |
| T2 | Reconcile YAML | Copied repo `configs/spectrum.yaml` to `cake-shaper:/etc/wanctl/spectrum.yaml` with `root:wanctl` and mode `0640` |
| T2b | Predeploy gate run #2 | `PASS` |
| T3 | Snapshot B post-gate candidate captured | `/opt/wanctl-prephase201-recanary-20260505T122130Z-snapB.tar.gz` and `/etc/wanctl/spectrum.yaml.prephase201-recanary-20260505T122130Z-snapB` created |
| T3 verification | Snapshot B Phase 201 key count | `5` — candidate Phase 201 YAML evidence confirmed |
| T4 | Deploy v1.42.1 binary | `REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper`; service restarted |

**Rollback rule:** on FAIL, restore from Snapshot A only. Snapshot B is deploy evidence and must never be used as the rollback target.

## Predeploy Gate Results

- Run #1: **BLOCK** on rejected v1.41 `continuous_monitoring.upload.target_bloat_ms` and `warn_bloat_ms`.
- Reconcile: repo `configs/spectrum.yaml` installed to `/etc/wanctl/spectrum.yaml`.
- Run #2: **PASS**.

Full Task 3 log: `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122130Z/task3-predeploy-deploy.log`

## Post-Deploy /health Snapshot

```json
{
  "version": "1.42.1",
  "docsis_mode_active": true,
  "setpoint_mbps": 12.0,
  "anti_windup_cycles": 60,
  "anti_windup_triggers": 0,
  "headroom_exhausted_streak": 47,
  "floor_hit_cycles_total": 0,
  "max_delay_delta_us": 117,
  "red_streak": 0,
  "zone_trace_len": 47,
  "red_decay_step_pct": 0.02,
  "red_decay_delta_max_pct": 0.1
}
```

## Active Control Knob Assertion Table

| Knob | Source | Expected | Actual | Pass? |
|------|--------|----------|--------|-------|
| version | /health | 1.42.1 | 1.42.1 | yes |
| version | pyproject.toml | 1.42.1 | 1.42.1 | yes |
| version | docker/Dockerfile LABEL | 1.42.1 | 1.42.1 | yes |
| anti_windup_cycles | /health | 60 | 60 | yes |
| red_decay_step_pct | /health | 0.02 | 0.02 | yes |
| red_decay_delta_max_pct | /health | 0.10 | 0.10 | yes |
| red_decay_step_pct | YAML SSH grep | 0.02 | 0.02 | yes |
| red_decay_delta_max_pct | YAML SSH grep | 0.10 | 0.10 | yes |
| anti_windup_cycles | YAML SSH grep | 60 | 60 | yes |

## Task 3 Verification

- `build-identity.json` exists and all three version surfaces report `1.42.1`.
- Snapshot A and Snapshot B files exist on `cake-shaper`.
- Snapshot A YAML key count is `0` for the Phase 201/rev-4 key set.
- `/health` reports version `1.42.1`, DOCSIS mode active, setpoint `12.0`, anti-windup cycles `60`, red decay step `0.02`, red decay max delta `0.10`, and diagnostic fields with expected numeric/array types.
- Deployed YAML contains exactly the three active rev-4 knobs checked by Plan 201-15.

## Canary Results

Pending Task 4.

## Decision

Pending Task 5 operator verdict decision after canary execution.
