# Testing Patterns

**Analysis Date:** 2026-03-10

## Test Framework

**Runner:**
- pytest 8.0.0+
- Config: `pyproject.toml` `[tool.pytest.ini_options]` — `addopts = "--cov-config=pyproject.toml"`

**Assertion Library:**
- pytest built-in `assert` statement
- `pytest.raises(ExceptionType, match="pattern")` for exception testing

**Run Commands:**
```bash
.venv/bin/pytest tests/ -v                   # All tests, verbose
.venv/bin/pytest tests/test_foo.py -v        # Specific file
.venv/bin/pytest tests/ --cov=src --cov-report=term-missing --cov-report=html  # With HTML coverage
.venv/bin/pytest tests/ --cov=src --cov-fail-under=90  # Coverage enforcement (CI)
```

**Make targets:**
```bash
make test             # Run tests without coverage
make coverage         # Tests + HTML report (coverage-report/index.html)
make coverage-check   # Tests + enforce 90% threshold (used by CI)
make ci               # lint + type + coverage-check
```

## Test File Organization

**Location:** `tests/` at project root, co-located with source but separate directory

**Naming:** `test_<module_name>.py` mirroring `src/wanctl/<module_name>.py`

**Structure:**
```
tests/
├── conftest.py                        # Shared fixtures (temp_dir, mock_autorate_config, mock_steering_config)
├── test_autorate_baseline_bounds.py   # Baseline RTT boundary conditions
├── test_autorate_config.py            # Config loading and validation
├── test_autorate_continuous.py        # WANController pending rate integration
├── test_autorate_entry_points.py      # main() and ContinuousAutoRate (2047 lines)
├── test_autorate_error_recovery.py    # Error recovery paths (1032 lines)
├── test_autorate_metrics_recording.py # SQLite metrics integration
├── test_autorate_telemetry.py         # Profiling telemetry
├── test_backends.py                   # RouterBackend ABC and RouterOSBackend
├── test_baseline_rtt_manager.py       # BaselineRTTManager class
├── test_cake_stats.py                 # CakeStatsReader
├── test_calibrate.py                  # Calibration tool (1572 lines)
├── test_config_base.py                # BaseConfig schema validation
├── test_config_edge_cases.py          # Config edge cases
├── test_config_snapshot.py            # Config snapshot recording
├── test_config_validation_utils.py    # Validation utility functions
├── test_daemon_interaction.py         # Cross-daemon interactions
├── test_daemon_utils.py               # Deadline tracking
├── test_error_handling.py             # handle_errors, safe_operation, safe_call
├── test_failure_cascade.py            # Cascade failure scenarios
├── test_health_check.py               # HTTP health endpoint (799 lines)
├── test_health_check_history.py       # Health endpoint history data
├── test_history_cli.py                # wanctl-history CLI (605 lines)
├── test_hot_loop_retry_params.py      # Hot loop retry parameter validation
├── test_lock_utils.py / test_lockfile.py  # Lock file utilities
├── test_logging_utils.py              # JSONFormatter, setup_logging
├── test_metrics.py                    # Prometheus metrics (639 lines)
├── test_metrics_reader.py             # SQLite metrics reader
├── test_path_utils.py                 # Path utilities
├── test_pending_rates.py              # PendingRateChange
├── test_perf_profiler.py              # OperationProfiler, PerfTimer
├── test_queue_controller.py           # QueueController state machine (1196 lines)
├── test_rate_limiter.py               # RateLimiter
├── test_retry_utils.py / test_retry_utils_extended.py  # Retry with backoff
├── test_router_behavioral.py          # Router behavioral tests
├── test_router_client.py              # Router client with failover (745 lines)
├── test_router_command_utils.py       # CommandResult, command parsing
├── test_router_connectivity.py        # RouterConnectivityState
├── test_routeros_rest.py              # REST backend (969 lines)
├── test_routeros_ssh.py               # SSH backend (717 lines)
├── test_rtt_measurement.py            # RTTMeasurement, icmplib
├── test_signal_utils.py               # Signal handling
├── test_state_manager.py              # StateManager (997 lines)
├── test_state_utils.py                # atomic_write_json, safe_json_load_file
├── test_steering_confidence.py        # Confidence scoring (1120 lines)
├── test_steering_daemon.py            # SteeringDaemon (5360 lines — largest file)
├── test_steering_health.py            # Steering health endpoint (1312 lines)
├── test_steering_logger.py            # SteeringLogger
├── test_steering_metrics_recording.py # Steering SQLite metrics
├── test_steering_module_boundary.py   # Steering module boundaries
├── test_steering_telemetry.py         # Steering profiling
├── test_steering_timers.py            # Timer management
├── test_storage_downsampler.py        # Metrics downsampling
├── test_storage_maintenance.py        # DB maintenance
├── test_storage_retention.py          # Retention policy
├── test_storage_schema.py             # SQLite schema
├── test_storage_writer.py             # MetricsWriter singleton
├── test_systemd_utils.py              # systemd notify
├── test_timeouts.py                   # Timeout constants
├── test_wan_controller.py             # WANController (2115 lines)
├── test_wan_controller_state.py       # WANControllerState persistence
└── integration/
    ├── conftest.py                    # Integration fixtures, custom markers
    ├── test_latency_control.py        # End-to-end RRUL validation
    └── framework/                     # ControllerMonitor, LatencyCollector, SLAChecker
```

