# wanctl v1.0.0-rc3

**Release Candidate 3** - Package renamed from `cake` to `wanctl` to avoid confusion with the CAKE qdisc project.

## What is wanctl?

wanctl is an adaptive CAKE bandwidth controller for MikroTik RouterOS. It eliminates bufferbloat by dynamically adjusting queue limits based on real-time latency measurements.

### Key Features

- **Automatic Bufferbloat Elimination** - Maintains near-zero latency under load
- **4-State Congestion Control** - GREEN/YELLOW/SOFT_RED/RED state machine for download
- **Multi-WAN Steering** - Optional latency-sensitive traffic routing during congestion
- **RouterOS Integration** - Native SSH control of CAKE queue trees
- **Zero Configuration Drift** - EWMA-based tracking with state persistence

## Installation

```bash
git clone https://github.com/kevinb361/wanctl.git
cd wanctl
pip install .
```

Or for system-wide deployment:

```bash
sudo ./scripts/install.sh
```

See [QUICKSTART.md](docs/QUICKSTART.md) for detailed setup instructions.

## What's New in RC3

### Package Rename: `cake` → `wanctl`

**BREAKING CHANGE**: The Python package has been renamed from `cake` to `wanctl` to avoid confusion with the [CAKE qdisc](https://www.bufferbloat.net/projects/codel/wiki/Cake/) project.

- Renamed `src/cake/` → `src/wanctl/`
- All imports changed from `cake.*` to `wanctl.*`
- Module invocation changed: `python -m wanctl.autorate_continuous`
- Updated all documentation, scripts, and deployment files

**Migration**: If upgrading from RC2, update any custom scripts that import from `cake.*` to use `wanctl.*` instead.

### From RC2

#### Packaging Fixes (from RC1 audit)
- **Added `__version__`** - Package now exports version for programmatic access
- **Added CLI entry points** - `wanctl`, `wanctl-calibrate`, `wanctl-steering` commands
- **Fixed CLI argument** - Changed `--configs` to `--config` to match systemd unit
- **Synced dependency versions** - `requirements.txt` now matches `pyproject.toml`
- **Fixed systemd URLs** - Corrected GitHub repository URLs in all unit files

### From RC1

#### Repository Cleanup
- Removed deprecated modules and analysis scripts
- Removed site-specific configurations
- Standardized file permissions (644 for files, 755 for scripts)

#### Security Fixes
- **Fixed race condition in lock file** - Now uses atomic `O_EXCL` creation
- **Fixed temp file permissions** - Explicit 0600 permissions on state files

#### Developer Experience
- Added GitHub Actions CI (lint + test on every PR)
- Added `DEVELOPMENT.md` with setup and contribution guide
- Added `CONFIG_SCHEMA.md` with full configuration reference
- Added ruff linting configuration
- Pinned all dependency versions
- Added "Good First Issues" guidance for contributors

#### Documentation
- Complete configuration schema documentation
- Improved CONTRIBUTING.md with test instructions
- Example configs for fiber, cable, DSL, and multi-WAN setups

## System Requirements

- Python 3.12+
- MikroTik RouterOS with CAKE queues configured
- SSH key authentication to router
- Linux host (tested on Debian 12, Ubuntu 22.04)

## Usage

### CLI Commands (after pip install)

```bash
# Main controller
wanctl --config /etc/wanctl/wan1.yaml

# Calibration wizard
wanctl-calibrate --wan-name wan1 --router 192.168.1.1

# Steering daemon (multi-WAN)
wanctl-steering --config /etc/wanctl/steering.yaml
```

### Python Module

```bash
python -m wanctl.autorate_continuous --config /etc/wanctl/wan1.yaml
python -m wanctl.calibrate --wan-name wan1 --router 192.168.1.1
python -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml
```

## Configuration

Minimal configuration example:

```yaml
wan_name: "wan1"

router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"

queues:
  download: "WAN-Download"
  upload: "WAN-Upload"

continuous_monitoring:
  enabled: true
  download:
    floor_red_mbps: 50
    ceiling_mbps: 500
  upload:
    floor_mbps: 10
    ceiling_mbps: 50
```

See `configs/examples/` for complete examples.

## Known Limitations

- RouterOS-only (OpenWrt, pfSense backends welcome as contributions)
- Requires pre-configured CAKE queues on router
- Single-threaded design (one instance per WAN)

## Testing This Release

This is a release candidate. Please test and report issues:

1. **Fresh install** - Follow QUICKSTART.md on a new system
2. **Upgrade** - If upgrading from RC2, update any `cake.*` imports to `wanctl.*`
3. **Multi-WAN** - Test steering if using dual-WAN setup
4. **pip install** - Verify `wanctl --help` works after `pip install .`

Report issues at: https://github.com/kevinb361/wanctl/issues

## Acknowledgments

- [LibreQoS](https://libreqos.io/) - Inspiration for CAKE-based QoS
- [Flent](https://flent.org/) - Latency measurement methodology
- [CAKE](https://www.bufferbloat.net/projects/codel/wiki/Cake/) - The qdisc that makes this work
- Claude (Anthropic) - AI-assisted development

## License

GPL-2.0 - See [LICENSE](LICENSE) for details.

---

**Full Changelog**: https://github.com/kevinb361/wanctl/compare/v1.0.0-rc2...v1.0.0-rc3
