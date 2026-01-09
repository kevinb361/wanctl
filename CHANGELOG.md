# Changelog

All notable changes to wanctl will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 2: Operational Reliability Hardening (2026-01-09)

#### Added

- **Operation-Appropriate Timeouts (W1+W9)**: RouterOS client methods now accept optional timeout parameter
  - Fast queries (read_stats, find rules): 5 second timeout
  - Control operations (enable/disable steering): 10 second timeout
  - Prevents timeout exceptions from blocking 2-second steering cycles
- **State File Backup (W2)**: Automatic backups on corruption detection and successful saves
  - Backs up to `.corrupt` when load corruption detected
  - Backs up to `.backup` after successful state saves
  - Enables manual recovery without code changes
- **Verification Retry with Exponential Backoff (W6)**: Steering rule verification now retries on failure
  - 3 maximum attempts with exponential backoff: 100ms → 200ms → 400ms
  - Handles RouterOS processing delay for rule state changes
  - Prevents false "verification failed" errors
- **Ping Retry & Fallback to Historical RTT (W7)**: RTT measurement resilience
  - 3 ping attempts with 0.5s delay between retries
  - Fallback to last known RTT from state history on failure
  - Prevents single transient ping failure from skipping steering cycle
- **Delta Math Documentation (W11)**: Comprehensive explanation of counter accumulation approach
  - RouterOS counters are monotonic and cumulative
  - Delta method: subtract previous read from current read
  - Eliminates measurement gap race condition of reset→read approach

#### Changed

- **Counter Reset Removal (W11)**: Removed `reset_counters()` and `reset_all_counters()` methods
  - Switched to delta math for more accurate event counting
  - Reduces RouterOS command overhead (50-150ms saved per cycle)
  - `reset_counters` config field no longer loaded
- **State Management**: Added `_backup_state_file()` to SteeringState class
- **RouterOS Communication**: All client methods now support per-operation timeout

#### Fixed

- Transient ping failures no longer skip steering cycles (W7)
- False "rule verification failed" errors eliminated via retry (W6)
- State corruption no longer causes permanent data loss (W2)
- RouterOS timeout exceptions no longer block steering loops (W1+W9)
- CAKE statistics now collected without race condition (W11)

#### Deployed & Verified

- Both containers (cake-spectrum, cake-att) deployed successfully
- Python syntax validation passed
- Services restarted cleanly with no errors
- Spectrum container showing healthy operational metrics (GREEN/YELLOW states, no RED)
- Steering daemon running on schedule with no failures

---

### Previous Changes

#### REST API & Security Hardening (2026-01-08)

### Added

- **REST API Transport**: 2x faster than SSH (~50ms vs ~150ms latency)
- **Steering REST Support**: Steering daemon now supports REST transport via `get_router_client` factory
- **Config Validation**: Threshold and floor ordering enforcement with clear error messages
- **Upgrade Documentation**: `docs/UPGRADING.md` with procedures and state file compatibility
- **Non-Goals Section**: Clear project scope in README

### Changed

- **SSH Host Key Validation**: Now enforced via `paramiko.RejectPolicy()` (security hardening)
- **REST Retry Parity**: REST client now has same retry behavior as SSH client

### Fixed

- SSH security: Removed `AutoAddPolicy()` that accepted any host key (MITM vulnerability)
- README: Changed "eliminates bufferbloat" to "reduces bufferbloat" (accuracy)
- Standardized example IPs to conventional 192.168.1.x range

---

## [1.0.0-rc5] - 2026-01-08

### Added

- **Interactive Setup Wizard**: Guided first-time installation via `install.sh`
  - Router connection testing (REST API and SSH validation)
  - Queue discovery from router (auto-detects existing CAKE queues)
  - Connection-type presets (cable/DSL/fiber) with optimized defaults
  - Multi-WAN architecture guidance for dual-WAN deployments
  - Secure credential storage with clear user messaging
- **Wizard Modes**: `--no-wizard` (automation), `--reconfigure` (modify existing), `--uninstall`
- **Auto-Dependency Installation**: Installs python3-yaml, python3-pexpect, bc automatically
- **REST API Transport**: Alternative to SSH for RouterOS communication
- **Transport Comparison**: `docs/TRANSPORT_COMPARISON.md` with stress test data
- **Secrets Management**: Password support via `/etc/wanctl/secrets` environment file

### Changed

- REST API is now the recommended transport (configurable via `transport: "rest"`)
- Installation now defaults to interactive wizard (use `--no-wizard` to skip)

### Fixed

- Password storage handles special characters correctly (no sed injection vulnerability)
- SSH key path uses `SUDO_USER` home directory when run with sudo
- bc auto-installed as dependency for floor calculations
- Fixed echo color escape codes in install script

---

## [1.0.0-rc3] - 2026-01-05

### Changed

- **Package Rename**: `cake` → `wanctl` to avoid confusion with CAKE qdisc
- **CLI Entry Points**: `wanctl`, `wanctl-calibrate`, `wanctl-steering`
- **FHS Compliance**: `/opt/wanctl`, `/etc/wanctl`, `/var/lib/wanctl`

### Security

- Atomic lock file creation with `O_CREAT | O_EXCL`
- Restrictive temp file permissions (0o600)

---

## [1.0.0-rc1] - 2026-01-01

### Initial Open Source Release

wanctl is an adaptive CAKE bandwidth controller for Mikrotik RouterOS that reduces bufferbloat through continuous RTT monitoring and automatic queue adjustment.

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
- FHS-compliant directory structure
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

### Technical Details

#### State Machine Thresholds (Configurable)

| State    | RTT Delta | Action                                |
| -------- | --------- | ------------------------------------- |
| GREEN    | ≤15ms     | Gradually increase bandwidth          |
| YELLOW   | 15-45ms   | Hold current bandwidth                |
| SOFT_RED | 45-80ms   | Reduce to soft floor, no steering     |
| RED      | >80ms     | Reduce to hard floor, enable steering |

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

- **Dave Täht (1965-2025)**: Pioneer of the bufferbloat movement, lead developer of CAKE
- **CAKE Team**: Jonathan Morton, Toke Høiland-Jørgensen, and contributors
- **LibreQoS**: Robert McMahon and team for enterprise CAKE orchestration
- **sqm-autorate**: Lynx and the OpenWrt community
- **Mikrotik**: For implementing CAKE in RouterOS
- **Claude AI**: Development assistance from Anthropic's Claude

### License

GPL-2.0 - Compatible with CAKE and LibreQoS ecosystem

---

[Unreleased]: https://github.com/kevinb361/wanctl/compare/v1.0.0-rc5...HEAD
[1.0.0-rc5]: https://github.com/kevinb361/wanctl/compare/v1.0.0-rc4...v1.0.0-rc5
[1.0.0-rc4]: https://github.com/kevinb361/wanctl/compare/v1.0.0-rc3...v1.0.0-rc4
[1.0.0-rc3]: https://github.com/kevinb361/wanctl/compare/v1.0.0-rc1...v1.0.0-rc3
[1.0.0-rc1]: https://github.com/kevinb361/wanctl/releases/tag/v1.0.0-rc1
