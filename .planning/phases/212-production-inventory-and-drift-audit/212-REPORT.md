# Phase 212 Final Operator Report: Production Inventory and Drift Audit

Phase 212 was read-only/default-no-mutation. It classified saved evidence from Plan 212-01 and the Plan 212-02 inventory; it did not deploy code, restart services, write production config, issue RouterOS write operations, or stage a controlled steering degraded restart. Any drift alignment called out below requires separate operator approval before mutation.

## Executive Verdict

| Requirement | Coverage note | Verdict | Evidence path | Downstream impact |
|---|---|---|---|---|
| DRIFT-01 | Spectrum, ATT, and steering deployed versions, health endpoints, service state, uptime, restart count, and daemon health summaries are captured and classified. | Covered | `212-production-inventory.md`, `evidence/systemd-spectrum.txt`, `evidence/systemd-att.txt`, `evidence/systemd-steering.txt`, `evidence/health-spectrum.json`, `evidence/health-att.json`, `evidence/health-steering.json` | Phase 213 can start from exact service/endpoint facts without re-probing production. |
| DRIFT-02 | Spectrum/ATT runtime version and config state are classified; ATT prior version drift is resolved by approved Phase 211 deployment; steering runtime/threshold semantics remain `unknown drift`. | Covered with unresolved steering drift | `212-production-inventory.md`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md`, `evidence/health-steering.json` | Phase 213/214/216 must carry steering drift as unresolved until operator-approved alignment. |
| DRIFT-03 | Repo config, redacted deployed YAML, and `/health` critical operating points were compared without preserving raw secret-bearing values. | Covered | `212-production-inventory.md`, `evidence/config-spectrum.redacted.yaml`, `evidence/config-att.redacted.yaml`, `evidence/config-steering.redacted.yaml`, `evidence/steering-state.redacted.json` | Phase 215 can cite current Spectrum upload setpoint/ceiling as intentional operating points, not accidental drift. |

Key operator takeaways:

- Spectrum autorate is active at `1.45.0`, bound to `http://10.10.110.223:9101/health`, reporting daemon-state `healthy`/GREEN at DL `920.0` Mbps and UL `18.0` Mbps.
- ATT autorate is active at `1.45.0`, bound to `http://10.10.110.227:9101/health`, reporting daemon-state `healthy`/GREEN at DL `95.0` Mbps and UL `18.0` Mbps.
- Steering is active and daemon-state healthy, but reports runtime version `1.39.0` while repo source is `1.45.0`; threshold naming/semantics also look v1.39-shaped. This is `unknown drift` and requires operator approval before alignment.
- `/health.status == healthy` and GREEN states are daemon-state evidence only. They are not proof that user-perceived internet quality is good.

## Evidence Index

| Evidence surface | Stable artifact | Source/provenance | Report use |
|---|---|---|---|
| Repo expected summary | `evidence/repo-expected-summary.json` | Local repo expected version, service units, config paths, and proof-relevant non-secret fields | Expected-value side of inventory tables. |
| Systemd Spectrum | `evidence/systemd-spectrum.txt` | `cake-shaper` read-only `systemctl show wanctl@spectrum.service` | Service identity, active state, config path, uptime, restart/watchdog facts. |
| Systemd ATT | `evidence/systemd-att.txt` | `cake-shaper` read-only `systemctl show wanctl@att.service` | Service identity, active state, config path, uptime, restart/watchdog facts. |
| Systemd steering | `evidence/systemd-steering.txt` | `cake-shaper` read-only `systemctl show steering.service` | Steering service identity, active state, uptime, restart/watchdog facts. |
| Spectrum health | `evidence/health-spectrum.json` | Bound production endpoint `http://10.10.110.223:9101/health` | Runtime version, state/rates, measurement quality, daemon summary. |
| ATT health | `evidence/health-att.json` | Bound production endpoint `http://10.10.110.227:9101/health` | Runtime version, state/rates, measurement quality, daemon summary. |
| Steering health | `evidence/health-steering.json` | Discovered listener `http://127.0.0.1:9102/health` on `cake-shaper` | Steering version, state, counters, threshold surface. |
| Redacted deployed YAML | `evidence/config-spectrum.redacted.yaml`, `evidence/config-att.redacted.yaml`, `evidence/config-steering.redacted.yaml` | Read-only `/etc/wanctl/*.yaml` snapshots with D-08 key omission | Deployed config comparison for endpoints, thresholds, floors/ceilings/setpoints, topology. |
| Redacted steering state | `evidence/steering-state.redacted.json` | Read-only `/var/lib/wanctl/steering_state.json` snapshot | Folded D-03 current-state-good evidence. |
| Evidence command index | `evidence/README.md` | Timestamped command/source/redaction/mutation posture index | Auditability and mutation-boundary provenance. |

