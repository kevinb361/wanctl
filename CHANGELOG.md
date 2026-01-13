# Changelog

All notable changes to wanctl are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - Unreleased

**First stable release** - Adaptive CAKE bandwidth control for MikroTik RouterOS.

This release represents 18+ days of production validation with 231,000+ autorate cycles
and 604,000+ steering assessments. All critical security issues resolved, comprehensive
test coverage (474 tests), and enterprise-grade observability.

### Performance Optimizations (2026-01-13)

**50ms cycle interval** - Optimization milestone complete, delivering **40x speed improvement** over original 2s baseline.

#### Optimization Results

- **Cycle Interval:** 2s → 50ms (0.5Hz → 20Hz polling)
- **Congestion Detection:** 1-2s → 50-100ms (sub-second response)
- **Router CPU Impact:** 0% at idle (20Hz REST API polling)
- **CPU Under Load:** 45% peak during RRUL stress (comfortable headroom)
- **Validation:** 3-minute RRUL bidirectional stress test passed
- **Baseline Stability:** Zero drift with extreme EWMA alpha values (0.0005-0.000375)
- **Timing Consistency:** ±1ms on DSL, ±10ms on cable (acceptable variance)

#### Phase 2: Interval Optimization Testing

**250ms Interval Test (Plan 02-01):**

- 8x faster than original 2s baseline
- Proven stable over 28-minute test
- Router CPU: 1-3% under load
- Utilization: 12-16% (excellent headroom)
- Documentation: `docs/INTERVAL_TESTING_250MS.md`

**50ms Extreme Interval Test (Plan 02-03):**

- 40x faster than original 2s baseline
- Proven stable: 11-minute test + 3-minute RRUL stress
- Router CPU: 0% idle, 45% peak under stress
- Utilization: 60-80% (practical performance limit)
- Timing: ATT ±1ms (exceptional), Spectrum ±10ms (acceptable)
- RRUL Results: Sub-second detection, perfect baseline stability, zero errors
- Documentation: `docs/INTERVAL_TESTING_50MS.md`, `/tmp/rrul-test-50ms/STRESS_TEST_SUMMARY.md`

#### Phase 3: Production Finalization

**50ms Selected as Production Standard (Plan 03-01):**

- Maximum speed with proven stability
- Configuration verified across all services
- Time-constant preservation methodology documented
- Conservative alternatives documented (100ms, 250ms)
- Documentation: `docs/PRODUCTION_INTERVAL.md`

#### Technical Details

**Time-Constant Preservation:**

- EWMA alpha values scaled proportionally with interval changes
- Steering sample counts scaled to maintain wall-clock timing
- Formula: New Alpha = Old Alpha × (New Interval / Old Interval)
- Result: Identical congestion response behavior regardless of polling rate

**Configuration Changes:**

- `CYCLE_INTERVAL_SECONDS`: 2.0 → 0.05 (autorate daemon)
- `ASSESSMENT_INTERVAL_SECONDS`: 2.0 → 0.05 (steering daemon)
- EWMA alphas: Reduced 40x (e.g., 0.02 → 0.0005 for Spectrum baseline)
- Steering samples: Increased 40x (e.g., 8 → 320 bad samples for 16s activation)
- Schema validation: Extended to support extreme alpha values (min 0.0001)

**Performance Boundary:**

- 50ms represents practical limit (60-80% cycle utilization)
- Execution time: 30-40ms per cycle (from Phase 1 profiling)
- Conservative alternatives available: 100ms (20x speed, 2x headroom), 250ms (8x speed, 4x headroom)

### Complete Feature Reference

#### Adaptive Bandwidth Control

- **Continuous RTT Monitoring** - 50ms control loop (configurable) measures latency and adjusts bandwidth in real-time
- **4-State Download Model** - GREEN/YELLOW/SOFT_RED/RED state machine with per-state floor enforcement
- **3-State Upload Model** - GREEN/YELLOW/RED (upload is less latency-sensitive)
- **EWMA Smoothing** - Exponential weighted moving average for stable RTT and rate tracking
- **Baseline RTT Protection** - Baseline only updates when connection is idle (delta < 3ms)
- **Asymmetric Rate Changes** - Fast backoff on congestion, slow recovery (requires 5 consecutive GREEN cycles)
- **State-Dependent Floors** - Policy-based minimum rates per congestion state (not just safety margins)
- **Flash Wear Protection** - Only writes queue changes to router when values actually change

