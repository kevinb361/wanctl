# Phase 108: Steering Dual-Backend & Observability - Research

**Researched:** 2026-03-25
**Domain:** Steering daemon split data sources, per-tin CAKE observability
**Confidence:** HIGH

## Summary

Phase 108 wires the steering daemon to use split data sources when `router_transport: "linux-cake"`: local `LinuxCakeBackend` for CAKE queue statistics and the existing `FailoverRouterClient` for MikroTik mangle rule toggling. It also exposes per-tin CAKE statistics (Voice/Video/BestEffort/Bulk) in the health endpoint and `wanctl-history` CLI.

All building blocks already exist. `LinuxCakeBackend.get_queue_stats()` (Phase 105) already returns per-tin data in `stats["tins"]` with 11 fields per tin. `CakeStatsReader` currently hardcodes RouterOS queue tree commands via `FailoverRouterClient`. The change is adding an alternate code path that delegates to `LinuxCakeBackend` when transport is `linux-cake`. The health endpoint and metrics writer already support labels and nested JSON -- per-tin data slots naturally into existing patterns.

**Primary recommendation:** Modify `CakeStatsReader` to accept a transport-detection parameter in its constructor (or detect via `getattr(config, "router_transport", "rest")`), then delegate to `LinuxCakeBackend.get_queue_stats()` for the linux-cake path. For health and metrics, extend the existing batch write and health dict patterns with per-tin data gated on transport type.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** When `router_transport: "linux-cake"`, the steering daemon creates a `LinuxCakeBackend` instance for CAKE stats collection. The existing `FailoverRouterClient` is kept for mangle rule toggling (enable_steering/disable_steering) -- it still needs REST/SSH to MikroTik.
- **D-02:** `CakeStatsReader` gets an alternate code path. When transport is `linux-cake`, it delegates to `LinuxCakeBackend.get_queue_stats()` instead of running RouterOS queue tree commands. The `CakeStats` dataclass return contract is unchanged -- consumers see the same fields.
- **D-03:** The steering config YAML retains its `router:` section for mangle rule connectivity even when `router_transport: "linux-cake"`. CAKE stats come from local tc, mangle rules go to the router -- both are needed simultaneously.
- **D-04:** The `LinuxCakeBackend` instance is created via the factory (`get_backend()`) using the autorate config's `cake_params` section. The steering daemon reads the primary WAN's autorate config path to get the transport and interface settings.
- **D-05:** Per-tin stats nest under `congestion.primary.tins` as an array of 4 dicts (one per diffserv4 tin: Bulk, BestEffort, Video, Voice).
- **D-06:** Each tin dict contains: `tin_name`, `dropped_packets`, `ecn_marked_packets`, `avg_delay_us`, `peak_delay_us`, `backlog_bytes`, `sparse_flows`, `bulk_flows`, `unresponsive_flows`.
- **D-07:** When transport is NOT linux-cake (i.e., RouterOS mode), `tins` is omitted from the health response (MikroTik doesn't expose per-tin data).
- **D-08:** New metric names in `STORED_METRICS`: `wanctl_cake_tin_dropped`, `wanctl_cake_tin_ecn_marked`, `wanctl_cake_tin_delay_us`, `wanctl_cake_tin_backlog_bytes`.
- **D-09:** Labels discriminate tins: `{"tin": "Bulk"}`, `{"tin": "BestEffort"}`, `{"tin": "Video"}`, `{"tin": "Voice"}`.
- **D-10:** `wanctl-history --tins` flag displays per-tin statistics. Reuses existing `query_metrics()` with metric name filtering and label parsing.
- **D-11:** Per-tin metrics are only written when transport is linux-cake (no per-tin data available from MikroTik).

### Claude's Discretion
- How CakeStatsReader detects transport mode (config attribute vs constructor parameter)
- Per-tin metric batch construction details
- wanctl-history --tins display format (table, per-tin columns, etc.)
- Test fixture design for dual-backend scenarios

### Deferred Ideas (OUT OF SCOPE)
- Per-tin stats in the TUI dashboard (wanctl-dashboard) -- would need new sparkline widgets
- Per-tin alerting (e.g., alert when Voice tin drops exceed threshold) -- AlertEngine extension
- CakeStatsReader refactor to use RouterBackend ABC instead of FailoverRouterClient -- cleanup
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONF-03 | Steering daemon uses dual-backend -- linux-cake for CAKE stats, REST for mangle rules | CakeStatsReader alternate code path (D-02), LinuxCakeBackend already has get_queue_stats(), RouterOSController already has enable/disable_steering via FailoverRouterClient |
| CAKE-07 | Per-tin statistics visible in health endpoint and wanctl-history | LinuxCakeBackend.get_queue_stats() already returns per-tin data, health endpoint has nested JSON pattern, MetricsWriter supports labels for tin discrimination |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (subprocess) | 3.12 | tc command execution in LinuxCakeBackend | Already used, zero deps |
| sqlite3 | 3.12 stdlib | Metrics storage with labels | Already used, WAL mode enabled |
| tabulate | 0.9.0+ | CLI table output for --tins | Already a project dependency |

### Supporting
No new dependencies required. All functionality builds on existing project infrastructure.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Constructor param for transport detection | getattr(config, "router_transport", "rest") | Config attribute detection is simpler, matches existing factory pattern in `get_backend()` -- RECOMMENDED |
| New CakeStatsReader subclass for linux-cake | Conditional logic in existing class | Subclass adds unnecessary complexity for a single branch -- RECOMMEND conditional |

## Architecture Patterns

### Integration Point Map
```
SteeringDaemon.__init__
  |
  +-> CakeStatsReader.__init__(config, logger)
  |     |
  |     +-> [linux-cake] LinuxCakeBackend via get_backend(autorate_config)
  |     +-> [rest/ssh]   FailoverRouterClient via get_router_client_with_failover()
  |
  +-> RouterOSController.__init__(config, logger)    # ALWAYS created for mangle rules
        |
        +-> FailoverRouterClient via get_router_client_with_failover()
```

### Pattern 1: Transport-Aware CakeStatsReader
**What:** CakeStatsReader detects transport via config, creates appropriate backend
**When to use:** In CakeStatsReader.__init__ when transport is "linux-cake"
**Implementation approach:**
```python
class CakeStatsReader:
    def __init__(self, config: Any, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self._transport = getattr(config, "router_transport", "rest")

        if self._transport == "linux-cake":
            # Load autorate config to get cake_params for LinuxCakeBackend
            from ..backends import get_backend
            autorate_config = self._load_autorate_config(config)
            self._linux_backend = get_backend(autorate_config)
            self.client = None  # No RouterOS client needed for CAKE stats
        else:
            self._linux_backend = None
            self.client = get_router_client_with_failover(config, logger)

        self.previous_stats: dict[str, CakeStats] = {}
```

### Pattern 2: Per-Tin Health Endpoint Extension
**What:** Add `tins` array to `congestion.primary` when linux-cake transport
**When to use:** In `_get_health_status()` after existing congestion section
**Key detail:** The daemon needs access to the raw per-tin data from the most recent stats read. CakeStatsReader should cache the last raw stats (including tins) when using linux-cake backend.

### Pattern 3: Per-Tin Metrics Batch Write
**What:** Append per-tin metrics to the existing `metrics_batch` list in `run_cycle()`
**When to use:** After the existing metrics batch construction, gated on linux-cake transport
**Example structure:**
```python
# Per-tin metrics (only when linux-cake transport)
if self._is_linux_cake and last_tin_stats:
    for i, tin in enumerate(last_tin_stats):
        tin_name = TIN_NAMES[i] if i < len(TIN_NAMES) else f"tin_{i}"
        tin_labels = {"tin": tin_name}
        metrics_batch.extend([
            (ts, wan, "wanctl_cake_tin_dropped", float(tin["dropped_packets"]), tin_labels, "raw"),
            (ts, wan, "wanctl_cake_tin_ecn_marked", float(tin["ecn_marked_packets"]), tin_labels, "raw"),
            (ts, wan, "wanctl_cake_tin_delay_us", float(tin["avg_delay_us"]), tin_labels, "raw"),
            (ts, wan, "wanctl_cake_tin_backlog_bytes", float(tin["backlog_bytes"]), tin_labels, "raw"),
        ])
```

### Pattern 4: wanctl-history --tins Flag
**What:** New argparse flag that queries per-tin metrics and displays them
**When to use:** User wants to see per-tin CAKE statistics over time
**Approach:** Filter on the 4 new metric names, parse labels to group by tin, display as table

### Anti-Patterns to Avoid
- **Creating a second RouterOSController for mangle rules in linux-cake mode:** The existing RouterOSController already uses FailoverRouterClient. Keep it unchanged -- only CakeStatsReader needs the alternate path.
- **Modifying CakeStats dataclass:** The aggregate stats contract is unchanged. Per-tin data is additional context stored separately (cached on the reader, passed to health/metrics).
- **Writing per-tin metrics when transport is rest/ssh:** MikroTik doesn't expose per-tin data, so writing zeros would be misleading. Gate on transport type (D-11).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Backend factory | Custom if/else for LinuxCakeBackend creation | `get_backend()` from `backends/__init__.py` | Already handles transport routing (Phase 107) |
| Label-based metrics storage | Custom label storage mechanism | Existing `write_metrics_batch()` with labels dict | Already supports JSON labels (used by wanctl_state with `{"source": "steering"}`) |
| Time-range metric queries | Custom SQL for per-tin queries | Existing `query_metrics()` with metrics name filter | Already supports metric name filtering and label parsing |
| Config loading for autorate | Manual YAML parsing | `BaseConfig` / existing config loader | SteeringConfig already has `primary_wan_config` pointing to the autorate YAML |

## Common Pitfalls

### Pitfall 1: Autorate Config Loading for LinuxCakeBackend
**What goes wrong:** The steering daemon's config (`SteeringConfig`) doesn't have `cake_params` -- that's in the autorate config (a separate YAML file pointed to by `topology.primary_wan_config`).
**Why it happens:** `get_backend()` expects a config object with `router_transport` and `cake_params.download_interface` attributes. The steering config doesn't have these.
**How to avoid:** Load the autorate config from `self.config.primary_wan_config` path to get the transport and cake_params, then pass that config to `get_backend()`. Or construct the LinuxCakeBackend directly using `LinuxCakeBackend.from_config()`.
**Warning signs:** `ValueError: cake_params.download_interface required for linux-cake transport`

### Pitfall 2: CakeStats vs Raw Stats Dict Mismatch
**What goes wrong:** `CakeStatsReader.read_stats()` returns a `CakeStats` dataclass with 5 fields (packets, bytes, dropped, queued_packets, queued_bytes). But `LinuxCakeBackend.get_queue_stats()` returns a dict with 9+ fields plus tins list.
**Why it happens:** Two different return types for two different code paths.
**How to avoid:** The linux-cake path in CakeStatsReader must: (1) convert the dict back to `CakeStats` for the aggregate return value (preserving the existing contract), and (2) separately cache the per-tin data for health/metrics use.
**Warning signs:** `AttributeError: 'dict' object has no attribute 'dropped'`

### Pitfall 3: Delta Calculation on Linux-Cake Path
**What goes wrong:** LinuxCakeBackend.get_queue_stats() returns cumulative counters (like RouterOS). CakeStatsReader already handles delta calculation via `_calculate_stats_delta()`. The linux-cake path must also go through delta calculation.
**Why it happens:** Forgetting that the delta logic is essential for the steering cycle (drops per interval, not total drops).
**How to avoid:** Ensure the linux-cake code path converts raw stats to CakeStats and passes through `_calculate_stats_delta()` just like the RouterOS path.
**Warning signs:** Drops count grows monotonically instead of showing per-interval deltas.

### Pitfall 4: Per-Tin Delta Not Needed for Health/Metrics
**What goes wrong:** Attempting to compute per-tin deltas for health endpoint display.
**Why it happens:** Confusion between what the steering cycle needs (aggregate deltas for congestion detection) and what observability needs (instantaneous tin state for operator visibility).
**How to avoid:** Health endpoint shows **current** per-tin state (drops/delays/flows as returned by tc). The aggregate delta for steering decisions uses `_calculate_stats_delta()`. Per-tin metrics in the DB can use either cumulative or per-interval values -- cumulative is simpler and more useful for historical analysis. However, if using cumulative values in the time-series DB, queries will need to compute deltas. Consider storing per-interval deltas for the 4 new metrics to match the existing convention.
**Warning signs:** Health endpoint showing impossibly large drop counts (cumulative instead of current).

### Pitfall 5: Transport Detection Scope
**What goes wrong:** The steering config has `router_transport` from its own `router:` section. But the autorate config also has `router_transport`. These could differ if the steering YAML still says `rest` while the autorate YAML says `linux-cake`.
**Why it happens:** D-03 says steering config retains its `router:` section for mangle rules. The transport detection for CAKE stats should come from the autorate config (primary_wan_config), not the steering config.
**How to avoid:** Read the autorate config file (from `topology.primary_wan_config`) to detect whether CAKE stats should use linux-cake or RouterOS. The steering config's `router.transport` remains "rest" or "ssh" for mangle rule connectivity.
**Warning signs:** Steering daemon uses RouterOS for CAKE stats even when linux-cake is configured.

### Pitfall 6: MetricsWriter Singleton in Tests
**What goes wrong:** Tests pollute each other via the MetricsWriter singleton.
**Why it happens:** MetricsWriter uses singleton pattern -- `_reset_instance()` must be called between tests.
**How to avoid:** Use `MetricsWriter._reset_instance()` in test fixtures (already established pattern in `test_steering_metrics_recording.py`).
**Warning signs:** Tests pass individually but fail when run together.

## Code Examples

### CakeStatsReader Transport Detection (Recommended Approach)
```python
# In CakeStatsReader.__init__
# Detect transport from the PRIMARY WAN's autorate config (not steering config)
# because steering config's router.transport is always rest/ssh for mangle rules
autorate_config_path = getattr(config, "primary_wan_config", None)
if autorate_config_path:
    # Load minimal config to check transport
    import yaml
    with open(autorate_config_path) as f:
        autorate_data = yaml.safe_load(f)
    autorate_transport = autorate_data.get("router", {}).get("transport", "rest")
else:
    autorate_transport = "rest"

self._is_linux_cake = autorate_transport == "linux-cake"
```

### Per-Tin Health Endpoint Integration
```python
# In SteeringHealthHandler._get_health_status(), after existing congestion section:
# Add per-tin stats when linux-cake transport (D-05, D-06, D-07)
if hasattr(self.daemon, '_last_tin_stats') and self.daemon._last_tin_stats:
    tins_list = []
    for i, tin in enumerate(self.daemon._last_tin_stats):
        tin_name = TIN_NAMES[i] if i < len(TIN_NAMES) else f"tin_{i}"
        tins_list.append({
            "tin_name": tin_name,
            "dropped_packets": tin.get("dropped_packets", 0),
            "ecn_marked_packets": tin.get("ecn_marked_packets", 0),
            "avg_delay_us": tin.get("avg_delay_us", 0),
            "peak_delay_us": tin.get("peak_delay_us", 0),
            "backlog_bytes": tin.get("backlog_bytes", 0),
            "sparse_flows": tin.get("sparse_flows", 0),
            "bulk_flows": tin.get("bulk_flows", 0),
            "unresponsive_flows": tin.get("unresponsive_flows", 0),
        })
    health["congestion"]["primary"]["tins"] = tins_list
```

### STORED_METRICS Registration
```python
# In storage/schema.py -- add these 4 new entries
STORED_METRICS.update({
    "wanctl_cake_tin_dropped": "Per-tin CAKE dropped packets (label: tin=Bulk|BestEffort|Video|Voice)",
    "wanctl_cake_tin_ecn_marked": "Per-tin ECN marked packets (label: tin=Bulk|BestEffort|Video|Voice)",
    "wanctl_cake_tin_delay_us": "Per-tin average queue delay in microseconds (label: tin=Bulk|BestEffort|Video|Voice)",
    "wanctl_cake_tin_backlog_bytes": "Per-tin backlog in bytes (label: tin=Bulk|BestEffort|Video|Voice)",
})
```

### wanctl-history --tins Display
```python
# In history.py -- new --tins flag handler
def format_tins_table(results: list[dict]) -> str:
    """Format per-tin metrics as grouped table."""
    headers = ["Timestamp", "Tin", "Dropped", "ECN", "Delay(us)", "Backlog(B)"]
    rows = []
    for r in results:
        labels = json.loads(r["labels"]) if r["labels"] else {}
        tin_name = labels.get("tin", "?")
        metric = r["metric_name"]
        # Group by timestamp+tin, show each metric as a column
        # (implementation detail -- could also do one row per metric)
        ...
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_cake_stats.py tests/test_steering_health.py tests/test_steering_metrics_recording.py tests/test_history_cli.py -x -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-03a | CakeStatsReader uses LinuxCakeBackend when transport=linux-cake | unit | `.venv/bin/pytest tests/test_cake_stats.py -x -q -k linux_cake` | Wave 0 |
| CONF-03b | CakeStatsReader still uses FailoverRouterClient for rest/ssh | unit | `.venv/bin/pytest tests/test_cake_stats.py -x -q -k routeros` | Existing (pass) |
| CONF-03c | RouterOSController still uses FailoverRouterClient for mangle rules regardless of transport | unit | `.venv/bin/pytest tests/test_steering_daemon.py -x -q -k mangle` | Existing (pass) |
| CONF-03d | CakeStats return contract unchanged on linux-cake path | unit | `.venv/bin/pytest tests/test_cake_stats.py -x -q -k linux_cake_contract` | Wave 0 |
| CAKE-07a | Health endpoint includes tins[] when linux-cake | unit | `.venv/bin/pytest tests/test_steering_health.py -x -q -k tins` | Wave 0 |
| CAKE-07b | Health endpoint omits tins[] when rest/ssh | unit | `.venv/bin/pytest tests/test_steering_health.py -x -q -k no_tins` | Wave 0 |
| CAKE-07c | Per-tin metrics written to SQLite with labels | unit | `.venv/bin/pytest tests/test_steering_metrics_recording.py -x -q -k tin` | Wave 0 |
| CAKE-07d | STORED_METRICS includes 4 new tin metric names | unit | `.venv/bin/pytest tests/test_steering_metrics_recording.py -x -q -k stored_metrics` | Wave 0 |
| CAKE-07e | wanctl-history --tins queries and displays per-tin data | unit | `.venv/bin/pytest tests/test_history_cli.py -x -q -k tins` | Wave 0 |
| CAKE-07f | Per-tin metrics NOT written when transport is rest/ssh | unit | `.venv/bin/pytest tests/test_steering_metrics_recording.py -x -q -k no_tin_rest` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_cake_stats.py tests/test_steering_health.py tests/test_steering_metrics_recording.py tests/test_history_cli.py -x -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cake_stats.py` -- new test classes for linux-cake code path: `TestCakeStatsReaderLinuxCake`
- [ ] `tests/test_steering_health.py` -- new tests for per-tin health data: `TestPerTinHealth`
- [ ] `tests/test_steering_metrics_recording.py` -- new tests for per-tin metric batch writes
- [ ] `tests/test_history_cli.py` -- new tests for `--tins` flag parsing and display

## Open Questions

1. **Per-tin metric values: cumulative or per-interval?**
   - What we know: LinuxCakeBackend returns cumulative counters from tc. CakeStatsReader computes deltas for the aggregate stats. The existing metrics batch writes per-interval values (deltas).
   - What's unclear: Should per-tin metrics in the DB be cumulative or per-interval? Per-interval is more useful for time-series analysis (no need for client-side delta computation) and matches existing convention.
   - Recommendation: Store per-interval (delta) values. Cache per-tin cumulative counters in CakeStatsReader alongside the aggregate previous_stats, compute per-tin deltas the same way. This is Claude's discretion.

2. **How does CakeStatsReader access LinuxCakeBackend config?**
   - What we know: D-04 says use `get_backend()` with autorate config. SteeringConfig has `primary_wan_config` path. The autorate config has `cake_params`.
   - What's unclear: Whether to load the full autorate config object or just parse the YAML for transport+cake_params.
   - Recommendation: Load the autorate YAML minimally (just router.transport and cake_params) rather than constructing a full BaseConfig. This avoids side effects from autorate config validation. Claude's discretion.

3. **Per-tin data caching in SteeringDaemon**
   - What we know: The health endpoint reads from daemon attributes. Per-tin data comes from CakeStatsReader's linux-cake path.
   - What's unclear: Where to cache -- on CakeStatsReader as `last_raw_stats` or on SteeringDaemon as `_last_tin_stats`?
   - Recommendation: Cache on CakeStatsReader (it already owns the stats lifecycle). SteeringDaemon accesses via `self.cake_reader.last_tin_stats`. Health endpoint accesses via `self.daemon.cake_reader.last_tin_stats`. Claude's discretion.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/backends/linux_cake.py` -- LinuxCakeBackend.get_queue_stats() returns per-tin data with 11 fields per tin, TIN_NAMES constant
- `src/wanctl/steering/cake_stats.py` -- CakeStatsReader current implementation, CakeStats dataclass, delta calculation
- `src/wanctl/steering/health.py` -- SteeringHealthHandler._get_health_status() pattern, nested JSON structure
- `src/wanctl/steering/daemon.py` -- SteeringDaemon.__init__ creates CakeStatsReader at line 972, metrics batch at line 1911-2019
- `src/wanctl/storage/schema.py` -- STORED_METRICS dict, labels support in metrics table
- `src/wanctl/storage/writer.py` -- MetricsWriter.write_metrics_batch() with labels dict support
- `src/wanctl/storage/reader.py` -- query_metrics() with metric name filtering, labels column returned
- `src/wanctl/history.py` -- argparse pattern with --alerts, --tuning flags as template for --tins
- `src/wanctl/backends/__init__.py` -- get_backend() factory with linux-cake routing
- `tests/test_linux_cake_backend.py` -- per-tin test patterns, SAMPLE_CAKE_JSON fixture with 4 tins

### Secondary (MEDIUM confidence)
- Existing test patterns in `tests/conftest.py` (mock_steering_config fixture at line 137)
- Test infrastructure conventions from `tests/test_steering_metrics_recording.py`, `tests/test_steering_health.py`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all patterns already exist in codebase
- Architecture: HIGH -- all integration points verified by reading actual source code
- Pitfalls: HIGH -- identified from concrete code patterns (CakeStats vs dict mismatch, transport detection scope)

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable internal refactoring, no external dependency changes)
