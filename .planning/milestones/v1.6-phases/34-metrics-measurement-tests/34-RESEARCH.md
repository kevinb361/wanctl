# Phase 34: Metrics & Measurement Tests - Research

**Researched:** 2026-01-25
**Domain:** Python test coverage, HTTP server testing, subprocess mocking, RouterOS client mocking
**Confidence:** HIGH

## Summary

Phase 34 covers test coverage for metrics collection (`metrics.py` 26% -> 90%), CAKE statistics (`steering/cake_stats.py` 24% -> 90%), and RTT measurement (`rtt_measurement.py` 67% -> 90%).

The standard approach uses pytest's existing fixtures combined with unittest.mock for subprocess calls (ping), HTTP client testing (metrics server), and RouterOS client mocking (CAKE stats). Real HTTP server testing uses the threading-based MetricsServer with short-lived connections. Subprocess.run mocking is essential for ping tests since real network calls are unreliable in CI.

**Primary recommendation:** Use mock subprocess.run for all ping tests; test MetricsServer with real HTTP requests in short-lived threads; mock router client for CAKE stats parsing tests.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test framework | Already configured in pyproject.toml |
| pytest-cov | 7.0.0 | Coverage measurement | Already configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | Mocking subprocess, router client | All network/external calls |
| urllib.request | stdlib | HTTP client for metrics server | Testing /metrics endpoint |
| caplog | pytest fixture | Log capture | Verify warning/error logs |
| tmp_path | pytest fixture | Temp directories | Any file I/O tests |
| MagicMock | unittest.mock | Mock objects with attributes | Router client, logger |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| urllib.request | requests library | stdlib sufficient, no extra dep |
| Real subprocess calls | Mock subprocess | Mocks faster, reliable in CI |
| Real router calls | Mock router client | Tests must work without router |

**Installation:** No additional packages needed.

## Architecture Patterns

### Recommended Test File Structure
```
tests/
├── test_metrics.py            # NEW - metrics.py comprehensive tests
├── test_cake_stats.py         # NEW - steering/cake_stats.py tests
└── test_rtt_measurement.py    # EXISTS - expand coverage
```

### Pattern 1: HTTP Server Testing
**What:** Start MetricsServer, make HTTP requests, verify responses
**When to use:** Testing MetricsHandler endpoints (/metrics, /health, 404)
**Example:**
```python
import urllib.request
from wanctl.metrics import MetricsServer, metrics

def test_metrics_endpoint_returns_exposition(self):
    """Test /metrics returns Prometheus exposition format."""
    server = MetricsServer(host="127.0.0.1", port=0)  # port=0 for random
    # Note: MetricsServer uses fixed port, so use unique port per test
    server = MetricsServer(host="127.0.0.1", port=19100)
    try:
        assert server.start() is True

        # Set some metrics
        metrics.reset()
        metrics.set_gauge("test_gauge", 42.0, help_text="Test help")

        # Fetch /metrics
        url = f"http://{server.host}:{server.port}/metrics"
        with urllib.request.urlopen(url, timeout=2) as response:
            content = response.read().decode("utf-8")

        assert "# TYPE test_gauge gauge" in content
        assert "test_gauge 42.0" in content
    finally:
        server.stop()
```

### Pattern 2: Subprocess Mock for Ping
**What:** Mock subprocess.run to simulate ping output
**When to use:** All RTTMeasurement tests
**Example:**
```python
from unittest.mock import patch, Mock

def test_ping_host_parses_rtt(self, rtt_measurement):
    """Test ping_host extracts RTT from output."""
    with patch("wanctl.rtt_measurement.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="64 bytes from 8.8.8.8: time=12.5 ms\n"
        )

        result = rtt_measurement.ping_host("8.8.8.8", count=1)

        assert result == pytest.approx(12.5)
```

### Pattern 3: Router Client Mock for CAKE Stats
**What:** Mock get_router_client_with_failover to return mock client
**When to use:** CakeStatsReader tests
**Example:**
```python
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_router_client():
    """Create mock router client."""
    client = MagicMock()
    client.run_cmd.return_value = (0, '{"packets": 100, "dropped": 5}', "")
    return client

def test_read_stats_parses_json_response(self, mock_router_client, mock_logger):
    """Test read_stats parses REST API JSON response."""
    with patch("wanctl.steering.cake_stats.get_router_client_with_failover",
               return_value=mock_router_client):
        reader = CakeStatsReader(mock_config, mock_logger)

        stats = reader.read_stats("WAN-Download")

        assert stats.packets == 100
        assert stats.dropped == 5
```