#### State Machine Behavior

| State    | RTT Delta | Action                                             | Floor Example |
| -------- | --------- | -------------------------------------------------- | ------------- |
| GREEN    | ≤15ms     | Slowly increase rate (+1 Mbps/cycle after 5 GREEN) | 550 Mbps      |
| YELLOW   | 15-45ms   | Hold steady, monitor                               | 350 Mbps      |
| SOFT_RED | 45-80ms   | Clamp to floor, no steering                        | 275 Mbps      |
| RED      | >80ms     | Aggressive backoff, steering eligible              | 200 Mbps      |

#### Binary Search Calibration

- **Flent/LibreQoS Method** - Finds optimal rate where bloat ≤ target (not max throughput)
- **Iterative Search** - 5 iterations to converge on optimal rate
- **Baseline Measurement** - Measures idle RTT before load testing
- **Raw Throughput Test** - Measures unshaped capacity via netperf
- **Config Auto-Generation** - Creates YAML config from discovered values
- **Connection Type Detection** - Suggests presets for cable/DSL/fiber

#### Multi-WAN Traffic Steering

- **Multi-Signal Detection** - RTT delta + CAKE drops + queue depth (not RTT alone)
- **Asymmetric Hysteresis** - 2 RED samples to enable steering, 15 GREEN to disable
- **Latency-Sensitive Routing** - Steers VoIP, DNS, gaming, SSH to healthier WAN
- **Bulk Traffic Stays** - Downloads, streaming, background traffic unaffected
- **New Connections Only** - Existing flows never rerouted mid-session
- **CAKE Statistics** - Reads drops and queue depth directly from RouterOS

**What Gets Steered:**

- VoIP/voice calls (DSCP EF)
- DNS queries
- Gaming traffic
- SSH/RDP sessions
- Interactive web (small packets)
- Push notifications

**What Stays on Primary WAN:**

- Bulk downloads/uploads
- Video streaming
- Background sync
- Large file transfers

### Router Transports

#### REST API (Recommended)

- **2x Faster** - ~50ms latency vs ~150-200ms for SSH
- **Better Congestion Response** - Prevents hard congestion cycles
- **Password Authentication** - Via environment variable from secrets file
- **SSL Support** - HTTPS with configurable certificate verification

#### SSH Transport

- **Paramiko-Based** - Persistent connections for efficiency
- **Key Authentication** - SSH keys (no passwords in config)
- **Fallback Option** - Works on older RouterOS versions

### Observability

#### Health Check Endpoint

- **HTTP Endpoint** - `http://127.0.0.1:9101/health` (enabled by default)
- **JSON Response** - Status, uptime, version, per-WAN metrics
- **Kubernetes Ready** - Liveness and readiness probe compatible
- **Failure Tracking** - Reports consecutive failures for alerting

```json
{
  "status": "healthy",
  "uptime_seconds": 3600.5,
  "version": "1.0.0",
  "consecutive_failures": 0,
  "wans": [
    {
      "name": "wan1",
      "download": { "state": "GREEN" },
      "upload": { "state": "GREEN" }
    }
  ]
}
```

#### Prometheus Metrics

- **Standard Format** - Prometheus text exposition on port 9100
- **Disabled by Default** - Opt-in via config
- **Metrics Exposed:**
  - `wanctl_bandwidth_mbps{wan,direction}` - Current bandwidth limit
  - `wanctl_rtt_baseline_ms{wan}` - Baseline RTT
  - `wanctl_rtt_load_ms{wan}` - Load RTT (EWMA)
  - `wanctl_rtt_delta_ms{wan}` - RTT delta (load - baseline)
  - `wanctl_state{wan,direction}` - Current state (1=GREEN, 2=YELLOW, 3=SOFT_RED, 4=RED)
  - `wanctl_cycles_total{wan}` - Total autorate cycles
  - `wanctl_rate_limit_events_total{wan}` - Router update throttle events

#### Structured Logging

