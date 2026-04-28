# Subsystem Operations Reference

This document covers runtime subsystems that are not fully described by the core configuration guide.

## Storage Architecture

Implementation map:

- `src/wanctl/storage/writer.py`: `MetricsWriter`, SQLite connection ownership, table writes.
- `src/wanctl/storage/deferred_writer.py`: `DeferredIOWorker`, queued background writes for metrics, alerts, and reflector events.
- `src/wanctl/storage/schema.py`: metric, alert, reflector event, benchmark, and tuning tables plus schema maintenance.
- `src/wanctl/storage/downsampler.py`: raw to `1m`, `5m`, and `1h` aggregate generation.
- `src/wanctl/storage/retention.py`: per-granularity cleanup and incremental vacuum.
- `src/wanctl/storage/maintenance.py`: startup and periodic bounded maintenance.
- `src/wanctl/storage/db_utils.py`: per-WAN DB discovery and merged query helpers.
- `src/wanctl/storage/reader.py`: history readers used by CLI and HTTP history views.

wanctl stores historical observability data in SQLite using WAL mode. Each autorate process writes to its configured database path, normally a per-WAN file such as `/var/lib/wanctl/metrics-spectrum.db`.

Hot-path writes are queued through `DeferredIOWorker` so SQLite I/O does not block the 50ms controller loop. The background worker drains metric, alert, and reflector event writes into `MetricsWriter`, which owns the process-local SQLite connection.

Tables include:

- `metrics`: time-series metrics with `raw`, `1m`, `5m`, and `1h` granularities.
- `alerts`: fired alert history plus webhook delivery status.
- `reflector_events`: reflector deprioritization and recovery transitions.
- `benchmarks`: RRUL and bufferbloat benchmark history.
- `tuning_params`: adaptive tuning decisions.

Retention and downsampling are separate operations. Raw samples are aggregated to `1m`, then `5m`, then `1h` according to `storage.retention.*`. Cleanup deletes rows per granularity in batches. Startup maintenance is watchdog-safe and may defer downsampling when a startup time budget is active. Space reclamation uses incremental vacuum after large deletions instead of full `VACUUM` in the hot path.

## Dashboard

Implementation map:

- `src/wanctl/dashboard/app.py`: `DashboardApp`, CLI parsing, live polling orchestration.
- `src/wanctl/dashboard/config.py`: `DashboardConfig`, YAML loading, CLI overrides.
- `src/wanctl/dashboard/poller.py`: `EndpointPoller`, HTTP polling and error handling.
- `src/wanctl/dashboard/widgets/history_browser.py`: history tab and `/metrics/history` fetching.
- `src/wanctl/dashboard/widgets/history_state.py`: history state classification.

`wanctl-dashboard` is a local Textual TUI for operator monitoring. It polls autorate and steering health endpoints and renders live WAN state, rates, RTT delta, cycle budget, steering status, and short in-process sparklines.

Default endpoints:

- autorate: `http://127.0.0.1:9101/health`
- steering: `http://127.0.0.1:9102/health`

Configuration is loaded from `~/.config/wanctl/dashboard.yaml` unless `--config` is supplied. CLI flags override the config file.

```yaml
autorate_url: "http://127.0.0.1:9101"
secondary_autorate_url: "http://127.0.0.1:9111"
steering_url: "http://127.0.0.1:9102"
refresh_interval: 2
wan_rate_limits:
  spectrum:
    dl_mbps: 940
    ul_mbps: 38
```

The History tab queries the selected autorate endpoint's `/metrics/history`. When that endpoint is attached to a live daemon, it reads that daemon's configured local DB. For authoritative merged cross-WAN history, use:

```bash
sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json
```

## Backend Transports

Implementation map:

- `src/wanctl/backends/base.py`: `RouterBackend` control contract.
- `src/wanctl/backends/__init__.py`: `get_backend()` transport factory.
- `src/wanctl/backends/routeros.py`: RouterOS REST/SSH-compatible backend.
- `src/wanctl/backends/linux_cake.py`: local Linux CAKE control through `tc` subprocesses.
- `src/wanctl/backends/netlink_cake.py`: pyroute2/netlink CAKE writes with `tc` fallback.
- `src/wanctl/backends/linux_cake_adapter.py`: daemon-compatible adapter around Linux CAKE backends.

Supported `router.transport` values:

- `rest`: RouterOS REST API for queue and rule control.
- `ssh`: RouterOS SSH command execution.
- `linux-cake`: local Linux CAKE qdisc control via `tc` subprocess.
- `linux-cake-netlink`: local Linux CAKE qdisc control via pyroute2/netlink, with automatic fallback to `tc` subprocess.

`linux-cake` and `linux-cake-netlink` are intended for bridge or VM deployments where CAKE runs on the Linux host. Steering rule enable/disable remains a RouterOS-side concern and is not performed by the Linux CAKE backend.

Install optional netlink support with:

```bash
pip install 'wanctl[netlink]'
```

## Bridge QoS And Priority Protection

Implementation map:

