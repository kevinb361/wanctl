# Deployment

This guide covers the current `wanctl` deployment flow built around the service units in
[`deploy/systemd/`](/home/kevin/projects/wanctl/deploy/systemd).

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

`./scripts/deploy.sh --dry-run` prints the planned actions without requiring SSH checks.

## Install-Only Mode

To prepare a host without copying code yet:

```bash
./scripts/deploy.sh --install-only <target_host>
```

That runs [`scripts/install.sh`](/home/kevin/projects/wanctl/scripts/install.sh) remotely to create the
service user, directories, and base systemd integration.

## Manual Deployment

If you are not using `deploy.sh`, copy these current assets to the target host:

- `/opt/wanctl/` from `src/wanctl/`
- `/etc/wanctl/<wan_name>.yaml`
- [`deploy/systemd/wanctl@.service`](/home/kevin/projects/wanctl/deploy/systemd/wanctl@.service)
- optionally [`deploy/systemd/steering.service`](/home/kevin/projects/wanctl/deploy/systemd/steering.service)

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
```

If steering is enabled:

```bash
systemctl status steering.service
journalctl -u steering.service -f
```

## Troubleshooting

Check recent controller logs:

```bash
journalctl -u wanctl@wan1.service -n 100 --no-pager
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
