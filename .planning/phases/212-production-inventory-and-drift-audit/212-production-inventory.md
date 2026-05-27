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

## Config, Health Operating Point, and Steering State Comparison

### Spectrum repo/deployed/health operating points

| Surface | Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|---|
| WAN name and transport | repo `wan_name=spectrum`, transport `linux-cake-netlink` | deployed `wan_name=spectrum`, transport `linux-cake-netlink`; health WAN `name=spectrum` | not drift | `configs/spectrum.yaml`, `evidence/config-spectrum.redacted.yaml`, `evidence/health-spectrum.json` | Phase 213 can attribute Spectrum samples to the intended Linux CAKE backend. |
| Router host identity | repo router host `10.10.99.1` | deployed router host `10.10.99.1`; health `router_reachable=true` | not drift | `configs/spectrum.yaml`, `evidence/config-spectrum.redacted.yaml`, `evidence/health-spectrum.json` | Router reachability is a daemon-state precondition, not UX proof. |
| Health and metrics ports | repo health `10.10.110.223:9101`, metrics `10.10.110.223:9100` | deployed same health/metrics host and ports; health captured from `10.10.110.223:9101` | not drift | `configs/spectrum.yaml`, `evidence/config-spectrum.redacted.yaml`, `evidence/health-spectrum.json` | Baseline harness should use the bound Spectrum endpoint and keep metrics scrape assumptions aligned. |
| Download floors and ceilings | floors `550/350/275/200`, ceiling `920` Mbps | deployed floors/ceiling match; health current DL rate `920.0` Mbps, state `GREEN` | not drift | `configs/spectrum.yaml`, `evidence/config-spectrum.redacted.yaml`, `evidence/health-spectrum.json` | Phase 213 should treat DL as currently at configured ceiling while still measuring user experience. |
| Upload floors, ceilings, and setpoints | floor `8`, ceiling `18`, DOCSIS mode `true`, setpoint `12` Mbps | deployed matches; health current UL rate `18.0`, `docsis_mode_active=true`, `setpoint_mbps=12.0`, state `GREEN` | not drift | `configs/spectrum.yaml`, `evidence/config-spectrum.redacted.yaml`, `evidence/health-spectrum.json` | Phase 215 must account for intentionally conservative Spectrum upload setpoint before any reclaim canary. |
| Thresholds and cooldowns | target/warn/hard-red `15/75/100` ms; deadband `3.0`; dwell `5`; flapping cooldown `600` sec | deployed matches; health alerting active cooldowns `[]`, alert fire count `133` | not drift | `configs/spectrum.yaml`, `evidence/config-spectrum.redacted.yaml`, `evidence/health-spectrum.json` | Alert/cooldown interpretation in Phase 218 should use Spectrum's 600s flapping window. |
| Measurement quality | repo reflectors `1.1.1.1`, `9.9.9.9`, `208.67.222.222`; IRTT disabled | health measurement available with `successful_count=3`, `stale=false`, confidence `0.915`, outlier rate `0.467`, IRTT unavailable because disabled | not drift | `configs/spectrum.yaml`, `evidence/health-spectrum.json` | Phase 214 should investigate high outlier rate separately from GREEN state if UX data is bad. |
| Current rate/state summary | expected daemon reports current rates and state from health | health summary DL `920.0 GREEN`, UL `18.0 GREEN`, runtime/storage `ok` | not drift | `evidence/health-spectrum.json` | Starts Phase 213 from a healthy daemon-state snapshot, not from proof that the WAN feels good. |

### ATT repo/deployed/health operating points

| Surface | Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|---|
| WAN name and transport | repo `wan_name=att`, transport `linux-cake-netlink` | deployed `wan_name=att`, transport `linux-cake-netlink`; health WAN `name=att` | not drift | `configs/att.yaml`, `evidence/config-att.redacted.yaml`, `evidence/health-att.json` | Phase 213 can attribute ATT samples to the intended Linux CAKE backend. |
| Router host identity | repo router host `10.10.99.1` | deployed router host `10.10.99.1`; health `router_reachable=true` | not drift | `configs/att.yaml`, `evidence/config-att.redacted.yaml`, `evidence/health-att.json` | Router reachability is a daemon-state precondition, not UX proof. |
| Health and metrics ports | repo health `10.10.110.227:9101`, metrics `10.10.110.227:9100` | deployed same health/metrics host and ports; health captured from `10.10.110.227:9101` | not drift | `configs/att.yaml`, `evidence/config-att.redacted.yaml`, `evidence/health-att.json` | Baseline harness should use the bound ATT endpoint and not assume loopback. |
| Download floors and ceilings | floors `55/35/28/20`, ceiling `95` Mbps | deployed floors/ceiling match; health current DL rate `95.0` Mbps, state `GREEN` | not drift | `configs/att.yaml`, `evidence/config-att.redacted.yaml`, `evidence/health-att.json` | Phase 213 should treat ATT DL as currently at configured ceiling. |
| Upload floors, ceilings, and setpoints | floor `6`, ceiling `18`, no DOCSIS setpoint in repo/deployed config | deployed matches; health current UL rate `18.0`, `docsis_mode_active=false`, `setpoint_mbps=null`, state `GREEN` | not drift | `configs/att.yaml`, `evidence/config-att.redacted.yaml`, `evidence/health-att.json` | ATT is not part of Spectrum DOCSIS setpoint reclaim; it remains the alternate WAN baseline. |
| Thresholds and cooldowns | target/warn/hard-red `3/10/80` ms; deadband `5.0`; dwell `5`; default alerting with no per-rule cooldown override in repo config | deployed matches repo; health alerting active cooldowns `[]`, alert fire count `1` | not drift | `configs/att.yaml`, `evidence/config-att.redacted.yaml`, `evidence/health-att.json` | ATT alert interpretation should not inherit Spectrum's explicit 600s flapping cooldown. |
| Measurement quality | repo reflectors `1.1.1.1`, `8.8.8.8`, `151.101.1.57`; IRTT enabled against `104.200.21.31:2112` | health measurement available with `successful_count=3`, `stale=false`, confidence `0.999`, outlier rate `0.0`; IRTT available with RTT mean `25.35` ms | not drift | `configs/att.yaml`, `evidence/health-att.json` | ATT provides a cleaner measurement-quality contrast for Phase 214. |
| Current rate/state summary | expected daemon reports current rates and state from health | health summary DL `95.0 GREEN`, UL `18.0 GREEN`, runtime/storage `ok` | not drift | `evidence/health-att.json` | Starts Phase 213 from a healthy daemon-state ATT snapshot. |

