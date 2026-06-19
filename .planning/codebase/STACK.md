# Technology Stack

**Analysis Date:** 2026-06-19

## Languages

**Primary:**
- Python 3.11+ — all application logic, daemons, CLIs, and test suite
  - `pyproject.toml` declares `requires-python = ">=3.11"`; mypy configured for `python_version = "3.11"`
  - Production VM (`requirements-production.txt`) runs system Python 3.12 (`/usr/bin/python3`)
  - Dev venv is Python 3.12 (`.venv/pyvenv.cfg`)

**Secondary:**
- Bash — deployment scripts (`scripts/install.sh`, `scripts/deploy.sh`, `scripts/install-systemd.sh`), cake-autorate external config (`configs/cake-autorate/config.spectrum.sh`, `configs/cake-autorate/config.att.sh`), soak/canary scripts
- YAML — all per-WAN and steering configuration (`configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml`, `configs/examples/*.yaml.example`)
- nftables — bridge QoS DSCP classification (`deploy/nftables/bridge-qos.nft`)

## Runtime

**Environment:**
- Linux (Debian 13 / systemd) — production target is Proxmox VM running at `/opt/wanctl`
- System capabilities required: `CAP_NET_RAW` (ICMP sockets via icmplib), `CAP_NET_ADMIN` (tc/netlink CAKE updates)
- CPU affinity: wanctl daemons pinned to CPUs 1–2 via systemd `CPUAffinity=1-2`
- Memory limits: 512 MB `MemoryHigh` / 640 MB `MemoryMax` per service unit

**Package Manager:**
- `uv` (declared in `[tool.uv]` in `pyproject.toml`) — used in development
- `pip3 --break-system-packages` — used in production install scripts (`scripts/install.sh`) targeting system Python
- Lockfile: `requirements-production.txt` — manually maintained `pip freeze` snapshot from production VM (not a uv lockfile)

## Frameworks

**Core:**
- None — wanctl is a stdlib-heavy Python daemon; no web/async/WSGI framework

**Dashboard (optional feature):**
- Textual `>=0.50` — TUI dashboard (`src/wanctl/dashboard/`) accessed via `wanctl-dashboard` entry point
- httpx `>=0.27` — async HTTP polling for dashboard health endpoint (`src/wanctl/dashboard/poller.py`)

**Testing:**
- pytest `>=8.0.0` — primary test runner; config in `pyproject.toml [tool.pytest.ini_options]`
- pytest-cov `>=4.1.0` — branch coverage; 90% `fail_under` enforced via `make coverage-check`
- pytest-xdist `>=3.8.0` — parallel test execution
- pytest-timeout `>=2.4.0` — 30s per-test hard timeout (`timeout_method = "thread"`)
- Default `addopts` skips `integration` marker tests (`-m 'not integration'`)

**Build/Dev:**
- Ruff `>=0.4.0` — combined linter + formatter (`line-length = 100`, `target-version = "py311"`); replaces Black, isort, flake8
- MyPy `>=1.10.0` — strict type checking (`disallow_untyped_defs = true`, `warn_return_any = true`, `no_implicit_optional = true`)
- Vulture — dead code detection; whitelist in `vulture_whitelist.py`
- pip-audit `>=2.10.0` — dependency CVE scanning (`make security-deps`)
- Bandit `>=1.9.3` — static security analysis (skips B101/B311/B601 by design; see `pyproject.toml`)
- detect-secrets `>=1.5.0` — secrets scanning (`make security-secrets`)
- pip-licenses `>=5.0.0` — license compliance (`make security-licenses`)

## Key Dependencies

**Critical (core runtime):**
- `icmplib>=3.0.4` — default RTT measurement backend; used in `src/wanctl/rtt_measurement.py` for in-process ICMP probes without subprocess fork; production pin 3.0.4
- `paramiko>=3.4.0` — SSH transport for RouterOS command execution (`src/wanctl/routeros_ssh.py`); persistent connection reuse; production pin 4.0.0
- `requests>=2.33.0` — HTTP client for RouterOS REST API (`src/wanctl/routeros_rest.py`) and Discord webhook delivery (`src/wanctl/webhook_delivery.py`); production pin 2.32.3 (below declared minimum — CVE-2026-25645 flagged in `requirements-production.txt`)
- `pyyaml>=6.0.1` — YAML config parsing throughout `src/wanctl/autorate_config.py` and `src/wanctl/config_base.py`; production pin 6.0.2

