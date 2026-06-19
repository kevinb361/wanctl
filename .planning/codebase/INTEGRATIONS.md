# External Integrations

**Analysis Date:** 2026-06-19

## Router Control — MikroTik RouterOS

**Purpose:** CAKE queue bandwidth updates, firewall mangle rule toggling for WAN steering

**Transport options (configured per-WAN in YAML `router.transport`):**

- `rest` — RouterOS REST API over HTTPS (default for steering; recommended for lower latency)
  - Client: `src/wanctl/routeros_rest.py` (`RouterOSREST`)
  - Auth: HTTP Basic (username + password); password via `${ROUTER_PASSWORD}` env var
  - Port: 443 (HTTPS) or configurable; SSL verify controlled by `router.verify_ssl`
  - Handles: `/queue/tree`, `/ip/firewall/mangle` operations via `requests` HTTP client
  - Mangle rule ID cache keyed by rule comment string to avoid repeated lookup calls
  - Failover: `get_router_client_with_failover()` in `src/wanctl/router_client.py` retries REST → SSH on failure

- `ssh` — RouterOS SSH via persistent paramiko connection
  - Client: `src/wanctl/routeros_ssh.py` (`RouterOSSSH`)
  - Auth: SSH key at `router.ssh_key` path (e.g., `/etc/wanctl/ssh/router.key`)
  - Latency: ~30–50ms reused connection vs ~200ms subprocess SSH

- `linux-cake` — Local `tc` subprocess on Linux bridge VM (no RouterOS needed for CAKE control)
  - Client: `src/wanctl/backends/linux_cake.py` (`LinuxCakeBackend`)
  - Controls CAKE qdiscs on `cake_params.download_interface` / `upload_interface`
  - Requires `CAP_NET_ADMIN`; uses subprocess `tc qdisc change/replace/show`

- `linux-cake-netlink` — Netlink socket extension of `linux-cake` (production default on Spectrum)
  - Client: `src/wanctl/backends/netlink_cake.py` (`NetlinkCakeBackend`)
  - Requires optional dep `pyroute2>=0.9.5`; falls back to subprocess on any netlink failure
  - Performance: ~0.3ms vs ~3.1ms subprocess; reclaims ~5ms per 50ms control cycle

**RouterOS API operations:**
- `/queue tree print` — read queue statistics
- `/queue tree set bandwidth` — update download/upload rate limits
- `/ip firewall mangle enable/disable [find comment="..."]` — toggle steering rules

**Config keys:** `router.host`, `router.user`, `router.ssh_key`, `router.password`, `router.port`, `router.verify_ssl`, `router.transport`
**Secret:** `ROUTER_PASSWORD` env var → `/etc/wanctl/secrets`

---

## RTT Measurement Backends

**Purpose:** ICMP/UDP round-trip time measurement for congestion detection

### icmplib (default)
- Library: `icmplib>=3.0.4` (Python package, no subprocess)
- Entry: `src/wanctl/rtt_measurement.py` (`RTTMeasurement`, `BackgroundRTTThread`)
- Measures: parallel ICMP pings to reflector hosts (e.g., `1.1.1.1`, `9.9.9.9`, `208.67.222.222`)
- Requires: `CAP_NET_RAW` (ICMP raw sockets)
- Config: `measurement.backend: "icmplib"`, `continuous_monitoring.ping_hosts`, `ping_source_ip`
- Strategy: AVERAGE (autorate daemon) or MEDIAN (steering daemon); Hampel outlier filtering

### fping (optional, non-production profiling)
- Binary: `fping` (system package, located via `shutil.which("fping")`)
- Entry: `src/wanctl/fping_measurement.py` (`FpingMeasurement`, `FpingThread`)
- Mode: `fping -C` burst per probe cycle; parses per-host RTT and loss from stdout/stderr
- Config: `measurement.backend: "fping"`; validated by `src/wanctl/check_config_validators.py`
- Status: implemented and wired (Phase 242); non-production profiling only (per MEMORY.md note)
- Lock: per-WAN file lock in `WANCTL_RUN_DIR` to prevent concurrent fping bursts

