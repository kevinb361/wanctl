# Coding Conventions

**Analysis Date:** 2026-03-10

## Naming Patterns

**Files:**
- `snake_case.py` for all modules: `state_manager.py`, `baseline_rtt_manager.py`, `retry_utils.py`
- Utility modules use `_utils` suffix: `state_utils.py`, `lock_utils.py`, `daemon_utils.py`, `router_command_utils.py`
- Test files mirror source: `src/wanctl/state_utils.py` → `tests/test_state_utils.py`
- Subpackages use `__init__.py` for explicit re-exports: `src/wanctl/steering/__init__.py`, `src/wanctl/storage/__init__.py`

**Classes:**
- `PascalCase` throughout: `WANController`, `BaselineRTTManager`, `RouterOSSSH`, `MetricsWriter`
- Acronyms kept uppercase: `WANController`, `RTTMeasurement`, `JSONFormatter`
- Abstract base classes suffixed `Backend`: `RouterBackend` in `src/wanctl/backends/base.py`
- State managers suffixed `Manager` or `State`: `SteeringStateManager`, `WANControllerState`
- Config objects named `Config` or `BaseConfig` within their modules

**Functions:**
- `snake_case` everywhere: `atomic_write_json`, `setup_logging`, `is_retryable_error`
- Private helpers prefixed `_`: `_get_nested`, `_type_name`, `_create_formatter`, `_is_state_changed`
- Boolean predicates start with `is_` or `has_`: `is_reachable`, `has_pending`, `is_shutdown_requested`
- Factory functions prefixed `get_`: `get_router_client_with_failover`, `get_backend`, `get_storage_config`

**Variables:**
- `snake_case` for all: `baseline_rtt`, `cycle_interval`, `rtt_delta_ewma`
- Constants in `UPPER_SNAKE_CASE`: `CYCLE_INTERVAL_SECONDS`, `DEFAULT_HARD_RED_BLOAT_MS`, `LOG_WARNING`
- Numeric constants use underscores for readability: `800_000_000`, `35_000_000`

**Module-level constants block:**
```python
# =============================================================================
# CONSTANTS
# =============================================================================

# Daemon cycle interval - target time between cycle starts (seconds)
# Production standard: 0.05s (50ms, 20Hz polling) - validated Phase 2 (2026-01-13)
CYCLE_INTERVAL_SECONDS = 0.05
```
Always include a "why" comment explaining the value's significance.

## Code Style