- **JSON Format** - Enable via `WANCTL_LOG_FORMAT=json` environment variable
- **Log Aggregation Ready** - Compatible with Loki, ELK, Splunk
- **Per-WAN Tags** - Each log entry tagged with WAN name
- **Log Rotation** - External logrotate configuration included

### Safety & Reliability

#### Rate Limiting

- **Sliding Window** - Max 10 router changes per 60 seconds (configurable)
- **Prevents API Overload** - Protects router during instability
- **Graceful Degradation** - Logs warning, continues cycle without update

#### Lock File Management

- **PID-Based Validation** - Checks if lock holder process is still alive
- **Stale Lock Cleanup** - Auto-removes locks from dead processes
- **Atomic Creation** - Race condition safe with O_EXCL
- **Per-WAN Isolation** - Each WAN has independent lock

#### Signal Handling

- **Graceful Shutdown** - SIGTERM/SIGINT handlers for clean exit
- **Thread-Safe** - Uses threading.Event() to prevent race conditions
- **Resource Cleanup** - Properly closes SSH/REST connections on exit

#### Watchdog Integration

- **Systemd Watchdog** - Sends heartbeat only on successful cycles
- **Degradation Tracking** - Stops heartbeat after 3 consecutive failures
- **Auto-Recovery** - Allows systemd to restart degraded daemon

#### EWMA Overflow Protection

- **Bounds Checking** - Input values validated against max_value
- **NaN/Inf Detection** - Rejects invalid floating point values
- **Raises ValueError** - Explicit error on invalid input

#### State File Recovery

- **Automatic Backup** - `.backup` file created on each save
- **Corruption Recovery** - Loads backup if primary file corrupt
- **Forensic Preservation** - Corrupt file saved as `.corrupt` for analysis

#### Configuration Validation

- **Schema Versioning** - Tracks config format version for migrations
- **Injection Prevention** - Validates queue names, ping hosts, comments
- **Constraint Validation** - Enforces floor ≤ ceiling, threshold ordering
- **CLI Validation** - `--validate-config` flag for CI/CD integration

### CLI Tools

#### wanctl (Main Controller)

```bash
wanctl --config /etc/wanctl/wan1.yaml [options]

Options:
  --config PATH          Config file (required, can specify multiple)
  --wan-name NAME        Override WAN name from config
  --debug                Enable debug logging
  --reset                Clear state and EWMA history
  --once                 Single cycle mode (for systemd timer)
  --profile              Enable performance profiling
  --validate-config      Validate config and exit (exit code 0=valid, 1=invalid)
  --health-check-port N  Health endpoint port (default: 9101)
  --metrics-port N       Prometheus metrics port (default: 9100)
```

#### wanctl-calibrate (Setup Wizard)

```bash
wanctl-calibrate --wan-name NAME --router HOST [options]

Options:
  --wan-name NAME        WAN identifier (required)
  --router HOST          Router IP/hostname (required)
  --user USER            SSH username (default: admin)
  --ssh-key PATH         SSH private key path
  --netperf-host HOST    Netperf server (default: netperf.bufferbloat.net)
  --ping-host HOST       RTT measurement target (default: 1.1.1.1)
  --download-queue NAME  RouterOS download queue name
  --upload-queue NAME    RouterOS upload queue name
  --target-bloat MS      Target bloat for binary search (default: 10)
  --output-dir PATH      Config output directory (default: /etc/wanctl)
  --skip-binary-search   Measure raw throughput only
```

#### wanctl-steering (Traffic Steering)

```bash
wanctl-steering --config /etc/wanctl/steering.yaml [options]

Options:
  --config PATH          Steering config file (required)
  --debug                Enable debug logging
  --once                 Single measurement (for systemd timer)
  --reset-steering       Disable steering rule and exit
```

### Deployment

#### FHS-Compliant Paths

```
/opt/wanctl/           # Application code
/etc/wanctl/           # Configuration files
  ├── wan1.yaml        # WAN config
  ├── secrets          # Credentials (mode 640)
  └── ssh/router.key   # SSH key
/var/lib/wanctl/       # State files (EWMA, hysteresis)
/var/log/wanctl/       # Logs (with rotation)
/run/wanctl/           # Lock files
```

#### Systemd Integration