### Steering config, health, and persisted-state inventory

| Surface | Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|---|
| Topology WAN names | primary `spectrum`, alternate `att`, primary config `/etc/wanctl/spectrum.yaml` | deployed topology matches repo | not drift | `configs/steering.yaml`, `evidence/config-steering.redacted.yaml` | Steering decisions should be interpreted as Spectrum-primary/ATT-alternate. |
| Router host and transport | repo/deployed router transport `rest`, host `10.10.99.1` | deployed config matches; health `router_reachable=true` | not drift | `configs/steering.yaml`, `evidence/config-steering.redacted.yaml`, `evidence/health-steering.json` | Router control path is reachable at capture time, but no RouterOS write was performed. |
| State file path | repo/deployed state file `/var/lib/wanctl/steering_state.json` | read-only persisted state artifact from `/var/lib/wanctl/steering_state.json` | not drift | `configs/steering.yaml`, `evidence/config-steering.redacted.yaml`, `evidence/steering-state.redacted.json` | Folded D-03 can cite the actual persisted-state source without triggering recovery. |
| Thresholds | repo/deployed bad/recovery thresholds `25.0/12.0` ms and confidence thresholds steer/recovery `55/20` | deployed config matches repo; health endpoint exposes v1.39-style `green/yellow/red` thresholds `5/15/15` alongside version `1.39.0` | unknown drift | `configs/steering.yaml`, `evidence/config-steering.redacted.yaml`, `evidence/health-steering.json` | Phase 216 must not assume steering health threshold names map cleanly to current repo semantics while steering remains on `1.39.0`. |
| Current steering state | expected current-state evidence, not controlled restart proof | health `SPECTRUM_GOOD`, WAN zone `GREEN`, decision last transition `2026-04-28T17:53:27.724650+00:00` | not drift | `evidence/health-steering.json` | Current steering is good; this does not prove degraded restart cannot recur. |
| Current decision and counters | expected counters visible from health/state | health `red_count=0`, `good_count=0`, `cake_read_failures=0`; persisted state `current_state=SPECTRUM_GOOD`, `congestion_state=GREEN` | not drift | `evidence/health-steering.json`, `evidence/steering-state.redacted.json` | Later steering interpretation starts from a non-degraded persisted state. |
| Transition timing | expected last transition timing available if state exists | health last transition `2026-04-28T17:53:27.724650+00:00`, time in state about `2508757.8` sec at capture; persisted state timestamp omits timezone but matches same instant content | not drift | `evidence/health-steering.json`, `evidence/steering-state.redacted.json` | Shows long-lived GOOD state before Phase 212; not a fresh restart test. |
| Steering persisted-state todo D-03 | classify as current inventory only; allowed labels include `current-state-good/reproduction-not-attempted`, `current-state-degraded/reproduction-not-attempted`, `state-unavailable`, `needs later controlled-restart investigation` | `current-state-good/reproduction-not-attempted`; no controlled restart staged, and one GOOD snapshot cannot close historical degraded-reload behavior | not drift | `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md`, `evidence/steering-state.redacted.json`, `evidence/health-steering.json` | Keep the todo as later controlled-restart investigation only if operator wants proof; do not close from this snapshot. |

## Downstream Constraints

- Phase 213 should treat health `healthy`/`GREEN` as daemon-state only and still capture normal-use, RRUL, and `tcp_12down` user-experience evidence.
- Phase 214 should pay attention to Spectrum measurement quality: high outlier rate can coexist with GREEN state.
- Phase 215 should not treat Spectrum upload `12` Mbps setpoint and `18` Mbps ceiling as accidental drift; they are intentional current operating points requiring evidence-backed canary approval before tuning.
- Phase 216 should carry steering version/threshold drift as unresolved until the operator decides whether to align steering runtime with repo v1.45+ or leave it staged.
