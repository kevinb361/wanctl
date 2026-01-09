# Technology Stack

**Analysis Date:** 2026-01-09

## Languages

**Primary:**
- Python 3.12 - All application code in `src/wanctl/`

**Secondary:**
- Bash - Deployment and utility scripts in `scripts/` directory
- YAML - Configuration files in `configs/`
- Dockerfile - Container definition in `docker/Dockerfile`

## Runtime

**Environment:**
- Python 3.12 (specified in `docker/Dockerfile` line 9)
- Linux (requires Unix utilities: ping, openssh-client, bash)
- systemd support for service management and timers

**Package Manager:**
- uv - Fast Python package manager
- Lockfile: `uv.lock` (production dependency freeze)

## Frameworks

**Core:**
- None (pure Python - no web framework)

**Testing:**
- pytest - Unit test framework (`pyproject.toml`)
- pytest-asyncio - Async test support

**Build/Dev:**
- setuptools - Build system (`pyproject.toml`)
- Ruff - Code linting and formatting (`pyproject.toml` line 35)

## Key Dependencies

**Critical Network:**
- requests >= 2.31.0 - HTTP client for RouterOS REST API (`src/wanctl/routeros_rest.py`)
- paramiko >= 3.4.0 - SSH client for RouterOS SSH fallback (`src/wanctl/routeros_ssh.py`)

**Configuration & Utilities:**
- PyYAML >= 6.0.1 - YAML parsing for config files (`src/wanctl/config_base.py`)
- pexpect >= 4.9.0 - Expect-like scripting for interactive commands
- urllib3 - HTTP networking (transitive via requests)
- certifi - SSL certificate validation

**Development:**
- pyflakes - Static code analysis
- pytest >= 8.0.0 - Test framework

## Configuration

**Environment:**
- YAML configuration files in `/etc/wanctl/` (production)
- Config examples in `configs/examples/`
- Supports environment variable substitution (e.g., `${ROUTER_PASSWORD}`)

**Build:**
- `pyproject.toml` - Project configuration and dependencies
- `.dockerignore` - Excludes files from Docker builds
- `docker/Dockerfile` - Multi-stage container builds

## Platform Requirements

**Development:**
- Python 3.12 or later
- Linux/macOS/Windows (for testing)
- Virtual environment support (venv or uv)

**Production:**
- Linux (Ubuntu 20.04+, or any distribution with systemd)
- Python 3.12
- Network access to MikroTik RouterOS device (REST API on 443 or SSH on 22)
- systemd for service/timer management
- FHS-compliant paths (`/etc/wanctl`, `/var/lib/wanctl`, `/var/log/wanctl`)

---

*Stack analysis: 2026-01-09*
*Update after major dependency changes*
