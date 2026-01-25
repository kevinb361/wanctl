# Requirements: wanctl

**Defined:** 2026-01-25
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.7 Requirements

Requirements for Metrics History milestone. Each maps to roadmap phases.

### Storage & Retention

- [x] **STOR-01**: Metrics stored in SQLite at `/var/lib/wanctl/metrics.db`
- [x] **STOR-02**: Configurable retention period via config (default 7 days)
- [x] **STOR-03**: Automatic downsampling (1s -> 1m -> 5m -> 1h as data ages)
- [x] **STOR-04**: Automatic cleanup of expired data on daemon startup

### Data Capture

- [x] **DATA-01**: Record RTT metrics (current, baseline, delta) each cycle
- [x] **DATA-02**: Record rate metrics (download, upload rates) each cycle
- [x] **DATA-03**: Record state transitions with reason (e.g., "RTT delta exceeded threshold")
- [x] **DATA-04**: Record config snapshot on startup and config reload
- [x] **DATA-05**: Prometheus-compatible metric naming (`wanctl_rtt_ms`, `wanctl_rate_download_mbps`)

### CLI Tool

- [x] **CLI-01**: `wanctl-history` command available for querying history
- [x] **CLI-02**: Query by time range (`--last 1h`, `--from/--to timestamps`)
- [x] **CLI-03**: Filter by metric type (`--metrics rtt,rate,state`)
- [x] **CLI-04**: Output formats: human-readable table (default), JSON (`--json`)
- [x] **CLI-05**: Summary statistics mode (`--summary` shows min/max/avg/p95)

### API Endpoint

- [x] **API-01**: `/metrics/history` endpoint on autorate health server (port 9101)
- [x] **API-02**: Query params: `range`, `from`, `to`, `metrics`, `wan`
- [x] **API-03**: JSON response with timestamps, values, and metadata
- [x] **API-04**: Pagination support (`limit`, `offset` params)

### Integration

- [x] **INTG-01**: Autorate daemon records metrics each cycle with minimal overhead
- [x] **INTG-02**: Steering daemon records metrics each cycle with minimal overhead
- [x] **INTG-03**: Performance impact <5ms overhead per cycle (measured)

## Future Requirements

None currently. Prometheus `/metrics` endpoint deferred to v1.8+.

## Out of Scope

| Feature             | Reason                                                        |
| ------------------- | ------------------------------------------------------------- |
| Real-time streaming | Polling via API is sufficient for this use case               |
| Grafana dashboards  | Future scope, Prometheus-compatible naming enables later      |
| External database   | SQLite is sufficient, no need for PostgreSQL/InfluxDB         |
| Per-host metrics    | Single-WAN focus per daemon, multi-WAN via separate instances |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status   |
| ----------- | ----- | -------- |
| STOR-01     | 38    | Complete |
| STOR-02     | 38    | Complete |
| STOR-03     | 38    | Complete |
| STOR-04     | 38    | Complete |
| DATA-01     | 39    | Complete |
| DATA-02     | 39    | Complete |
| DATA-03     | 39    | Complete |
| DATA-04     | 39    | Complete |
| DATA-05     | 38    | Complete |
| CLI-01      | 40    | Complete |
| CLI-02      | 40    | Complete |
| CLI-03      | 40    | Complete |
| CLI-04      | 40    | Complete |
| CLI-05      | 40    | Complete |
| API-01      | 41    | Complete |
| API-02      | 41    | Complete |
| API-03      | 41    | Complete |
| API-04      | 41    | Complete |
| INTG-01     | 39    | Complete |
| INTG-02     | 39    | Complete |
| INTG-03     | 39    | Complete |

**Coverage:**

- v1.7 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0

---

_Requirements defined: 2026-01-25_
_Last updated: 2026-01-25 after Phase 41 completion — v1.7 MILESTONE COMPLETE_
