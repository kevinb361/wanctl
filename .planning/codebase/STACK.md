# Technology Stack

**Analysis Date:** 2026-03-10

## Languages

**Primary:**
- Python 3.12 - All application logic, daemons, CLI tools in `src/wanctl/`

**Secondary:**
- YAML - Configuration files in `/etc/wanctl/` and `configs/`
- SQL (SQLite dialect) - Schema and queries in `src/wanctl/storage/`
- Bash - Entrypoint `docker/entrypoint.sh`, monitoring scripts in `scripts/`
- JSON - State persistence, health check responses

## Runtime

**Environment:**
- CPython 3.12 (requires >=3.11 per `pyproject.toml`)
- Production: system Python `/usr/bin/python3` (no venv on deployment hosts)
- Development: `.venv/` managed by `uv`

**Package Manager:**
- `uv` — project management and lockfile generation
- Lockfile: `uv.lock` present (revision 3, hashed wheel URLs)
- `pip` — production container install (Dockerfile uses `pip install --no-cache-dir`)

## Frameworks

**Core:**
- None — stdlib-first: `http.server`, `sqlite3`, `threading`, `subprocess`, `socket`

**Testing:**
- `pytest` >=8.0.0 — test runner; config in `pyproject.toml` `[tool.pytest.ini_options]`
- `pytest-cov` >=4.1.0 — coverage enforcement (`fail_under = 90` in `[tool.coverage.report]`)

**Build/Dev:**
- `setuptools` — build backend (`pyproject.toml` `[build-system]`)
- `uv` — dependency resolution and venv management
- `ruff` >=0.4.0 — linting and formatting (target: py312, line-length: 100, rules: E/W/F/I/B/UP)
- `mypy` >=1.10.0 — type checking (Python 3.12 mode, `check_untyped_defs = true`, `ignore_missing_imports = true`)

## Key Dependencies

**Critical:**
- `requests` >=2.31.0 — MikroTik RouterOS REST API HTTP client (`src/wanctl/routeros_rest.py`)
- `paramiko` >=3.4.0 — MikroTik RouterOS SSH transport with persistent connections (`src/wanctl/routeros_ssh.py`)
- `icmplib` >=3.0.4 — Raw ICMP ping for sub-millisecond RTT measurement (`src/wanctl/rtt_measurement.py`); requires `CAP_NET_RAW` capability
- `pyyaml` >=6.0.1 — Configuration file parsing via `yaml.safe_load` (`src/wanctl/config_base.py`)
- `cryptography` >=46.0.5 — SSH key handling (transitive dependency via paramiko)

**Supporting:**
- `pexpect` >=4.9.0 — Legacy SSH interaction; also in `requirements.txt` for production containers
- `tabulate` >=0.9.0 — CLI table output in `src/wanctl/history.py`

**Optional Runtime:**
- `systemd.daemon` (python-systemd) — watchdog and status notifications; gracefully absent if not installed (`src/wanctl/systemd_utils.py` uses try/except ImportError)

**Security / Dev Only:**
- `pip-audit` >=2.10.0 — dependency CVE scanning (`make security-deps`)
- `bandit` >=1.9.3 — static security analysis (`make security-code`); skips B101, B311, B601
- `detect-secrets` >=1.5.0 — secret leak detection (`make security-secrets`)
- `pip-licenses` >=5.0.0 — license compliance; fails on GPL-2/3, AGPL-3 (`make security-licenses`)
- `pyflakes` >=3.4.0 — unused import detection

## Configuration

**Environment Variables:**
- `WANCTL_CONFIG` — path to autorate daemon config (default: `/etc/wanctl/wan.yaml`)
- `WANCTL_STEERING_CONFIG` — path to steering daemon config
- `WANCTL_STATE_DIR` — state file directory (default: `/var/lib/wanctl`)
- `WANCTL_LOG_DIR` — log directory (default: `/var/log/wanctl`)
- `WANCTL_RUN_DIR` — runtime/lock directory (default: `/run/wanctl`)
- `ROUTER_PASSWORD` — referenced from YAML as `password: "${ROUTER_PASSWORD}"`; resolved at runtime in `src/wanctl/routeros_rest.py` via `os.environ`

**Config Files:**
- `pyproject.toml` — single source of truth for metadata, deps, ruff/mypy/coverage/pytest/bandit settings
- `Makefile` — task runner (`make ci`, `make test`, `make lint`, `make type`, `make format`, `make security`)
- YAML per WAN: `/etc/wanctl/wan1.yaml`, `/etc/wanctl/steering.yaml` etc. (see `configs/examples/`)
- Secrets: `/etc/wanctl/secrets` loaded via systemd `EnvironmentFile=-/etc/wanctl/secrets`

## Console Entry Points

- `wanctl` → `wanctl.autorate_continuous:main` — autorate CAKE tuning daemon
- `wanctl-calibrate` → `wanctl.calibrate:main` — interactive bandwidth discovery
- `wanctl-steering` → `wanctl.steering.daemon:main` — multi-WAN steering controller
- `wanctl-history` → `wanctl.history:main` — CLI metrics history query tool

## Platform Requirements

**Development:**
- Linux (Ubuntu), Python 3.12, `uv` for venv
- `CAP_NET_RAW` capability required for raw ICMP (icmplib)
- Dev commands via `Makefile` (`.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/mypy`)

**Production (systemd):**
- Linux with systemd, non-root `wanctl` user
- `systemd/wanctl@.service` template unit; `AmbientCapabilities=CAP_NET_RAW`
- `systemd/steering.service` for steering daemon
- Circuit breaker: `StartLimitBurst=5` / `StartLimitIntervalSec=300`; watchdog `WatchdogSec=30s`

**Production (Docker):**
- `docker/Dockerfile` — `python:3.12-slim` base; system packages: `openssh-client`, `iputils-ping`, `netperf`
- `docker/docker-compose.yml` — multi-container reference (wan1, wan2, steering services)
- `network_mode: host` required for accurate RTT measurements (direct host network stack)
- FHS paths: `/opt/wanctl` (code), `/etc/wanctl` (config), `/var/lib/wanctl` (state+db), `/var/log/wanctl` (logs), `/run/wanctl` (locks)

---

*Stack analysis: 2026-03-10*
