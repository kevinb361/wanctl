# Testing Patterns

**Analysis Date:** 2026-01-21

## Test Framework

**Runner:**
- pytest 8.0.0+
- Config: `pyproject.toml` (minimal, uses defaults)
- 25 test files, 684 test functions, all passing

**Assertion Library:**
- pytest built-in assert statement
- Matchers: `assert x == y`, `assert x in y`, `assert isinstance(x, Type)`

**Run Commands:**
```bash
.venv/bin/pytest tests/ -v              # Run all tests with verbose output
.venv/bin/pytest tests/ -vvs            # Very verbose (show print statements)
.venv/bin/pytest tests/test_*.py        # Run specific test file
.venv/bin/pytest tests/ -k test_name    # Run tests matching pattern
.venv/bin/pytest tests/ --tb=short      # Shorter traceback format
```

## Test File Organization

**Location:**
- `tests/` directory at project root
- Subdirectories: `tests/integration/`, `tests/integration/framework/`
- One test file per module being tested
- Naming: `test_<module_name>.py` (e.g., `test_config_validation_utils.py`)

**Structure:**
```
tests/
├── conftest.py                      # Shared fixtures
├── test_autorate_baseline_bounds.py # State machine boundary tests
├── test_baseline_rtt_manager.py     # RTT baseline tracking
├── test_config_base.py              # Config schema validation
├── test_config_edge_cases.py        # Edge case scenarios
├── test_config_validation_utils.py  # Config validation (590 lines)
├── test_health_check.py             # HTTP health endpoint
├── test_lock_utils.py               # Lock file acquisition
├── test_lockfile.py                 # Lockfile implementation
├── test_logging_utils.py            # Structured logging
├── test_path_utils.py               # Path utilities
├── test_rate_limiter.py             # Rate limiting (sliding window)
├── test_retry_utils.py              # Retry with exponential backoff
├── test_retry_utils_extended.py     # Extended retry scenarios
├── test_rtt_measurement.py          # RTT parsing and aggregation
├── test_router_command_utils.py     # RouterOS command utilities
├── test_state_manager.py            # State persistence
├── test_state_utils.py              # State file utilities
├── test_steering_daemon.py          # Steering daemon tests
├── test_steering_deprecation.py     # Steering deprecation scenarios
├── test_steering_logger.py          # Steering event logging
├── test_steering_timers.py          # Steering timer logic
├── test_timeouts.py                 # Timeout constants
├── test_wan_controller.py           # WANController (1500+ lines)
├── test_wan_controller_state.py     # WANController state persistence
└── integration/
    ├── test_latency_control.py      # End-to-end validation
    └── framework/                   # Integration test utilities
```

## Test Structure

**Suite Organization:**
```python
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wanctl.module_name import FunctionUnderTest


@pytest.fixture
def logger():
    """Provide logger for tests."""
    return logging.getLogger("test_module_name")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestFeatureName:
    """Tests for FeatureName functionality."""

    def test_specific_behavior_succeeds(self, logger):
        """Test that specific behavior succeeds."""
        # Arrange
        input_value = setup_test_data()

        # Act
        result = FunctionUnderTest(input_value)

        # Assert
        assert result == expected_value

    def test_specific_behavior_fails(self):
        """Test that invalid input raises error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            FunctionUnderTest(invalid_input)
        assert "expected error message" in str(exc_info.value)
```

**Patterns:**
- Use `@pytest.fixture` for shared setup (logger, temp files)
- Organize tests in classes by feature/function
- Arrange-Act-Assert pattern in each test
- One assertion focus per test (multiple asserts OK if testing single behavior)
- Descriptive test names: `test_<behavior>_<result>` format
- Fixtures defined in `conftest.py` for cross-test reuse

## Mocking

**Framework:**
- `unittest.mock` (built-in)
- pytest does not auto-mock
- Imports: `from unittest.mock import MagicMock, patch`

**Patterns:**

1. **Mock Creation:**
   ```python
   mock_config = MagicMock()
   mock_config.wan_name = "TestWAN"
   mock_config.baseline_rtt_initial = 25.0
   mock_config.ping_hosts = ["1.1.1.1"]

   mock_router = MagicMock()
   mock_router.set_limits.return_value = True
   ```

2. **Context Manager Patching:**
   ```python
   with patch('wanctl.module.function') as mock_fn:
       mock_fn.return_value = expected_value
       # test code
   ```

3. **Decorator Patching:**
   ```python
   @patch('wanctl.module.external_call')
   def test_function(self, mock_external):
       mock_external.return_value = test_value
       # test code
   ```

4. **Assertion on Mocks:**
   ```python
   mock_router.set_limits.assert_called()
   mock_logger.warning.assert_called_with("msg")
   mock_object.method.assert_not_called()
   ```

**What to Mock:**
- External services (RouterOS commands via `RouterOSREST`, `RouterOSSSH`)
- File I/O (state files, logs)
- System calls (ping, netperf)
- Time-dependent behavior (datetime, sleep)
- HTTP servers (health check, metrics endpoints)

**What NOT to Mock:**
- Pure validation functions (`validate_field()`, `enforce_rate_bounds()`)
- EWMA calculations and state machine logic
- Config parsing and schema validation
- Rate limiter sliding window logic

**Example from Tests:**

Real-world example from `test_wan_controller.py`:
```python
@pytest.fixture
def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
    """Create a WANController with mocked dependencies."""
    from wanctl.autorate_continuous import WANController

    # Patch load_state to avoid file I/O
    with patch.object(WANController, "load_state"):
        controller = WANController(
            wan_name="TestWAN",
            config=mock_config,
            router=mock_router,
            rtt_measurement=mock_rtt_measurement,
            logger=mock_logger,
        )
    return controller
```

