# wanctl Agent Guide

Production network control system. Change conservatively.

## What This Repo Does

`wanctl` is a long-running adaptive CAKE controller for MikroTik RouterOS with optional multi-WAN steering.
It measures RTT and queue signals, adjusts shaping rates in real time, and runs continuously under systemd.

Current runtime assumptions:
- Python `>=3.11`
- Installed code under `/opt/wanctl`
- Config under `/etc/wanctl`
- State under `/var/lib/wanctl`
- Logs under `/var/log/wanctl`
- Runtime files under `/run/wanctl`

## Change Policy

- Stability is the top priority.
- Explain risky changes before making them.
- Do not change core control logic, thresholds, timing, or safety bounds without explicit approval.
- Prefer targeted fixes over refactors.
- Treat docs, scripts, and deployment commands as production-facing interfaces.

## Architectural Rules

These are the project spine and should be treated as read-only unless the task explicitly says otherwise.

- The controller is link-agnostic. Deployment-specific behavior belongs in YAML, not Python branches.
- Congestion decisions are based on RTT delta, not absolute RTT.
- Baseline RTT must only update during idle/healthy conditions.
- Rate decreases happen immediately; rate increases require sustained healthy cycles.
- Flash-wear protection matters: do not send queue updates unless values changed.
- Steering must not perturb the autorate baseline logic.
- Health and observability paths are part of the contract; avoid breaking payload shape casually.

## Active Operational Flow

Use the current service-based deployment flow.

Primary scripts:
- `scripts/install.sh`
- `scripts/deploy.sh`
- `scripts/install-systemd.sh`

Current units:
- `deploy/systemd/wanctl@.service`
- `deploy/systemd/steering.service`

Do not reintroduce timer-based guidance into active docs or scripts. Legacy timer-era helper scripts in `scripts/` are intentionally stubbed out.

## Development Commands

Use the project virtualenv directly.

```bash
.venv/bin/pytest tests/ -v
.venv/bin/pytest tests/test_foo.py -v
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/wanctl/
.venv/bin/ruff format src/ tests/
```

Focused regression slice that has been useful for hot-path work:

```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
```

## Operational Checks

Useful commands during investigation:

```bash
./scripts/soak-monitor.sh
ssh <host> 'journalctl -u wanctl@<wan> -f'
ssh <host> 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'
```

## Documentation Expectations

When updating docs or scripts, keep these current facts aligned:
- Python requirement is `>=3.11`
- Active startup path is `wanctl@<wan>.service`
- Optional steering runs as `steering.service`
- Config examples live under `configs/examples/`
- Remote deployment uses `scripts/deploy.sh`

## Good Defaults For Agents

- Read the local code before making assumptions.
- Verify claims against the repo, especially docs and helper scripts.
- Preserve user changes in a dirty worktree.
- Prefer small, reviewable edits.
- Run the narrowest relevant validation after each change.
