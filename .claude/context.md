# wanctl - Technical Context

Current project-specific operational context for local work.

## Core Runtime

`wanctl` is a production, long-running adaptive CAKE controller for MikroTik RouterOS with optional WAN steering.

Current assumptions:
- Python `>=3.11`
- Code installs to `/opt/wanctl`
- Config lives in `/etc/wanctl`
- State lives in `/var/lib/wanctl`
- Logs live in `/var/log/wanctl`
- Runtime files live in `/run/wanctl`
- Active systemd units are `wanctl@<wan>.service` and optional `steering.service`

## Router Access

### MikroTik Router

**Router:** RB5009 at `10.10.99.1`

**REST API:** preferred transport
- Host: `10.10.99.1`
- Port: `443`
- Password source: `/etc/wanctl/secrets` via `ROUTER_PASSWORD`

**SSH Access:** still supported
```bash
ssh -i ~/.ssh/mikrotik_cake admin@10.10.99.1
```

**Key Location:** `~/.ssh/mikrotik_cake`

## Active Operational Flow

Primary scripts:
- `scripts/install.sh`
- `scripts/deploy.sh`
- `scripts/install-systemd.sh`

Primary unit files:
- `deploy/systemd/wanctl@.service`
- `deploy/systemd/steering.service`

Legacy timer-era helper scripts in `scripts/` are intentionally stubbed and should not be used as active deployment guidance.

## Development Commands

```bash
.venv/bin/pytest tests/ -v
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/wanctl/
.venv/bin/ruff format src/ tests/
```

Focused hot-path regression slice:

```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
```

## Useful Operational Checks

```bash
./scripts/soak-monitor.sh
ssh <host> 'journalctl -u wanctl@<wan> -f'
ssh <host> 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'
```

## Change Constraints

- Change conservatively; this is production network-control software.
- Do not alter control logic, thresholds, timing, or safety bounds without explicit approval.
- Keep the controller link-agnostic; deployment-specific behavior belongs in YAML.
- Keep docs and scripts aligned with the current service-based deployment model.

## Current References

Use these as the primary current docs:
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`
- `docs/GETTING-STARTED.md`
- `docs/CONFIGURATION.md`
- `docs/DEPLOYMENT.md`
- `docs/TESTING.md`
- `docs/STEERING.md`

## Current Validation Note

- Phase 196 Spectrum cake-primary documented B-leg exceptions were accepted for continuation, but the follow-up tcp_12down throughput check failed at 73.92243773827883 Mbps versus the 532 Mbps acceptance threshold; the A/B comparison remains blocked until passing throughput evidence exists.