### Pattern 4: MetricsRegistry Thread Safety Test
**What:** Test concurrent access to MetricsRegistry
**When to use:** Verifying thread-safe gauge/counter operations
**Example:**
```python
import threading
from wanctl.metrics import MetricsRegistry

def test_concurrent_gauge_updates(self):
    """Test thread-safe gauge updates."""
    registry = MetricsRegistry()
    errors = []

    def update_gauge(name, value):
        try:
            for _ in range(100):
                registry.set_gauge(name, value)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=update_gauge, args=("test", i))
        for i in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    # Final value should be one of the thread values
    assert registry.get_gauge("test") in range(10)
```

### Pattern 5: Statistics Aggregation Strategy Testing
**What:** Test each RTTAggregationStrategy with known inputs
**When to use:** RTTMeasurement._aggregate_rtts tests
**Example:**
```python
from wanctl.rtt_measurement import RTTAggregationStrategy, RTTMeasurement

def test_aggregation_strategies(self, mock_logger):
    """Test all aggregation strategies produce expected results."""
    rtts = [10.0, 20.0, 30.0, 40.0, 50.0]

    # AVERAGE
    m = RTTMeasurement(mock_logger, aggregation_strategy=RTTAggregationStrategy.AVERAGE)
    assert m._aggregate_rtts(rtts) == pytest.approx(30.0)

    # MEDIAN
    m = RTTMeasurement(mock_logger, aggregation_strategy=RTTAggregationStrategy.MEDIAN)
    assert m._aggregate_rtts(rtts) == pytest.approx(30.0)

    # MIN
    m = RTTMeasurement(mock_logger, aggregation_strategy=RTTAggregationStrategy.MIN)
    assert m._aggregate_rtts(rtts) == pytest.approx(10.0)

    # MAX
    m = RTTMeasurement(mock_logger, aggregation_strategy=RTTAggregationStrategy.MAX)
    assert m._aggregate_rtts(rtts) == pytest.approx(50.0)
```

### Anti-Patterns to Avoid
- **Real network calls in unit tests:** Mock subprocess.run, never real ping
- **Fixed ports without cleanup:** Use try/finally to stop servers, or unique ports
- **Testing router without mocks:** CakeStatsReader needs router client mock
- **Forgetting metrics.reset():** Global registry persists; reset between tests

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP response parsing | Manual string parsing | urllib.request | Handles headers, status codes |
| Concurrent test isolation | Manual locks | metrics.reset() | Already thread-safe |
| RTT parsing | Custom regex per test | parse_ping_output() | Tested, handles edge cases |
| JSON parsing | Manual json.loads | safe_json_loads() | Error handling built in |

**Key insight:** The metrics module already has reset() for test isolation - use it.

## Common Pitfalls

### Pitfall 1: Port Conflicts in MetricsServer Tests
**What goes wrong:** Tests fail with "Address already in use"
**Why it happens:** Previous test didn't stop server, or parallel test execution
**How to avoid:**
  - Always use try/finally with server.stop()
  - Use unique ports per test class (19100, 19101, etc.)
  - Add small sleep after server.stop() if flaky
**Warning signs:** Tests pass alone, fail when run together

### Pitfall 2: Global Metrics Registry Pollution
**What goes wrong:** Tests see metrics from previous tests
**Why it happens:** `metrics` is a module-level global registry
**How to avoid:** Call `metrics.reset()` in test setup/teardown
**Warning signs:** Test order affects results

### Pitfall 3: Subprocess Mock Not Covering All Exit Paths
**What goes wrong:** Missing coverage for timeout, non-zero return code
**Why it happens:** Only happy path mocked
**How to avoid:** Explicitly test:
  - returncode != 0 (ping failure)
  - TimeoutExpired exception
  - Empty stdout (no RTT values)
  - Generic Exception
**Warning signs:** Coverage report shows lines 195-200 not covered

### Pitfall 4: CAKE Stats Delta Calculation First-Read Edge Case
**What goes wrong:** First read returns raw stats, not delta
**Why it happens:** No previous stats to diff against
**How to avoid:** Test both:
  - First read (baseline stored, raw returned)
  - Second read (delta calculated)
**Warning signs:** Only testing steady-state, missing initialization

### Pitfall 5: RTT Parsing Edge Cases
**What goes wrong:** parse_ping_output fails on unusual formats
**Why it happens:** Different ping versions, locales
**How to avoid:** Test formats:
  - "time=12.3 ms" (standard)
  - "time=12.3ms" (no space)
  - Empty string
  - No "time=" lines
  - Invalid float value
**Warning signs:** Real ping output differs from test mock

### Pitfall 6: MetricsHandler Logging Suppression
**What goes wrong:** Tests verify logging but log_message is no-op
**Why it happens:** MetricsHandler.log_message intentionally suppresses
**How to avoid:** Don't test for HTTP access logs; test metric content instead
**Warning signs:** Expecting log output that never appears

## Code Examples

Verified patterns from existing codebase tests:

### Metrics Registry Basic Operations
```python
# Source: Based on metrics.py implementation
def test_set_gauge_and_get_gauge(self):
    """Test gauge set and get operations."""
    registry = MetricsRegistry()

    registry.set_gauge("test_metric", 42.5)
    assert registry.get_gauge("test_metric") == 42.5

    # With labels
    registry.set_gauge("labeled", 10.0, labels={"env": "test"})
    assert registry.get_gauge("labeled", labels={"env": "test"}) == 10.0
    assert registry.get_gauge("labeled") is None  # No labels = different key

def test_inc_counter_accumulates(self):
    """Test counter increments accumulate."""
    registry = MetricsRegistry()

    registry.inc_counter("requests")
    registry.inc_counter("requests")
    registry.inc_counter("requests", value=5)

    assert registry.get_counter("requests") == 7
```

### Exposition Format Test
```python
# Source: Based on metrics.py exposition() method
def test_exposition_format(self):
    """Test Prometheus exposition format output."""
    registry = MetricsRegistry()
    registry.set_gauge("http_requests", 100, help_text="Total HTTP requests")
    registry.inc_counter("errors_total", help_text="Total errors")

    output = registry.exposition()

    # Verify format
    assert "# HELP http_requests Total HTTP requests" in output
    assert "# TYPE http_requests gauge" in output
    assert "http_requests 100" in output
    assert "# TYPE errors_total counter" in output
    assert "errors_total 1" in output
```

### CAKE Stats Text Parsing
```python
# Source: Based on cake_stats.py _parse_text_response
def test_parse_text_response_ssh_format(self, mock_logger):
    """Test parsing SSH CLI text output."""
    text = '''name="WAN-Download-1" parent=bridge1
    rate=0 packet-rate=0 queued-bytes=1024 queued-packets=10
    bytes=272603902153 packets=184614358 dropped=500'''

    reader = CakeStatsReader(mock_config, mock_logger)
    stats = reader._parse_text_response(text)

    assert stats.packets == 184614358
    assert stats.bytes == 272603902153
    assert stats.dropped == 500
    assert stats.queued_packets == 10
    assert stats.queued_bytes == 1024
```

### RTT Measurement Timeout Handling
```python
# Source: Based on test_rtt_measurement.py pattern
def test_ping_timeout_returns_none(self, mock_logger):
    """Test subprocess timeout returns None."""
    rtt = RTTMeasurement(mock_logger, timeout_ping=1)

    with patch("wanctl.rtt_measurement.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ping", timeout=1)

        result = rtt.ping_host("8.8.8.8")

        assert result is None
        mock_logger.warning.assert_called()
```

### Record Functions Test Pattern
```python
# Source: Based on metrics.py record_* functions
def test_record_autorate_cycle(self):
    """Test record_autorate_cycle sets all expected metrics."""
    metrics.reset()

    record_autorate_cycle(
        wan_name="spectrum",
        dl_rate_mbps=750.0,
        ul_rate_mbps=35.0,
        baseline_rtt=10.0,
        load_rtt=15.0,
        dl_state="GREEN",
        ul_state="GREEN",
        cycle_duration=0.045,
    )

    # Verify gauges set
    assert metrics.get_gauge("wanctl_bandwidth_mbps", {"wan": "spectrum", "direction": "download"}) == 750.0
    assert metrics.get_gauge("wanctl_rtt_baseline_ms", {"wan": "spectrum"}) == 10.0
    assert metrics.get_gauge("wanctl_rtt_delta_ms", {"wan": "spectrum"}) == 5.0
    assert metrics.get_gauge("wanctl_state", {"wan": "spectrum", "direction": "download"}) == 1  # GREEN

    # Verify counter incremented
    assert metrics.get_counter("wanctl_cycles_total", {"wan": "spectrum"}) == 1
```

## Coverage Gap Analysis

### metrics.py (26% -> 90%)

**Current Coverage:** 26.3%
**Missing Lines:** 63-67, 85-89, 102-104, 117-119, 123-126, 130-132, 141-165, 169-171, 184, 188-207, 226-230, 239-256, 260-265, 270, 286-288, 343-401, 411, 420, 429, 449-459, 469

**Uncovered Functions:**
- `MetricsRegistry.set_gauge` with help_text (lines 63-67)
- `MetricsRegistry.inc_counter` with help_text (lines 85-89)
- `MetricsRegistry.get_gauge` (lines 102-104)
- `MetricsRegistry.get_counter` (lines 117-119)
- `MetricsRegistry._make_key` with labels (lines 123-126)
- `MetricsRegistry._extract_base_name` (lines 130-132)
- `MetricsRegistry.exposition` (lines 141-165) - ENTIRE FUNCTION
- `MetricsRegistry.reset` (lines 169-171)
- `MetricsHandler.do_GET` (lines 188-207) - HTTP endpoint handling
- `MetricsServer.start` (lines 239-256) - Server startup
- `MetricsServer.stop` (lines 260-265)
- `MetricsServer.is_running` (line 270)
- `start_metrics_server` (lines 286-288)
- `record_autorate_cycle` (lines 343-401) - ENTIRE FUNCTION
- `record_rate_limit_event` (line 411)
- `record_router_update` (line 420)
- `record_ping_failure` (line 429)
- `record_steering_state` (lines 449-459)
- `record_steering_transition` (line 469)

