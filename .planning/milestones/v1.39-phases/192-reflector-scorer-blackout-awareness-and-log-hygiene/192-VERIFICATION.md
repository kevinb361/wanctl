---
phase: 192
status: in_progress
created_at: 2026-04-24T13:40:00Z
---

# Phase 192 Verification

## Precondition Waiver

Phase 191 remains blocked with `VALN-02 verdict: FAIL`. Phase 192 proceeded
under the explicit operator waiver recorded in `192-PRECONDITION-WAIVER.md`.
The waiver is limited to additive observability/log-hygiene work and guarded
production validation. It does not close Phase 191.

## Deployment

Production code deployment used a clean `git archive` of committed `HEAD`
(`663d46846a22bf8c7ec12465c8dbb831d7079ae5`) for `src/wanctl/` only, then
overlaid the intended uncommitted closeout files:

- `src/wanctl/__init__.py` (`1.39.0`)
- `src/wanctl/wan_controller.py` (`RTTCycleStatus` guard)

That clean tree was rsynced to `cake-shaper:/opt/wanctl/`.

The standard `scripts/deploy.sh` path was intentionally not used because the
local worktree contains unrelated dirty source files. This avoided shipping
unreviewed local edits.

Services restarted:

- `wanctl@spectrum`: `active`
- `wanctl@att`: `active`

Final production health after the `1.39.0` overlay:

- Spectrum `/health`: `version="1.39.0"`, `status="healthy"`, `download.hysteresis.dwell_bypassed_count=0`, `active_primary_signal="queue"`
- ATT `/health`: `version="1.39.0"`, `status="healthy"`, `download.hysteresis.dwell_bypassed_count=0`, `active_primary_signal="queue"`
- `steering.service`: `active`, production-local health `status=healthy`

## Local Regression

- `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q -k "DwellBypassedCount or hysteresis"`: `9 passed, 162 deselected`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`: `513 passed`
- `.venv/bin/pytest tests/ -q`: `4650 passed, 2 deselected`
- `bash -n scripts/phase192-soak-capture.sh`: passed
- Missing-env script behavior: `WANS='' scripts/phase192-soak-capture.sh pre` exited `2` with `ERROR: WANS is required`

## Production Canary

Autorate canary checks passed for both WAN health endpoints after restart.
The repo canary script reported one failure for steering because it checks
`http://127.0.0.1:9102/health` from the dev machine. Direct production-host
verification passed:

- `systemctl is-active steering.service`: `active`
- `curl http://127.0.0.1:9102/health` on `cake-shaper`: `status=healthy`

## Health Field

Both production autorate health endpoints expose the Phase 192 additive field:

- Spectrum `.wans[0].download.hysteresis.dwell_bypassed_count`: `0`
- ATT `.wans[0].download.hysteresis.dwell_bypassed_count`: `0`

Both endpoints also expose `signal_arbitration.active_primary_signal="queue"`
from the already-deployed v1.40 queue-primary work.

## Pre-Soak Capture

Command:

```bash
WANS="spectrum att" \
WANCTL_SPECTRUM_HEALTH_URL="http://10.10.110.223:9101/health" \
WANCTL_ATT_HEALTH_URL="http://10.10.110.227:9101/health" \
WANCTL_SPECTRUM_SSH_HOST="kevin@10.10.110.223" \
WANCTL_ATT_SSH_HOST="kevin@10.10.110.223" \
./scripts/phase192-soak-capture.sh pre
```

Output directory:

`.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/soak/pre`

### Spectrum

```json
{
  "captured_at_iso": "2026-04-24T13:33:45Z",
  "dwell_bypassed_count": 0,
  "burst_trigger_count_dl": 0,
  "burst_trigger_count_ul": 0,
  "fusion_transition_count_24h": 0,
  "protocol_deprio_count_24h": 4069
}
```

### ATT

```json
{
  "captured_at_iso": "2026-04-24T13:33:45Z",
  "dwell_bypassed_count": 0,
  "burst_trigger_count_dl": 0,
  "burst_trigger_count_ul": 0,
  "fusion_transition_count_24h": 0,
  "protocol_deprio_count_24h": 622
}
```

Raw side artifacts exist under `soak/pre/{spectrum,att}-raw/`.

## Post-Soak Capture

The operator noted that production had already been soaking for days. The post
capture was therefore run immediately against the current live 24-hour journal
window:

```bash
WANS="spectrum att" \
WANCTL_SPECTRUM_HEALTH_URL="http://10.10.110.223:9101/health" \
WANCTL_ATT_HEALTH_URL="http://10.10.110.227:9101/health" \
WANCTL_SPECTRUM_SSH_HOST="kevin@10.10.110.223" \
WANCTL_ATT_SSH_HOST="kevin@10.10.110.223" \
./scripts/phase192-soak-capture.sh post
```

Output directory:

`.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/soak/post`

### Post Spectrum

```json
{
  "captured_at_iso": "2026-04-24T13:36:23Z",
  "dwell_bypassed_count": 0,
  "burst_trigger_count_dl": 0,
  "burst_trigger_count_ul": 0,
  "fusion_transition_count_24h": 0,
  "protocol_deprio_count_24h": 4062
}
```

### Post ATT

```json
{
  "captured_at_iso": "2026-04-24T13:36:23Z",
  "dwell_bypassed_count": 0,
  "burst_trigger_count_dl": 0,
  "burst_trigger_count_ul": 0,
  "fusion_transition_count_24h": 0,
  "protocol_deprio_count_24h": 620
}
```

## Soak Comparison

| WAN | Metric | Pre | Post | Result |
| --- | --- | ---: | ---: | --- |
| spectrum | dwell_bypassed_count | `0` | `0` | zero baseline preserved |
| spectrum | burst_trigger_count_dl | `0` | `0` | zero baseline preserved |
| spectrum | burst_trigger_count_ul | `0` | `0` | zero baseline preserved |
| spectrum | fusion_transition_count_24h | `0` | `0` | zero baseline preserved |
| spectrum | protocol_deprio_count_24h | `4069` | `4062` | `-0.2%` |
| att | dwell_bypassed_count | `0` | `0` | zero baseline preserved |
| att | burst_trigger_count_dl | `0` | `0` | zero baseline preserved |
| att | burst_trigger_count_ul | `0` | `0` | zero baseline preserved |
| att | fusion_transition_count_24h | `0` | `0` | zero baseline preserved |
| att | protocol_deprio_count_24h | `622` | `620` | `-0.3%` |

Soak gate read: PASS for the captured D-08/OPER-02 categories. The new
`dwell_bypassed_count` field itself was only exposed after the clean deploy on
2026-04-24, so its historical multi-day value is not reconstructable; the
current post-deploy value is zero on both WANs.

## Remaining Gate

Phase 192 closeout version bump is complete locally and deployed to production:

- `src/wanctl/__init__.py`: `1.39.0`
- `pyproject.toml`: `1.39.0`
- `docker/Dockerfile`: `1.39.0`
- `CLAUDE.md`: `1.39.0`
- `CHANGELOG.md`: `1.39.0` entry

No additional soak wait is required by this verification artifact.