- **Service Template** - `wanctl@.service` for per-WAN instances
- **Timer Template** - `wanctl@.timer` for scheduled execution
- **Steering Service** - `wanctl-steering.service` for traffic routing
- **Service User** - Dedicated `wanctl` user with minimal privileges

#### Installation

```bash
# Interactive wizard (recommended for first-time setup)
sudo ./scripts/install.sh

# Non-interactive (for automation)
sudo ./scripts/install.sh --no-wizard

# Reconfigure existing installation
sudo ./scripts/install.sh --reconfigure

# Uninstall
sudo ./scripts/install.sh --uninstall
```

#### Interactive Setup Wizard

- **Router Connection** - Configure REST API or SSH transport
- **Connection Testing** - Validates credentials with retry options
- **Queue Discovery** - Auto-detects CAKE queues from router
- **Connection Presets** - Optimized defaults for cable/DSL/fiber
- **Multi-WAN Guidance** - Architecture explanation for dual-WAN
- **Steering Setup** - Optional traffic steering configuration

### Configuration

#### Minimal Example

```yaml
wan_name: "wan1"

router:
  transport: "rest"
  host: "192.168.1.1"
  user: "admin"
  password: "${ROUTER_PASSWORD}"
  port: 443
  verify_ssl: false

queues:
  download: "WAN-Download"
  upload: "WAN-Upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 24.0

  download:
    floor_green_mbps: 550
    floor_yellow_mbps: 350
    floor_soft_red_mbps: 275
    floor_red_mbps: 200
    ceiling_mbps: 940
    step_up_mbps: 1.0
    factor_down: 0.92

  upload:
    floor_green_mbps: 30
    floor_yellow_mbps: 25
    floor_red_mbps: 20
    ceiling_mbps: 38
    step_up_mbps: 0.5
    factor_down: 0.90

  thresholds:
    target_bloat_ms: 15.0
    warn_bloat_ms: 45.0
    hard_red_bloat_ms: 80.0
    alpha_baseline: 0.05
    alpha_load: 0.3
    baseline_update_threshold_ms: 3.0

  ping_hosts: ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
  use_median_of_three: true

health_check:
  enabled: true
  port: 9101

metrics:
  enabled: false
  port: 9100
```

See `configs/examples/` for complete examples (cable, DSL, fiber, steering).

### System Requirements

- Python 3.11+ (3.12 recommended)
- MikroTik RouterOS 7.x with CAKE queues configured
- Linux host with systemd (Debian 12, Ubuntu 22.04+)
- REST API enabled on router (recommended) or SSH key authentication

### Dependencies

- `requests>=2.31.0` - REST API transport
- `pyyaml>=6.0.1` - Configuration parsing
- `paramiko>=3.4.0` - SSH transport
- `pexpect>=4.9.0` - SSH command execution

---

## [1.0.0-rc8] - 2026-01-12

**Fallback Connectivity Checks** - Graceful degradation reduces watchdog restarts.

### Added

- **Fallback Connectivity Checks (Mode C)** - Graceful degradation when ICMP fails
  - TCP connectivity verification (port 443 to 1.1.1.1) as fallback
  - Gateway ping test (10.10.110.1) before TCP check
  - Tolerates up to 3 consecutive failures (6 seconds) before restart
  - Significantly reduces Spectrum WAN watchdog restarts (observed 1 restart in 25 hours vs previous 3-5/day)
  - Configurable via `fallback_checks` in YAML config
- **Production Validation** - 38+ hours of profiling data collected
  - Spectrum WAN: 69,539 autorate cycles, 43.7ms avg (1,956ms headroom)
  - ATT WAN: 45,822 autorate cycles, 31.5ms avg (1,968ms headroom)
  - REST API performing excellently (20-23ms router updates)
  - Flash wear protection working perfectly (only 224 updates despite 69k+ cycles)

### Fixed

- **Steering Configuration Mismatch** - Resolved deployment issue
  - Renamed `configs/steering_config.yaml` → `configs/steering.yaml`
  - Deploy script now finds correct config instead of falling back to example template
  - Fixed state file path: `/run/wanctl/spectrum_state.json` (was: `wan1_state.json`)
  - Fixed WAN references: `spectrum`/`att` (was: `wan1`/`wan2`)
  - Steering daemon now operational in production

