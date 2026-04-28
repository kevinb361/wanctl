# wanctl

[![License: GPL v2](https://img.shields.io/badge/License-GPL_v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
[![Coverage Gate](https://img.shields.io/badge/coverage_gate-90%25-brightgreen)](pyproject.toml)

**Adaptive CAKE bandwidth control for MikroTik RouterOS and Linux CAKE backends.**

Reduces bufferbloat by continuously monitoring RTT and adjusting CAKE bandwidth limits in real time. Supports multi-WAN RouterOS deployments with optional intelligent traffic steering.

## Features

- **Continuous RTT monitoring** - 50ms control loops (40x faster than original 2s baseline)
- **Multi-state congestion control** - GREEN/YELLOW/SOFT_RED/RED state machine
- **Multi-signal detection** - RTT + CAKE drops + queue depth for accuracy
- **REST API transport** - 2x faster than SSH (~50ms vs ~150ms latency)
- **Optional WAN steering** - Route latency-sensitive traffic during congestion
- **Config-driven** - Same code works for fiber, cable, DSL, or any connection
- **FHS compliant** - Proper Linux directory layout and service user
- **Hardened security** - Input validation, EWMA bounds checking, rate limiting, centralized validation
- **Production reliability** - Bounded memory, file locking, automatic state backup recovery
- **Observability** - Health check endpoint, Prometheus metrics, JSON structured logging
- **Signal processing** - Hampel outlier filter + EWMA smoothing for noise-resilient RTT measurement
- **Dual-signal fusion** - Weighted ICMP + IRTT UDP measurement blending (ships disabled, SIGUSR1 toggle)
- **IRTT measurement** - Isochronous UDP RTT with directional loss detection and OWD asymmetry analysis
- **Reflector quality scoring** - Rolling quality scores with automatic deprioritization and recovery
- **Adaptive tuning** - Self-optimizing controller learns optimal parameters from production metrics
- **Alerting** - Discord webhook notifications for congestion, hard-red, connectivity, IRTT loss, fusion healing, and cycle-budget events
- **TUI dashboard** - Real-time terminal dashboard with sparklines and history browser
- **CLI tools** - Config validation, CAKE queue audit, RRUL benchmarking, metrics/alert/tuning history

## Quick Start

### Prerequisites

- MikroTik router running RouterOS 7.x with CAKE queues configured, or Linux CAKE qdiscs for `linux-cake` transports
- Linux host (LXC container, VM, or bare metal) with Python 3.11+
- For RouterOS control: REST API enabled on the router (recommended) or SSH key authentication

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
sudo systemctl enable --now wanctl@wan1.service
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
  ssh_key: "/etc/wanctl/ssh/router.key" # Currently required by base validation
  password: "${ROUTER_PASSWORD}" # Expanded from /etc/wanctl/secrets
  port: 443
  verify_ssl: false
```

The plaintext password is not stored in the config file - systemd loads `/etc/wanctl/secrets` via `EnvironmentFile` and the `${VAR}` syntax is expanded at runtime.

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

Every 50ms by default:

1. **Measure RTT** to reference hosts (1.1.1.1, 8.8.8.8, 9.9.9.9)
2. **Track baseline** RTT via slow EWMA (only updates when idle)
3. **Calculate delta** = loaded_rtt - baseline_rtt
4. **Determine state** based on delta thresholds
5. **Adjust bandwidth** limits on the configured CAKE backend
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

## Performance

wanctl has been optimized for extremely fast congestion response while maintaining stability:

**Cycle Interval:** 50ms (20Hz polling)

- 40x faster than original 2-second baseline
- Sub-second congestion detection (50-100ms response time)
- Controlled by the `CYCLE_INTERVAL_SECONDS` source constant, not by YAML config

**Router Efficiency:**

- **0% CPU at idle** - Zero measurable impact from 20Hz REST API polling
- **~45% peak under heavy load** - Comfortable headroom during RRUL stress testing
- MikroTik RB5009 handles 50ms intervals effortlessly

**Time-Constant Preservation:**

- EWMA alpha values automatically scale with interval changes
- Steering hysteresis uses configured sample counts to maintain stable activation and recovery timing
- Same congestion response characteristics regardless of polling rate

**Validation:**

- Proven stable under 3-minute RRUL bidirectional stress testing
- Perfect baseline RTT stability (no drift under extreme alpha values)
- Zero errors or timing violations
- Tested on both cable (Spectrum) and DSL (AT&T) connections

**Performance Boundary:**

- 50ms represents practical limit (60-80% cycle utilization)
- Execution time: 30-40ms per cycle
- ATT (DSL): ±1ms timing consistency
- Spectrum (cable): ±10ms variance (acceptable for cable networks)

The 50ms interval provides maximum responsiveness without sacrificing stability. Conservative intervals such as 100ms or 250ms have historical validation context, but the active deployment standard is 50ms and the interval is not a YAML setting.

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

Copy to `/etc/wanctl/` and customize for your setup. See [CONFIG_SCHEMA.md](docs/CONFIG_SCHEMA.md) for the complete configuration reference including alerting, fusion, IRTT, and adaptive tuning options.

Additional references:

- [Documentation Index](docs/README.md) - canonical map of current docs versus archived historical notes
- [SUBSYSTEMS.md](docs/SUBSYSTEMS.md) - storage, dashboard, backend, health, alerting, and measurement-quality internals
- [PERFORMANCE.md](docs/PERFORMANCE.md) - production timing, cycle-budget, and profiling guidance
- [TESTING.md](docs/TESTING.md) - current test commands and integration-test invocation

## Directory Structure

```
/opt/wanctl/           # Code
/etc/wanctl/           # Configuration
  ├── wan1.yaml        # WAN config
  ├── secrets          # Environment secrets (ROUTER_PASSWORD, DISCORD_WEBHOOK_URL)
  └── ssh/router.key   # Router SSH key (for SSH transport)
/var/lib/wanctl/       # State files (EWMA persistence, SQLite metrics database)
/var/log/wanctl/       # Logs
/run/wanctl/           # Lock files
```

## Multi-WAN Steering (Optional)

For dual-WAN setups, the steering daemon routes latency-sensitive traffic to the healthier WAN during congestion:

```bash
# Enable steering
sudo systemctl enable --now steering.service
```

**What gets steered:** VoIP, gaming, DNS, SSH, interactive web
**What stays:** Bulk downloads, video streaming, background traffic

Steering uses multi-signal detection (RTT + CAKE drops + queue depth) with hysteresis to prevent flapping.

## Monitoring

```bash
# Service status
systemctl status wanctl@wan1.service

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

## Observability

### Health Check Endpoint

HTTP endpoint for Kubernetes probes and monitoring systems (enabled by default):

```bash
curl http://127.0.0.1:9101/health
```

```json
{
  "status": "healthy",
  "uptime_seconds": 3600.5,
  "version": "<installed wanctl version>",
  "consecutive_failures": 0,
  "wan_count": 1,
  "wans": [
    {
      "name": "wan1",
      "baseline_rtt_ms": 24.01,
      "load_rtt_ms": 25.5,
      "download": { "state": "GREEN", "current_rate_mbps": 940.0 },
      "upload": { "state": "GREEN", "current_rate_mbps": 38.0 },
      "signal_quality": {
        "jitter_ms": 0.42,
        "variance_ms2": 0.18,
        "confidence": 0.95,
        "outlier_rate": 0.03
      },
      "irtt": { "available": true, "rtt_mean_ms": 28.5, "ipdv_ms": 0.8 },
      "reflector_quality": {
        "available": true,
        "hosts": { "1.1.1.1": { "score": 0.98, "status": "active" } }
      },
      "fusion": { "enabled": false, "reason": "disabled" },
      "tuning": { "enabled": false, "reason": "disabled" }
    }
  ],
  "alerting": { "enabled": true, "fire_count": 3, "active_cooldowns": [] },
  "router_reachable": true,
  "disk_space": { "status": "ok" }
}
```

Configure in your WAN config:

```yaml
health_check:
  enabled: true # default
  port: 9101 # default
```

### Prometheus Metrics

Prometheus-compatible metrics endpoint (disabled by default):

```bash
curl http://127.0.0.1:9100/metrics
```

Common metrics include `wanctl_bandwidth_mbps`, `wanctl_rtt_delta_ms`, `wanctl_state`, `wanctl_cycles_total`, storage pressure gauges, runtime pressure gauges, checkpoint/WAL counters, router update counters, ping failure counters, and steering counters.

Stored SQLite history is also available through the autorate health server:

```bash
curl 'http://127.0.0.1:9101/metrics/history?range=1h&limit=20'
```

The history response includes `metadata.source` so operators can tell whether the data came from the endpoint-local daemon DB or merged DB discovery fallback.

Enable in config:

```yaml
metrics:
  enabled: true
  port: 9100
```

### JSON Structured Logging

For log aggregation tools (Loki, ELK):

```bash
export WANCTL_LOG_FORMAT=json
```

### Config Validation

Validate configuration without starting the daemon:

```bash
wanctl --config /etc/wanctl/wan1.yaml --validate-config
# Exit code: 0 = valid, 1 = invalid
```

For more thorough offline validation, use the dedicated CLI tool:

```bash
wanctl-check-config /etc/wanctl/wan1.yaml
```

This validates all sections including alerting, tuning, signal_processing, IRTT, and fusion config.

## CLI Tools

wanctl ships with several CLI utilities for diagnostics, operations, and validation:

| Tool | Purpose | Example |
| --- | --- | --- |
| `wanctl` | Run the autorate daemon or one-shot validation modes | `wanctl --config /etc/wanctl/wan1.yaml` |
| `wanctl-calibrate` | Measure baseline/throughput and generate a starter WAN config | `wanctl-calibrate --wan-name wan1 --router 192.168.1.1` |
| `wanctl-steering` | Run the optional multi-WAN steering daemon | `wanctl-steering --config /etc/wanctl/steering.yaml` |
| `wanctl-dashboard` | Open the terminal monitoring dashboard | `wanctl-dashboard --autorate-url http://127.0.0.1:9101` |
| `wanctl-operator-summary` | Render compact health summaries from health JSON URLs/files | `wanctl-operator-summary http://host:9101/health` |
| `wanctl-history` | Query metrics, alerts, tuning, and per-tin history from SQLite | `wanctl-history --last 1h --metrics wanctl_rtt_ms --json` |
| `wanctl-check-config` | Validate config files offline before deploy | `wanctl-check-config /etc/wanctl/wan1.yaml` |
| `wanctl-check-cake` | Audit live CAKE queue config; `--fix` mutates router state | `wanctl-check-cake /etc/wanctl/wan1.yaml` |
| `wanctl-benchmark` | Run RRUL benchmark, store results, compare/list past runs | `wanctl-benchmark --quick --label before-change` |
| `wanctl-analyze-baseline` | Summarize CAKE signal baselines and state transitions | `wanctl-analyze-baseline --hours 24 --wan spectrum` |

```bash
# Query recent metrics history
wanctl-history --last 1h --metrics wanctl_rtt_ms

# View alert history
wanctl-history --alerts --last 24h

# View tuning adjustment history
wanctl-history --tuning --last 24h

# View CAKE tin history as JSON
wanctl-history --tins --last 1h --json

# Validate config before deploying
wanctl-check-config /etc/wanctl/wan1.yaml

# Audit CAKE queues on router
wanctl-check-cake /etc/wanctl/wan1.yaml

# Run RRUL benchmark
wanctl-benchmark --server netperf-server --wan wan1 --label post-deploy
wanctl-benchmark history --last 24h --wan wan1
```

By default, `wanctl-history` auto-discovers active per-WAN metrics DBs under `/var/lib/wanctl`. Use `--db PATH` only when inspecting a specific database file.

## Real-World Test: Congestion Response

Here's actual output from a stress test on a 940/38 Mbps Spectrum cable connection. Eight parallel netperf streams were used to saturate the link.

**Note:** This test was conducted with the original 2-second interval. Modern deployments run at 50ms intervals for 40x faster response (see Performance section below).

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

wanctl is designed to support multiple shaping backends. Current backends include RouterOS REST/SSH and local Linux CAKE control via `tc` or optional pyroute2/netlink.

To add a new backend (e.g., OpenWrt, pfSense):

1. Create `src/wanctl/backends/<platform>.py`
2. Implement the `RouterBackend` interface
3. Add to factory in `__init__.py`

See `src/wanctl/backends/base.py` for the interface definition.

## Acknowledgments

### Dave Täht (1965-2025) - In Memoriam

This project stands on the shoulders of **Dave Täht**, pioneer of the bufferbloat movement and lead developer of CAKE. Dave personally helped configure CAKE on MikroTik in the early days:

- [Forum thread: Some quick comments on configuring CAKE](https://forum.mikrotik.com/t/some-quick-comments-on-configuring-cake/) (October-November 2021)

His work on CAKE, fq_codel, and the bufferbloat project benefits millions of internet users. Rest in peace, Dave.

### Other Acknowledgments

- **CAKE team** - Jonathan Morton, Toke Høiland-Jørgensen, and contributors
- **LibreQoS** - Robert McMahon and team for enterprise-grade CAKE orchestration
- **sqm-autorate** - Lynx and the OpenWrt community for automatic SQM tuning
- **MikroTik** - For implementing CAKE in RouterOS

### AI Transparency

This project was developed with assistance from **Claude** (Anthropic). The architecture, algorithms, and documentation were created collaboratively between a human sysadmin and AI.

## Project Philosophy

**This is a power-user tool, not enterprise software.**

Built by a sysadmin for personal use, now shared with the community. Not competing with LibreQoS - just a well-engineered solution for MikroTik users who want adaptive CAKE tuning.

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
