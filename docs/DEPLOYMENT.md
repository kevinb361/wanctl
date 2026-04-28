# Deployment

This guide covers the current `wanctl` deployment flow built around the service units in
[`deploy/systemd/`](../deploy/systemd/).

## Automated Remote Deployment

From your workstation:

```bash
cd /path/to/wanctl
./scripts/deploy.sh <wan_name> <target_host>
./scripts/deploy.sh <wan_name> <target_host> --with-steering
```

The deploy script:

- copies `src/wanctl/` into `/opt/wanctl`
- installs the WAN config into `/etc/wanctl/<wan_name>.yaml` when found
- deploys helper scripts, docs, QoS assets, and systemd units
- optionally deploys `steering.service` and `/etc/wanctl/steering.yaml`
- runs a pre-startup validation step on the target host
- deploys operator helpers such as `wanctl-operator-summary` when present

`deploy.sh` copies files and validates the target layout. It does not silently run
`migrate-storage.sh` or restart services for you beyond the explicit `systemctl` commands you choose to run afterward.

`./scripts/deploy.sh --dry-run` prints the planned actions without requiring SSH checks.

## Post-Deploy Operator Flow

After `./scripts/deploy.sh <wan_name> <target_host>` finishes:

1. Confirm config and secrets on the target host.
2. Check whether the storage migration archive exists:

```bash
ssh <target_host> 'sudo test -f /var/lib/wanctl/metrics.db.pre-v135-archive && echo migrated || echo needs-migration'
```

3. If the archive marker is missing, run the migration from your workstation before restart/canary:

```bash
./scripts/migrate-storage.sh --ssh <target_host>
```

4. Restart the WAN service:

```bash
ssh <target_host> 'sudo systemctl enable --now wanctl@<wan_name>.service'
```

5. If steering is enabled, restart or inspect `steering.service`:

```bash
ssh <target_host> 'sudo systemctl restart steering.service'
```

6. Run the acceptance gate:

```bash
./scripts/canary-check.sh --ssh <target_host>
```

7. Capture operator-facing snapshots:

```bash
ssh <target_host> 'wanctl-operator-summary http://<health-ip-1>:9101/health http://<health-ip-2>:9101/health'
./scripts/soak-monitor.sh
```

8. Inspect the measurement-health contract:

```bash
ssh <target_host> 'curl -s http://<health-ip-1>:9101/health' \
  | jq '.wans[] | {name, download: .download.state, upload: .upload.state, measurement: {state: .measurement.state, successful_count: .measurement.successful_count, stale: .measurement.stale}}'
```

On a freshly deployed host that includes the measurement-resilience changes,
`state` should be
`"healthy"`, `successful_count` should be `3`, and `stale` should be `false`.
Any other combination must be correlated against the rubric in
[`RUNBOOK.md`](RUNBOOK.md) under `## Measurement Health Inspection` before
signing off on the deploy. Inspect these literal paths in the payload:
`.wans[].measurement.state`,
`.wans[].measurement.successful_count`,
`.wans[].measurement.stale`.

9. Re-check the active storage topology and retained history with read-only commands:

```bash
ssh <target_host> 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics.db /var/lib/wanctl/spectrum_metrics.db /var/lib/wanctl/att_metrics.db 2>/dev/null'
./scripts/soak-monitor.sh --json
ssh <target_host> 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json | python3 -m json.tool | head -n 40'
ssh <target_host> 'curl -s "http://<health-ip-1>:9101/metrics/history?range=1h&limit=5" | python3 -m json.tool'
```

Expected topology after Phase 178:

- `/var/lib/wanctl/metrics-spectrum.db` and `/var/lib/wanctl/metrics-att.db` remain the active autorate DBs
- `/var/lib/wanctl/metrics.db` remains active for steering
- `/var/lib/wanctl/spectrum_metrics.db` and `/var/lib/wanctl/att_metrics.db` are not part of the authoritative active DB set

For autorate history validation, do not target `/var/lib/wanctl/metrics.db` directly.
On the current production hosts:

- `/metrics/history` is the endpoint-local HTTP history view for the connected autorate daemon.
- `python3 -m wanctl.history` is the authoritative merged cross-WAN proof path.