## Spectrum Inventory

| Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|
| Service `wanctl@spectrum.service`, loaded/enabled from `wanctl@.service`. | `Id=wanctl@spectrum.service`, `LoadState=loaded`, `UnitFileState=enabled`, `FragmentPath=/etc/systemd/system/wanctl@.service`. | not drift | `212-production-inventory.md`, `evidence/systemd-spectrum.txt` | Phase 213/214 can cite Spectrum daemon as the expected autorate service. |
| ExecStart uses `/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/spectrum.yaml`. | Live argv uses `/etc/wanctl/spectrum.yaml`. | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-spectrum.txt` | Deployed config source is known. |
| Runtime version `1.45.0`. | `/health.version=1.45.0`. | not drift | `evidence/repo-expected-summary.json`, `evidence/health-spectrum.json`, `../211-production-verification-milestone-closure/211-01-SUMMARY.md` | Spectrum evidence matches current v1.46 baseline expectations. |
| Health endpoint `http://10.10.110.223:9101/health`; do not assume loopback. | Captured from `http://10.10.110.223:9101/health`, with deployed config provenance host `10.10.110.223`, port `9101`. | not drift | `evidence/repo-expected-summary.json`, `evidence/health-spectrum.json`, `evidence/config-spectrum.redacted.yaml` | Phase 213 automation must use the bound Spectrum endpoint. |
| Active/running after approved v1.45 activation, no unexpected restart. | `ActiveState=active`, `SubState=running`, `ExecMainStartTimestamp=Tue 2026-05-26 13:48:02 CDT`, `NRestarts=0`. | not drift | `evidence/systemd-spectrum.txt`, `evidence/health-spectrum.json` | Later captures start from a long-running daemon, not a Phase 212 restart. |
| DL ceiling `920`, UL floor/ceiling/setpoint `8/18/12`, DOCSIS mode active. | Health current DL `920.0` GREEN; UL `18.0` GREEN; `docsis_mode_active=true`; `setpoint_mbps=12.0`. | not drift | `configs/spectrum.yaml`, `evidence/config-spectrum.redacted.yaml`, `evidence/health-spectrum.json`, `212-production-inventory.md` | Phase 215 must treat `setpoint_mbps=12` and `ceiling_mbps=18` as current intentional operating points before any reclaim canary. |
| Measurement quality should be interpreted separately from daemon state. | `successful_count=3`, `stale=false`, confidence `0.915`, outlier rate `0.467`; health remains GREEN. | not drift | `evidence/health-spectrum.json`, `212-production-inventory.md` | Phase 214 must investigate measurement collapse/high outlier behavior if UX evidence is bad. |

## ATT Inventory

| Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|
| Service `wanctl@att.service`, loaded/enabled from `wanctl@.service`. | `Id=wanctl@att.service`, `LoadState=loaded`, `UnitFileState=enabled`, `FragmentPath=/etc/systemd/system/wanctl@.service`. | not drift | `212-production-inventory.md`, `evidence/systemd-att.txt` | Phase 213 can cite ATT daemon as the expected autorate service. |
| ExecStart uses `/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/att.yaml`. | Live argv uses `/etc/wanctl/att.yaml`. | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-att.txt` | Deployed ATT config source is known. |
| Runtime version `1.45.0`; prior mismatch should be resolved by approved ATT rollout. | `/health.version=1.45.0`. | resolved by approved deployment | `evidence/repo-expected-summary.json`, `evidence/health-att.json`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | Phase 213 should use v1.45 ATT facts; do not carry old ATT `1.39.0` as active drift. |
| Health endpoint `http://10.10.110.227:9101/health`; do not assume loopback. | Captured from `http://10.10.110.227:9101/health`, with deployed config provenance host `10.10.110.227`, port `9101`. | not drift | `evidence/repo-expected-summary.json`, `evidence/health-att.json`, `evidence/config-att.redacted.yaml` | Phase 213 automation must use the bound ATT endpoint. |
| Active/running after approved ATT service activation, no unexpected restart. | `ActiveState=active`, `SubState=running`, `ExecMainStartTimestamp=Wed 2026-05-27 12:43:11 CDT`, `NRestarts=0`. | not drift | `evidence/systemd-att.txt`, `evidence/health-att.json`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | ATT has a shorter v1.45 warmup window than Spectrum and should be labeled that way. |
| DL ceiling `95`, UL floor/ceiling `6/18`, no DOCSIS setpoint. | Health current DL `95.0` GREEN; UL `18.0` GREEN; `docsis_mode_active=false`; `setpoint_mbps=null`. | not drift | `configs/att.yaml`, `evidence/config-att.redacted.yaml`, `evidence/health-att.json`, `212-production-inventory.md` | ATT remains alternate WAN baseline, not part of Spectrum DOCSIS upload reclaim. |
| Measurement quality should provide a contrast to Spectrum. | `successful_count=3`, `stale=false`, confidence `0.999`, outlier rate `0.0`, IRTT available with RTT mean `25.35` ms. | not drift | `evidence/health-att.json`, `212-production-inventory.md` | Phase 214 can use ATT as cleaner measurement-quality contrast. |