## Fixtures and Factories

**Shared Fixtures in `conftest.py`:**
```python
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing."""
    return {
        "wan_name": "TestWAN",
        "router": {"host": "192.168.1.1", "user": "admin"},
        "queues": {"download": "WAN-Download", "upload": "WAN-Upload"},
        "bandwidth": {"down_max": 100, "down_min": 10, "up_max": 20, "up_min": 5},
    }
```

**Test-Specific Fixtures:**
```python
@pytest.fixture
def mock_config(self):
    """Create a mock config for WANController."""
    config = MagicMock()
    config.wan_name = "TestWAN"
    config.baseline_rtt_initial = 25.0
    config.download_floor_green = 800_000_000
    config.download_ceiling = 920_000_000
    # ... more fields
    return config
```

**Factory Functions:**
```python
def create_test_state(overrides=None):
    """Create test state with optional overrides."""
    state = {
        "download": {"green_streak": 0, "current_rate": 800_000_000},
        "upload": {"green_streak": 0, "current_rate": 35_000_000},
        "ewma": {"baseline_rtt": 25.0, "load_rtt": 28.0},
    }
    if overrides:
        state.update(overrides)
    return state
```

**Location:**
- Fixtures used across multiple tests: `tests/conftest.py`
- Test-specific fixtures: Define in test class or test file
- Factories: Define near usage or in `conftest.py` for reuse

## Coverage

**Requirements:**
- No enforced coverage target in CI
- Focus on critical paths: validation, state machines, measurements
- Gaps are acceptable for error recovery paths and integration code

**Current Status:**
- 684 test functions across 25 test files
- 594 passing unit tests (per CLAUDE.md)
- Comprehensive coverage: config validation, state management, retry logic, rate limiting

**Configuration:**
- Pytest-cov plugin available but not configured
- Run: `pytest --cov=src/wanctl tests/` if coverage report needed

## Test Types

**Unit Tests:**
- Test single function in isolation
- Mock all external dependencies (RouterOS, file I/O)
- Fast execution (< 100ms per test)
- Examples:
  - `test_config_validation_utils.py` (590 lines, extensive config validation)
  - `test_retry_utils.py` (error classification logic)
  - `test_rate_utils.py` (rate bounding functions)

**Integration Tests:**
- Test multiple modules together
- Mock external boundaries only (RouterOS commands)
- Verify data flow between components
- Examples:
  - `test_baseline_rtt_manager.py` (RTT tracking with state persistence)
  - `test_wan_controller.py` (controller with mocked router/RTT)
  - `test_health_check.py` (HTTP server with controller integration)

**End-to-End Tests:**
- `tests/integration/test_latency_control.py`: Full system validation
- Runs actual RRUL load tests (flent/netperf)
- Measures latency under load to validate congestion control
- Requires network setup (Dallas netperf server)

## Common Patterns

**Async Testing:**
- Not used in wanctl (synchronous code only)
- If needed: Use pytest-asyncio plugin

**Error Testing:**
```python
def test_invalid_input_raises_error(self, logger):
    """Test that invalid input raises ConfigValidationError."""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_bandwidth_order(
            name="download",
            floor_red=20000000,      # greater than floor_yellow
            floor_yellow=10000000,
            floor_green=50000000,
            ceiling=100000000,
            logger=logger,
        )
    assert "floor ordering violation" in str(exc_info.value)
```

**Parametrized Testing:**
```python
@pytest.mark.parametrize("input,expected", [
    (1.0, 2.0),
    (2.0, 4.0),
    (3.0, 6.0),
])
def test_function_with_values(self, input, expected):
    assert function(input) == expected
```

**Fixtures with Parameters:**
```python
@pytest.fixture(params=[10, 50, 100])
def baseline_rtt(request):
    """Provide different baseline RTT values."""
    return request.param

def test_with_baseline_values(self, baseline_rtt):
    # Test runs 3 times with different values
    assert valid_baseline(baseline_rtt)
```

**State Machine Testing:**
State transitions tested extensively in:
- `test_wan_controller.py`: RED/YELLOW/GREEN state transitions, hysteresis
- `test_wan_controller_state.py`: State persistence and recovery
- `test_state_manager.py`: Generic state schema validation
- Tests verify: state transitions, streak counts, rate changes per state

**Fallback Mode Testing:**
From `test_wan_controller.py`:
```python
def test_graceful_degradation_cycle_1_uses_last_rtt(self, controller):
    """Cycle 1 should use last known RTT and return True."""
    controller.config.fallback_mode = "graceful_degradation"
    controller.config.fallback_max_cycles = 3
    controller.icmp_unavailable_cycles = 0
    controller.load_rtt = 28.5

    with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
        should_continue, measured_rtt = controller.handle_icmp_failure()

    assert should_continue is True
    assert measured_rtt == 28.5
    assert controller.icmp_unavailable_cycles == 1
    controller.logger.warning.assert_called()
```

## Test Execution

**All Tests:**
```bash
.venv/bin/pytest tests/ -v
```

**Specific Test File:**
```bash
.venv/bin/pytest tests/test_wan_controller.py -v
```

**Specific Test Class:**
```bash
.venv/bin/pytest tests/test_wan_controller.py::TestHandleIcmpFailure -v
```

**Specific Test Method:**
```bash
.venv/bin/pytest tests/test_wan_controller.py::TestHandleIcmpFailure::test_graceful_degradation_cycle_1_uses_last_rtt -v
```

**Integration Tests Only:**
```bash
.venv/bin/pytest tests/integration/ -v
```

---

*Testing analysis: 2026-01-21*