Use `/metrics/history` (for example via the `curl` command above) to confirm endpoint availability,
response shape, and that WAN's local history view. Use
`sudo -n env PYTHONPATH=/opt python3 -m wanctl.history ...` when you need merged cross-WAN proof;
fall back to direct DB inventory only if the CLI is unavailable. The dashboard history tab
surfaces this same distinction via `metadata.source` so operators see it in both places.

10. If the per-WAN DB files are still above the expected footprint after retention cleanup has had
time to run, compact them explicitly during a controlled restart window:

```bash
./scripts/compact-metrics-dbs.sh --ssh <target_host>
./scripts/canary-check.sh --ssh <target_host> --expect-version <deployed-version>
```

If only ATT remains above the expected footprint while Spectrum is already below baseline, use:

```bash
./scripts/compact-metrics-dbs.sh --ssh <target_host> --wan att
./scripts/canary-check.sh --ssh <target_host> --expect-version <deployed-version> --json
./scripts/soak-monitor.sh --json
```

## Install-Only Mode

To prepare a host without copying code yet:

```bash
./scripts/deploy.sh --install-only <target_host>
```

That runs [`scripts/install.sh`](../scripts/install.sh) remotely to create the
service user, directories, and base systemd integration.

## Manual Deployment

If you are not using `deploy.sh`, copy these current assets to the target host:

- `/opt/wanctl/` from `src/wanctl/`
- `/etc/wanctl/<wan_name>.yaml`
- [`deploy/systemd/wanctl@.service`](../deploy/systemd/wanctl@.service)
- optionally [`deploy/systemd/steering.service`](../deploy/systemd/steering.service)

Then on the target host:

```bash
sudo install -d /opt/wanctl /etc/wanctl /var/lib/wanctl /var/log/wanctl /run/wanctl
sudo cp -r /path/to/src/wanctl/. /opt/wanctl/
sudo cp /path/to/wan1.yaml /etc/wanctl/wan1.yaml
sudo cp /path/to/deploy/systemd/wanctl@.service /etc/systemd/system/wanctl@.service
sudo systemctl daemon-reload
sudo systemctl enable --now wanctl@wan1.service
```

For steering:

```bash
sudo cp /path/to/deploy/systemd/steering.service /etc/systemd/system/steering.service
sudo cp /path/to/steering.yaml /etc/wanctl/steering.yaml
sudo systemctl daemon-reload
sudo systemctl enable --now steering.service
```

## Monitoring

```bash
systemctl status wanctl@wan1.service
journalctl -u wanctl@wan1.service -f
scripts/canary-check.sh --ssh <host>
scripts/soak-monitor.sh
wanctl-operator-summary http://<health-ip-1>:9101/health http://<health-ip-2>:9101/health
```

If steering is enabled:

```bash
systemctl status steering.service
journalctl -u steering.service -f
journalctl -u wanctl@spectrum.service -u wanctl@att.service -u steering.service -n 100 --no-pager
```

## Troubleshooting

Check recent controller logs:

```bash
journalctl -u wanctl@wan1.service -n 100 --no-pager
```

For the all-services soak evidence path:

```bash
journalctl -u wanctl@spectrum.service -u wanctl@att.service -u steering.service --since '24 hours ago' -p err --no-pager
```

Run the controller manually on the target host:

```bash
cd /opt/wanctl
python3 -m wanctl.autorate_continuous --config /etc/wanctl/wan1.yaml --debug
```

Disable the service temporarily:

```bash
sudo systemctl stop wanctl@wan1.service
```

Disable it across reboots:

```bash
sudo systemctl disable --now wanctl@wan1.service
```

Re-enable it:

```bash
sudo systemctl enable --now wanctl@wan1.service
```

## Files Created

- `/etc/systemd/system/wanctl@.service` - main controller unit template
- `/etc/systemd/system/steering.service` - optional steering daemon unit
- `/etc/wanctl/<wan_name>.yaml` - WAN-specific configuration
- `/etc/wanctl/steering.yaml` - optional steering configuration
- `/var/lib/wanctl/<wan_name>_state.json` - persisted controller state