## Steering Inventory

| Expected value | Live value | Verdict | Evidence path | Impact on later phases |
|---|---|---|---|---|
| Service `steering.service`, loaded/enabled from `steering.service`. | `Id=steering.service`, `LoadState=loaded`, `UnitFileState=enabled`, `FragmentPath=/etc/systemd/system/steering.service`. | not drift | `212-production-inventory.md`, `evidence/systemd-steering.txt` | Steering daemon is live and should be interpreted as active inventory, not absent. |
| ExecStart uses `/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml`. | Live argv uses `/etc/wanctl/steering.yaml`. | not drift | `evidence/repo-expected-summary.json`, `evidence/systemd-steering.txt` | Deployed steering config source is known. |
| Repo source version `1.45.0`; no Phase 211 steering rollout evidence exists. | `/health.version=1.39.0`. | unknown drift | `evidence/repo-expected-summary.json`, `evidence/health-steering.json`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | Phase 213/214/216 must carry steering version drift until operator approval aligns or accepts it. |
| Steering endpoint should be discovered, not assumed. | Discovered listener and capture at `http://127.0.0.1:9102/health`. | not drift | `evidence/health-steering.json`, `evidence/config-steering.redacted.yaml`, `evidence/README.md` | Phase 213/216 should use `127.0.0.1:9102` from `cake-shaper` unless newer evidence supersedes it. |
| Long-running service unless explicitly restarted. | `ExecMainStartTimestamp=Tue 2026-04-28 17:34:13 CDT`, `/health.uptime_seconds=2491911.1`, `NRestarts=0`. | not drift | `evidence/systemd-steering.txt`, `evidence/health-steering.json` | Steering predates v1.45 autorate rollout; do not assume steering was refreshed. |
| Deployed topology primary `spectrum`, alternate `att`; state file `/var/lib/wanctl/steering_state.json`. | Deployed config and redacted state match expected topology/state path. | not drift | `configs/steering.yaml`, `evidence/config-steering.redacted.yaml`, `evidence/steering-state.redacted.json` | Steering decisions should be interpreted as Spectrum-primary/ATT-alternate. |
| Current steering state evidence only; no controlled restart proof. | Health and persisted state show `SPECTRUM_GOOD` / GREEN; no controlled degraded restart was staged. | current-state-good/reproduction-not-attempted | `evidence/health-steering.json`, `evidence/steering-state.redacted.json`, `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md` | Folded D-03 todo remains later controlled-restart work only if operator wants proof; Phase 212 did not close it by mutation. |
| Repo/deployed thresholds bad/recovery `25.0/12.0` and confidence thresholds `55/20`. | Health exposes v1.39-style `green/yellow/red` thresholds `5/15/15` alongside version `1.39.0`. | unknown drift | `configs/steering.yaml`, `evidence/config-steering.redacted.yaml`, `evidence/health-steering.json`, `212-production-inventory.md` | Phase 216 must not assume steering health threshold names map to current repo semantics while runtime stays `1.39.0`. |

## Drift Register

Every non-`not drift` row from `212-production-inventory.md` is carried forward here.

| Surface | Expected value | Live value | Verdict | Evidence path | Impact / required follow-up |
|---|---|---|---|---|---|
| ATT runtime version | Repo and approved ATT rollout expect `1.45.0`. | `/health.version=1.45.0`; earlier ATT `1.39.0` mismatch was corrected by approved Phase 211 deployment. | resolved by approved deployment | `evidence/repo-expected-summary.json`, `evidence/health-att.json`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | No active ATT version drift remains for Phase 213. |
| Steering runtime version | Repo source is `1.45.0`; no approved steering rollout evidence exists. | `/health.version=1.39.0`. | unknown drift | `evidence/repo-expected-summary.json`, `evidence/health-steering.json`, `../211-production-verification-milestone-closure/211-02-SUMMARY.md` | Operator approval required before alignment; no Phase 212 mutation performed. Phase 213/214/216 must carry this as a constraint. |
| Steering thresholds | Repo/deployed config uses bad/recovery thresholds `25.0/12.0` ms and confidence thresholds steer/recovery `55/20`. | Steering health exposes v1.39-style `green/yellow/red` thresholds `5/15/15` while runtime version is `1.39.0`. | unknown drift | `configs/steering.yaml`, `evidence/config-steering.redacted.yaml`, `evidence/health-steering.json` | Operator approval required before alignment; no Phase 212 mutation performed. Phase 216 must resolve semantics before relying on threshold health fields. |
| Steering persisted-state folded todo | Evidence-only inventory; no controlled restart in Phase 212. | Current health/state is `SPECTRUM_GOOD` / GREEN. | current-state-good/reproduction-not-attempted | `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md`, `evidence/steering-state.redacted.json`, `evidence/health-steering.json` | Current state is good, but historical degraded-on-clean-restart behavior is not disproven. No controlled degraded restart was staged. |