### IRTT (optional, disabled in production)
- Binary: `irtt` (external Go binary, located via `shutil.which`)
- Entry: `src/wanctl/irtt_measurement.py` (`IRTTMeasurement`, `IRTTThread`)
- Protocol: UDP to configurable server (production config: `104.200.21.31:2112` — Dallas Linode/netperf)
- Provides: OWD asymmetry ratio, per-direction loss, IPDV
- Config: `irtt.enabled: false` in production configs; `irtt.server`, `irtt.port`, `irtt.duration_ms`
- Status: disabled in production (`irtt.enabled: false` in `configs/spectrum.yaml`)

**Backend factory:** `src/wanctl/rtt_backend_factory.py` (`build_rtt_backend`) — constructs icmplib or fping driver thread; fping probed via `shutil.which("fping")` at startup

---

## cake-autorate External Mode

**Purpose:** Standalone cake-autorate (bash) handles rate shaping; wanctl state bridge polls its log and publishes health/state

**Components:**
- `cake-autorate` bash script — external binary; not bundled; configured via `configs/cake-autorate/config.spectrum.sh`, `configs/cake-autorate/config.att.sh`
- State bridge Python scripts — poll cake-autorate log, write `spectrum_state.json` / `att_state.json`, serve health endpoint
- Systemd units: `deploy/systemd/cake-autorate-spectrum.service`, `deploy/systemd/cake-autorate-att.service`, `deploy/systemd/cake-autorate-spectrum-state-bridge.service`, `deploy/systemd/cake-autorate-att-state-bridge.service`

**Data flow:**
1. cake-autorate writes rate/RTT decisions to `/var/log/cake-autorate/cake-autorate.{wan}.log`
2. State bridge reads log, writes state JSON to `/var/lib/wanctl/{wan}_state.json`
3. Steering daemon reads state JSON for baseline RTT and congestion state
4. Health endpoint served by state bridge on `CAKE_AUTORATE_BRIDGE_HEALTH_HOST:PORT`

**Key env vars (state bridge systemd units):**
- `WANCTL_EXTERNAL_WAN_NAME` — spectrum or att
- `WANCTL_EXTERNAL_DL_IF` / `WANCTL_EXTERNAL_UL_IF` — interface names
- `CAKE_AUTORATE_BRIDGE_LOG` — path to cake-autorate log
- `WANCTL_EXTERNAL_STATE_PATH` — output state JSON path
- `WANCTL_EXTERNAL_METRICS_DB` — SQLite metrics DB path
- `WANCTL_EXTERNAL_BASELINE_RTT` — seeded baseline RTT value

---

## Data Storage — SQLite

**Purpose:** Time-series metrics, alert history, adaptive tuning state, config snapshots

**Database files:**
- Per-WAN databases: `/var/lib/wanctl/metrics-{wan}.db` (e.g., `metrics-spectrum.db`, `metrics-att.db`)
- Legacy single database: `/var/lib/wanctl/metrics.db` (fallback when per-WAN files absent)

**Client:** stdlib `sqlite3` — no ORM
**Schema:** `src/wanctl/storage/schema.py` — `metrics` table + `alerts` table; time-indexed with composite index `(wan_name, metric_name, timestamp)`
**Writer:** `src/wanctl/storage/writer.py` (`MetricsWriter`) — deferred via `src/wanctl/storage/deferred_writer.py` (`DeferredIOWorker`) to isolate storage I/O from 50ms control loop
**Reader:** `src/wanctl/storage/reader.py` — granularity auto-selection (raw/1m/5m aggregates)
**Downsampler:** `src/wanctl/storage/downsampler.py` — background aggregation
**Retention:** `src/wanctl/storage/retention.py` — raw data 1h, 1m aggregates 24h, 5m aggregates 7d (per `configs/spectrum.yaml` `storage.retention`)
**Discovery:** `src/wanctl/storage/db_utils.py` (`discover_wan_dbs`, `query_all_wans`) — merges per-WAN results, sorted by timestamp

**Prometheus-compatible metric names stored** (subset from `src/wanctl/storage/schema.py`):
- `wanctl_rtt_ms`, `wanctl_rtt_baseline_ms`, `wanctl_rtt_delta_ms`
- `wanctl_rate_download_mbps`, `wanctl_rate_upload_mbps`
- `wanctl_state` (0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED)
- `wanctl_cake_tin_dropped`, `wanctl_cake_tin_ecn_marked`, `wanctl_cake_tin_delay_us`, `wanctl_cake_tin_backlog_bytes`
- `wanctl_irtt_rtt_ms`, `wanctl_irtt_ipdv_ms`, `wanctl_irtt_loss_up_pct`, `wanctl_irtt_loss_down_pct`

