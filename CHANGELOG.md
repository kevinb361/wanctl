# Changelog

All notable changes to wanctl are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Tuned `accel_threshold_ms`** - Reduced from 15ms to 12ms for faster spike detection
  - A/B testing showed 19% reduction in average RTT under load (48ms → 39ms)
  - 11% reduction in peak latency spikes (83ms → 74ms avg peak)
  - 50% reduction in 100ms+ spike frequency (40% → 20% of test runs)
  - Lower values (10ms) caused over-correction; higher values (15ms) missed spikes

### Documentation

- Updated `cable.yaml.example` with modern EWMA time constants and `accel_threshold_ms`

## [1.1.0] - 2026-01-14

**First stable release** - Adaptive CAKE bandwidth control for MikroTik RouterOS.

This release represents 18+ days of production validation with 231,000+ autorate cycles
and 604,000+ steering assessments. Comprehensive test coverage (594 tests), enterprise-grade
observability, and validated 50ms cycle interval for sub-second congestion response.

### Highlights

- **50ms Cycle Interval** - 40x faster than original 2s baseline, sub-second congestion detection
- **594 Unit Tests** - Comprehensive test coverage, all passing
- **Flash Wear Protection** - 99.7% reduction in router writes
- **Fallback Connectivity** - Graceful degradation reduces false-positive restarts
- **REST API Transport** - 2x faster than SSH (~50ms vs ~150ms latency)
- **Production Validated** - Stability score 9.0/10 from comprehensive analysis

### Performance

| Metric               | Value                  |
| -------------------- | ---------------------- |
| Cycle Interval       | 50ms (20Hz polling)    |
| Congestion Detection | 50-100ms response time |
| Router CPU (idle)    | 0%                     |
| Router CPU (load)    | 45% peak               |
| Flash Wear Reduction | 99.7%                  |

### Features

#### Adaptive Bandwidth Control

- **Continuous RTT Monitoring** - 50ms control loop measures latency and adjusts bandwidth in real-time
- **4-State Download Model** - GREEN/YELLOW/SOFT_RED/RED state machine with per-state floor enforcement
- **3-State Upload Model** - GREEN/YELLOW/RED (upload is less latency-sensitive)
- **EWMA Smoothing** - Exponential weighted moving average for stable RTT and rate tracking
- **Baseline RTT Protection** - Baseline only updates when connection is idle (delta < 3ms)
- **Asymmetric Rate Changes** - Fast backoff on congestion, slow recovery (requires 5 consecutive GREEN cycles)
- **Flash Wear Protection** - Only writes queue changes to router when values actually change

#### State Machine Behavior

| State    | RTT Delta | Action                                             | Floor Example |
| -------- | --------- | -------------------------------------------------- | ------------- |
| GREEN    | ≤15ms     | Slowly increase rate (+1 Mbps/cycle after 5 GREEN) | 550 Mbps      |
| YELLOW   | 15-45ms   | Hold steady, monitor                               | 350 Mbps      |
| SOFT_RED | 45-80ms   | Clamp to floor, no steering                        | 275 Mbps      |
| RED      | >80ms     | Aggressive backoff, steering eligible              | 200 Mbps      |

#### Multi-WAN Traffic Steering

- **Multi-Signal Detection** - RTT delta + CAKE drops + queue depth (not RTT alone)
- **Asymmetric Hysteresis** - 2 RED samples to enable steering, 15 GREEN to disable
- **Latency-Sensitive Routing** - Steers VoIP, DNS, gaming, SSH to healthier WAN
- **New Connections Only** - Existing flows never rerouted mid-session

#### Router Transports

- **REST API (Recommended)** - ~50ms latency, 2x faster than SSH
- **SSH Transport** - Paramiko-based with persistent connections

#### Observability

- **Health Check Endpoint** - `http://127.0.0.1:9101/health` with JSON response
- **Prometheus Metrics** - Optional metrics on port 9100
- **Structured Logging** - JSON format via `WANCTL_LOG_FORMAT=json`

#### Safety & Reliability

- **Rate Limiting** - Max 10 router changes per 60 seconds
- **Lock File Management** - PID-based validation with stale lock cleanup
- **Watchdog Integration** - Systemd watchdog with degradation tracking
- **State File Recovery** - Automatic backup and corruption recovery
- **Fallback Connectivity** - TCP/gateway checks when ICMP fails

### CLI Tools

```bash
# Main controller
wanctl --config /etc/wanctl/wan1.yaml

# Calibration wizard
wanctl-calibrate --wan-name NAME --router HOST

# Traffic steering
wanctl-steering --config /etc/wanctl/steering.yaml
```

### Deployment

```
/opt/wanctl/           # Application code
/etc/wanctl/           # Configuration files
/var/lib/wanctl/       # State files
/var/log/wanctl/       # Logs
/run/wanctl/           # Lock files
```

### System Requirements

- Python 3.11+ (3.12 recommended)
- MikroTik RouterOS 7.x with CAKE queues
- Linux host with systemd (Debian 12, Ubuntu 22.04+)

### Dependencies

- `requests>=2.31.0` - REST API transport
- `pyyaml>=6.0.1` - Configuration parsing
- `paramiko>=3.4.0` - SSH transport
- `pexpect>=4.9.0` - SSH command execution

---

## Pre-Release History

### Development Milestones

- **v1.0.0-rc8** (2026-01-12) - Fallback connectivity checks
- **v1.0.0-rc7** (2026-01-10) - Health endpoints, rate limiting, 474 tests
- **v1.0.0-rc5** (2026-01-08) - Interactive setup wizard
- **v1.0.0-rc4** (2026-01-08) - REST API transport (2x faster)
- **v1.0.0-rc3** (2026-01-07) - Open source release, package rename

### Earlier Development (Pre-Open Source)

- **v4.x** (Dec 2025) - CAKE-aware steering, 4-state model
- **v3.x** (Nov 2025) - Binary search calibration
- **v2.x** (Nov 2025) - Config-driven, EWMA smoothing
- **v1.x** (Oct 2025) - Initial implementation

---

## Acknowledgments

### Dave Taht (1965-2025) - In Memoriam

This project stands on the shoulders of **Dave Taht**, pioneer of the bufferbloat movement
and lead developer of CAKE. His work benefits millions of internet users.

### Projects

- [CAKE](https://www.bufferbloat.net/projects/codel/wiki/Cake/) - The qdisc that makes this work
- [LibreQoS](https://libreqos.io/) - Inspiration for CAKE-based QoS
- [Flent](https://flent.org/) - Latency measurement methodology
- [sqm-autorate](https://github.com/sqm-autorate/sqm-autorate) - OpenWrt automatic SQM tuning

### AI Transparency

This project was developed with assistance from **Claude** (Anthropic).
The architecture, algorithms, and documentation were created collaboratively
between a human sysadmin and AI.

---

## License

GPL-2.0 - See [LICENSE](LICENSE) for details.

[1.1.0]: https://github.com/kevinb361/wanctl/releases/tag/v1.1.0