## Secret-Redaction Review

| Check | Result | Evidence path | Notes |
|---|---|---|---|
| D-08 artifact policy | PASS | `evidence/README.md` | Evidence index records redaction policy and forbids raw credential material. |
| Redacted deployed configs | PASS | `evidence/config-spectrum.redacted.yaml`, `evidence/config-att.redacted.yaml`, `evidence/config-steering.redacted.yaml` | D-08 matching keys were omitted from saved YAML artifacts; proof-relevant non-secret fields were retained. |
| Redacted steering state | PASS | `evidence/steering-state.redacted.json` | State artifact was captured without triggering recovery/backup mutation. |
| Final report content | PASS pending automated closeout check | `212-REPORT.md` | This report cites stable redacted artifacts and does not include raw router passwords, tokens, private keys, or full secret-bearing config dumps. |

## Production-Mutation Review

| Boundary | Phase 212 result | Evidence path | Impact |
|---|---|---|---|
| Deploy/code rollout | Not performed. | `evidence/README.md`, `212-01-SUMMARY.md`, `212-02-SUMMARY.md` | Any alignment belongs to a later operator-approved phase. |
| Service restart | Not performed by Phase 212. | `evidence/systemd-spectrum.txt`, `evidence/systemd-att.txt`, `evidence/systemd-steering.txt` | Uptime/restart counts remain valid read-only inventory facts. |
| Production config write | Not performed. | `evidence/config-spectrum.redacted.yaml`, `evidence/config-att.redacted.yaml`, `evidence/config-steering.redacted.yaml` | Deployed config is classified, not changed. |
| RouterOS write operation | Not performed. | `evidence/README.md` | Router state was not mutated for inventory. |
| Controlled steering degraded restart | Not performed. | `evidence/health-steering.json`, `evidence/steering-state.redacted.json` | Folded steering todo remains current-state evidence only. |

## Downstream Constraints

### Phase 213: Experience Baseline Harness

- Use bound autorate endpoints from evidence, not loopback assumptions: Spectrum `http://10.10.110.223:9101/health`, ATT `http://10.10.110.227:9101/health`.
- Treat `/health` `healthy`/GREEN as daemon-state only. Phase 213 must still capture user-experience evidence for normal browsing, upload/download, RRUL, and `tcp_12down`.
- Label Spectrum as longer-running since v1.45 activation and ATT as shorter-running after the approved early rollout.
- Carry steering runtime `1.39.0` and threshold semantic mismatch as unresolved context; do not assume steering has v1.45 behavior.

### Phase 214: Measurement-Collapse Investigation

- Spectrum health can be GREEN with high measurement outlier rate (`0.467` in saved evidence). Bad p99 latency while health remains GREEN is still plausible and must be investigated from UX/test artifacts.
- ATT health evidence has cleaner measurement quality (`outlier_rate=0.0`, confidence `0.999`) and can provide a contrast path.
- Preserve daemon-health versus user-experience distinction in all conclusions; do not use `/health.status` alone to close the bad-p99 todo.

### Phase 215: Spectrum Upload Reclaim Canary

- Spectrum upload operating points are current intentional config, not drift: floor `8`, ceiling `18`, DOCSIS mode active, setpoint `12` Mbps, current UL rate `18.0` GREEN.
- Any reclaim must be evidence-backed after Phase 213 baseline, one knob at a time, with Snapshot A rollback and explicit success/rollback gates.
- Do not treat the 40 Mbps plan anchor as permission to tune during inventory; Phase 212 performed no mutation.

### Additional constraints for Phase 216/217/218

- Phase 216 must resolve steering version/threshold semantics before relying on steering health threshold fields for recovery/refractory decisions.
- Phase 217 cycle-budget profiling remains separate unless later evidence shows immediate performance risk; Phase 212 did not run profiling captures.
- Phase 218 VERIFY watch-list remains dependent on a natural production flapping event; Phase 212 did not generate or simulate one.