**Infrastructure:**
- `tabulate>=0.9.0` — table formatting for `wanctl-history` and `wanctl-operator-summary` CLI output
- `pyroute2>=0.9.5` — optional netlink backend (`src/wanctl/backends/netlink_cake.py`); installed with `pip install wanctl[netlink]`; replaces subprocess `tc` calls for CAKE bandwidth updates (netlink ~0.3ms vs subprocess ~3.1ms)
- `textual>=0.50` + `httpx>=0.27` — optional dashboard; installed with `pip install wanctl[dashboard]`
- `systemd-python==235` — systemd watchdog and sd_notify integration (`src/wanctl/systemd_utils.py`); production system package; graceful no-op fallback when unavailable

**Transitive (production):**
- `cryptography==46.0.5`, `bcrypt==5.0.0`, `PyNaCl==1.6.2` — paramiko SSH cryptographic dependencies
- `urllib3==2.3.0`, `certifi==2025.1.31` — requests TLS chain

## Configuration

**Environment:**
- Per-WAN config files: YAML at `/etc/wanctl/{wan_name}.yaml` (e.g., `spectrum.yaml`, `att.yaml`, `steering.yaml`)
- Secrets file: `/etc/wanctl/secrets` — sourced as systemd `EnvironmentFile=-/etc/wanctl/secrets`
- Env var references in YAML: `${VAR_NAME}` syntax expanded at config load time in Python (`os.environ.get`)
- Required env vars at runtime: `ROUTER_PASSWORD` (RouterOS REST auth), `DISCORD_WEBHOOK_URL` (alerting webhook)
- Runtime path env vars (set in systemd units): `WANCTL_STATE_DIR=/var/lib/wanctl`, `WANCTL_LOG_DIR=/var/log/wanctl`, `WANCTL_RUN_DIR=/run/wanctl`
- `WANCTL_LOG_FORMAT` — controls text vs JSON log format (`src/wanctl/logging_utils.py`)

**Build:**
- `pyproject.toml` — all project metadata, dependency declarations, Ruff, MyPy, pytest, coverage, Bandit, Vulture config
- `Makefile` — developer workflow: `make test`, `make lint`, `make type`, `make ci`, `make coverage`, `make security`, `make dead-code`, `make check-deps`

## Platform Requirements

**Development:**
- Python 3.11+ with uv (or pip3)
- `.venv/` managed locally (prompt: `cake`)
- `make ci` runs: ruff lint → mypy type check → pytest with 90% coverage → vulture dead-code → pip-audit → bandit → boundary/brittleness checks

**Production:**
- Linux with systemd (Debian 13 on Proxmox VM)
- `fping` binary on PATH — required for cake-autorate external mode (pinger in `configs/cake-autorate/config.spectrum.sh`) and optional `fping` RTT backend (`src/wanctl/fping_measurement.py`)
- `irtt` binary on PATH — optional IRTT UDP RTT measurement (`src/wanctl/irtt_measurement.py`); disabled in production config (`irtt.enabled: false`)
- `tc` (iproute2) — required for `linux-cake` subprocess backend (`src/wanctl/backends/linux_cake.py`)
- `pyroute2` — optional, required only for `linux-cake-netlink` transport (`src/wanctl/backends/netlink_cake.py`)
- `netperf` — only for `wanctl-calibrate` tool (`src/wanctl/calibrate_measurements.py`); not a runtime dependency
- FHS layout: app at `/opt/wanctl/`, config at `/etc/wanctl/`, state at `/var/lib/wanctl/`, logs at `/var/log/wanctl/`, PID/locks at `/run/wanctl/`
- Log rotation: `configs/logrotate-wanctl` → `/etc/logrotate.d/wanctl` on production hosts

---

*Stack analysis: 2026-06-19*
