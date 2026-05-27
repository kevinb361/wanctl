# Phase 212 Production Inventory and Drift Classification

Phase 212 is read-only/default-no-mutation. This report classifies saved Wave 1 evidence only; it does not deploy, restart services, write production config, or issue RouterOS write operations. Drift alignment, if needed, is future operator-approved work per D-02.

Allowed verdict vocabulary: `not drift`, `expected staging`, `accidental drift`, `unknown drift`, `resolved by approved deployment`.

## Service, Version, Endpoint, and Health Inventory

### Spectrum autorate

| Surface | Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|---|
| Service identity | `wanctl@spectrum.service` loaded/enabled from `wanctl@.service` | `Id=wanctl@spectrum.service`, `LoadState=loaded`, `UnitFileState=enabled`, `FragmentPath=/etc/systemd/system/wanctl@.service` | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-spectrum.txt` | Phase 213/214 can cite Spectrum daemon as the expected autorate service. |
| Active state | systemd active/running for inventory capture | `ActiveState=active`, `SubState=running`, `ExecMainPID=3716280` | not drift | `evidence/systemd-spectrum.txt` | Later baseline captures should treat Spectrum as live, not absent. |
| ExecStart/config path | `/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/spectrum.yaml` | same argv with `/etc/wanctl/spectrum.yaml` | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-spectrum.txt` | Config comparisons can use `/etc/wanctl/spectrum.yaml` as the deployed source. |
| Runtime version | repo and v1.45 deploy facts expect `1.45.0` | `/health.version=1.45.0` | not drift | `evidence/repo-expected-summary.json`, `evidence/health-spectrum.json`, `../211-production-verification-milestone-closure/211-01-SUMMARY.md` | Spectrum quality evidence is from v1.45.0, matching v1.46 baseline expectations. |
| Health endpoint binding | repo/deployed config endpoint `http://10.10.110.223:9101/health`; do not assume loopback | captured endpoint `http://10.10.110.223:9101/health`, provenance `/etc/wanctl/spectrum.yaml` host `10.10.110.223`, port `9101` | not drift | `evidence/repo-expected-summary.json`, `evidence/health-spectrum.json`, `evidence/config-spectrum.redacted.yaml` | Phase 213 automation must query the bound Spectrum IP, not loopback. |
| Service uptime/start timestamp | started after Spectrum v1.45 activation window | `ExecMainStartTimestamp=Tue 2026-05-26 13:48:02 CDT`; `/health.uptime_seconds=86279.2` at capture | not drift | `evidence/systemd-spectrum.txt`, `evidence/health-spectrum.json`, `../211-production-verification-milestone-closure/211-01-SUMMARY.md` | Confirms Spectrum had been running since the approved v1.45 activation, not freshly restarted during Phase 212. |
| Restart count | no unexpected post-activation restart during inventory | `NRestarts=0`, restart policy `on-failure` | not drift | `evidence/systemd-spectrum.txt` | Later analyses do not need to compensate for repeated daemon restarts before this capture. |
| Watchdog setting | expected service watchdog managed by systemd | `WatchdogUSec=30s` | not drift | `evidence/systemd-spectrum.txt`, `deploy/systemd/wanctl@.service` | Runtime health can be interpreted with watchdog protection present. |
| Health summary state | daemon-state `healthy`, one Spectrum WAN, DL/UL GREEN, rates at configured ceilings | `status=healthy`, `summary.status=healthy`, DL `GREEN` at `920.0`, UL `GREEN` at `18.0` | not drift | `evidence/health-spectrum.json` | Does not prove user experience; it only bounds Phase 213 starting state. |

healthy/GREEN is daemon-state evidence only and is not proof of user experience.

### ATT autorate