### Documentation

- **Fallback Implementation Docs** - Comprehensive design documentation
  - `docs/FALLBACK_CONNECTIVITY_CHECKS.md` - Architecture and design rationale
  - `docs/FALLBACK_CHECKS_IMPLEMENTATION.md` - Implementation details
  - `docs/SPECTRUM_WATCHDOG_RESTARTS.md` - Root cause analysis
- **Steering Configuration Issue** - Documented in `docs/STEERING_CONFIG_MISMATCH_ISSUE.md`

### Deployment

- Deployed to production: 2026-01-12 19:20 UTC
- Both containers (cake-spectrum, cake-att) running rc8
- All systems healthy: GREEN/GREEN state, 0 consecutive failures
- Steering daemon operational with correct configuration

---

## [1.0.0-rc7] - 2026-01-10

**Observability & Reliability** - Comprehensive improvements from code review.

### Added

- **Health Check Endpoint** - HTTP endpoint at `http://127.0.0.1:9101/health` (enabled by default)
  - JSON response with status, uptime, version, per-WAN metrics
  - Kubernetes liveness/readiness probe compatible
  - Consecutive failure tracking for alerting
- **Prometheus Metrics Endpoint** - `/metrics` on port 9100 (disabled by default, opt-in)
  - Standard Prometheus text exposition format
  - Bandwidth, RTT, state, cycle count, rate limit events
- **JSON Structured Logging** - Enable via `WANCTL_LOG_FORMAT=json`
  - Compatible with Loki, ELK, Splunk
  - Includes timestamp, level, logger, message, and contextual fields
- **Rate Limiting** - Sliding window rate limiter for router config changes
  - Default: 10 changes per 60 seconds
  - Prevents router API overload during instability
  - Logs warning when throttled, continues cycle without update
- **EWMA Overflow Protection** - Bounds checking on EWMA calculations
  - Input values validated against max_value (default: 1000.0)
  - NaN/Inf detection on input and output
  - Raises ValueError for invalid inputs
- **State File Backup Recovery** - Automatic recovery from `.backup` files
  - Loads backup if primary state file is corrupt
  - Corrupt file preserved as `.corrupt` for analysis
- **Configuration Schema Versioning** - `schema_version: "1.0"` field
  - Tracks config format for future migrations
  - Logs info when version differs from current
  - Backward compatible (defaults to "1.0")
- **Config Validation CLI** - `--validate-config` flag
  - Validates configuration without starting daemon
  - Exit code 0 = valid, 1 = invalid
  - CI/CD integration ready
- **96 New Unit Tests** - 474 total (up from 378)
  - Rate limiter tests (27)
  - Validation security tests (54)
  - Health check tests (11)
  - State machine documentation tests (5)

### Fixed

- **Exit Code Propagation** - `--validate-config` now returns proper exit codes
- **Resource Cleanup** - atexit handler ensures lock cleanup on abnormal termination
- **Cleanup Ordering** - Locks cleaned up first, then SSH/REST connections

### Security

- Thread-safe shutdown using `threading.Event()` eliminates signal handler race conditions

---

## [1.0.0-rc5] - 2026-01-08

**Interactive Setup Wizard** - Guided first-time installation.

### Added

- **Interactive Setup Wizard** - Complete guided setup via `install.sh`
  - Router connection testing (REST API and SSH validation)
  - Queue discovery from router (auto-detects existing CAKE queues)
  - Connection-type presets (cable/DSL/fiber) with optimized defaults
  - Multi-WAN architecture guidance for dual-WAN deployments
  - Secure credential storage with clear user messaging
- **Wizard Modes** - `--no-wizard` (automation), `--reconfigure` (modify existing), `--uninstall`
- **Auto-Dependency Installation** - Installs python3-yaml, python3-pexpect, bc automatically
- **Connection Testing** - Validates credentials with retry/re-enter/skip options

### Fixed

