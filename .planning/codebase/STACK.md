# Technology Stack

**Analysis Date:** 2026-01-21

## Languages

**Primary:**
- Python 3.12 - Core application, daemons (autorate_continuous, steering), calibration tools in `src/wanctl/`

**Secondary:**
- Bash - Docker entrypoint (`docker/entrypoint.sh`), deployment scripts, systemd integration
- YAML - Configuration files (`configs/*.yaml`), supported via PyYAML
- JSON - State persistence, health check responses, metrics exposition

## Runtime

**Environment:**
- Python 3.12 runtime (tested on 3.12, requires 3.11+ for type hints)
- Linux kernel (Ubuntu/Debian-based containers, systemd support)
- Container base: `python:3.12-slim` official image

**Package Manager:**
- uv - Development environment (fast dependency resolution)
- pip - Production container installation
- Lockfile: `requirements.txt` (production pinned versions) and `pyproject.toml` (dev/optional)

## Frameworks

**Core:**
- None - Standard library-centric architecture (socket, subprocess, logging, http.server)

**Testing:**
- pytest 8.0.0+ - Unit test runner, discovery in `tests/` directory
- Config: Standard pytest discovery, fixture support via conftest.py

**Build/Dev:**
- ruff 0.4.0+ - Linting (E, W, F, I, B, UP rules) and formatting (100 char line length)
- mypy 1.10.0+ - Static type checking (python_version: 3.12, check_untyped_defs enabled)
- setuptools - Package building (backend in pyproject.toml)
- black conceptually (100 char via ruff formatter configuration)

## Key Dependencies

**Critical (Production):**
- requests 2.31.0+ - HTTP/HTTPS REST API calls to RouterOS (used in `routeros_rest.py`)
- paramiko 3.4.0+ - SSH client for RouterOS command execution (used in `routeros_ssh.py`, persistent connections reduce latency 6x vs subprocess SSH: 30-50ms vs ~200ms)
- pyyaml 6.0.1+ - YAML configuration file parsing (safe_load for untrusted configs)
- pexpect 4.9.0+ - TTY/subprocess control for ping execution and interactive shell fallback

**Development:**
- pyflakes 3.4.0+ - Static code analysis
- pytest 8.0.0+ - Test framework

## Configuration

**Environment Variables:**
- WANCTL_CONFIG - Path to main daemon config (default: `/etc/wanctl/wan.yaml`)
- WANCTL_STEERING_CONFIG - Path to steering daemon config (default: `/etc/wanctl/steering.yaml`)
- WANCTL_MODE - Daemon mode override (continuous, calibrate, steering, oneshot, shell)
- PYTHONPATH - Set to `/opt/wanctl` in containers
- PYTHONUNBUFFERED - Set to 1 for real-time log output

**Build Configuration Files:**
- `pyproject.toml` - Project metadata, dependencies, ruff/mypy settings, entry points
- `docker/Dockerfile` - Multi-stage image, system dependencies (openssh-client, iputils-ping, netperf), FHS directory structure
- `docker/docker-compose.yml` - Multi-container orchestration example (wan1, wan2, steering services)
- `requirements.txt` - Pinned production dependencies for pip

**No .env files:** Secrets managed via environment variables (injected at runtime) or YAML config references like `${ROUTER_PASSWORD}`

## Platform Requirements

**Development:**
- Python 3.11+ (3.12 tested)
- Linux, macOS, or WSL2 (requires ping and network tools)
- Virtual environment: venv or uv
- Make (optional, for `make ci`, `make lint`, `make test`)

**Production:**
- Linux with kernel 5.10+ (for CAKE queue discipline)
- Python 3.12 runtime
- System packages: openssh-client, iputils-ping (from Dockerfile)
- Network access to MikroTik RouterOS device
- FHS-compliant filesystem:
  - `/opt/wanctl/` - Application code (755 root:wanctl)
  - `/etc/wanctl/` - Configuration, SSH keys (750 root:wanctl)
  - `/var/lib/wanctl/` - State files, lock files (750 wanctl:wanctl)
  - `/var/log/wanctl/` - Log files (750 wanctl:wanctl)
  - `/run/wanctl/` - Runtime files (750 wanctl:wanctl)
- User: `wanctl` non-root user (UID/GID arbitrary)
- Docker: Host network mode required (`network_mode: host` in compose)

## Entry Points

**Console Scripts (from pyproject.toml):**
- `wanctl` → `wanctl.autorate_continuous:main` - Main continuous CAKE tuning daemon
- `wanctl-calibrate` → `wanctl.calibrate:main` - Interactive bandwidth discovery
- `wanctl-steering` → `wanctl.steering.daemon:main` - Multi-WAN steering controller

**Docker Entrypoint:** `/usr/local/bin/entrypoint.sh`
- Modes: `continuous` (default), `calibrate`, `steering`, `oneshot`, `shell`, `help`
- Validation: YAML syntax check, SSH key permission audit (requires 600 or 400)
- Signal Handling: SIGTERM, SIGINT for graceful shutdown

## Performance Characteristics

**Cycle Interval:** 0.05 seconds (50ms, 20Hz polling)
- 40x faster than 2-second baseline (v1.0)
- Congestion detection latency: 50-100ms (sub-second response)
- Proven stable: 0% router CPU idle, 45% peak under RRUL stress load
- Utilization: 60-80% (30-40ms execution per 50ms interval)
- See `docs/PRODUCTION_INTERVAL.md` for validation results

**Connection Optimization:**
- Persistent SSH (paramiko): 30-50ms per command vs ~200ms for subprocess SSH (6-7x faster)
- REST API (requests): ~50ms per state query (2x faster than SSH for JSON responses)
- Reused connections maintained across daemon lifetime with automatic reconnection

**RTT Measurement:**
- Strategy: Median-of-three samples (handles reflector variation)
- Hosts: 1.1.1.1, 8.8.8.8, 9.9.9.9 (public, reliable, diverse)
- Ping timeout: 0.5 seconds per attempt (reduced from 1s for sub-100ms cycle targets)
- Fallback: TCP connections to HTTPS ports (443) if ICMP blocked
- Samples: 3 concurrent pings per cycle, aggregated via statistics.median()

## Version

**Current:** 1.1.0 (First Stable Release - 2026-01-13)
- 594 unit tests passing
- Phase2BController integrated (dry-run validation)
- TCP RTT fallback for ICMP blackout (Spectrum ISP fix, v1.1.0)
- Cycle interval: 50ms production standard

---

*Stack analysis: 2026-01-21*