---

## State Files — JSON

**Purpose:** Persistent daemon state across restarts; cross-process state sharing between steering and autorate

**Files:**
- `/var/lib/wanctl/spectrum_state.json` — Spectrum WAN controller state (baseline RTT, current rates, congestion state)
- `/var/lib/wanctl/att_state.json` — ATT WAN controller state

**Producers:** `src/wanctl/wan_controller.py` (wanctl@ mode) or state bridge scripts (cake-autorate mode)
**Consumers:** `src/wanctl/steering/daemon.py` reads `cake_state_sources.primary` path for baseline RTT and steering decisions

---

## Health Endpoints — HTTP JSON

**Purpose:** Liveness/readiness probes; external monitoring; dashboard polling

**Autorate health server:**
- Implementation: `src/wanctl/health_check.py` — stdlib `http.server.HTTPServer` in daemon thread
- Port: 9101 (per `configs/spectrum.yaml` `health_check.port`)
- Bound to WAN-specific IP (e.g., `10.10.110.223` for Spectrum) so both WANs can use same port on separate IPs
- Endpoints: `GET /health` — returns JSON with controller state, cycle stats, disk space, RTT, runtime pressure
- Also serves historical metrics via `GET /history`, queue status, budget breakdown

**Steering health server:**
- Implementation: `src/wanctl/steering/health.py`
- Served from steering daemon thread

---

## Prometheus Metrics Endpoint — HTTP

**Purpose:** Prometheus-compatible scraping; burst-validation telemetry

**Implementation:** `src/wanctl/metrics.py` (`MetricsServer`, `MetricsRegistry`)
- Custom lightweight HTTP server (no `prometheus_client` library)
- Follows Prometheus text exposition format v0.0.4
- Port: 9100 (per `configs/spectrum.yaml` `metrics.port`)
- Endpoint: `GET /metrics`
- Thread-safe registry with gauges and counters; scrape callbacks registered at startup

---

## Alerting — Discord Webhook

**Purpose:** Congestion event notifications; recovery alerts; WAN state changes

**Implementation:** `src/wanctl/webhook_delivery.py` (`WebhookDelivery`, `DiscordFormatter`)
- HTTP POST via `requests` library to Discord webhook URL
- Non-blocking: delivery runs in daemon thread to avoid blocking 50ms control loop
- Retry on 5xx/timeout; no retry on 4xx
- Rate-limited to prevent Discord API abuse
- Rich embeds with color-coded severity (critical=red, warning=orange, recovery=green, info=blue)
- Formatted by `DiscordFormatter`; extensible via `AlertFormatter` Protocol for other backends (ntfy.sh documented in source)

**Alert engine:** `src/wanctl/alert_engine.py` (`AlertEngine`)
- Per-event cooldown suppression keyed on `(alert_type, wan)` tuple
- Cooldown times: configurable per rule; defaults in `RULE_DEFAULTS`
- Persistence: alerts stored to `alerts` table in per-WAN SQLite database via `MetricsWriter`
- Enabled/disabled per-rule; master switch in config `alerting.enabled`

**Config:** `alerting.webhook_url: "${DISCORD_WEBHOOK_URL}"` — expanded from env at config load
**Secret:** `DISCORD_WEBHOOK_URL` env var → `/etc/wanctl/secrets`

---

## WAN Steering — RouterOS Mangle Rules

**Purpose:** Route latency-sensitive connections to alternate WAN on primary congestion

**Implementation:** `src/wanctl/steering/daemon.py`
- Reads Spectrum RTT delta from state file; compares to thresholds
- Toggles RouterOS mangle rule identified by `mangle_rule.comment` key
- Three layers: DSCP (EF/AF31 = latency-sensitive), connection-marks (`QOS_HIGH`, `QOS_MEDIUM`, `GAMES`), address lists (`FORCE_OUT_{WAN}`)
- Uses REST transport (`configs/steering.yaml` `router.transport: "rest"`)

---

## systemd Integration

**Purpose:** Service lifecycle, watchdog, process supervision

