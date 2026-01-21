# External Integrations

**Analysis Date:** 2026-01-21

## APIs & External Services

**MikroTik RouterOS - Primary Integration (Network Device):**
- **Type:** Network device control API and state query interface
- **What it's used for:** Queue limit configuration, CAKE parameter tuning, routing table updates, connection marking for traffic steering, DSCP enforcement
- **Transport Options:**
  - SSH (port 22): Uses `paramiko` 3.4.0+, persistent connections (~30-50ms per command)
  - REST API (port 443 HTTPS): Uses `requests` 2.31.0+, JSON responses (~50ms per query), FASTER recommended
- **SDK/Client:** Dual-mode factory in `src/wanctl/router_client.py`
  - SSH implementation: `src/wanctl/routeros_ssh.py` (persistent paramiko.SSHClient)
  - REST implementation: `src/wanctl/routeros_rest.py` (stateless requests.Session)
- **Configuration:** `router` section in YAML
  - Transport selection: `transport: "rest"` or `transport: "ssh"`
  - Host/user/auth: `host`, `user`, `password` (REST) or `ssh_key` (SSH)
- **Endpoints/Commands Used:**
  - `/queue/tree` - Query and update CAKE queue limits
  - `/ip/address-list` - Query for steering overrides, add/remove addresses
  - `/ip/firewall/mangle` - Query connection marks for steering state
  - Custom RouterOS script commands via `/system/script/run`
- **State Persistence:** Tracks `last_applied_dl_rate` and `last_applied_ul_rate` to minimize router API calls (flash wear protection)

**Public DNS/Echo Servers - RTT Measurement:**
- **Services:** Cloudflare (1.1.1.1), Google (8.8.8.8), Quad9 (9.9.9.9)
- **What it's used for:** ICMP echo responses to measure round-trip latency, baseline RTT calculation, congestion detection via RTT delta
- **Protocol:** ICMP ping (3 concurrent pings per cycle)
- **Aggregation:** Median-of-three strategy (handles reflector variation, reduces noise)
- **Configuration:** `continuous_monitoring.ping_hosts` in YAML (configurable per WAN)
- **Measurement Interval:** 50ms cycle interval (pings sent per cycle, results parsed via subprocess `ping` command)

**TCP Echo Servers (Fallback Connectivity):**
- **Services:** HTTPS endpoints (port 443) for TCP-based RTT measurement when ICMP blocked/rate-limited
- **What it's used for:** Internet connectivity verification, TCP RTT fallback when ISP blocks ICMP (Spectrum ISP observed behavior)
- **Configuration:** `fallback_checks.tcp_targets` list in YAML (e.g., `[["1.1.1.1", 443], ["8.8.8.8", 443]]`)
- **Trigger:** Activated when consecutive ping failures exceed threshold (graceful_degradation mode)
- **Implementation:** `src/wanctl/rtt_measurement.py` - Falls back to socket-based TCP connection timing
- **Result:** Uses TCP RTT as congestion signal until ICMP recovers

## Data Storage

**State Files (JSON - Local File System):**
- **Location:** `/var/lib/wanctl/<wan_name>_state.json` (configurable via `state_file` in YAML)
- **Format:** Human-readable JSON, compact separators (no spaces)
- **Persistence:** Atomic write-then-move pattern (avoid corruption on crash)
- **Contents:** EWMA baseline RTT, load RTT, measurement history, transition counters, cycle numbers
- **Locking:** fcntl-based file locking for multi-process safety (readers/writers)
- **Implementation:** `src/wanctl/state_utils.py` (atomic_write_json, safe_json_load_file, safe_json_loads)
- **Access Pattern:** Read on daemon start, write every 60 seconds + on state changes

**Configuration Files (YAML):**
- **Location:** `/etc/wanctl/*.yaml` (spectrum.yaml, att.yaml, steering.yaml, etc.)
- **Format:** YAML with environment variable references (e.g., `${ROUTER_PASSWORD}`)
- **Parsing:** PyYAML safe_load (no arbitrary code execution)
- **Implementation:** `src/wanctl/config_base.py` - BaseConfig class with attribute accessor pattern