- `deploy/nftables/bridge-qos.nft`: bridge-level DSCP classification rules.
- `deploy/systemd/wanctl-bridge-qos.service`: loads the bridge QoS ruleset.

Bridge QoS classifies download traffic into CAKE `diffserv4` tins before packets reach the Linux CAKE egress qdisc. It exists because inbound ISP traffic often arrives as `CS0`, so endpoint DSCP markings alone are not enough for useful download tin separation.

The bridge classifier can:

- trust existing non-zero DSCP when endpoints already mark traffic.
- restore DSCP from conntrack marks for established flows.
- classify selected latency-sensitive reply traffic into `EF`.
- classify selected media or QUIC reply traffic into `AF41`.
- demote large unclassified transfers into lower-priority tins.

Operational checks:

```bash
sudo nft list table bridge qos
curl -s http://127.0.0.1:9101/health | python3 -m json.tool
PYTHONPATH=/opt python3 -m wanctl.history --db /var/lib/wanctl/metrics-spectrum.db --last 1h --tins --json
```

Priority traffic is protected by not listing EF/priority queues in the wanctl queue config. wanctl adjusts only the configured CAKE queues; fixed EF queues remain outside the adaptive rate controller and rely on CAKE tin scheduling plus router/bridge classification.

## Health And Metrics

Implementation map:

- `src/wanctl/health_check.py`: `HealthCheckHandler`, `/health`, `/metrics`, and `/metrics/history` handlers.
- `src/wanctl/metrics.py`: `MetricsRegistry`, autorate, steering, storage, runtime, and process metrics.

`GET /health` returns HTTP 200 when healthy and HTTP 503 when degraded. Degraded means at least one of: repeated controller failures, router unreachable, or disk/runtime critical status.

Major response sections:

- `wans[]`: per-WAN rate, state, hysteresis, RTT, connectivity, measurement, IRTT, reflector, fusion, CAKE, tuning, storage, and runtime status.
- `alerting`: alert engine enabled state, fired count, and active cooldowns.
- `disk_space`: free/total bytes and warning state for `/var/lib/wanctl`.
- `summary`: compact operator-facing status rows.
- `storage` and `runtime`: bounded pressure status for SQLite and process memory.

`GET /metrics/history` queries stored SQLite metrics. Query parameters include `range`, `from`, `to`, `metrics`, `wan`, `limit`, and `offset`. Responses include `metadata.source.mode` and `metadata.source.db_paths` so callers can distinguish endpoint-local data from merged discovery fallback.

The Prometheus text exporter is lightweight and does not require `prometheus_client`. It exposes autorate, steering, burst, storage, checkpoint, WAL, ping failure, router update, process RSS, and runtime pressure metrics.

## Alerting

Implementation map:

- `src/wanctl/alert_engine.py`: `AlertEngine`, cooldowns, persistence, active cooldown reporting.
- `src/wanctl/webhook_delivery.py`: Discord formatting, async delivery, retry, delivery status updates.
- `src/wanctl/fusion_healer.py`: fusion transition alert emission.

Alerting is disabled by default. When enabled, each fired alert passes through:

1. master `alerting.enabled`.
2. optional per-rule `enabled`.
3. per `(alert_type, wan)` cooldown.
4. SQLite persistence in the `alerts` table.
5. optional webhook delivery.

Webhook delivery is asynchronous and never blocks the controller loop. Transient HTTP failures are retried with exponential backoff; non-retryable failures update `alerts.delivery_status` to `failed`. Successful delivery updates it to `delivered`.

## Measurement Quality Stack

Implementation map:

- `src/wanctl/irtt_measurement.py`: `IRTTMeasurement`, serialized subprocess execution, JSON parsing.
- `src/wanctl/irtt_thread.py`: `IRTTThread`, background IRTT cadence.
- `src/wanctl/reflector_scorer.py`: `ReflectorScorer`, rolling scores, recovery probes, event drain.
- `src/wanctl/fusion_healer.py`: `FusionHealer`, correlation-based suspension and recovery.

wanctl uses ICMP as the authoritative default RTT signal. Optional IRTT adds periodic UDP RTT, IPDV, and loss observations. When fusion is enabled, fresh IRTT RTT can be blended with ICMP according to `fusion.icmp_weight`; otherwise IRTT remains observational.

IRTT measurements run in a background thread. Same-target IRTT bursts are serialized with an advisory lock under `/run/wanctl` to avoid multiple WAN daemons probing one server simultaneously. All IRTT failures return no sample and fall back to ICMP-only operation.

Reflector quality scoring maintains a rolling success score per ICMP reflector. Hosts below `reflector_quality.min_score` after warmup are deprioritized. A deprioritized host is periodically probed and restored after `recovery_count` consecutive successful probes. Deprioritization and recovery events are persisted to SQLite.

Fusion healer states:

- `active`: fusion may operate when IRTT is fresh.
- `suspended`: fusion is disabled because ICMP/IRTT delta correlation is poor.
- `recovering`: correlation has improved but must remain good before full recovery.

During suspended and recovering states, adaptive tuning of `fusion_icmp_weight` is locked to prevent tuning from re-enabling a bad signal path.
