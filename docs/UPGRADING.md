# Upgrading wanctl

Use this checklist for service-based upgrades. For the full deploy flow, see
[`DEPLOYMENT.md`](DEPLOYMENT.md). For post-upgrade checks, see
[`RUNBOOK.md`](RUNBOOK.md).

## Standard Upgrade Flow

1. Review [`CHANGELOG.md`](../CHANGELOG.md) for release notes and known gaps.
2. Back up the target config and state if the change affects config, storage, or controller behavior.
3. Deploy with the active remote deployment script.
4. Validate config before restart.
5. Restart the relevant service units.
6. Run the canary and inspect `/health`.

```bash
./scripts/deploy.sh <wan_name> <target_host>
ssh <target_host> 'sudo wanctl-check-config --config /etc/wanctl/<wan_name>.yaml'
ssh <target_host> 'sudo systemctl restart wanctl@<wan_name>.service'
./scripts/canary-check.sh --ssh <target_host>
```

If steering is deployed:

```bash
ssh <target_host> 'sudo systemctl restart steering.service'
```

## Backup Points

Useful files to capture before major upgrades:

- `/etc/wanctl/*.yaml`
- `/etc/wanctl/secrets` metadata and ownership, not plaintext contents in shared notes
- `/var/lib/wanctl/*_state.json`
- `/var/lib/wanctl/metrics-*.db` when storage changes are in scope

Example state backup:

```bash
ssh <target_host> 'sudo cp /var/lib/wanctl/<wan_name>_state.json /var/lib/wanctl/<wan_name>_state.json.pre-upgrade'
```

## Compatibility Notes

- State files are forward-tolerant: missing fields initialize to safe defaults and unknown fields are ignored.
- Config files are not silently migrated. Run `wanctl-check-config` and update YAML when release notes call out new required fields or renamed keys.
- Older shared `metrics.db` layouts should be migrated only through the documented storage migration flow in [`DEPLOYMENT.md`](DEPLOYMENT.md) and [`RUNBOOK.md`](RUNBOOK.md).

## Rollback

If an upgrade causes a production issue:

1. Stop or restart only the affected service.
2. Restore the prior `/opt/wanctl` tree or redeploy the previous known-good commit.
3. Restore config or state only if the upgrade changed their format or contents.
4. Run the canary and inspect `/health` before considering rollback complete.

```bash
ssh <target_host> 'sudo systemctl stop wanctl@<wan_name>.service'
# Restore code/config by your normal deployment process.
ssh <target_host> 'sudo systemctl start wanctl@<wan_name>.service'
./scripts/canary-check.sh --ssh <target_host>
```

Do not delete state or metrics DBs as a first response. Preserve them for
forensics unless there is a specific corruption finding.

## Common Upgrade Failures

| Symptom | Likely cause | First check |
| --- | --- | --- |
| Service fails immediately | Config validation or missing secret | `journalctl -u wanctl@<wan>.service -n 100` |
| SSH transport fails | Missing key, permissions, or host key | [`SECURITY.md`](SECURITY.md) SSH setup |
| REST transport fails | TLS, credential, or RouterOS API issue | Config `router.*` fields and service logs |
| `/health` degraded after restart | Router unreachable, repeated controller failures, or storage pressure | [`RUNBOOK.md`](RUNBOOK.md) quick reference |
| History missing or split by WAN | Expected endpoint-local HTTP history versus merged CLI distinction | [`SUBSYSTEMS.md`](SUBSYSTEMS.md) dashboard/storage sections |
