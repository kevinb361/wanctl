# Phase 164 Observation Runbook

Use this runbook for the T+1h, T+6h, T+12h, and T+24h Phase 164 spot checks and for the final `164-02` pass. The goal is to make the production observation flow mechanical and repeatable.

## Fixed Context

- Soak phase: `164-confirmation-soak`
- Soak host: `cake-shaper`
- Service under observation: `wanctl@spectrum`
- Soak start: `2026-04-10 19:49:48 CDT`
- Formal completion gate: `2026-04-11 19:49:48 CDT`

## Checkpoint Schedule

- `T+1h`: `2026-04-10 20:49:48 CDT`
- `T+6h`: `2026-04-11 01:49:48 CDT`
- `T+12h`: `2026-04-11 07:49:48 CDT`
- `T+24h`: `2026-04-11 19:49:48 CDT`

## Quick Spot-Check Procedure

Run these commands from the repo root on the dev machine.

### 1. Health snapshot

```bash
curl -s http://10.10.110.223:9101/health | python3 -m json.tool
```

Capture at minimum:
- `status`
- `uptime_seconds`
- `consecutive_failures`
- `download.state`
- `cake_signal.download.drop_rate`
- `cake_signal.download.backlog_bytes`
- `cake_signal.detection.dl_dwell_bypassed_count`
- `cake_signal.detection.dl_backlog_suppressed_count`
- upload-side equivalents if they look abnormal

### 2. Error-level journal check

```bash
ssh cake-shaper 'sudo journalctl -u wanctl@spectrum --since "2026-04-10 19:49:48" -p err --no-pager'
```

Expected result:
- no entries

### 3. Rolling analysis snapshot

For interim checkpoints, use a 1-hour view:

```bash
ssh cake-shaper 'cd /opt/wanctl && sudo python3 /opt/wanctl/scripts/analyze_baseline.py --hours 1'
```

For the formal final pass, use the full 24-hour view:

```bash
ssh cake-shaper 'cd /opt/wanctl && sudo python3 /opt/wanctl/scripts/analyze_baseline.py --hours 24'
```

Capture at minimum:
- total metric rows
- `wanctl_cake_drop_rate` avg/p50/p99 by direction
- `wanctl_cake_backlog_bytes` avg/p50/p99 by direction
- state transition count

## Interpretation Rules

- Do not treat pre-soak data as valid proof. Only the uninterrupted window beginning at `2026-04-10 19:49:48 CDT` counts for `VALID-01`.
- Phase 162 was idle baseline with detection disabled. Phase 164 is real traffic with detection enabled. Higher transition counts and some nonzero drop rate are not automatic failures.
- What matters is stability:
  - no unexpected restart
  - no error-level CAKE/detection failures
  - no sustained unhealthy state
  - no evidence of pathological false-positive churn

## Final T+24h Procedure

### 1. Confirm the gate is real

```bash
date
curl -s http://10.10.110.223:9101/health | python3 -c "import json,sys; h=json.load(sys.stdin); print(h.get('uptime_seconds', 0)/3600)"
```

Expected:
- local time is at or after `2026-04-11 19:49:48 CDT`
- service uptime is at least 24 hours

### 2. Run the 24h analysis

```bash
ssh cake-shaper 'cd /opt/wanctl && sudo python3 /opt/wanctl/scripts/analyze_baseline.py --hours 24'
```

### 3. Compare against Phase 162 baseline

Read:
- `.planning/phases/162-baseline-measurement/162-01-SUMMARY.md`
- `.planning/phases/164-confirmation-soak/164-01-SUMMARY.md`

Produce a simple table:

| Metric | Direction | Phase 162 | Phase 164 | Delta | Notes |
|--------|-----------|-----------|-----------|-------|-------|
| drop_rate p99 | DL | | | | |
| drop_rate p99 | UL | | | | |
| backlog_bytes p99 | DL | | | | |
| backlog_bytes p99 | UL | | | | |
| state transitions | total | | | | |

### 4. Confirm restart/error stability

```bash
ssh cake-shaper 'systemctl show wanctl@spectrum -p ActiveEnterTimestamp -p NRestarts --no-pager'
ssh cake-shaper 'sudo journalctl -u wanctl@spectrum --since "2026-04-10 19:49:48" -p err --no-pager'
```

Expected:
- `NRestarts=0`
- no error entries

### 5. Optional final RRUL check

Only if you want one final controlled validation pass:

```bash
flent rrul_be -H dallas -l 60 -o /tmp/rrul-soak-validation-run1.png
sleep 30
flent rrul_be -H dallas -l 60 -o /tmp/rrul-soak-validation-run2.png
sleep 30
flent rrul_be -H dallas -l 60 -o /tmp/rrul-soak-validation-run3.png
```

Then summarize recent history:

```bash
ssh cake-shaper 'wanctl-history --last 10m --summary --wan spectrum'
```

### 6. Re-enable autotuner only after pass

```bash
ssh cake-shaper 'sudo sed -i "s/^  enabled: false.*/  enabled: true/" /etc/wanctl/spectrum.yaml'
ssh cake-shaper 'grep -A 2 "^tuning:" /etc/wanctl/spectrum.yaml'
ssh cake-shaper 'sudo kill -USR1 $(pgrep -f "wanctl.*spectrum")'
ssh cake-shaper 'journalctl -u wanctl@spectrum --since "1 min ago" --no-pager | grep TUNING'
```

Then update local git config to match:

```bash
grep -A 2 '^tuning:' configs/spectrum.yaml
```

## Decision Record

At the end of `164-02`, record one of:

- `approved: soak passed and autotuner re-enabled`
- `blocked: restart/error/health regression`
- `blocked: metrics unclear, extend observation`

## Output Artifacts

After the final pass, update:
- `.planning/phases/164-confirmation-soak/164-02-SUMMARY.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/REQUIREMENTS.md`

If the soak passes, Phase 164 can close and the milestone can advance. If it fails, document the failure mode before changing config.