**Formatter:** `ruff format` (Ruff's built-in formatter)

**Key settings (`pyproject.toml`):**
- Line length: 100 characters
- Target version: Python 3.12

**Linter:** `ruff check`
- Rule sets: `E`, `W` (pycodestyle), `F` (pyflakes), `I` (isort), `B` (flake8-bugbear), `UP` (pyupgrade)
- Ignored: `E501` (handled by formatter), `B008` (function call in default argument)
- First-party package: `wanctl` (controls isort ordering)

**Type checker:** `mypy` with `check_untyped_defs = true`, `python_version = "3.12"`

## Import Organization

**Order (enforced by ruff isort):**
1. Standard library: `import logging`, `from pathlib import Path`, `from collections.abc import Callable`
2. Third-party: `import yaml`, `import icmplib`, `import requests`
3. First-party (`wanctl`): `from wanctl.state_utils import atomic_write_json`

**Intra-package imports:**
- Top-level modules use **absolute** imports: `from wanctl.path_utils import ensure_file_directory`
- Subpackages (`steering/`, `storage/`) use **relative** imports: `from ..config_base import BaseConfig`, `from .cake_stats import CongestionSignals`

**Suppression comments (always include rationale):**
```python
from wanctl.perf_profiler import (
    PROFILE_REPORT_INTERVAL,  # noqa: F401 -- re-exported for test compatibility
)
import random  # nosec B311 - used for jitter timing, not security
import subprocess  # noqa: F401 -- retained for test patching
```

## Type Annotations

**Style:** Python 3.12 modern syntax throughout
- Union types: `str | None` (not `Optional[str]`)
- Generics: `list[float]`, `dict[str, Any]`, `tuple[int, str]`
- Generic classes use PEP 695: `class CommandResult[T]`, `def handle_command_error[T]`
- `from typing import Any, TypeVar` for remaining typing needs
- `from collections.abc import Callable, Generator` (not `typing.Callable`)
- `type: ignore` used sparingly with inline explanation

**Docstrings:**
- Module-level: triple-quoted string summarizing purpose
- Function-level: Args/Returns/Raises/Examples sections for public functions
- Inline `>>>` doctest examples in utility functions (`state_manager.py`, `retry_utils.py`, `state_utils.py`)
```python
def non_negative_int(value: Any) -> int:
    """Validate and coerce value to non-negative integer.

    Args:
        value: Value to validate

    Returns:
        Non-negative integer (min 0)

    Example:
        >>> non_negative_int(5)
        5
        >>> non_negative_int(-3)
        0
    """
```

## Module Design

**Section dividers (used consistently):**
```python
# =============================================================================
# CONSTANTS
# =============================================================================
```
Sections in large files: CONSTANTS, class definitions, function groups.

**Exports:**
- Subpackage `__init__.py` files explicitly define public API
- No star imports
- `src/wanctl/storage/__init__.py` and `src/wanctl/steering/__init__.py` are the access points

**Barrel files:**
- `from wanctl.steering import SteeringDaemon` works because `steering/__init__.py` re-exports it

## Error Handling

**Primary pattern: `@handle_errors` decorator** (`src/wanctl/error_handling.py`):
```python
@handle_errors(default_return=None, log_level=logging.WARNING)
def my_method(self):
    return self.risky_operation()

@handle_errors(default_return=False, log_traceback=True, error_msg="Failed to ping {exception}")
def verify_state(self):
    ...
```
Decorator auto-discovers `self.logger` from the instance.

**Context manager for inline blocks** (`safe_operation`):
```python
with safe_operation(logger, operation="database query", log_traceback=True):
    data = read_data()
```

**Functional variant** (`safe_call`):
```python
result = safe_call(load_config, config_path, logger=self.logger, default={})
```

**Result type pattern** (`CommandResult[T]` in `src/wanctl/router_command_utils.py`):
```python
result = CommandResult.ok(value)           # Success
result = CommandResult.err("Conn failed")  # Failure
data = result.unwrap_or(default)           # Safe extraction
```

**Custom exceptions:**
- `ConfigValidationError(ValueError)` in `src/wanctl/config_base.py`
- `LockAcquisitionError(Exception)` in `src/wanctl/lock_utils.py`

**Retry pattern** (`src/wanctl/retry_utils.py`):
```python
@retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0, jitter=True)
def _run_cmd(self, cmd: str) -> ...:
    ...
```
Only retries errors classified as transient by `is_retryable_error()`.

**Safe JSON I/O** (`src/wanctl/state_utils.py`):
- `atomic_write_json(path, data)` — write-to-temp-then-rename, fsync, 0o600 permissions
- `safe_json_load_file(path, logger, default, error_context)` — never raises, returns default
- `safe_read_json(path, default)` — simplified variant without logging

## Logging

**Framework:** Python standard `logging` module

**Logger injection:** Classes receive `logger: logging.Logger` as constructor argument.
Module-level logger: `logger = logging.getLogger(__name__)` for standalone modules.

**Structured logging with `extra=`:**
```python
logger.info("State change", extra={"state": "GREEN", "rtt_delta": 5.2, "wan_name": "spectrum"})
```
JSON format available via `WANCTL_LOG_FORMAT=json` env var (`src/wanctl/logging_utils.py`).

**Log levels:**
- `DEBUG`: per-cycle details, baseline freeze, retry attempts
- `INFO`: state transitions, startup/shutdown, periodic summaries, rate changes
- `WARNING`: transient failures, fallback activations, config degradation
- `ERROR`: persistent failures, unrecoverable states after retries

## Production Guards

**Dirty-tracking for high-frequency writes:**
- Compare state dicts before writing: `if current != self._last_saved_state` in `WANControllerState`
- Prevents flash wear from 20Hz cycle loop
- High-frequency metadata (congestion zone) explicitly excluded from dirty tracking

**MagicMock guard pattern (required when value may come from mock config):**
```python
if db_path and isinstance(db_path, str):
    path = Path(db_path)
```
This prevents `Path(MagicMock())` errors in tests.

**MetricsWriter singleton:**
- Always call `MetricsWriter._reset_instance()` in test setup/teardown
- Never share instance across tests

---

*Convention analysis: 2026-03-10*
