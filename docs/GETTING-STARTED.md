# Getting Started

This guide covers the shortest path from a fresh checkout to a validated `wanctl` installation.

## What You Need

- A Linux host with Python 3.11 or newer
- A MikroTik router running RouterOS 7.x
- CAKE queues already configured on the router
- Network access from the host to the router
- One of these router access methods:
  - RouterOS REST API with credentials in `/etc/wanctl/secrets`
  - SSH key-based access for the `wanctl` service account

## 1. Clone the Repository

```bash
git clone https://github.com/kevinb361/wanctl.git
cd wanctl
```

## 2. Pick a Configuration Template

Example configs live under `configs/examples/`:

- `wan1.yaml.example`
- `wan2.yaml.example`
- `fiber.yaml.example`
- `cable.yaml.example`
- `dsl.yaml.example`
- `steering.yaml.example`

For a first deployment, start with the template closest to your WAN type and copy it to a working file.

```bash
cp configs/examples/wan1.yaml.example /tmp/wan1.yaml
```

## 3. Install on the Target Host

The supported installer is [`scripts/install.sh`](/home/kevin/projects/wanctl/scripts/install.sh). It creates the service user, FHS-style directories, secrets file, and systemd integration.

Interactive install:

```bash
sudo ./scripts/install.sh
```

Other supported modes:

```bash
sudo ./scripts/install.sh --no-wizard
sudo ./scripts/install.sh --reconfigure
sudo ./scripts/install.sh --uninstall
```

The installer prepares these paths on the target host:

- `/opt/wanctl`
- `/etc/wanctl`
- `/etc/wanctl/ssh`
- `/etc/wanctl/secrets`
- `/var/lib/wanctl`
- `/var/log/wanctl`
- `/run/wanctl`

## 4. Put Your Config in Place

Install the chosen config as `/etc/wanctl/<wan>.yaml`. For a `wan1` instance:

```bash
sudo cp /tmp/wan1.yaml /etc/wanctl/wan1.yaml
sudo chown root:wanctl /etc/wanctl/wan1.yaml
sudo chmod 640 /etc/wanctl/wan1.yaml
```

If you use REST transport, add the router password to `/etc/wanctl/secrets`:

```bash
sudoedit /etc/wanctl/secrets
```

Example:

```text
ROUTER_PASSWORD=replace_me
```

Then reference it from the YAML with `${ROUTER_PASSWORD}`.

If you use SSH transport, place the private key under `/etc/wanctl/ssh/` and restrict permissions:

```bash
sudo cp ~/.ssh/router_key /etc/wanctl/ssh/router.key
sudo chown wanctl:wanctl /etc/wanctl/ssh/router.key
sudo chmod 600 /etc/wanctl/ssh/router.key
```

## 5. Validate the Config Before Starting

`wanctl` ships an offline validator exposed as `wanctl-check-config`.

From a development checkout:

```bash
PYTHONPATH=src python -m wanctl.check_config /etc/wanctl/wan1.yaml
```

From an installed system:

```bash
wanctl-check-config /etc/wanctl/wan1.yaml
```

If validation cannot infer the config type, pass `--type autorate` or `--type steering`.

## 6. Start the Controller

`wanctl` currently runs as a long-lived systemd service. Both
[`scripts/install.sh`](/home/kevin/projects/wanctl/scripts/install.sh) and
[`scripts/install-systemd.sh`](/home/kevin/projects/wanctl/scripts/install-systemd.sh)
prepare or enable the same `wanctl@<wan>.service` unit.

