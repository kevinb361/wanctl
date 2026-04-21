# wanctl - Adaptive Dual-WAN Control System

**IMPORTANT:** Production network control system. Change conservatively.

## What It Does

`wanctl` is a long-running adaptive CAKE controller for MikroTik RouterOS with optional WAN steering.
It measures RTT and queue signals, adjusts shaping rates in real time, and runs continuously under systemd.

**Type:** Production (24/7), Python 3.11+, deployed to `/opt/wanctl`
**Version:** 1.38.0
**Cycle Interval:** 50ms (20Hz polling)

## Change Policy

- Explain risky changes before changing behavior.
- Never refactor core logic, algorithms, thresholds, or timing without approval.
- Prefer targeted fixes over broad cleanup in the control path.
- **Priority:** stability > safety > clarity > elegance

## Portable Controller Architecture

**NON-NEGOTIABLE:** The controller is link-agnostic. The same code must run across cable, DSL, fiber, and other deployments. Deployment-specific behavior belongs in YAML config, not Python branching.

See `docs/ARCHITECTURE.md` and `docs/CONFIGURATION.md`.

## Runtime Layout

```text
/opt/wanctl/          # Application code
/etc/wanctl/          # Config (*.yaml, secrets, SSH keys)
/var/lib/wanctl/      # State files
/var/log/wanctl/      # Logs
/run/wanctl/          # Runtime files
```

## RouterOS Integration

**Recommended:** REST API (typically lower latency than SSH)

```yaml
router:
  transport: "rest" # or "ssh"
  host: "10.10.99.1"
  password: "${ROUTER_PASSWORD}" # From /etc/wanctl/secrets
```

## Development Commands

Use the virtualenv directly:

```bash
.venv/bin/pytest tests/ -v
.venv/bin/pytest tests/test_foo.py -v
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/wanctl/
.venv/bin/ruff format src/ tests/
```

Focused hot-path regression slice:

```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
```

## Quick Operational Commands

```bash
./scripts/soak-monitor.sh
ssh <host> 'journalctl -u wanctl@<wan> -f'
ssh <host> 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'
```

## Architectural Spine (Read-Only Unless Explicitly Requested)

### Control Model

- All congestion decisions are based on RTT delta, not absolute RTT.
- Baseline RTT must stay frozen during load and only update under healthy/idle conditions.
- Rate decreases are immediate.
- Rate increases require sustained healthy cycles.

### State Logic

- Download uses a 4-state model: GREEN/YELLOW/SOFT_RED/RED.
- Upload uses a 3-state model: GREEN/YELLOW/RED.
- SOFT_RED clamps to floor and holds; it is not repeated decay.

### Flash Wear Protection

- Queue limits should only be sent to the router when values change.
- `last_applied_dl_rate` and `last_applied_ul_rate` tracking are part of the safety model.

### Steering Spine

- Steering is optional and binary: enabled or disabled.
- Only new latency-sensitive connections are rerouted.
- Autorate baseline RTT remains authoritative.

### Health / Observability

- Health and observability paths are part of the contract — do not break payload shape casually.

## Tuning Guidance

Do not recommend threshold or bounds changes casually. First read:

- `.planning/` phase research for the relevant area
- YAML comments in the active configs/examples
- `CHANGELOG.md`

“Pegged at bounds” is often by design, not automatically a bug.

## Service Model

Active deployment is service-based, not timer-based.

Current primary scripts:

- `scripts/install.sh`
- `scripts/deploy.sh`
- `scripts/install-systemd.sh`

Current units:

- `deploy/systemd/wanctl@.service`
- `deploy/systemd/steering.service`

Do not reintroduce timer-era guidance into active docs or scripts.

## Performance Characteristics

**Cycle Interval:** 50ms (production standard)
**Congestion Response:** sub-second detection under normal operating conditions
**Startup Maintenance:** watchdog-safe, time-budgeted cleanup/downsampling
**Periodic Maintenance:** background cleanup and retention work must remain bounded

See `docs/PRODUCTION_INTERVAL.md` for deeper background.

## Documentation

Primary references:

- `README.md`
- `docs/GETTING-STARTED.md`
- `docs/CONFIGURATION.md`
- `docs/TESTING.md`
- `docs/DEPLOYMENT.md`
- `docs/STEERING.md`
- `docs/TRANSPORT_COMPARISON.md`
