# Snapshot A Manifest

- Captured: 20260529T144229Z
- Source posture: read-only; no deploy, service restart, config mutation, traffic generation, or production write was performed.
- Health source URL: http://10.10.110.223:9101/health (bound endpoint; not 127.0.0.1).
- Health version: 1.45.0
- Health uptime_seconds: 244463.8
- Repo upload ceiling: 18
- Deployed upload ceiling: 18
- DB query status: absent_config_snapshot_row
- Loaded ceiling from DB: None
- Rollback anchor: Retained wanctl_config_snapshot DB row was absent; rollback anchor is repo config ceiling=18 + deployed config ceiling=18 + bound /health baseline evidence.

## Artifacts

- repo-spectrum.redacted.yaml — redacted repo config captured before mutation.
- deployed-spectrum.redacted.yaml — redacted deployed config from `ssh cake-shaper sudo -n cat /etc/wanctl/spectrum.yaml`.
- state.redacted.json — redacted state file from `/var/lib/wanctl/spectrum_state.json`.
- snapshot-a-health.redacted.json — redacted bound `/health` baseline.
- db-query.redacted.json — exact read-only config-snapshot query result or absent-row evidence.

## Exact DB Query

```sql
SELECT json_extract(labels, '$.autorate.upload_ceiling_mbps') FROM metrics WHERE metric_name='wanctl_config_snapshot' AND wan_name='spectrum' ORDER BY timestamp DESC LIMIT 1;
```

Run over SSH with:

```bash
ssh cake-shaper "sudo -n sqlite3 -readonly 'file:/var/lib/wanctl/metrics-spectrum.db?mode=ro' \"SELECT json_extract(labels, '$.autorate.upload_ceiling_mbps') FROM metrics WHERE metric_name='wanctl_config_snapshot' AND wan_name='spectrum' ORDER BY timestamp DESC LIMIT 1;\""
```

## Targeted Revert Sequence

1. Restore ONLY `continuous_monitoring.upload.ceiling_mbps` in `configs/spectrum.yaml` back to `18` by editing that single YAML key or copying only that value from `repo-spectrum.redacted.yaml`.
2. Do not use a whole-file worktree restore; specifically, do not run `git checkout configs/spectrum.yaml` because it could discard unrelated worktree edits.
3. Run `scripts/deploy.sh spectrum cake-shaper`.
4. Run `ssh cake-shaper 'sudo systemctl restart wanctl@spectrum.service'`.
5. Verify `curl -s http://10.10.110.223:9101/health` shows the reverted service healthy on the bound endpoint.
6. Re-run the exact DB query above; if the retained config-snapshot row is present, confirm it reads `18`.
7. Run `scripts/canary-check.sh --ssh cake-shaper` and require exit 0.

## No-Mutation Attestation

This task performed only read-only commands: local repo read/copy, `ssh cake-shaper sudo -n cat ...`, `sqlite3 -readonly`, and `curl` against the bound health endpoint. It did not perform deploy, restart, config mutation, traffic generation, or any production write.
