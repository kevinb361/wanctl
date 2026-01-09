# External Integrations

**Analysis Date:** 2026-01-09

## APIs & External Services

**MikroTik RouterOS (Network Device - Primary Integration):**
- Type: Network device control API
- Transport: Dual-mode (REST API recommended, SSH fallback)
- SDK/Client: `requests` library for REST, `paramiko` for SSH
- Auth: REST uses username/password from config, SSH uses SSH key at `/etc/wanctl/ssh/router.key`
- Endpoints used:
  - `/queue/tree` - Queue limit management
  - `/interface` - Interface statistics
  - `/routing/table` - Routing table management
  - `/ip/address-list` - Address list for surgical steering
- Files: `src/wanctl/routeros_rest.py`, `src/wanctl/routeros_ssh.py`, `src/wanctl/router_client.py`

**Public Ping Reflectors (RTT Measurement):**
- Type: ICMP echo servers (external reflectors)
- Hosts: 1.1.1.1 (Cloudflare), 8.8.8.8 (Google), 9.9.9.9 (Quad9)
- Protocol: ICMP ping (3 pings per cycle, median aggregation)
- Configuration: `configs/spectrum.yaml` line 55
- Purpose: Baseline and current RTT measurement for congestion detection
- Typical latency: 24ms (cable), 48ms (DSL)

**Netperf Server (Optional - Currently Disabled):**
- Type: Synthetic throughput testing
- Host: 104.200.21.31 (Dallas, TX)
- Status: **DISABLED** as of 2025-12-28 (Phase 2A validation complete)
- Was used for: Binary search bandwidth discovery
- Reason: Replaced by CAKE-aware bandwidth estimation
- Reference: `docs/SYNTHETIC_TRAFFIC_DISABLED.md`

## Data Storage

**Configuration:**
- YAML files in `configs/` directory
- Environment variable substitution supported (e.g., `${ROUTER_PASSWORD}`)
- Per-WAN configuration (spectrum.yaml, att.yaml, steering config)

**State Management:**
- JSON file-based persistence in `/var/lib/wanctl/`
- State files: `<wan_name>_state.json`
- Schema: EWMA values, measurement history, cycle counters, state machine state
- Reference: `CLAUDE.md` "State File Schema" section

## Monitoring & Observability

**Logging:**
- File-based logging to `/var/log/wanctl/continuous.log` (INFO level)
- Debug logs to `continuous_debug.log` when enabled
- Log rotation via `/etc/logrotate.d/wanctl` (daily, 7-day retention)
- Syslog-compatible format for integration with system log aggregation

**No External Monitoring Integrations:**
- Prometheus/Grafana - Not integrated
- Sentry/DataDog - Not integrated
- Custom metrics export - Not implemented

## Traffic Steering Integration

**RouterOS Mangle Rules:**
- Type: Packet classification and routing policy
- Operation: Toggle latency-sensitive traffic to alternate WAN during degradation
- Rule identifier: Comment `"ADAPTIVE: Steer latency-sensitive to <WAN>"`
- Configuration: `configs/steering_config_v2.yaml` lines 25-27
- Target packets: DSCP EF (voice), AF31, QOS_HIGH/MEDIUM
- Implementation: `src/wanctl/steering/daemon.py` (RouterOSController.enable_steering/disable_steering)

## Service Management

**systemd Integration:**
- Service template: `wanctl@<wan_name>.service`
- Timer-based execution: `wanctl@<wan_name>.timer` (default: every 10 minutes for autorate, every 2 seconds for steering)
- Watchdog: Optional systemd watchdog with health tracking
- Log destination: systemd journal (via logging module)

## Environment Configuration

**Development:**
- Local YAML configs with test RouterOS credentials
- Ping reflectors: Public IPs (1.1.1.1, 8.8.8.8)
- State directory: `.venv/state/` or local test paths

**Staging:**
- Separate staging RouterOS instance or test device
- Same ping reflectors as production
- State files for test data

**Production:**
- Encrypted credentials in `/etc/wanctl/secrets`
- SSH keys at `/etc/wanctl/ssh/router.key`
- State persistence at `/var/lib/wanctl/`
- Logs at `/var/log/wanctl/`
- Systemd timers for continuous and steering operations

---

*Integration audit: 2026-01-09*
*Update when adding/removing external services*
