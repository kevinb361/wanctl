# Testing Patterns

**Analysis Date:** 2026-01-09

## Test Framework

**Runner:**
- pytest 8.0.0+
- Config: `pyproject.toml` (minimal, uses defaults)

**Assertion Library:**
- pytest built-in assert statement
- Matchers: `assert x == y`, `assert x in y`, `assert isinstance(x, Type)`

**Run Commands:**
```bash
uv run pytest tests/ -v              # Run all tests with verbose output
uv run pytest tests/ -vvs            # Very verbose (show print statements)
uv run pytest tests/test_*.py        # Run specific test file
uv run pytest tests/ -k test_name    # Run tests matching pattern
uv run pytest tests/ --tb=short      # Shorter traceback format
```

## Test File Organization

**Location:**
- `tests/` directory at project root
- One test file per module being tested
- Naming: `test_<module_name>.py` (e.g., `test_config_validation_utils.py`)

**Structure:**
```
tests/
├── test_config_validation_utils.py    (590 lines - comprehensive)
├── test_baseline_rtt_manager.py       (379 lines)
├── test_rate_utils.py
├── test_rtt_measurement.py
└── (additional test files)
```

## Test Structure

**Suite Organization:**
```python
import logging
import pytest
from wanctl.module_name import FunctionUnderTest

@pytest.fixture
def logger():
    """Provide logger for tests."""
    return logging.getLogger("test_module_name")

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

    def test_specific_behavior_fails(self, logger):
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
- Descriptive test names: test_<behavior>_<result> format

## Mocking

**Framework:**
- unittest.mock (built-in)
- pytest does not auto-mock

**Patterns:**
```python
from unittest.mock import Mock, MagicMock, patch

# Mock a class instance
mock_logger = Mock(spec=logging.Logger)
mock_logger.info.assert_called_with("message")

# Patch at module level
with patch('wanctl.module.function') as mock_fn:
    mock_fn.return_value = expected_value
    # test code

# Patch for entire test
@patch('wanctl.module.external_call')
def test_function(mock_external):
    mock_external.return_value = test_value
    # test code
```

**What to Mock:**
- External services (RouterOS commands)
- File I/O (state files, logs)
- System calls (ping, netperf)
- Time-dependent behavior (datetime, sleep)

**What NOT to Mock:**
- Pure validation functions
- EWMA calculations
- Config parsing
- State machine logic

## Fixtures and Factories

**Test Data:**
```python
# Fixture for logger
@pytest.fixture
def logger():
    return logging.getLogger("test")

# Fixture for temporary state file
@pytest.fixture
def temp_state_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        yield state_file
        # cleanup automatic

# Factory function for test objects
def create_test_config(overrides=None):
    config = Config()
    config.wan_name = "test"
    config.baseline_rtt = 50.0
    if overrides:
        for key, value in overrides.items():
            setattr(config, key, value)
    return config
```

**Location:**
- Fixtures: Define in test file or `conftest.py`
- Factories: Define in test file near usage or in `conftest.py`

## Coverage

**Requirements:**
- No enforced coverage target
- Focus on critical paths: validation, state machines, measurements
- Gaps are acceptable for error paths and integration code

**Configuration:**
- Pytest-cov plugin available but not configured
- Run: `pytest --cov=src/wanctl tests/` if wanted

## Test Types

**Unit Tests:**
- Test single function in isolation
- Mock all external dependencies (RouterOS, file I/O)
- Fast execution (< 100ms per test)
- Examples: test_config_validation_utils.py (590 lines, many unit tests)

**Integration Tests:**
- Test multiple modules together
- Mock only external boundaries (RouterOS commands)
- Examples: test_baseline_rtt_manager.py (tests manager with mocked state files)

**E2E Tests:**
- Not currently in test suite
- Manual deployment testing used instead

## Common Patterns

**Async Testing:**
- Not currently used (synchronous code only)
- If needed: Use pytest-asyncio plugin

**Error Testing:**
```python
def test_invalid_input_raises_error(self, logger):
    """Test that invalid input raises ConfigValidationError."""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_bandwidth_order(
            name="download",
            floor_red=20000000,    # greater than floor_yellow
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

def test_with_baseline_values(baseline_rtt):
    # Test runs 3 times with different values
    assert valid_baseline(baseline_rtt)
```

---

*Testing analysis: 2026-01-09*
*Update when test patterns change*