**Total:** 2,210 tests collected, all passing (as of 2026-03-10)

## Test Structure

**Suite Organization:** Class-per-feature, one behavior per test method
```python
from unittest.mock import MagicMock, patch
import pytest
from wanctl.autorate_continuous import WANController


class TestHandleIcmpFailure:
    """Tests for WANController.handle_icmp_failure() method.

    Tests all 3 fallback modes and edge cases.
    """

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with mocked dependencies."""
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return controller

    def test_graceful_degradation_cycle_1_uses_last_rtt(self, controller):
        """Cycle 1 should use last known RTT and return True."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == 28.5
        assert controller.icmp_unavailable_cycles == 1
        controller.logger.warning.assert_called()
```

**Test naming:** `test_<behavior>_<result>` — `test_graceful_degradation_cycle_1_uses_last_rtt`, `test_singleton_same_instance`

**Module-level section dividers** in large test files:
```python
# =========================================================================
# graceful_degradation mode tests
# =========================================================================
```

## Shared Fixtures (conftest.py)

Two canonical mock config fixtures in `tests/conftest.py` cover the full attribute superset:

```python
@pytest.fixture
def mock_autorate_config():
    """Shared mock config for autorate WANController tests."""
    config = MagicMock()
    config.wan_name = "TestWAN"
    config.baseline_rtt_initial = 25.0
    config.download_floor_green = 800_000_000
    config.ping_hosts = ["1.1.1.1"]
    config.metrics_enabled = False
    config.state_file = MagicMock()
    # ... full superset of attributes
    return config

@pytest.fixture
def mock_steering_config():
    """Shared mock config for steering daemon tests."""
    config = MagicMock()
    config.primary_wan = "spectrum"
    config.wan_state_config = None  # WAN-aware steering disabled by default
    # ... full superset of attributes
    return config
```

**Also in conftest.py:**
- `temp_dir` — `tempfile.TemporaryDirectory` yielding `Path`
- `sample_config_data` — baseline config dict

**Fixture delegation pattern** (per-class overrides without renaming):
```python
class TestCollectCakeStats:
    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config from conftest.py."""
        return mock_steering_config
```
This preserves the local name `mock_config` while reusing the shared fixture.

**`autouse=True` for class-level teardown:**
```python
class TestMainEntryPoint:
    @pytest.fixture(autouse=True)
    def _mock_storage(self):
        """Prevent main() from hitting production storage paths."""
        with patch(
            "wanctl.steering.daemon.get_storage_config",
            return_value={"retention_days": 7, "db_path": ""},
        ):
            yield
```
Used to isolate all tests in a class from production filesystem paths.

**Module-level `autouse` for global state reset:**
```python
@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset global metrics registry before and after each test."""
    metrics.reset()
    yield
    metrics.reset()
```

## Mocking

**Framework:** `unittest.mock` — `from unittest.mock import MagicMock, patch`

**MagicMock config objects:**
```python
config = MagicMock()
config.wan_name = "TestWAN"
config.download_floor_green = 800_000_000
router = MagicMock()
router.set_limits.return_value = True
```

**Context manager patch (most common form):**
```python
with patch("wanctl.rtt_measurement.icmplib.ping") as mock:
    mock.return_value = make_host_result(rtts=[12.3])
    result = rtt_measurement.ping_hosts_concurrent(["8.8.8.8"])
```

**patch.object for methods:**
```python
with patch.object(WANController, "load_state"):
    controller = WANController(...)

with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
    result = controller.handle_icmp_failure()
```

**side_effect for sequential returns:**
```python
mock_icmplib_ping.side_effect = [
    make_host_result(rtts=[12.3]),   # First call
    make_host_result(is_alive=False), # Second call
]
```