**Test Categories Needed:**
1. MetricsRegistry: All public methods with/without labels
2. MetricsRegistry: exposition() format validation
3. MetricsHandler: /metrics, /health, 404 paths
4. MetricsServer: start(), stop(), is_running, double-start
5. Record functions: All 6 record_* functions

### steering/cake_stats.py (24% -> 90%)

**Current Coverage:** 24.2%
**Missing Lines:** 49-66, 80-106, 129-153, 170-191, 204-236

**Uncovered Functions:**
- `CakeStatsReader.__init__` (lines 49-66): Partial, client creation
- `CakeStatsReader._parse_json_response` (lines 80-106): REST API parsing
- `CakeStatsReader._parse_text_response` (lines 129-153): SSH text parsing
- `CakeStatsReader._calculate_stats_delta` (lines 170-191): Delta calculation
- `CakeStatsReader.read_stats` (lines 204-236): Main entry point

**Test Categories Needed:**
1. JSON response parsing: Valid, invalid, empty, list vs dict
2. Text response parsing: All field patterns, missing fields
3. Delta calculation: First read, subsequent reads, counter overflow
4. read_stats: Success, failure, validation error
5. Queue name validation (ConfigValidationError)

### rtt_measurement.py (67% -> 90%)

**Current Coverage:** 66.9%
**Missing Lines:** 46, 50, 60-68, 155, 175-176, 183, 198-200, 216, 221-228, 275-276

**Uncovered Functions:**
- `parse_ping_output` empty text path (line 46)
- `parse_ping_output` no "time=" in line (line 50)
- `parse_ping_output` fallback string parsing (lines 60-68)
- `RTTMeasurement.ping_host` timeout_total path (line 155)
- `RTTMeasurement.ping_host` no RTT samples warning (lines 175-176)
- `RTTMeasurement.ping_host` log_sample_stats path (line 183)
- `RTTMeasurement.ping_host` generic exception (lines 198-200)
- `RTTMeasurement._aggregate_rtts` empty list error (line 216)
- `RTTMeasurement._aggregate_rtts` all strategy branches (lines 221-228)
- `ping_hosts_concurrent` timeout handling (lines 275-276)

**Test Categories Needed:**
1. parse_ping_output: Empty, no matches, fallback parsing, invalid
2. ping_host: All return paths, timeout_total parameter
3. _aggregate_rtts: All 4 strategies, empty list error
4. ping_hosts_concurrent: Timeout, exception handling

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mock HTTP at socket level | Real HTTP with MetricsServer | Python 3.x | More realistic tests |
| tempfile.NamedTemporaryFile | pytest tmp_path fixture | pytest 3.9+ | Cleaner, auto-cleanup |

**Deprecated/outdated:**
- None for this domain

## Open Questions

Things that couldn't be fully resolved:

1. **MetricsServer port allocation strategy**
   - What we know: Port conflicts possible in parallel tests
   - What's unclear: Whether pytest-xdist is used for parallel execution
   - Recommendation: Use unique ports per test class, add server cleanup fixture

2. **CAKE stats counter overflow handling**
   - What we know: Code comments mention handling 2^64 overflow
   - What's unclear: Whether to test this edge case
   - Recommendation: Add one test for large counter values to verify subtraction

## Sources

### Primary (HIGH confidence)
- `/home/kevin/projects/wanctl/src/wanctl/metrics.py` - Source analysis
- `/home/kevin/projects/wanctl/src/wanctl/steering/cake_stats.py` - Source analysis
- `/home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py` - Source analysis
- `/home/kevin/projects/wanctl/tests/test_rtt_measurement.py` - Existing test patterns
- `/home/kevin/projects/wanctl/tests/test_wan_controller.py` - Metrics usage patterns
- `/home/kevin/projects/wanctl/tests/test_steering_daemon.py` - CAKE stats usage patterns
- Coverage reports from pytest --cov runs

### Secondary (MEDIUM confidence)
- Python unittest.mock documentation - Mock patterns
- pytest documentation - Fixture patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing pytest stack
- Architecture: HIGH - Following existing test patterns
- Pitfalls: HIGH - Derived from code analysis and coverage reports
- Coverage gaps: HIGH - From pytest --cov output with line numbers

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (stable domain, internal code)