| Surface | Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|---|
| Service identity | `wanctl@att.service` loaded/enabled from `wanctl@.service` | `Id=wanctl@att.service`, `LoadState=loaded`, `UnitFileState=enabled`, `FragmentPath=/etc/systemd/system/wanctl@.service` | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-att.txt` | ATT baseline capture can cite the expected autorate service. |
| Active state | systemd active/running after ATT rollout | `ActiveState=active`, `SubState=running`, `ExecMainPID=66556` | not drift | `evidence/systemd-att.txt`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | Later ATT evidence should treat the daemon as live on the v1.45 rollout path. |
| ExecStart/config path | `/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/att.yaml` | same argv with `/etc/wanctl/att.yaml` | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-att.txt` | Config comparisons can use `/etc/wanctl/att.yaml` as the deployed source. |
| Runtime version | repo and approved ATT rollout expect `1.45.0` | `/health.version=1.45.0` | resolved by approved deployment | `evidence/repo-expected-summary.json`, `evidence/health-att.json`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | Previous ATT `1.39.0` mismatch was resolved by the approved Phase 211 rollout; Phase 213 should use v1.45.0 facts. |
| Health endpoint binding | repo/deployed config endpoint `http://10.10.110.227:9101/health`; do not assume loopback | captured endpoint `http://10.10.110.227:9101/health`, provenance `/etc/wanctl/att.yaml` host `10.10.110.227`, port `9101` | not drift | `evidence/repo-expected-summary.json`, `evidence/health-att.json`, `evidence/config-att.redacted.yaml` | Phase 213 automation must query the bound ATT IP, not loopback. |
| Service uptime/start timestamp | started after approved ATT service activation | `ExecMainStartTimestamp=Wed 2026-05-27 12:43:11 CDT`; `/health.uptime_seconds=3772.6` at capture | not drift | `evidence/systemd-att.txt`, `evidence/health-att.json`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | ATT v1.45 data has a shorter warmup window than Spectrum and should be labeled accordingly. |
| Restart count | no unexpected restart after ATT activation | `NRestarts=0`, restart policy `on-failure` | not drift | `evidence/systemd-att.txt` | Later analyses do not need to explain repeated ATT daemon churn before this capture. |
| Watchdog setting | expected service watchdog managed by systemd | `WatchdogUSec=30s` | not drift | `evidence/systemd-att.txt`, `deploy/systemd/wanctl@.service` | Runtime health can be interpreted with watchdog protection present. |
| Health summary state | daemon-state `healthy`, one ATT WAN, DL/UL GREEN, rates at configured ceilings | `status=healthy`, `summary.status=healthy`, DL `GREEN` at `95.0`, UL `GREEN` at `18.0` | not drift | `evidence/health-att.json` | Does not prove user experience; it only bounds Phase 213 starting state. |

healthy/GREEN is daemon-state evidence only and is not proof of user experience.

### Steering daemon

| Surface | Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|---|
| Service identity | `steering.service` loaded/enabled from `steering.service` | `Id=steering.service`, `LoadState=loaded`, `UnitFileState=enabled`, `FragmentPath=/etc/systemd/system/steering.service` | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-steering.txt` | Steering inventory can cite the expected systemd service. |
| Active state | systemd active/running for inventory capture | `ActiveState=active`, `SubState=running`, `ExecMainPID=876` | not drift | `evidence/systemd-steering.txt` | Later steering interpretation can use the daemon as live, not absent. |
| ExecStart/config path | `/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml` | same argv with `/etc/wanctl/steering.yaml` | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-steering.txt` | Config comparison can use `/etc/wanctl/steering.yaml` as deployed source. |
| Runtime version | repo source is `1.45.0`; no Phase 211 steering rollout evidence exists | `/health.version=1.39.0` | unknown drift | `evidence/repo-expected-summary.json`, `evidence/health-steering.json`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | Steering-dependent conclusions in Phase 213/214/216 must carry this version drift until operator classifies or approves alignment. |
| Health endpoint binding | steering endpoint must be discovered from deployed config/service/socket evidence | discovered listener `127.0.0.1:9102`; captured endpoint `http://127.0.0.1:9102/health`; config read first failed unprivileged, socket discovery succeeded | not drift | `evidence/health-steering.json`, `evidence/config-steering.redacted.yaml` | Phase 213/216 should use `127.0.0.1:9102` from `cake-shaper` unless new evidence supersedes it. |
| Service uptime/start timestamp | long-running steering service expected unless explicitly restarted | `ExecMainStartTimestamp=Tue 2026-04-28 17:34:13 CDT`; `/health.uptime_seconds=2491911.1` at capture | not drift | `evidence/systemd-steering.txt`, `evidence/health-steering.json` | Steering state predates v1.45 rollout; do not assume steering was refreshed with autorate deployments. |
| Restart count | no unexpected restart recorded by systemd | `NRestarts=0`, restart policy `on-failure` | not drift | `evidence/systemd-steering.txt` | Folded restart todo cannot be closed from this snapshot; no controlled restart was attempted. |
| Watchdog setting | expected service watchdog managed by systemd | `WatchdogUSec=30s` | not drift | `evidence/systemd-steering.txt`, `deploy/systemd/steering.service` | Runtime health can be interpreted with watchdog protection present. |
| Health summary state | daemon-state `healthy`, steering state `SPECTRUM_GOOD`, WAN zone GREEN | `status=healthy`, `steering.state=SPECTRUM_GOOD`, `wan_awareness.zone=GREEN`, `summary.status=healthy` | not drift | `evidence/health-steering.json` | Current steering is good, but old degraded-on-restart hypothesis remains unproven. |

healthy/GREEN is daemon-state evidence only and is not proof of user experience.

## Classification Notes for Later Phases

- Spectrum and ATT health endpoint evidence is bound to per-WAN IP addresses; later automation must not silently fall back to loopback for autorate.
- ATT version drift observed before the approved rollout is classified as `resolved by approved deployment`; the saved Wave 1 evidence now shows ATT at `1.45.0`.
- Steering runtime version `1.39.0` versus repo `1.45.0` is `unknown drift`, not fixed during Phase 212. Operator approval is required before any alignment.
- No production mutation was performed by this plan; all rows above are classify-only except the historical ATT rollout already approved and documented by Phase 211.