**Implementation:** `src/wanctl/systemd_utils.py`
- `systemd.daemon.notify` — `READY=1`, `WATCHDOG=1`, `WATCHDOG_USEC`, `STATUS=`, `ERRNO=`
- Graceful no-op fallback when `systemd-python` not installed
- Watchdog timeout: 30s (`WatchdogSec=30s` in `deploy/systemd/wanctl@.service`)
- Daemon only sends watchdog ping when cycle is healthy (not on consecutive failures)

**Service units:**
- `deploy/systemd/wanctl@.service` — parameterized by WAN name; pure wanctl controller mode
- `deploy/systemd/cake-autorate-spectrum.service` / `cake-autorate-att.service` — external cake-autorate
- `deploy/systemd/cake-autorate-spectrum-state-bridge.service` / `cake-autorate-att-state-bridge.service` — bridge daemons
- `deploy/systemd/steering.service` — steering daemon (both modes)
- `deploy/systemd/wanctl-nic-tuning.service`, `wanctl-bridge-qos.service` — NIC and QoS init
- `deploy/systemd/silicom-bypass-init.service`, `silicom-bypass-watchdog@.service` — hardware bypass watchdog for Silicom NIC

---

## External Binaries (subprocess)

**Purpose:** Tools invoked as subprocesses for measurements and network control

| Binary | Purpose | Module |
|--------|---------|--------|
| `tc` | CAKE qdisc control (linux-cake backend) | `src/wanctl/backends/linux_cake.py` |
| `fping` | RTT measurement bursts (fping backend, cake-autorate) | `src/wanctl/fping_measurement.py` |
| `irtt` | UDP OWD/IPDV measurement (disabled) | `src/wanctl/irtt_measurement.py` |
| `netperf` | Throughput calibration under load | `src/wanctl/calibrate_measurements.py` |

All subprocess calls use `subprocess.run`/`Popen` with explicit argument lists (not shell=True).

---

## CI/CD — GitHub Actions

**Purpose:** Syntax validation, lint, test

**Pipeline:** `.github/workflows/ci.yml`
- Jobs: `lint` (pyflakes), `test` (pytest), `syntax-check` (py_compile)
- All run on `ubuntu-latest` with Python 3.12
- Triggers: push/PR to `main`
- Note: CI pipeline is minimal (pyflakes only, not full ruff); full `make ci` is more comprehensive

**Hosting:** Project hosted on private Gitea at `10.10.110.208:3030` (SSH alias `gitea:`); `.github/workflows/` is present but GitHub mirroring status is unconfirmed

---

## Monitoring Infrastructure

**Purpose:** Operational visibility into production deployments

**Logrotate:** `configs/logrotate-wanctl` → `/etc/logrotate.d/wanctl` on each production host
**journald:** `StandardOutput=journal` / `StandardError=journal` in systemd units; `SyslogIdentifier=wanctl-{wan}`
**Prometheus:** Self-hosted HTTP endpoint at `:9100/metrics` per WAN (scraped externally)
**Health API:** HTTP JSON at `:9101/health` per WAN (consumed by dashboard, external checks)
**CLI tools:**
- `wanctl-history` — queries per-WAN SQLite for historical metrics
- `wanctl-operator-summary` — tabular operational summary
- `wanctl-dashboard` — live Textual TUI polling health endpoint

---

## Environment Variables Reference

| Variable | Required | Source | Consumer |
|----------|----------|--------|----------|
| `ROUTER_PASSWORD` | Yes (REST mode) | `/etc/wanctl/secrets` | `RouterOSREST`, `router_client.py` |
| `DISCORD_WEBHOOK_URL` | Yes (alerting) | `/etc/wanctl/secrets` | `autorate_config.py`, `steering/daemon.py` |
| `WANCTL_STATE_DIR` | No (default `/var/lib/wanctl`) | systemd unit | `path_utils.py` |
| `WANCTL_LOG_DIR` | No (default `/var/log/wanctl`) | systemd unit | `logging_utils.py` |
| `WANCTL_RUN_DIR` | No (default `/run/wanctl`) | systemd unit | lock files, fping/irtt locks |
| `WANCTL_LOG_FORMAT` | No (default `text`) | env | `logging_utils.py` — `text` or `json` |
| `CAKE_ROOT` | No | env | `path_utils.py` — overrides cake-autorate log root |
| `NO_COLOR` | No | env | `check_config.py`, `dashboard/app.py` |

---

*Integration audit: 2026-06-19*
