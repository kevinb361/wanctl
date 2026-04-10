# Phase 108: Steering Dual-Backend & Observability - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the steering daemon to use split data sources when `router_transport: "linux-cake"`: local LinuxCakeBackend for CAKE stats, remote FailoverRouterClient for mangle rules. Expose per-tin statistics in the health endpoint and wanctl-history CLI. No changes to the autorate daemon (WANController). No VM setup (Phase 109).

</domain>

<decisions>
## Implementation Decisions

### Dual-Backend Wiring
- **D-01:** When `router_transport: "linux-cake"`, the steering daemon creates a `LinuxCakeBackend` instance for CAKE stats collection. The existing `FailoverRouterClient` is kept for mangle rule toggling (enable_steering/disable_steering) — it still needs REST/SSH to MikroTik.
- **D-02:** `CakeStatsReader` gets an alternate code path. When transport is `linux-cake`, it delegates to `LinuxCakeBackend.get_queue_stats()` instead of running RouterOS queue tree commands. The `CakeStats` dataclass return contract is unchanged — consumers see the same fields.
- **D-03:** The steering config YAML retains its `router:` section for mangle rule connectivity even when `router_transport: "linux-cake"`. CAKE stats come from local tc, mangle rules go to the router — both are needed simultaneously.
- **D-04:** The `LinuxCakeBackend` instance is created via the factory (`get_backend()`) using the autorate config's `cake_params` section. The steering daemon reads the primary WAN's autorate config path to get the transport and interface settings.

### Per-Tin Health Endpoint
- **D-05:** Per-tin stats nest under `congestion.primary.tins` as an array of 4 dicts (one per diffserv4 tin: Bulk, BestEffort, Video, Voice).
- **D-06:** Each tin dict contains: `tin_name`, `dropped_packets`, `ecn_marked_packets`, `avg_delay_us`, `peak_delay_us`, `backlog_bytes`, `sparse_flows`, `bulk_flows`, `unresponsive_flows`.
- **D-07:** When transport is NOT linux-cake (i.e., RouterOS mode), `tins` is omitted from the health response (MikroTik doesn't expose per-tin data).

### Per-Tin Metrics & History
- **D-08:** New metric names in `STORED_METRICS`: `wanctl_cake_tin_dropped`, `wanctl_cake_tin_ecn_marked`, `wanctl_cake_tin_delay_us`, `wanctl_cake_tin_backlog_bytes`.
- **D-09:** Labels discriminate tins: `{"tin": "Bulk"}`, `{"tin": "BestEffort"}`, `{"tin": "Video"}`, `{"tin": "Voice"}`.
- **D-10:** `wanctl-history --tins` flag displays per-tin statistics. Reuses existing `query_metrics()` with metric name filtering and label parsing.
- **D-11:** Per-tin metrics are only written when transport is linux-cake (no per-tin data available from MikroTik).

### Claude's Discretion
- How CakeStatsReader detects transport mode (config attribute vs constructor parameter)
- Per-tin metric batch construction details
- wanctl-history --tins display format (table, per-tin columns, etc.)
- Test fixture design for dual-backend scenarios

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Steering Daemon
- `src/wanctl/steering/daemon.py` — SteeringDaemon class (line 949), run_cycle() (line 1799), collect_cake_stats() (line 1670)
- `src/wanctl/steering/cake_stats.py` — CakeStatsReader class (line 45), read_stats(), delta calculation
- `src/wanctl/steering/health.py` — SteeringHealthHandler (line 71), _get_health_status() (line 103)

### Router Control
- `src/wanctl/router_client.py` — get_router_client_with_failover(), FailoverRouterClient
- `src/wanctl/steering/daemon.py` — enable_steering() (line 767), disable_steering() (line 796)

### Backend (Phase 105/106/107 outputs)
- `src/wanctl/backends/linux_cake.py` — LinuxCakeBackend.get_queue_stats() with per-tin support
- `src/wanctl/backends/__init__.py` — get_backend() factory with linux-cake routing
- `src/wanctl/cake_params.py` — build_cake_params() for direction-aware defaults

### Metrics & History
- `src/wanctl/storage/schema.py` — STORED_METRICS dict, METRICS_SCHEMA
- `src/wanctl/storage/writer.py` — MetricsWriter singleton, write_metrics_batch()
- `src/wanctl/storage/reader.py` — query_metrics() with label support
- `src/wanctl/history.py` — wanctl-history CLI entry point

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LinuxCakeBackend.get_queue_stats()` — already returns per-tin data in `stats["tins"]`
- `CakeStats` dataclass — unchanged contract for aggregate stats
- `MetricsWriter.write_metrics_batch()` — batch write with labels support
- `query_metrics()` — already supports metric name and label filtering

### Established Patterns
- Steering daemon creates clients in `__init__` based on config
- Health endpoint builds JSON dict in `_get_health_status()` with nested sections
- Metrics use `(timestamp, wan_name, metric_name, value, labels_json, granularity)` tuples
- `wanctl-history` adds flags via argparse with dedicated query functions

### Integration Points
- `CakeStatsReader.__init__` — transport-aware client creation
- `SteeringHealthHandler._get_health_status()` — add tins section
- `SteeringDaemon._record_steering_metrics()` — add per-tin batch writes
- `STORED_METRICS` dict — register new metric names
- `history.py` argparse — add `--tins` flag

</code_context>

<specifics>
## Specific Ideas

- CakeStatsReader can detect transport via `getattr(config, "router_transport", "rest")` — same pattern used by factory
- Per-tin health format example:
  ```json
  "congestion": {
    "primary": {
      "state": "GREEN",
      "tins": [
        {"tin_name": "Bulk", "dropped_packets": 0, "ecn_marked_packets": 0, "avg_delay_us": 120, ...},
        {"tin_name": "BestEffort", "dropped_packets": 3, ...},
        {"tin_name": "Video", "dropped_packets": 0, ...},
        {"tin_name": "Voice", "dropped_packets": 0, ...}
      ]
    }
  }
  ```
- TIN_NAMES constant already exists in linux_cake.py: `["Bulk", "BestEffort", "Video", "Voice"]`

</specifics>

<deferred>
## Deferred Ideas

- Per-tin stats in the TUI dashboard (wanctl-dashboard) — would need new sparkline widgets
- Per-tin alerting (e.g., alert when Voice tin drops exceed threshold) — AlertEngine extension
- CakeStatsReader refactor to use RouterBackend ABC instead of FailoverRouterClient — cleanup

</deferred>

---

*Phase: 108-steering-dual-backend-observability*
*Context gathered: 2026-03-25*