Start and verify it with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now wanctl@wan1.service
systemctl status wanctl@wan1.service
journalctl -u wanctl@wan1.service -f
```

If you are upgrading an older timer-based install, disable any legacy timer units first:

```bash
sudo systemctl disable --now wanctl@wan1.timer 2>/dev/null || true
sudo systemctl disable --now steering.timer 2>/dev/null || true
```

The checked-in unit template is
[`deploy/systemd/wanctl@.service`](/home/kevin/projects/wanctl/deploy/systemd/wanctl@.service).

## 7. Optional Remote Deployment

If you are deploying from a workstation to a target host over SSH, use [`scripts/deploy.sh`](/home/kevin/projects/wanctl/scripts/deploy.sh):

```bash
./scripts/deploy.sh wan1 target-host
./scripts/deploy.sh wan1 target-host --with-steering
./scripts/deploy.sh --install-only target-host
```

The deploy script expects SSH connectivity and `rsync` on both ends.

## 8. First Verification Pass

After `deploy.sh` finishes, use the same operator sequence every time:

```bash
ssh target-host 'sudo test -f /var/lib/wanctl/metrics.db.pre-v135-archive && echo migrated || echo needs-migration'
./scripts/migrate-storage.sh --ssh target-host   # only when the archive marker is missing
ssh target-host 'sudo systemctl enable --now wanctl@wan1.service'
./scripts/canary-check.sh --ssh target-host
```

If steering is enabled, also inspect the optional service:

```bash
ssh target-host 'sudo systemctl restart steering.service'
ssh target-host 'sudo journalctl -u steering.service -f'
```

After the service is up, confirm:

- `systemctl status wanctl@wan1.service` reports `active (running)`
- `journalctl -u wanctl@wan1.service` shows successful router connectivity
- `/var/lib/wanctl/` begins receiving runtime state
- config validation passes with `wanctl-check-config`
- `scripts/canary-check.sh --ssh target-host` exits `0`
- `wan_health[wan].measurement.state` is `healthy`, `wan_health[wan].measurement.successful_count` is `3`, and `wan_health[wan].measurement.stale` is `false` before you sign off on a v1.38 deploy

For the bounded measurement-health check, follow
[`RUNBOOK.md`](RUNBOOK.md) under `## Measurement Health Inspection`. That
section is the canonical operator recipe for correlating `tcp_12down`-style
latency spikes with `/health` measurement honesty.

## Monitoring And History

Once `wanctl` is running, two complementary history surfaces are available for any deployed WAN:

- `/metrics/history` (HTTP) is the endpoint-local HTTP history view for the connected autorate daemon. Query it with `curl` against `http://<health-ip>:9101/metrics/history?range=1h&limit=5` to confirm endpoint availability, response shape, and that WAN's local history view.
- `python3 -m wanctl.history` (CLI) is the authoritative merged cross-WAN proof path. Run it as `sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json` when you need merged cross-WAN proof across all deployed autorate instances on the host.

The dashboard history tab surfaces the same distinction via `metadata.source`, so the rule is identical in the TUI, in the runbook, and in the deployment workflow. For deeper operator detail see [`RUNBOOK.md`](RUNBOOK.md) and [`DEPLOYMENT.md`](DEPLOYMENT.md).

On v1.38 and later, add the measurement-health inspection pass before treating
an endpoint as healthy under load: check `measurement.state`,
`measurement.successful_count`, and `measurement.stale` in `/health`, then use
the rubric in [`RUNBOOK.md`](RUNBOOK.md) under `## Measurement Health Inspection`
to decide whether the RTT view is current, reduced, or collapsed.

## Common Issues

### Config validation fails

Run:

```bash
wanctl-check-config /etc/wanctl/wan1.yaml --no-color
```

The validator reports grouped PASS/WARN/FAIL results and points to missing fields, bad paths, or ambiguous config types.

### Service starts but exits immediately

Check:

```bash
journalctl -u wanctl@wan1.service -n 100 --no-pager
```

The most common causes are invalid queue names, missing secrets, or router connectivity failures.

### SSH transport cannot authenticate

Verify key permissions and ownership:

```bash
ls -l /etc/wanctl/ssh/router.key
```

Then test access manually with the same identity you configured in the YAML.

## Related Docs

- [`README.md`](/home/kevin/projects/wanctl/README.md)
- [`docs/CONFIGURATION.md`](/home/kevin/projects/wanctl/docs/CONFIGURATION.md)
- [`DEVELOPMENT.md`](/home/kevin/projects/wanctl/DEVELOPMENT.md)
- [`docs/TESTING.md`](/home/kevin/projects/wanctl/docs/TESTING.md)
