# External Integrations

**Analysis Date:** 2026-03-10

## APIs & External Services

**MikroTik RouterOS — Primary Device Integration:**
- Used for: CAKE queue limit adjustment, routing rule toggling for traffic steering, queue statistics reads
- Transport (REST): HTTPS to RouterOS 7.x REST API on port 443 (default, recommended)
  - SDK/Client: `requests.Session` in `src/wanctl/routeros_rest.py`
  - Auth: HTTP Basic Auth (username + password)
  - Config vars: `router.host`, `router.user`, `router.password` (supports `${ROUTER_PASSWORD}` env ref)
  - Endpoints used: `PATCH /rest/queue/tree/{id}`, `GET /rest/queue/tree`, `POST /rest/queue/tree/reset-counters`, `PATCH /rest/ip/firewall/mangle/{id}`
  - ID caching: `_queue_id_cache` and `_mangle_id_cache` dicts reduce lookup round-trips
- Transport (SSH): Port 22 via persistent paramiko SSHClient
  - SDK/Client: `paramiko.SSHClient` in `src/wanctl/routeros_ssh.py`
  - Auth: SSH key file (path from `router.ssh_key`, e.g., `/etc/wanctl/ssh/router.key`)
  - Config vars: `router.host`, `router.user`, `router.ssh_key`
- Factory + failover: `src/wanctl/router_client.py` — `get_router_client()` (single transport), `get_router_client_with_failover()` (`FailoverRouterClient`: REST primary, SSH fallback with exponential re-probe backoff: 30s → 300s)
- SSL: `verify_ssl: false` typical (routers use self-signed certs); `urllib3.disable_warnings(InsecureRequestWarning)` suppressed when disabled

**Public ICMP Reflectors — RTT Measurement:**
- Services: Cloudflare `1.1.1.1`, Google `8.8.8.8`, Quad9 `9.9.9.9`
- Used for: Round-trip latency measurement as congestion signal; delta from frozen baseline drives state machine
- Protocol: Raw ICMP via `icmplib` (primary, hot-path); subprocess `ping` retained for `calibrate.py`
- Config: `continuous_monitoring.ping_hosts` in YAML (list, configurable per WAN)
- Strategy: `use_median_of_three: true` (median of 3 concurrent pings per cycle)
- Capability required: `CAP_NET_RAW` (systemd `AmbientCapabilities`, or Docker `--cap-add NET_RAW`)
- Implementation: `src/wanctl/rtt_measurement.py`

**TCP Fallback Connectivity — ICMP Blackout Handling:**
- Services: HTTPS endpoints (port 443) at same reflector IPs
- Used for: TCP-based RTT when ISP (Spectrum) blocks ICMP; prevents false positive congestion detection
- Protocol: TCP socket connect timing
- Trigger: Activated on consecutive ICMP failures (graceful degradation mode)
- Implementation: `src/wanctl/rtt_measurement.py` — TCP RTT path (v1.1.0 fix)

## Data Storage

**SQLite — Time-Series Metrics Database:**
- Location: `/var/lib/wanctl/metrics.db` (default `DEFAULT_DB_PATH` in `src/wanctl/storage/writer.py`)
- Used for: Historical metrics storage, trend analysis, `wanctl-history` CLI queries
- Client: Python stdlib `sqlite3`; WAL mode enabled for concurrent read/write
- Schema: Single `metrics` table (id, timestamp, wan_name, metric_name, value, labels, granularity) defined in `src/wanctl/storage/schema.py`
- Indexes: on `timestamp`, composite `(wan_name, metric_name, timestamp)`, `(granularity, timestamp)`
- Granularities: `raw`, `1m`, `5m`, `1h` (downsampled by `src/wanctl/storage/downsampler.py`)
- Writer: `MetricsWriter` singleton in `src/wanctl/storage/writer.py` — thread-safe, batch write support
- Reader: `src/wanctl/storage/reader.py` — `query_metrics()`, `select_granularity()`, `compute_summary()`
- Maintenance: Hourly cleanup + downsample + VACUUM in `src/wanctl/storage/maintenance.py`
- Stored metrics (from `src/wanctl/storage/schema.py`): `wanctl_rtt_ms`, `wanctl_rtt_baseline_ms`, `wanctl_rtt_delta_ms`, `wanctl_rate_download_mbps`, `wanctl_rate_upload_mbps`, `wanctl_state`, `wanctl_steering_enabled`, `wanctl_wan_zone`, `wanctl_wan_weight`, `wanctl_wan_staleness_sec`

**JSON State Files — Daemon State Persistence:**
- Location: `/var/lib/wanctl/<wan_name>_state.json`; configurable as `state_file` in YAML
- Used for: EWMA baseline RTT persistence across restarts, steering state, congestion zone (written by autorate, read by steering for WAN-aware scoring)
- Write pattern: Atomic write via `atomic_write_json()` in `src/wanctl/state_utils.py` (temp file + fsync + rename — crash-safe)
- Write frequency: Every 60s + on state transitions; dirty-tracking excludes high-frequency metadata (congestion zone) to prevent write amplification
- Steering state: `/var/lib/wanctl/steering_state.json`

**YAML Configuration Files:**
- Location: `/etc/wanctl/*.yaml` (one per WAN instance + steering)
- Parsing: `yaml.safe_load()` — no arbitrary code execution
- Env var substitution: `${VAR_NAME}` syntax resolved at runtime in `src/wanctl/routeros_rest.py` and `src/wanctl/config_base.py`
- Schema version: `schema_version: "1.0"` field for forward compatibility
- Examples: `configs/examples/` (cable, dsl, fiber, wan1, wan2, steering)
- Implementation: `src/wanctl/config_base.py` — `validate_field()` with dot-notation path, type checks, range/choice validation