- Password storage handles special characters correctly (`/`, `&`, `\`)
- SSH key path uses `SUDO_USER` home directory when run with sudo
- bc auto-installed as dependency for floor calculations
- Fixed echo color escape codes in install script

---

## [1.0.0-rc4] - 2026-01-08

**REST API Transport** - 2x faster congestion response.

### Added

- **REST API Transport** - RouterOS REST API as recommended transport
  - ~50ms latency vs ~150-200ms for SSH (2-4x faster)
  - Prevents hard congestion cycles in stress tests
  - Password authentication via environment variable
- **Transport Factory** - `get_router_client()` selects appropriate backend
- **Secrets Management** - `/etc/wanctl/secrets` for credentials (mode 640)
- **Paramiko Persistent Connections** - SSH transport now reuses connections

### Performance

| Metric          | REST API | SSH        | Improvement        |
| --------------- | -------- | ---------- | ------------------ |
| Peak RTT        | 194ms    | 404ms      | 2.1x better        |
| Command latency | ~50ms    | ~150-200ms | 3-4x faster        |
| RED/RED cycles  | 0        | 5          | No hard congestion |

### Documentation

- `docs/TRANSPORT_COMPARISON.md` with raw stress test data

---

## [1.0.0-rc3] - 2026-01-07

**Open Source Release** - Package renamed and published.

### Changed

- **BREAKING**: Package renamed from `cake` to `wanctl`
  - All imports changed from `cake.*` to `wanctl.*`
  - Module invocation: `python -m wanctl.autorate_continuous`

### Added

- **CLI Entry Points** - `wanctl`, `wanctl-calibrate`, `wanctl-steering` commands
- **Version Attribute** - `__version__` for programmatic access
- **FHS-Compliant Paths** - `/opt/wanctl`, `/etc/wanctl`, `/var/lib/wanctl`
- **GitHub Actions CI** - Lint and test on every PR
- **Developer Documentation** - `DEVELOPMENT.md`, `CONFIG_SCHEMA.md`
- **Example Configs** - fiber, cable, DSL, multi-WAN templates

### Security

- Atomic lock file creation with `O_CREAT | O_EXCL`
- Explicit 0600 permissions on state files

---

## Pre-Release Development

Development history before open source release:

### v4.5 (2025-12-28)

- Disabled automatic synthetic traffic (netperf/iperf3) after 18-day validation
- Binary search now on-demand only
- Continuous RTT monitoring remains active

### v4.4 (2025-12-28)

- Added log analysis tool (`analyze_logs.py`)
- Completed 18-day production validation period
- Results: 89.3% GREEN, steering active <0.03% of time
- Phase 2B (time-of-day bias) intentionally deferred

### v4.3 (2025-12-15)

- Architecture documentation formalized
- Configuration schema with invariants
- Portability verification checklist

### v4.2 - Phase 2A (2025-12-10)

- 4-state download model (added SOFT_RED)
- RTT-only congestion handling without steering
- Clamp-and-hold floor behavior
- Upload remains 3-state

### v4.1 (2025-12-08)

- Log rotation configuration
- Archived obsolete files
- Raspberry Pi deployment guidance

### v4.0 - CAKE-Aware Steering (2025-12-01)

- Multi-signal congestion detection (RTT + drops + queue)
- Three-state congestion model (GREEN/YELLOW/RED)
- Two-loop architecture (fast steering + slow calibration)
- Hysteresis to prevent flapping

### v3.0 - Binary Search (2025-11-15)

- Flent/LibreQoS calibration methodology
- Quick check mode for efficiency
- Proper bloat calculation
- Unshaping before measurement

### v2.0 - Config-Driven (2025-11-01)

- YAML configuration files
- EWMA smoothing
- Lock file management
- Measurement history

### v1.0 - Initial (2025-10-15)

- Sequential testing
- Hardcoded configs
- Basic bufferbloat mitigation

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

[1.0.0]: https://github.com/kevinb361/wanctl/releases/tag/v1.0.0
[1.0.0-rc7]: https://github.com/kevinb361/wanctl/releases/tag/v1.0.0-rc7
[1.0.0-rc5]: https://github.com/kevinb361/wanctl/releases/tag/v1.0.0-rc5
[1.0.0-rc4]: https://github.com/kevinb361/wanctl/releases/tag/v1.0.0-rc4
[1.0.0-rc3]: https://github.com/kevinb361/wanctl/releases/tag/v1.0.0-rc3
