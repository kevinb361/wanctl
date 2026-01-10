# wanctl v1.0.0-rc7

**Release Candidate 7** - Observability & Reliability improvements from comprehensive code review.

## What's New in RC7

### Observability

#### Health Check Endpoint

HTTP endpoint for Kubernetes probes and external monitoring (enabled by default):

```bash
curl http://127.0.0.1:9101/health
```

```json
{
  "status": "healthy",
  "uptime_seconds": 3600.5,
  "version": "1.0.0-rc7",
  "consecutive_failures": 0,
  "wans": [
    {
      "name": "spectrum",
      "baseline_rtt_ms": 24.0,
      "load_rtt_ms": 26.4,
      "download": {"current_rate_mbps": 940.0, "state": "GREEN"},
      "upload": {"current_rate_mbps": 38.0, "state": "GREEN"}
    }
  ]
}
```

**Configuration:**

```yaml
health_check:
  enabled: true       # default: true
  host: "127.0.0.1"   # default: localhost only
  port: 9101          # default: 9101
```

#### Prometheus Metrics Endpoint

Prometheus-compatible metrics for Grafana dashboards and alerting (disabled by default):

```bash
curl http://127.0.0.1:9100/metrics
```

**Metrics exposed:**

| Metric | Type | Description |
|--------|------|-------------|
| `wanctl_bandwidth_mbps{wan,direction}` | Gauge | Current bandwidth limit |
| `wanctl_rtt_baseline_ms{wan}` | Gauge | Baseline RTT |
| `wanctl_rtt_load_ms{wan}` | Gauge | Load RTT (EWMA) |
| `wanctl_rtt_delta_ms{wan}` | Gauge | RTT delta |
| `wanctl_state{wan,direction}` | Gauge | State (1=GREEN, 2=YELLOW, 3=SOFT_RED, 4=RED) |
| `wanctl_cycles_total{wan}` | Counter | Total autorate cycles |
| `wanctl_rate_limit_events_total{wan}` | Counter | Rate limit throttling events |

**Configuration:**

```yaml
metrics:
  enabled: true       # default: false
  host: "127.0.0.1"   # default: localhost only
  port: 9100          # default: 9100
```

#### JSON Structured Logging

JSON-formatted logs for log aggregation tools (Loki, ELK, Splunk):

```bash
export WANCTL_LOG_FORMAT=json
```

**Output example:**

```json
{"timestamp":"2026-01-10T12:00:00.000Z","level":"INFO","logger":"wanctl_spectrum","message":"State change","wan_name":"spectrum","state":"GREEN","rtt_delta":5.2}
```

### Reliability

#### Rate Limiting

Router config changes are now rate-limited to prevent API overload during instability:

- **Default:** 10 changes per 60 seconds
- Logs warning when throttled, continues cycle without router update
- Protects against rapid state oscillations

#### EWMA Overflow Protection

EWMA calculations now include bounds checking:

- Input values validated against `max_value` (default: 1000.0 for RTT)
- NaN/Inf detection on both input and output
- Raises `ValueError` for invalid inputs

#### Automatic Backup Recovery

State files now recover from `.backup` before falling back to defaults:

- On corruption, attempts to load `.backup` file
- Corrupt file saved as `.corrupt` for analysis
- Improves availability after transient corruption

#### Improved Resource Cleanup

- `atexit` handler ensures lock files are cleaned up on abnormal termination
- Cleanup order prioritized: locks first, then SSH/REST connections
- Handles both SSH and REST transports correctly

#### Configuration Schema Versioning

Configs now track schema version for future migration support:

```yaml
schema_version: "1.0"
```

- Logs info when version differs from current
- Backward compatible (defaults to "1.0" for existing configs)

### Testing

#### Config Validation CLI

Validate configuration without starting the daemon:

```bash
# Validate single config
wanctl --config /etc/wanctl/spectrum.yaml --validate-config

# Validate multiple configs
wanctl --config spectrum.yaml att.yaml --validate-config

# CI/CD integration
wanctl --config /etc/wanctl/production.yaml --validate-config || exit 1
```

**Exit codes:** 0 = valid, 1 = invalid

#### Expanded Test Coverage

- **+96 new tests** (474 total, up from 378)
- Rate limiter tests (27 tests)
- Validation security tests (54 tests)
- Health check tests (11 tests)
- State machine documentation tests (5 tests)

## Bug Fixes

- **Exit code propagation** - `--validate-config` now returns proper exit codes (was always 0)
- **Missing sys import** - Added `sys` import for `sys.exit()` call

## Files Added

| File | Purpose |
|------|---------|
| `src/wanctl/health_check.py` | Health check HTTP endpoint |
| `src/wanctl/metrics.py` | Prometheus metrics endpoint |
| `src/wanctl/rate_limiter.py` | Rate limiting for config changes |
| `tests/test_health_check.py` | Health check tests |
| `tests/test_rate_limiter.py` | Rate limiter tests |
| `tests/test_logging_utils.py` | JSON logging tests |

## Upgrade Notes

### From RC5/RC6

No breaking changes. All new features are additive:

1. **Health check** - Enabled by default on port 9101
2. **Metrics** - Disabled by default (opt-in)
3. **JSON logging** - Disabled by default (opt-in via environment variable)
4. **Rate limiting** - Active by default with sensible limits

### Deployment

After upgrading code:

```bash
# Restart service to pick up new version
sudo systemctl restart wanctl@wan1.service

# Verify version
curl -s http://127.0.0.1:9101/health | grep version
# "version": "1.0.0-rc7"
```

## System Requirements

- Python 3.11+ (3.12 recommended)
- MikroTik RouterOS 7.x
- Linux host with systemd (Debian 12, Ubuntu 22.04+)

## Testing This Release

1. **Health endpoint** - `curl http://127.0.0.1:9101/health`
2. **Config validation** - `wanctl --config config.yaml --validate-config`
3. **Invalid config test** - Verify exit code 1 for bad config
4. **JSON logging** - `WANCTL_LOG_FORMAT=json wanctl --config config.yaml`
5. **Metrics (if enabled)** - `curl http://127.0.0.1:9100/metrics`

## Documentation

- `README.md` - Updated with Observability section
- `CLAUDE.md` - Updated with v1.0.0-rc7 features (local only)
- `.claude/reviews/REVIEWS.md` - All review items marked complete

## Known Limitations

- Metrics endpoint disabled by default (enable in config)
- Health check binds to localhost only by default (configurable)
- JSON logging requires environment variable (not config file)

## Acknowledgments

- Comprehensive code review identified all improvements
- [LibreQoS](https://libreqos.io/) - Inspiration for CAKE-based QoS
- [Prometheus](https://prometheus.io/) - Metrics format standard
- Claude (Anthropic) - AI-assisted development

## License

GPL-2.0 - See [LICENSE](LICENSE) for details.

---

**Full Changelog**: https://github.com/kevinb361/wanctl/compare/v1.0.0-rc5...v1.0.0-rc7