**Log Files:**
- Location: `/var/log/wanctl/<wan_name>.log` and `<wan_name>_debug.log`
- Format: JSON structured logging via `JSONFormatter` in `src/wanctl/logging_utils.py`; fields: timestamp (ISO 8601 UTC), level, logger, message + extras (wan_name, state, rtt_delta, dl_rate, ul_rate)
- Rotation: External logrotate config at `configs/logrotate-wanctl`

## Authentication & Identity

**RouterOS SSH:**
- Method: SSH key-based (private key file, no password transmission)
- Config: `router.ssh_key` → path to private key (e.g., `/etc/wanctl/ssh/router.key`)
- Required permissions: 600 or 400 (enforced by `docker/entrypoint.sh`)
- Implementation: `paramiko.SSHClient` with `paramiko.RSAKey.from_private_key_file()` in `src/wanctl/routeros_ssh.py`

**RouterOS REST:**
- Method: HTTP Basic Auth over HTTPS
- Config: `router.user` + `router.password` (password supports `${ENV_VAR}` reference)
- Credentials injected via: (1) systemd `EnvironmentFile=/etc/wanctl/secrets`, (2) YAML env ref, (3) Docker environment block
- No OAuth, no token rotation, no external IdP

## Monitoring & Observability

**Health Check HTTP Endpoint:**
- Binding: `127.0.0.1:9101` (autorate), `127.0.0.1:9103` (steering)
- Endpoint: `GET /health` — JSON response with daemon status, uptime, version, cycle stats, disk space, `wan_awareness` section (v1.11)
- Status codes: 200 (healthy), 503 (degraded)
- Implementation: `src/wanctl/health_check.py` and `src/wanctl/steering/health.py` using stdlib `http.server.HTTPServer`

**Prometheus-Compatible Metrics Endpoint:**
- Binding: `127.0.0.1:9100` (autorate daemon)
- Endpoint: `GET /metrics` — Prometheus text exposition format v0.0.4
- Metrics: gauges (bandwidth_mbps, baseline_rtt_ms, load_rtt_ms, state), counters (cycles_total, state_transitions, router_updates, ping_failures)
- Implementation: `src/wanctl/metrics.py` — custom `MetricsRegistry` (no `prometheus_client` dependency); thread-safe via `threading.Lock`
- Note: Pull model only; no push to external Prometheus/Grafana

**Systemd Watchdog & Status:**
- Protocol: `sd_notify` socket messages (`WATCHDOG=1`, `STATUS=...`, `STOPPING=1`, `READY=1`)
- Watchdog timeout: `WatchdogSec=30s` in `systemd/wanctl@.service`
- Behavior: Daemon sends `WATCHDOG=1` every successful cycle; stops sending on failure — systemd auto-restarts
- Degraded notification: `STATUS=Degraded - {message}` on consecutive failures
- Implementation: `src/wanctl/systemd_utils.py` — graceful no-op if `systemd.daemon` module absent
- Circuit breaker: `StartLimitBurst=5` / `StartLimitIntervalSec=300` — stops restarting after 5 failures in 5 min

**Structured Logging (journald):**
- Daemon stdout/stderr → systemd journal (`StandardOutput=journal` in service unit)
- `SyslogIdentifier=wanctl-%i` for per-instance filtering
- JSON formatter enables downstream log aggregation (Loki, ELK, Splunk, CloudWatch)
- No remote error tracking (Sentry, Datadog) — local logs only

## CI/CD & Deployment

**Hosting:**
- Primary: Linux host with systemd (`systemd/wanctl@.service` template + `systemd/steering.service`)
- Alternative: Docker containers (`docker/docker-compose.yml`)
- No cloud hosting, no Kubernetes manifests present

**CI Pipeline:**
- No `.github/workflows/` directory detected — no automated CI configured
- Local CI gate: `make ci` → `make lint` + `make type` + `make coverage-check` (90% threshold)
- Security gate: `make security` → pip-audit + bandit + detect-secrets + pip-licenses

## Environment Configuration

**Required env vars at runtime:**
- `ROUTER_PASSWORD` — when using REST transport with `${ROUTER_PASSWORD}` YAML reference

**Optional env vars:**
- `WANCTL_CONFIG` — override config path (default: `/etc/wanctl/wan.yaml`)
- `WANCTL_STEERING_CONFIG` — override steering config path
- `WANCTL_STATE_DIR`, `WANCTL_LOG_DIR`, `WANCTL_RUN_DIR` — override FHS paths

**Secrets location:**
- Production: `/etc/wanctl/secrets` (plain env file, loaded by systemd `EnvironmentFile`)
- SSH key: `/etc/wanctl/ssh/router.key` (600 permissions, mounted read-only in Docker)
- Docker: `environment:` block in compose or host env injection

## Webhooks & Callbacks

**Incoming:** None — system is pull-based only

**Outgoing:** None — events logged locally; metrics exposed as HTTP pull endpoints (Prometheus scrape model)

## Network Requirements

**Outbound:**
- RouterOS device: port 443 (REST HTTPS) or port 22 (SSH)
- ICMP reflectors: raw ICMP (1.1.1.1, 8.8.8.8, 9.9.9.9)
- TCP fallback: port 443 to reflector IPs

**Inbound (localhost only):**
- Health check: port 9101 (autorate), 9103 (steering)
- Prometheus metrics: port 9100

**Docker network mode:** `network_mode: host` mandatory — required for raw ICMP and accurate link-layer RTT measurements

---

*Integration audit: 2026-03-10*
