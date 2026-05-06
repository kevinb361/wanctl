# Phase 201 — Canary Verdict (VALN-06 Primary Gate)

**Captured:** 2026-05-04 23:30 UTC  
**Capture path:** `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/`  
**Canonical verdict:** `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json`

## Rollback Artifacts

- Rollback timestamp: `20260504T231220Z`
- Binary archive: `/opt/wanctl-prephase201-20260504T231220Z.tar.gz`
- YAML snapshot: `/etc/wanctl/spectrum.yaml.prephase201-20260504T231220Z`

## Pre-deploy Reconciliation

- Predeploy gate first run: **BLOCK** on rejected v1.41 upload threshold keys in `continuous_monitoring.upload`:
  - `target_bloat_ms`
  - `warn_bloat_ms`
- YAML reconciliation applied by copying repo `configs/spectrum.yaml` to `/etc/wanctl/spectrum.yaml` on `cake-shaper` with ownership/mode `root:wanctl 640`.
- Predeploy gate second run: **PASS**.

## Deploy

- Deploy command: `REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper`
- Restart command: `sudo systemctl restart wanctl@spectrum.service`
- Post-deploy `/health.version`: `1.42.0`
- `/health.wans[0].upload.docsis_mode_active`: `true`
- `/health.wans[0].upload.setpoint_mbps`: `12.0`
- `/health.wans[0].upload.floor_hit_cycles_total`: `0` at initial post-deploy confirmation

## Canary

- Canary env used:
  - `PHASE200_OUT_DIR=.planning/phases/201-docsis-aware-ul-congestion-control`
  - `PHASE200_SPECTRUM_HEALTH_URL=http://10.10.110.223:9101/health`
  - `PHASE200_IPERF_TARGET=104.200.21.31`
  - `PHASE200_IPERF_LOCAL_BIND=10.10.110.226`
  - `PHASE200_UL_FLOOR_MBPS=8`
  - `PHASE200_UL_CEILING_MBPS=18`
  - `PHASE200_REMOTE_YAML_SSH=cake-shaper:/etc/wanctl/spectrum.yaml`
  - `PHASE201_DOCSIS_MODE=true`
  - `PHASE201_SETPOINT_MBPS=12`
  - `PHASE201_LOCAL_YAML_OVERRIDE` unset
- Pre-idle baseline RTT p50: `22.88 ms`
- Loaded window duration: `1022 s`
- `floor_hit_cycles_total` at loaded-window start: `0`
- `floor_hit_cycles_total` at loaded-window end: `1453`
- **`floor_hit_cycles_total` delta (PRIMARY VERDICT): `1453` — FAIL; VALN-06 requires `0`.**
- `ul_floor_hits_during_load` (1 Hz secondary cross-check): `84`
- Post-idle baseline RTT p50: `22.87 ms`
- Verdict: **FAIL**
- `verdict.json` reason: `ul_floor_hits_during_load_84_counter_delta_1453`

## Decision

- [ ] PASS -> proceed to Plan 201-12 (24h soak)
- [x] FAIL with reason `ul_floor_hits_during_load_84_counter_delta_1453` — both gates report floor hits; this is a clean control-model/canary failure at `setpoint_mbps=12`.
- [ ] ABORT -> environment remediation/re-run

Required action for this outcome was rollback. Rollback was executed and verified. Plan 201-12 must **not** proceed from this failed canary without an explicit operator decision creating either a setpoint-10 reattempt path or gap-closure planning.

A5 fallback availability: re-canary at `setpoint_mbps=10` is allowed as a future operator decision because both gates failed in the same control-model mode. It was **not** started during this execution.

## Rollback

Executed after FAIL per D-10 and REVIEWS HIGH-7:

- Restored `/opt/wanctl` from `/opt/wanctl-prephase201-20260504T231220Z.tar.gz`.
- Restored `/etc/wanctl/spectrum.yaml` from `/etc/wanctl/spectrum.yaml.prephase201-20260504T231220Z`.
- Restarted `wanctl@spectrum.service`.
- Post-rollback service state: active.
- Post-rollback `/health.status`: `healthy`.
- Post-rollback `/health.version`: `1.39.0`.

## Rollback Verification

REVIEWS HIGH-7 YAML restore checks after rollback:

| YAML key | Count after rollback | Expected |
|---|---:|---:|
| `docsis_mode:` | 0 | 0 |
| `setpoint_mbps:` | 0 | 0 |
| `integral_window_seconds:` | 0 | 0 |
| `integral_threshold_ms_s:` | 0 | 0 |
| `cake_backlog_low_threshold_bytes:` | 0 | 0 |
| `cake_delay_delta_low_threshold_us:` | 0 | 0 |

Rollback is complete. Production is back on pre-Phase-201 binary/config state for `wanctl@spectrum.service`.