**Logs (Text - Local File System):**
- **Main Log:** `/var/log/wanctl/<wan_name>.log` (configurable)
- **Debug Log:** `/var/log/wanctl/<wan_name>_debug.log` (optional, high verbosity)
- **Rotation:** External logrotate config at `configs/logrotate_cake.conf` (daily, 7-day retention)
- **Format:** Python logging with timestamps, levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Implementation:** `src/wanctl/logging_utils.py` - setup_logging() configures file handlers

**No Database:** Project uses local JSON state, no SQL database, no external storage backend, no cache server.

## Authentication & Identity

**RouterOS SSH:**
- **Method:** SSH key-based authentication (preferred, secure, no password transmission)
- **Configuration Field:** `router.ssh_key` in YAML (path to private key file, e.g., `/etc/wanctl/ssh/router.key`)
- **Permissions:** 600 or 400 (checked by entrypoint.sh)
- **Implementation:** `src/wanctl/routeros_ssh.py` with `paramiko.RSAKey.from_private_key_file()` or auto-detection
- **Fallback:** pexpect subprocess mode if paramiko fails (for password auth, legacy systems)

**RouterOS REST API:**
- **Method:** HTTP Basic Auth (username/password over HTTPS) or token-based (RouterOS 7.1+)
- **Configuration Fields:** `router.user`, `router.password` in YAML (password can be `${ROUTER_PASSWORD}` env var reference)
- **SSL Verification:** Disabled by default (`verify_ssl: false`) - routers typically use self-signed certificates
- **Implementation:** `src/wanctl/routeros_rest.py` with `requests.auth.HTTPBasicAuth()`
- **Credentials Injection:** Environment variables at container startup or YAML config references

**No OAuth/External IdP:** Direct credential-based auth only; no federated identity, no third-party auth providers.

## Monitoring & Observability

**Health Check HTTP Endpoint (Internal):**
- **Protocol:** HTTP (local only, no authentication, no TLS)
- **Port:** 9101 (configurable in daemon code, defaults to 127.0.0.1:9101)
- **Endpoint:** `GET /health` or `GET /`
- **Response:** JSON with daemon status, uptime, version, per-WAN health, consecutive failure count
- **Status Codes:** 200 (healthy), 503 (degraded)
- **Implementation:** `src/wanctl/health_check.py` with built-in `http.server.HTTPServer`
- **Usage:** Kubernetes liveness/readiness probes, health monitoring systems

**Metrics Endpoint (Prometheus-compatible - Internal):**
- **Protocol:** HTTP (local only, no authentication, no TLS)
- **Port:** 9100 (configurable in daemon code, defaults to 127.0.0.1:9100)
- **Endpoint:** `GET /metrics`
- **Format:** Prometheus text exposition format (v0.0.4)
- **Metrics Exposed:**
  - Gauges: bandwidth_mbps, baseline_rtt_ms, load_rtt_ms, per-WAN state
  - Counters: cycles_total, state_transitions, rate_limit_events, router_updates, ping_failures
- **Implementation:** `src/wanctl/metrics.py` - Custom MetricsRegistry (no prometheus_client dependency to keep slim)
- **Thread-Safe:** Metrics use threading.Lock() for concurrent daemon threads

**Systemd Integration (Host OS):**
- **Watchdog Notification:** `sd_notify(WATCHDOG=1)` periodic heartbeat (prevents watchdog restart during normal operation)
- **Status Updates:** `sd_notify(STATUS="...")` for daemon state messages (visible in `systemctl status`)
- **Degraded State:** Notifies systemd when consecutive failures detected (toggles between healthy/degraded)
- **Implementation:** `src/wanctl/systemd_utils.py` with systemd protocol socket communication
- **Availability:** Check `is_systemd_available()` before notifying (works in containers, optional)

**Error Logging:**
- **Framework:** Python logging module (standard library)
- **Levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Output:** Configured log files per WAN (e.g., spectrum.log, att.log)
- **Propagation:** All errors logged locally; no remote error tracking (Sentry, DataDog, etc.)
- **Files:** `src/wanctl/logging_utils.py` - Centralized logging config

**No External Monitoring Integrations:** Prometheus/Grafana not integrated, Sentry/DataDog not integrated, custom metrics export not implemented. Integration happens at edge (Prometheus scrapes /metrics endpoint, etc.).

## Traffic Steering Integration

