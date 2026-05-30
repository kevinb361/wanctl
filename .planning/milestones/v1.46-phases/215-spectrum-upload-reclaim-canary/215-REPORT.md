# Phase 215 Spectrum Upload Reclaim Canary Report

## Verdict

**Outcome: bounded VOID exhausted; targeted rollback completed.**

The approved single-knob canary was executed exactly inside the boundary: `continuous_monitoring.upload.ceiling_mbps` was changed from `18` to `20`, deployed to `cake-shaper`, `wanctl@spectrum.service` was restarted, and ceiling=20 was proven via config-snapshot DB row plus CAKE init log containing `20000kbit`. Leg B was captured three times, but the gate returned `void` each time due to `collapsed_measurement_window` (`signal_outlier_rate_p90` on the final attempt: 0.533). Per REVIEW-3/D-09 safe default, production was restored via a targeted single-key ceiling restore to 18, deployed, restarted, DB-proven as 18, and canary-check passed.

## RECLAIM Closeout

### RECLAIM-01 — Operating points evaluated

- Starting Spectrum upload knobs: floor 8 / setpoint 12 / ceiling 18 / step_up 5.
- Leg A at ceiling 18: p95 `45.9` ms, p99 `56.3` ms, upload median `13.743` Mbps.
- Final Leg B attempt at ceiling 20: p95 `45.6` ms, p99 `57.6` ms, upload median `15.299` Mbps.
- Observed upload median delta on final attempt: `1.556` Mbps, but the measurement window was VOID, so this is non-decisive evidence only.

### RECLAIM-02 — Single-knob + rollback discipline

- Pre/post YAML semantic delta before deploy was exactly one leaf: `continuous_monitoring.upload.ceiling_mbps: 18 -> 20`.
- `src/wanctl/` worktree was clean before deploy.
- Deploy used `scripts/deploy.sh spectrum cake-shaper`, followed by mandatory `systemctl restart wanctl@spectrum.service`.
- Rollback used a targeted YAML edit restoring only `continuous_monitoring.upload.ceiling_mbps: 20 -> 18`; no `git checkout configs/spectrum.yaml` rollback was used.
- Rollback proof: `evidence/rollback-ceiling18/db-row.redacted.txt` reads `18`; `evidence/rollback-ceiling18/canary-check.redacted.txt` was captured after restart.

### RECLAIM-03 — Keep/rollback decision

- Gate rc was captured under the set+e pattern: rc `2`.
- Parsed verdict from `evidence/verdict.json`: `void` / `collapsed_measurement_window`.
- Derived bounds from leg A: p95 ≤ `50.49` ms, p99 ≤ `61.93` ms, upload median ≥ `15.24262903532971` Mbps.
- Final candidate values: p95 `45.6` ms, p99 `57.6` ms, upload median `15.29909187886127` Mbps.
- Because bounded VOID was exhausted, the canary was **not kept**. Production is back at ceiling 18.

## Evidence Index

- Leg A: `evidence/leg-a-ceiling18/`
- Ceiling 20 deploy proof: `evidence/leg-b-ceiling20/deploy-proof/`
- Leg B attempts: `evidence/leg-b-ceiling20/RUN-*`
- Gate verdict: `evidence/verdict.json`
- Gate rc: `evidence/gate-rc.txt`
- Rollback proof: `evidence/rollback-ceiling18/`
- Optional non-gating libreqos corroboration: `evidence/libreqos-corroboration.redacted.txt` (rc in sibling `.rc`)

## Notes

- `scripts/libreqos-cli.mjs` was run only as non-gating corroboration per D-11.
- Gate script remote-yaml preflight initially failed due to a shell quoting bug in its SSH Python snippet; the script was fixed and `bash -n` passed before scoring.
