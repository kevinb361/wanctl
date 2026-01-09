# wanctl

[![License: GPL v2](https://img.shields.io/badge/License-GPL_v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)

**Adaptive CAKE bandwidth control for Mikrotik RouterOS.**

Reduces bufferbloat by continuously monitoring RTT and adjusting queue limits in real-time. Supports multi-WAN with optional intelligent traffic steering.

## Features

- **Continuous RTT monitoring** - 2-second control loops for responsive adaptation
- **Multi-state congestion control** - GREEN/YELLOW/SOFT_RED/RED state machine
- **Multi-signal detection** - RTT + CAKE drops + queue depth for accuracy
- **REST API transport** - 2x faster than SSH (~50ms vs ~150ms latency)
- **Optional WAN steering** - Route latency-sensitive traffic during congestion
- **Config-driven** - Same code works for fiber, cable, DSL, or any connection
- **FHS compliant** - Proper Linux directory layout and service user
- **Hardened security** - Input validation prevents command injection, EWMA bounds checking, configurable RTT thresholds
- **Production reliability** - Bounded memory with deques, file locking for concurrent safety, graceful CAKE stats degradation

## Quick Start

### Prerequisites

- Mikrotik router running RouterOS 7.x with CAKE queues configured
- Linux host (LXC container, VM, or bare metal) with Python 3.12+
- REST API enabled on router (recommended) or SSH key authentication

### Installation

```bash
# Clone the repository
git clone https://github.com/kevinb361/wanctl.git
cd wanctl

# Run installation with interactive setup wizard (recommended)
sudo ./scripts/install.sh
```

The **interactive setup wizard** guides you through:

- Router connection setup (REST API or SSH)
- Automated connection testing and validation
- Queue discovery from your router
- Connection-type presets (cable/DSL/fiber) with optimized defaults
- Multi-WAN architecture guidance
- Optional traffic steering configuration

**Alternative installation modes:**

```bash
# Non-interactive install (for automation)
sudo ./scripts/install.sh --no-wizard

# Re-run wizard on existing installation
sudo ./scripts/install.sh --reconfigure

# Uninstall wanctl
sudo ./scripts/install.sh --uninstall
```

After wizard completion, enable the service:

```bash
sudo systemctl enable --now wanctl@wan1.timer
```

### Transport Setup

**REST API (recommended):**

```bash
# Add password to secrets file (loaded by systemd as environment variable)
sudo nano /etc/wanctl/secrets
# Add line: ROUTER_PASSWORD=your_router_password
```

In your config, reference the environment variable:

```yaml
router:
  transport: "rest"
  host: "192.168.1.1"
  user: "admin"
  password: "${ROUTER_PASSWORD}" # Expanded from /etc/wanctl/secrets
  port: 443
  verify_ssl: false
```

The password is never stored in the config file - systemd loads `/etc/wanctl/secrets` via `EnvironmentFile` and the `${VAR}` syntax is expanded at runtime.

**SSH (alternative):**

```bash
# Copy your router SSH key
sudo cp ~/.ssh/router_key /etc/wanctl/ssh/router.key
sudo chown wanctl:wanctl /etc/wanctl/ssh/router.key
sudo chmod 600 /etc/wanctl/ssh/router.key
```

In your config, set:

```yaml
router:
  transport: "ssh"
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"
```

### Remote Deployment

Deploy from your development machine to a target host:

```bash
./scripts/deploy.sh wan1 target-hostname
./scripts/deploy.sh wan2 192.168.1.100 --with-steering
```

## How It Works

Every 2 seconds:

1. **Measure RTT** to reference hosts (1.1.1.1, 8.8.8.8, 9.9.9.9)
2. **Track baseline** RTT via slow EWMA (only updates when idle)
3. **Calculate delta** = loaded_rtt - baseline_rtt
4. **Determine state** based on delta thresholds
5. **Adjust bandwidth** limits on RouterOS CAKE queues
6. **Apply floors** based on current state (policy enforcement)

### State Machine

```
           delta <= 15ms
    ┌─────────────────────────┐
    │                         │
    ▼         15-45ms         │
  GREEN ───────────────► YELLOW
    ▲                         │
    │         45-80ms         ▼
    │     ┌───────────── SOFT_RED
    │     │                   │
    │     │       >80ms       ▼
    └─────┴───────────────── RED
         (recovery requires
          sustained GREEN)
```

**State-dependent floors** prevent bandwidth collapse:

- GREEN: High floor (e.g., 550 Mbps) - normal operation
- YELLOW: Moderate floor (e.g., 350 Mbps) - early warning
- SOFT_RED: Aggressive floor (e.g., 275 Mbps) - RTT-only congestion
- RED: Emergency floor (e.g., 200 Mbps) - hard congestion

## Configuration

Example configs are provided for common connection types:

| Config                  | Use Case                         |
| ----------------------- | -------------------------------- |
| `wan1.yaml.example`     | Generic primary WAN              |
| `wan2.yaml.example`     | Generic secondary WAN            |
| `fiber.yaml.example`    | GPON/XGS-PON fiber (low latency) |
| `cable.yaml.example`    | DOCSIS cable (variable latency)  |
| `dsl.yaml.example`      | DSL/VDSL (sensitive upload)      |
| `steering.yaml.example` | Multi-WAN traffic steering       |

Copy to `/etc/wanctl/` and customize for your setup.

## Directory Structure

```
/opt/wanctl/           # Code
/etc/wanctl/           # Configuration
  ├── wan1.yaml        # WAN config
  └── ssh/router.key   # Router SSH key
/var/lib/wanctl/       # State files (EWMA persistence)
/var/log/wanctl/       # Logs
/run/wanctl/           # Lock files
```

## Multi-WAN Steering (Optional)

For dual-WAN setups, the steering daemon routes latency-sensitive traffic to the healthier WAN during congestion:

```bash
# Enable steering
sudo systemctl enable --now steering.timer
```

**What gets steered:** VoIP, gaming, DNS, SSH, interactive web
**What stays:** Bulk downloads, video streaming, background traffic

Steering uses multi-signal detection (RTT + CAKE drops + queue depth) with hysteresis to prevent flapping.

## Monitoring

```bash
# Service status
systemctl status wanctl@wan1.timer

# Live logs
journalctl -u wanctl@wan1 -f
tail -f /var/log/wanctl/wan1.log

# Current state
cat /var/lib/wanctl/wan1_state.json
```

**Healthy output:**

```
[GREEN/GREEN] RTT=25.5ms, baseline=24.0ms, delta=1.5ms | DL=940M, UL=38M
```

## Real-World Test: Congestion Response

Here's actual output from a stress test on a 940/38 Mbps Spectrum cable connection. Eight parallel netperf streams were used to saturate the link:

### Test Timeline

```
Time      State         Delta    Upload BW   RTT      Event
────────────────────────────────────────────────────────────────
00:00:37  GREEN/GREEN    2.2ms   38M         26ms     Idle baseline
00:00:44  GREEN/GREEN   10.8ms   38M         70ms     Load increasing
00:00:52  YELLOW/RED    62.6ms   34M        295ms     Congestion detected!
00:00:59  YELLOW/RED    60.8ms   31M         79ms     Backing off upload
00:01:06  SOFT_RED/RED  47.9ms   28M         21ms     Continued reduction
00:01:18  YELLOW/YELLOW 29.3ms   28M         21ms     Recovering
00:01:31  YELLOW/YELLOW 17.9ms   28M         22ms     Almost there
00:01:56  GREEN/GREEN    7.1ms   28M         26ms     Recovered
```

### What Happened

1. **Congestion spike** - RTT jumped from 26ms to 295ms (bufferbloat)
2. **Automatic response** - Upload reduced from 38M to 28M (26% reduction)
3. **Latency controlled** - Delta dropped from 62ms back to 7ms
4. **Self-healing** - System returned to GREEN, upload will gradually recover

The entire event was handled automatically in under 90 seconds with no user intervention. Upload bandwidth will slowly climb back to 38M while the system stays GREEN (1 Mbps per cycle).

## Adding Router Backend Support

wanctl is designed to support multiple router platforms. Currently only RouterOS is implemented, but the architecture allows adding others.

To add a new backend (e.g., OpenWrt, pfSense):

1. Create `src/wanctl/backends/<platform>.py`
2. Implement the `RouterBackend` interface
3. Add to factory in `__init__.py`

See `src/wanctl/backends/base.py` for the interface definition.

## Acknowledgments

### Dave Täht (1965-2025) - In Memoriam

This project stands on the shoulders of **Dave Täht**, pioneer of the bufferbloat movement and lead developer of CAKE. Dave personally helped configure CAKE on Mikrotik in the early days:

- [Forum thread: Some quick comments on configuring CAKE](https://forum.mikrotik.com/t/some-quick-comments-on-configuring-cake/) (October-November 2021)

His work on CAKE, fq_codel, and the bufferbloat project benefits millions of internet users. Rest in peace, Dave.

### Other Acknowledgments

- **CAKE team** - Jonathan Morton, Toke Høiland-Jørgensen, and contributors
- **LibreQoS** - Robert McMahon and team for enterprise-grade CAKE orchestration
- **sqm-autorate** - Lynx and the OpenWrt community for automatic SQM tuning
- **Mikrotik** - For implementing CAKE in RouterOS

### AI Transparency

This project was developed with assistance from **Claude** (Anthropic). The architecture, algorithms, and documentation were created collaboratively between a human sysadmin and AI.

## Project Philosophy

**This is a power-user tool, not enterprise software.**

Built by a sysadmin for personal use, now shared with the community. Not competing with LibreQoS - just a well-engineered solution for Mikrotik users who want adaptive CAKE tuning.

**Target audience:** Power users, sysadmins, and homelabbers who can read configs and adapt.

## Non-Goals

- **Not a replacement for understanding CAKE** - You should know how CAKE works before using this
- **Not intended for automatic ISP tuning** - Designed for user-managed networks
- **Not enterprise orchestration software** - See [LibreQoS](https://libreqos.io/) for that

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Issues and PRs are welcome, but this is maintained by a sysadmin in spare time. Please be patient and provide detailed information when reporting issues.

## License

GPL-2.0 - See [LICENSE](LICENSE)

---

_wanctl aims to be the reference implementation for adaptive CAKE bandwidth control on RouterOS._