**RouterOS Mangle Rules (Packet Classification):**
- **Operation:** Toggle latency-sensitive traffic to alternate WAN during primary WAN degradation
- **Mechanism:** Add/remove mangle rules that mark packets (DSCP EF, AF31, custom marks) for routing policy
- **Rule Identifier:** Comment field `"ADAPTIVE: Steer latency-sensitive to <WAN>"` for identification
- **Implementation:** `src/wanctl/steering/daemon.py` - RouterOSController.enable_steering/disable_steering methods
- **State Machine:** Two-state (PRIMARY_GOOD → PRIMARY_DEGRADED transitions, hysteresis prevents flapping)
- **Decision Logic:** Based on RTT delta vs baseline (threshold configurable), asymmetric streak counting for hysteresis

**Address Lists (Surgical Overrides):**
- **Purpose:** Allow fine-grained routing exceptions (force specific addresses to particular WAN)
- **Format:** RouterOS address lists like `FORCE_OUT_SECONDARY` for manual overrides
- **Implementation:** Queried but not automatically managed (manual operator control)

## CI/CD & Deployment

**Hosting Platform:**
- Primary: Docker containers (self-hosted or orchestrated)
- Alternative: Bare metal Linux with systemd services

**Container Build:**
- Base: `python:3.12-slim` official image
- Build file: `docker/Dockerfile`
- System dependencies installed: openssh-client, iputils-ping, netperf
- Non-root user: `wanctl` (UID/GID auto-assigned)
- Multi-layer: Application code, configurations, entrypoint separated

**Orchestration:**
- Docker Compose: `docker/docker-compose.yml` - Reference multi-WAN setup (wan1, wan2, steering services)
- Network Mode: `host` required for accurate RTT measurements (direct system ping access)
- Health Checks: pgrep-based process monitoring (30s interval, 3 retries)
- Volumes: Config mount (read-only), state mount (read-write), logs mount (optional), SSH key mount (read-only)

**CI Pipeline (Expected from `.github/workflows/`):**
- Tests: `pytest tests/ -v` with 594 test cases
- Linting: `ruff check src/ tests/`
- Type Checking: `mypy src/wanctl/`
- Build: Docker image build test
- Trigger: Push to main, PR, manual dispatch

## Environment Configuration

**Required Environment Variables (at runtime):**
- WANCTL_CONFIG - Path to main daemon config (default: `/etc/wanctl/wan.yaml`)
- WANCTL_STEERING_CONFIG - Path to steering config (if multi-WAN enabled)
- ROUTER_PASSWORD - RouterOS REST API password (alternative: embed in YAML)

**Optional Environment Variables:**
- WANCTL_MODE - Daemon startup mode override
- PYTHONPATH - Python module search path (set to `/opt/wanctl` in containers)
- PYTHONUNBUFFERED - Real-time log output (set to 1 in containers)

**Secrets Injection Methods:**
1. Environment variables (injected at container startup)
2. YAML config file references (e.g., `${ROUTER_PASSWORD}` syntax)
3. SSH private key files (mounted read-only, permissions 600)

**No Vault Integration:** Ansible Vault or external secret managers can wrap config delivery, but wanctl itself uses direct environment/file substitution. No built-in HashiCorp Vault or AWS Secrets Manager support.

## Webhooks & Callbacks

**Incoming Webhooks:** None - system is pull-based only (queries router, measures RTT, sends updates)

**Outgoing Webhooks/Callbacks:** None - events logged locally, metrics exposed via HTTP endpoints (Prometheus-style pull model)

## Network Requirements

**Outbound Connections:**
- RouterOS device: SSH (port 22) or REST (port 443/80, configurable)
- DNS servers: ICMP echo (port 0, ICMP protocol)
- TCP echo services: HTTPS (port 443)
- Gateway: ICMP ping (gateway_ip in fallback_checks config)

**Inbound Connections (optional, internal only):**
- Health check HTTP: Port 9101 (localhost or restricted network)
- Metrics HTTP: Port 9100 (localhost or restricted network)

**Network Mode (Docker):**
- Host network mode required (`network_mode: host` in docker-compose)
- Necessary for: Direct system ping command, accurate link-layer latency, ARP resolution
- Alternative: Overlay network with bridge mode would add latency, not suitable for sub-100ms cycles

---

*Integration audit: 2026-01-21*
