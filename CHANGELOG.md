# Changelog

All notable changes to wanctl will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-07

### Initial Open Source Release

wanctl is an adaptive CAKE bandwidth controller for Mikrotik RouterOS that eliminates bufferbloat through continuous RTT monitoring and automatic queue adjustment.

### Added

#### Core Features
- **Continuous RTT Monitoring**: Ping-based latency measurement with EWMA smoothing
- **4-State Congestion Model**: GREEN → YELLOW → SOFT_RED → RED state machine for downloads
- **3-State Upload Model**: GREEN → YELLOW → RED for upload queues
- **Automatic CAKE Adjustment**: Dynamic bandwidth limits based on congestion state
- **State-Dependent Floors**: Policy-enforced minimum bandwidth per congestion state
- **Baseline RTT Tracking**: Adaptive baseline that only updates during healthy periods

#### Multi-WAN Support
- Generic WAN naming (wan1, wan2, wan3, etc.)
- Independent per-WAN configuration
- Concurrent operation on multiple WANs

#### Steering Module (Optional)
- Multi-signal congestion detection (RTT + CAKE drops + queue depth)
- Automatic routing of latency-sensitive traffic during congestion
- Config-driven state names (no hardcoded ISP references)
- Hysteresis to prevent flapping (2 RED samples to enable, 15 GREEN to disable)

#### Calibration Tool
- Interactive wizard for discovering optimal bandwidth settings
- Flent/LibreQoS binary search methodology
- Finds maximum throughput that maintains acceptable latency
- Auto-generates wanctl configuration files

#### Router Backend Abstraction
- Abstract `RouterBackend` interface for future extensibility
- RouterOS implementation via SSH
- Designed for future OpenWrt/pfSense support

#### Deployment Options
- **Bare Metal/LXC**: Native systemd integration
- **Docker**: Multi-container deployment with docker-compose
- FHS-compliant directory structure (`/opt/wanctl`, `/etc/wanctl`, `/var/lib/wanctl`)
- Dedicated `wanctl` service user with minimal privileges

#### Systemd Integration
- Template-based services: `wanctl@.service`, `wanctl@.timer`
- Instance per WAN: `systemctl enable wanctl@wan1.timer`
- Optional steering daemon: `steering.service`, `steering.timer`

#### Configuration
- YAML-based configuration files
- Example configs for various connection types:
  - `wan1.yaml.example`, `wan2.yaml.example` (generic)
  - `fiber.yaml.example` (low latency, stable)
  - `cable.yaml.example` (DOCSIS, variable)
  - `dsl.yaml.example` (higher baseline RTT)
  - `steering.yaml.example` (multi-WAN steering)

#### Documentation
- `README.md`: Project overview and quick start
- `docs/ARCHITECTURE.md`: Design principles and state machines
- `docs/CONFIGURATION.md`: Config schema reference
- `docs/CALIBRATION.md`: Calibration tool usage
- `docs/STEERING.md`: Multi-WAN steering guide
- `docs/DOCKER.md`: Container deployment guide
- `docs/SECURITY.md`: Security setup and considerations
- `docs/EF_QUEUE_PROTECTION.md`: Priority traffic protection
- `CONTRIBUTING.md`: Contribution guidelines
- `CLAUDE.md.example`: Template for AI assistant context

#### Scripts
- `scripts/install.sh`: System setup (user, directories, permissions)
- `scripts/deploy.sh`: Unified deployment to target hosts
- `scripts/calibrate.sh`: Interactive calibration wizard
- `scripts/install-systemd.sh`: Systemd unit installation

### Technical Details

#### State Machine Thresholds (Configurable)
| State | RTT Delta | Action |
|-------|-----------|--------|
| GREEN | ≤15ms | Gradually increase bandwidth |
| YELLOW | 15-45ms | Hold current bandwidth |
| SOFT_RED | 45-80ms | Reduce to soft floor, no steering |
| RED | >80ms | Reduce to hard floor, enable steering |

#### Control Hierarchy
1. **Tier 1 - Autorate**: Primary congestion control via bandwidth adjustment
2. **Tier 2 - Steering**: Emergency traffic routing (rare, <1% of time)
3. **Tier 3 - Floors**: Policy-enforced minimum bandwidth

#### Performance Characteristics
- Measurement cycle: ~2 seconds
- Memory usage: ~50 MB per WAN
- CPU usage: <1% idle, <5% measuring
- Convergence time: 60-120 minutes from cold start

### Acknowledgments

- **Dave Täht (1962-2023)**: Pioneer of the bufferbloat movement, lead developer of CAKE
- **CAKE Team**: Jonathan Morton, Toke Høiland-Jørgensen, and contributors
- **LibreQoS**: Robert McMahon and team for enterprise CAKE orchestration
- **sqm-autorate**: Lynx and the OpenWrt community
- **Mikrotik**: For implementing CAKE in RouterOS
- **Claude AI**: Development assistance from Anthropic's Claude

### License

GPL-2.0 - Compatible with CAKE and LibreQoS ecosystem

---

[1.0.0]: https://github.com/kevinb361/wanctl/releases/tag/v1.0.0