**Factory helper functions** for complex mocks:
```python
def make_host_result(address="8.8.8.8", rtts=None, is_alive=True):
    """Build a mock icmplib Host object for testing."""
    host = MagicMock()
    host.address = address
    host.rtts = rtts or [12.3]
    host.is_alive = is_alive
    host.packet_loss = 0.0 if is_alive else 1.0
    return host
```

**What to mock:**
- Router I/O: `RouterOSSSH`, `RouterOSREST`, `icmplib.ping`
- File system access: `WANController.load_state`, `get_storage_config`
- Singletons: `MetricsWriter._reset_instance()` in setup/teardown
- HTTP servers: `start_health_server`, `start_steering_health_server`
- Time: `time.monotonic` when testing deadline tracking (needs ~12+ extra values for cleanup path)

**What NOT to mock:**
- Pure calculation functions: `enforce_rate_bounds`, `is_retryable_error`, `compute_confidence`
- State machines: `QueueController.adjust`, `QueueController.adjust_4state`
- Config validation: `validate_field`, `validate_bandwidth_order`
- SQLite in-memory (use `tmp_path` for real SQLite in storage tests)

## Coverage

**Requirements:** 90% enforced by `make coverage-check` / `make ci`
- Config: `[tool.coverage.report]` in `pyproject.toml` — `fail_under = 90`
- Branch coverage enabled: `branch = true`
- Both `src` and `tests` in coverage source

**View HTML report:**
```bash
make coverage    # generates coverage-report/index.html
```

**Current state:** 2,210 tests, 91%+ coverage (as of 2026-03-10)

## Test Types

**Unit Tests (majority):**
- Test single class/function in isolation
- All external dependencies mocked
- Target: specific method behavior, edge cases, error paths
- Examples: `test_queue_controller.py`, `test_error_handling.py`, `test_retry_utils.py`

**Functional/Integration Tests (class-level in unit test files):**
- Test multiple modules wired together with boundary mocks only
- Examples: `test_wan_controller.py` (WANController + mocked router), `test_health_check.py` (HTTP server + real handler)

**E2E / Integration Tests:**
- `tests/integration/test_latency_control.py`
- Requires external tools: `flent`/`netperf`, `fping`/`ping`
- Marked with `@pytest.mark.integration` and `@pytest.mark.slow`
- Skipped automatically if dependencies missing (autouse fixture in `tests/integration/conftest.py`)
- Not run by `make test` or `make ci`

## Common Patterns

**Parametrize for boundary conditions:**
```python
@pytest.mark.parametrize(
    "delta,expected_zone",
    [
        (5.0, "GREEN"),   # delta <= 15 (well below target)
        (15.0, "GREEN"),  # boundary value
        (20.0, "YELLOW"),
        (45.0, "YELLOW"),  # boundary value
        (50.0, "RED"),
        (100.0, "RED"),
    ],
)
def test_zone_classification(self, controller_3state, delta, expected_zone):
    """Parametrized test for zone classification based on delta."""
    zone, _, _ = controller_3state.adjust(baseline_rtt=25.0, load_rtt=25.0 + delta, ...)
    assert zone == expected_zone
```

**Exception testing with match:**
```python
with pytest.raises(ConfigValidationError, match="floor ordering"):
    validate_bandwidth_order(...)

with pytest.raises(ValueError, match="expected error message"):
    some_validation(bad_input)
```

**Logger call assertion:**
```python
controller.logger.warning.assert_called()
mock_logger.error.assert_called_with("expected message")
```

**Logging capture with caplog:**
```python
def test_logs_warning(self, caplog):
    with caplog.at_level(logging.WARNING):
        trigger_warning()
    assert "expected text" in caplog.text
```

**stdout/stderr capture with capsys:**
```python
def test_validate_config_success(self, valid_config_yaml, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Valid" in captured.out
```

**Singleton reset pattern (MetricsWriter):**
```python
@pytest.fixture
def reset_singleton():
    MetricsWriter._reset_instance()
    yield
    MetricsWriter._reset_instance()
```

**Real SQLite with tmp_path:**
```python
@pytest.fixture
def temp_db(self, tmp_path: Path) -> tuple[Path, MetricsWriter]:
    db_path = tmp_path / "test_metrics.db"
    MetricsWriter._reset_instance()
    writer = MetricsWriter(db_path)
    yield db_path, writer
    MetricsWriter._reset_instance()
```

**Free port discovery for HTTP server tests:**
```python
def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
```

**Import inside fixture to avoid circular imports:**
```python
@pytest.fixture
def controller(self, mock_config, ...):
    from wanctl.autorate_continuous import WANController  # deferred import
    with patch.object(WANController, "load_state"):
        return WANController(...)
```

---

*Testing analysis: 2026-03-10*
