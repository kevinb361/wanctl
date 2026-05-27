# Phase 212 Evidence Command Index

Phase 212 is read-only/default-no-mutation. Evidence in this directory is captured from repo files or production host `cake-shaper` using inspection-only commands. Secret-like values are redacted with the D-08 key pattern: `password|secret|token|credential|auth|key|private`.

## Evidence Index

| Timestamp (UTC) | Source host | Command purpose | Redaction method | Output file | Mutation posture |
|---|---|---|---|---|---|
| 2026-05-27T18:42:41Z | dev repo checkout | Summarize repo expected version, service units, config paths, and non-secret health endpoints from committed files | Omit raw secret-bearing values; record only proof-relevant non-secret fields | `repo-expected-summary.json` | Read-only local file reads; no production access |

## Redaction Policy

- Redact any key whose lowercase name contains `password`, `secret`, `token`, `credential`, `auth`, `key`, or `private`.
- Do not save `/etc/wanctl/secrets` content, raw RouterOS passwords, webhook URLs, private key material, tokens, credentials, or raw secret-bearing environment dumps.
- Preserve proof-relevant non-secret operating points needed for drift interpretation: WAN name, transport, router host identity, queue names, floors, ceilings, setpoints, DOCSIS mode, health/metrics ports, steering thresholds, state paths, and cooldowns.
- `/health` artifacts are daemon-state evidence for version, state, rates, measurement quality, and active status; they are not user-experience proof.

## Production Boundary

- Production evidence must come from `ssh cake-shaper ...` or an already-local shell on that production host.
- The development VM is not production evidence.
- Do not deploy, restart services, write production config, write RouterOS state, or stage a steering degraded restart in Phase 212.
| 2026-05-27T18:46:04Z | cake-shaper | Capture systemd facts for wanctl@spectrum.service; command: `systemctl show wanctl@spectrum.service --property=Id,ActiveState,SubState,ExecMainStartTimestamp,ExecMainPID,NRestarts,ExecStart,FragmentPath,WatchdogUSec,User,Group,Restart,RestartUSec,LoadState,UnitFileState --no-pager` | Environment/secret-bearing fields not requested | `systemd-spectrum.txt` | Read-only production inspection; no deploy/restart/config write/RouterOS write |
| 2026-05-27T18:46:04Z | cake-shaper | Capture systemd facts for wanctl@att.service; command: `systemctl show wanctl@att.service --property=Id,ActiveState,SubState,ExecMainStartTimestamp,ExecMainPID,NRestarts,ExecStart,FragmentPath,WatchdogUSec,User,Group,Restart,RestartUSec,LoadState,UnitFileState --no-pager` | Environment/secret-bearing fields not requested | `systemd-att.txt` | Read-only production inspection; no deploy/restart/config write/RouterOS write |
| 2026-05-27T18:46:04Z | cake-shaper | Capture systemd facts for steering.service; command: `systemctl show steering.service --property=Id,ActiveState,SubState,ExecMainStartTimestamp,ExecMainPID,NRestarts,ExecStart,FragmentPath,WatchdogUSec,User,Group,Restart,RestartUSec,LoadState,UnitFileState --no-pager` | Environment/secret-bearing fields not requested | `systemd-steering.txt` | Read-only production inspection; no deploy/restart/config write/RouterOS write |
| 2026-05-27T18:46:04Z | cake-shaper | Capture health JSON from deployed endpoint http://10.10.110.223:9101/health; command: `curl -fsS --max-time 5 http://10.10.110.223:9101/health` | Health JSON saved as daemon-state evidence; no secret-bearing config output requested | `health-spectrum.json` | Read-only production inspection; no deploy/restart/config write/RouterOS write |
| 2026-05-27T18:46:04Z | cake-shaper | Capture health JSON from deployed endpoint http://10.10.110.227:9101/health; command: `curl -fsS --max-time 5 http://10.10.110.227:9101/health` | Health JSON saved as daemon-state evidence; no secret-bearing config output requested | `health-att.json` | Read-only production inspection; no deploy/restart/config write/RouterOS write |
| 2026-05-27T18:46:04Z | cake-shaper | Capture steering health JSON from discovered endpoint http://127.0.0.1:9102/health; command: `curl -fsS --max-time 3 http://127.0.0.1:9102/health` | Health JSON saved as daemon-state evidence; discovery sources recorded | `health-steering.json` | Read-only production inspection; no deploy/restart/config write/RouterOS write |
| 2026-05-27T18:46:34Z | cake-shaper | Confirm deployed autorate health endpoint host/port from `/etc/wanctl/spectrum.yaml` and `/etc/wanctl/att.yaml`; command: `sudo -n python3 structured YAML read` | Output limited to health_check host/port and file path; no secret-bearing values saved | `health-spectrum.json`, `health-att.json` | Read-only production inspection; no deploy/restart/config write/RouterOS write |
